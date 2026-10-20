"""Temporary research validation; this file is not proposed upstream."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import textwrap
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'validation-results'
OUT.mkdir(exist_ok=True)
BASE = 'effdc3fd3f6de6e75fe1374a51a7a7eed66f880b'
HEADER = 'src/nnue/layers/affine_transform_sparse_input.h'
IS_MSVC = sys.argv[1] == 'msvc'
CXX = 'cl' if IS_MSVC else (sys.argv[1] if len(sys.argv) > 1 else 'g++')
DEFINES = ['USE_AVX512', 'USE_VNNI', 'USE_SSSE3']
summary = {'platform': platform.platform(), 'compiler': CXX, 'base': BASE}


def run(command, name, expected=0):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (OUT / f'{name}.txt').write_text('COMMAND: ' + repr(command) + '\n' + result.stdout + result.stderr)
    if expected is not None:
        assert result.returncode == expected, (name, result.returncode, result.stdout, result.stderr)
    return result


version = run([CXX] if IS_MSVC else [CXX, '--version'], 'compiler', expected=None)
summary['compiler_version'] = version.stdout + version.stderr
original = subprocess.check_output(['git', 'show', f'{BASE}:{HEADER}'], cwd=ROOT, text=True)
fixed = (ROOT / HEADER).read_text()
old = 'while (start < end - 2)'
new = 'while (nnzInfo.count >= 3 && start < end - 2)'
assert original.count(old) == 1
assert fixed == original.replace(old, new, 1), 'Validation is restricted to the one-line guard'
summary['fixed_sha'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()

if IS_MSVC:
    common = ['/nologo', '/std:c++17', '/EHsc', '/permissive-', '/arch:AVX512']
    define_flags = ['/D' + d for d in DEFINES]
else:
    common = ['-std=c++17', '-mavx512vnni', '-mavx512bw']
    define_flags = ['-D' + d for d in DEFINES]
    if sys.platform == 'darwin':
        common = ['-arch', 'x86_64'] + common

# The constexpr probe uses the real NNZInfo member array and the exact predicates
# extracted from the real source. Intrinsic propagation itself is not constexpr.
proof = '''#include <immintrin.h>
#include "bitboard.h"
#include "nnue/nnz_helper.h"
using Stockfish::Eval::NNUE::NNZInfo;
constexpr unsigned iterations(unsigned n) {
    NNZInfo<1024> nnzInfo{};
    nnzInfo.count = n;
    const auto* start = nnzInfo.nnz;
    const auto* end = nnzInfo.nnz + nnzInfo.count;
    unsigned result = 0;
    while (PREDICATE) { start += 3; ++result; }
    return result;
}
ASSERTION
'''
proof_results = {}
for variant, predicate in [('original', 'start < end - 2'),
                           ('fixed', 'nnzInfo.count >= 3 && start < end - 2')]:
    for count in [0, 1, 2, 3, 256]:
        cpp = OUT / f'proof-{variant}-{count}.cpp'
        cpp.write_text(proof.replace('PREDICATE', predicate).replace(
            'ASSERTION', f'static_assert(iterations({count}) == {count // 3});'))
        if IS_MSVC:
            command = [CXX] + common + define_flags + ['/Zs', '/I' + str(ROOT / 'src'), str(cpp)]
        else:
            command = [CXX] + common + define_flags + ['-fsyntax-only', '-I' + str(ROOT / 'src'), str(cpp)]
        result = run(command, f'proof-{variant}-{count}', expected=None)
        want_failure = variant == 'original' and count < 2
        # GCC can accept the original local-expression constexpr probe. Record
        # diagnostic variance rather than treating acceptance as defined C++.
        if not want_failure:
            assert result.returncode == 0, (variant, count, result.returncode)
        proof_results[f'{variant}-{count}'] = 'rejected' if result.returncode else 'accepted'
summary['constexpr'] = proof_results

# Form the actual problematic pointer as a constexpr value. This makes the
# array-object boundary explicit even if a compiler folds the local comparison.
bound_proof = '''#include <immintrin.h>
#include "bitboard.h"
#include "nnue/nnz_helper.h"
using Stockfish::Eval::NNUE::NNZInfo;
constexpr NNZInfo<1024> make_info() {
    NNZInfo<1024> result{};
    result.count = COUNT;
    return result;
}
constexpr auto nnzInfo = make_info();
constexpr auto* start = nnzInfo.nnz;
constexpr auto* end = start + nnzInfo.count;
constexpr auto* triplet_limit = LIMIT;
'''
summary['constexpr_bound_pointer'] = {}
for variant, limit in [('original', 'end - 2'),
                       ('fixed', 'nnzInfo.count >= 3 ? end - 2 : start')]:
    for count in [0, 1, 2, 3]:
        cpp = OUT / f'bound-{variant}-{count}.cpp'
        cpp.write_text(bound_proof.replace('COUNT', str(count)).replace('LIMIT', limit))
        if IS_MSVC:
            command = [CXX] + common + define_flags + ['/Zs', '/I' + str(ROOT / 'src'), str(cpp)]
        else:
            command = [CXX] + common + define_flags + ['-fsyntax-only', '-I' + str(ROOT / 'src'), str(cpp)]
        result = run(command, f'bound-{variant}-{count}', expected=None)
        if variant == 'fixed' or count >= 2:
            assert result.returncode == 0
        summary['constexpr_bound_pointer'][f'{variant}-{count}'] = 'rejected' if result.returncode else 'accepted'

# Clone the actual src tree from the committed fixed revision without downloading
# a network. Change only the guarded source line in the baseline copy.
variants = {}
import shutil
triplet_start = original.index('        ' + old)
triplet_end = original.index('\n\n        for (IndexType k = 0;', triplet_start)
triplet_loop = original[triplet_start:triplet_end]
outside = (original[:triplet_start] + '        if (nnzInfo.count >= 3)\n        {\n'
           + textwrap.indent(triplet_loop, '    ') + '\n        }' + original[triplet_end:])
headers = {
    'original': original,
    'fixed': fixed,
    'difference': original.replace(old, 'while (end - start >= 3)', 1),
    'triplet_end': original.replace(old, 'const auto* tripletEnd = end - nnzInfo.count % 3;\n        while (start < tripletEnd)', 1),
    'outside': outside,
}
for variant, header in headers.items():
    directory = OUT / variant
    if directory.exists():
        shutil.rmtree(directory)
    shutil.copytree(ROOT / 'src', directory / 'src', ignore=shutil.ignore_patterns('*.o', '*.nnue', 'stockfish*'))
    (directory / HEADER).write_text(header)
    variants[variant] = directory


def compile_file(source, directory, name, assembly=False, native=False, release=False):
    output = directory / (name + ('.exe' if IS_MSVC else '.bin'))
    includes = ['/I' + str(directory / 'src')] if IS_MSVC else ['-I' + str(directory / 'src')]
    if IS_MSVC:
        flags = ['/nologo', '/std:c++17', '/EHsc', '/permissive-', '/O2']
        if not native:
            flags += ['/arch:AVX512'] + define_flags
        if release:
            flags += ['/DNDEBUG']
        command = [CXX] + flags + includes
        command += ['/Fo' + str(directory / (name + '.obj'))]
        if assembly:
            command += ['/c', '/FA', '/Fa' + str(directory / (name + '.asm'))]
        else:
            command += ['/Fe' + str(output)]
        command += [str(source)]
    else:
        flags = ['-std=c++17', '-O3']
        flags += ['-mxsave'] if native else ['-mavx512vnni', '-mavx512bw'] + define_flags
        if release:
            flags += ['-DNDEBUG']
        if sys.platform == 'darwin':
            flags = ['-arch', 'x86_64'] + flags
        output = directory / (name + ('.s' if assembly else '.bin'))
        command = [CXX] + flags + includes
        if assembly:
            command += ['-S', '-masm=intel']
        command += [str(source), '-o', str(output)]
    run(command, f'compile-{directory.name}-{name}')
    return output


def normalize_assembly(value):
    result = []
    for line in value.splitlines():
        line = line.strip()
        if not line or line.startswith((';', '#', '.file', '.ident', 'TITLE', '.cv_file')):
            continue
        # MSVC source-offset comments and GCC inline comments are annotations.
        line = line.split(';', 1)[0].strip() if IS_MSVC else line.split('#', 1)[0].strip()
        if line:
            result.append(re.sub(r'\s+', ' ', line))
    return '\n'.join(result) + '\n'


def coff_target_code(path):
    data = path.read_bytes()
    number_sections = struct.unpack_from('<H', data, 2)[0]
    symbol_offset, symbol_count = struct.unpack_from('<II', data, 8)
    optional_size = struct.unpack_from('<H', data, 16)[0]
    sections = []
    for index in range(number_sections):
        offset = 20 + optional_size + 40 * index
        size, pointer = struct.unpack_from('<II', data, offset + 16)
        sections.append(data[pointer:pointer + size])
    string_offset = symbol_offset + symbol_count * 18
    result = {}
    index = 0
    while index < symbol_count:
        offset = symbol_offset + index * 18
        rawname = data[offset:offset + 8]
        if rawname[:4] == b'\0\0\0\0':
            start = string_offset + struct.unpack_from('<I', rawname, 4)[0]
            name = data[start:data.index(b'\0', start)].decode(errors='replace')
        else:
            name = rawname.rstrip(b'\0').decode(errors='replace')
        section = struct.unpack_from('<h', data, offset + 12)[0]
        if section > 0 and (name == 'sparse_propagate' or name.startswith('?propagate@?$AffineTransformSparseInput')):
            result[name] = sections[section - 1].hex()
        index += 1 + data[offset + 17]
    assert result, path
    return result


summary['assembly'] = {}
for release in [False, True]:
    mode = 'release' if release else 'assertions'
    assembly = {}
    code = {}
    for variant, directory in variants.items():
        name = f'propagate-{mode}'
        compile_file(HERE / 'propagate.cpp', directory, name, assembly=True, release=release)
        path = directory / (name + ('.asm' if IS_MSVC else '.s'))
        assembly[variant] = normalize_assembly(path.read_text(errors='replace'))
        (OUT / f'{variant}-{mode}-normalized.asm').write_text(assembly[variant])
        if IS_MSVC:
            code[variant] = coff_target_code(directory / (name + '.obj'))
    summary['assembly'][mode] = {}
    for variant in variants:
        item = {'normalized_assembly_identical': assembly[variant] == assembly['original'],
                'normalized_assembly_sha256': hashlib.sha256(assembly[variant].encode()).hexdigest()}
        if IS_MSVC:
            item['target_function_code_bytes_identical'] = code[variant] == code['original']
            item['target_function_code_bytes_sha256'] = hashlib.sha256(json.dumps(code[variant], sort_keys=True).encode()).hexdigest()
        summary['assembly'][mode][variant] = item
        (OUT / f'{variant}-{mode}-assembly.diff').write_text(''.join(difflib.unified_diff(
            assembly['original'].splitlines(True), assembly[variant].splitlines(True),
            fromfile='original', tofile=variant)))
    if IS_MSVC:
        (OUT / f'target-code-{mode}.json').write_text(json.dumps(code, indent=2))

# The probe binary has no AVX-512 code; it checks CPUID and OS XCR0 before any
# executable compiled with AVX-512 is launched. On macOS cross-compilation is
# compile-only in this research script.
if sys.platform == 'darwin':
    summary['runtime'] = 'not run: local Apple Silicon host, x86 cross-compile only'
else:
    probe = compile_file(HERE / 'cpu.cpp', OUT, 'cpu', native=True)
    capability = run([str(probe)], 'cpu-capability', expected=None)
    assert capability.returncode in (0, 77)
    summary['cpu_probe'] = capability.stdout + capability.stderr
    summary['runtime'] = {}
    for variant, directory in variants.items():
        binary = compile_file(HERE / 'runtime.cpp', directory, 'runtime')
        if capability.returncode == 0:
            result = run([str(binary)], f'runtime-{variant}')
            summary['runtime'][variant] = result.stdout.strip()
        else:
            summary['runtime'][variant] = 'compiled only: AVX512F/BW/VNNI or OS state unavailable'

(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
