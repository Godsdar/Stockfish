"""Bounded Windows/MSVC research comparison; not an upstream test."""
from pathlib import Path
import ctypes
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'benchmark-results'
OUT.mkdir(exist_ok=True)
BASE = 'effdc3fd3f6de6e75fe1374a51a7a7eed66f880b'
HEADER = 'src/nnue/layers/affine_transform_sparse_input.h'
summary = {'platform': platform.platform(), 'baseline': BASE, 'pairs_requested': 20,
           'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
           'mode': 'MSVC /O2 /DNDEBUG AVX512F/BW/VNNI, no PGO, one engine thread',
           'pairs': []}


def save():
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')


def run(command, cwd, name, timeout=120, expected=0):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    (OUT / f'{name}.txt').write_text('COMMAND: ' + repr(command) + '\n' + result.stdout + result.stderr)
    if expected is not None:
        assert result.returncode == expected, (name, result.returncode)
    return result


try:
    assert os.name == 'nt'
    summary['compiler'] = run(['cl'], ROOT, 'compiler', expected=None).stderr
    info = run(['powershell', '-NoProfile', '-Command',
                'Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress'],
               ROOT, 'cpu-model')
    summary['cpu_model'] = info.stdout.strip()
    probe = OUT / 'cpu.exe'
    run(['cl', '/nologo', '/std:c++17', '/EHsc', '/O2', str(HERE / 'cpu.cpp'),
         '/Fo' + str(OUT / 'cpu.obj'), '/Fe' + str(probe)], ROOT, 'compile-cpu')
    result = run([str(probe)], ROOT, 'cpu-capability', expected=None)
    assert result.returncode in (0, 77)
    summary['cpu_capability'] = result.stdout.strip()
    if result.returncode == 77:
        summary['status'] = 'skipped: CPU/OS AVX-512 state unavailable; no timings collected'
        save()
        print(json.dumps(summary, indent=2))
        raise SystemExit(0)

    # Download only the official default net, validating the filename's hash.
    name = re.search(r'nn-[0-9a-f]+\.nnue', (ROOT / 'src/evaluate.h').read_text()).group()
    net = OUT / name
    with urllib.request.urlopen('https://tests.stockfishchess.org/api/nn/' + name, timeout=60) as source, net.open('wb') as target:
        shutil.copyfileobj(source, target)
    digest = hashlib.sha256(net.read_bytes()).hexdigest()
    assert digest.startswith(name[3:-5]), (name, digest)
    summary['network'] = {'filename': name, 'sha256': digest, 'size': net.stat().st_size}
    baseline = subprocess.check_output(['git', 'show', BASE + ':' + HEADER], cwd=ROOT, text=True)
    fixed = (ROOT / HEADER).read_text()
    assert fixed == baseline.replace('while (start < end - 2)', 'while (nnzInfo.count >= 3 && start < end - 2)', 1)
    binaries = {}
    for variant, header in [('original', baseline), ('fixed', fixed)]:
        directory = OUT / variant
        if directory.exists():
            shutil.rmtree(directory)
        shutil.copytree(ROOT / 'src', directory / 'src', ignore=shutil.ignore_patterns('*.o', '*.nnue', 'stockfish*'))
        (directory / HEADER).write_text(header)
        src = directory / 'src'
        sources = sorted(src.glob('*.cpp')) + sorted((src / 'nnue').glob('*.cpp')) + sorted((src / 'nnue/features').glob('*.cpp')) + sorted((src / 'syzygy').glob('*.cpp'))
        binary = src / ('stockfish-' + variant + '.exe')
        run(['cl', '/nologo', '/std:c++17', '/MT', '/EHsc', '/O2', '/MP2', '/DNDEBUG', '/W3', '/WX', '/permissive-',
             '/arch:AVX512', '/DUSE_POPCNT', '/DUSE_SSE2', '/DUSE_SSSE3', '/DUSE_SSE41', '/DUSE_AVX2', '/DUSE_AVX512', '/DUSE_VNNI',
             '/Fe' + str(binary)] + [str(p) for p in sources] + ['/link', '/STACK:8388608', 'shell32.lib'],
            src, 'compile-engine-' + variant, timeout=300)
        binaries[variant] = binary

    # Child processes inherit one allowed CPU, so each sequential run uses the
    # same logical processor. This cannot remove shared-runner/VM noise.
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    handle = kernel.GetCurrentProcess()
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    assert kernel.GetProcessAffinityMask(handle, ctypes.byref(process_mask), ctypes.byref(system_mask))
    mask = process_mask.value & -process_mask.value
    assert kernel.SetProcessAffinityMask(handle, mask)
    summary['affinity_mask'] = mask

    def bench(variant, depth, label):
        start = time.perf_counter()
        result = run([str(binaries[variant]), 'bench', '16', '1', str(depth), 'default', 'depth'],
                     OUT, label, timeout=90)
        wall = time.perf_counter() - start
        text = result.stdout + result.stderr
        nodes = int(re.findall(r'Nodes searched\s*:\s*(\d+)', text)[-1])
        elapsed = int(re.findall(r'Total time \(ms\)\s*:\s*(\d+)', text)[-1])
        return {'nodes': nodes, 'milliseconds': elapsed, 'wall_seconds': wall}

    summary['signature'] = {variant: bench(variant, 13, 'signature-' + variant) for variant in binaries}
    assert all(item['nodes'] == 1559611 for item in summary['signature'].values()), summary['signature']
    summary['warmup'] = {variant: bench(variant, 16, 'warmup-' + variant) for variant in binaries}
    assert summary['warmup']['original']['nodes'] == summary['warmup']['fixed']['nodes']
    save()
    deadline = time.monotonic() + 15 * 60
    for pair in range(20):
        if time.monotonic() > deadline - 180:
            summary['status'] = 'incomplete: stopped at bounded benchmark deadline'
            break
        order = ['original', 'fixed'] if pair % 2 == 0 else ['fixed', 'original']
        row = {'pair': pair + 1, 'order': order}
        for variant in order:
            row[variant] = bench(variant, 16, f'pair-{pair + 1:02d}-{variant}')
        assert row['original']['nodes'] == row['fixed']['nodes'] == summary['warmup']['original']['nodes'], row
        row['log_speed_ratio'] = math.log(row['original']['milliseconds'] / row['fixed']['milliseconds'])
        summary['pairs'].append(row)
        save()
    logs = [row['log_speed_ratio'] for row in summary['pairs']]
    if logs:
        mean = statistics.mean(logs)
        summary['geometric_speed_percent'] = math.expm1(mean) * 100
        if len(logs) > 1:
            # 2.093 is the two-sided 95% Student t critical value for 19 df.
            # Only label it a nominal paired interval when all 20 pairs finish.
            critical = 2.093 if len(logs) == 20 else 2.5
            margin = critical * statistics.stdev(logs) / math.sqrt(len(logs))
            summary['nominal_paired_interval_percent'] = [math.expm1(mean - margin) * 100, math.expm1(mean + margin) * 100]
    if len(logs) == 20:
        summary['status'] = 'completed: 20 sequential alternating pairs'
    summary['limitations'] = 'One hosted VM, no PGO; paired interval does not model every VM/systematic effect; no Elo claim.'
    save()
    print(json.dumps(summary, indent=2))
except Exception as error:
    summary['status'] = 'failed: ' + repr(error)
    save()
    raise
