"""One preregistered native Windows/MinGW PGO study. No source selection."""
from pathlib import Path
import ctypes
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'pgo-results'
OUT.mkdir(exist_ok=True)
BASE = 'effdc3fd3f6de6e75fe1374a51a7a7eed66f880b'
FIX = '49c5f5979c8af79d3807468dbf5e985054ed29d3'
HEADER = 'src/nnue/layers/affine_transform_sparse_input.h'
UTC_CUTOFF = dt.datetime(2026, 10, 20, 14, tzinfo=dt.timezone.utc).timestamp()
DEADLINE = min(time.time() + 42 * 60, UTC_CUTOFF)
summary = {'baseline': BASE, 'fixed': FIX, 'pairs_requested': 40, 'warmup_pairs_requested': 6,
           'mode': 'Native Windows MinGW64 GCC, supported profile-build x86-64-vnni512, own default bench training per variant',
           'pairs': [], 'warmup': [], 'builds': {}, 'correctness': {}}


def save():
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')


def run(command, cwd, name, timeout=120, expected=0, input_text=None):
    print(dt.datetime.now(dt.timezone.utc).isoformat(), name, flush=True)
    remaining = DEADLINE - time.time()
    if remaining <= 0:
        raise TimeoutError('Preregistered absolute/study cutoff reached')
    log = OUT / (name + '.txt')
    with log.open('w') as target:
        target.write('COMMAND: ' + repr(command) + '\n')
        target.flush()
        child = subprocess.Popen(command, cwd=cwd, stdout=target, stderr=subprocess.STDOUT,
                                 stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                                 text=True)
        try:
            child.communicate(input_text, timeout=min(timeout, remaining))
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True)
            child.wait()
            raise
    text = log.read_text(errors='replace')
    if expected is not None:
        assert child.returncode == expected, (name, child.returncode, text[-3000:])
    return child.returncode, text


def check_nodes(text, expected):
    value = int(re.findall(r'Nodes searched\s*:\s*(\d+)', text)[-1])
    assert value == expected, (value, expected)
    return value


try:
    assert os.name == 'nt'
    assert time.time() < dt.datetime(2026, 10, 20, 13, 10, tzinfo=dt.timezone.utc).timestamp(), 'Late queue: no study started'
    summary['start_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    summary['research_head'] = run(['git', 'rev-parse', 'HEAD'], ROOT, 'research-head')[1].splitlines()[-1]
    summary['compiler'] = run(['g++', '--version'], ROOT, 'compiler')[1]
    summary['cpu_model'] = run(['powershell.exe', '-NoProfile', '-Command',
        'Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress'], ROOT, 'cpu-model')[1]
    probe = OUT / 'cpu.exe'
    run(['g++', '-std=c++17', '-O2', '-mxsave', str(HERE / 'cpu.cpp'), '-o', str(probe)], ROOT, 'compile-cpu')
    code, text = run([str(probe)], ROOT, 'cpu-capability', expected=None)
    assert code in (0, 77), code
    summary['cpu_capability'] = text
    if code == 77:
        summary['status'] = 'skipped: CPU/OS unsupported; no retry, no timings'
        save()
        print(json.dumps(summary, indent=2), flush=True)
        raise SystemExit(0)

    original = run(['git', 'show', BASE + ':' + HEADER], ROOT, 'base-header')[1].split('\n', 1)[1]
    fixed = run(['git', 'show', FIX + ':' + HEADER], ROOT, 'fixed-header')[1].split('\n', 1)[1]
    assert fixed == original.replace('while (start < end - 2)', 'while (nnzInfo.count >= 3 && start < end - 2)', 1)
    name = 'nn-c9e480e92425.nnue'
    net = OUT / name
    summary['download_attempts'] = []
    for url in ['https://tests.stockfishchess.org/api/nn/' + name,
                'https://github.com/official-stockfish/networks/raw/master/' + name]:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Stockfish-research-validation/1.0'}), timeout=60) as source, net.open('wb') as target:
                shutil.copyfileobj(source, target)
            digest = hashlib.sha256(net.read_bytes()).hexdigest()
            assert digest == 'c9e480e92425f887df6ab9b05c6180fbd762b07879df9d9845f1aa75440caa73', digest
            summary['download_attempts'].append({'url': url, 'status': 'validated'})
            break
        except Exception as error:
            summary['download_attempts'].append({'url': url, 'status': repr(error)})
            net.unlink(missing_ok=True)
    assert net.exists(), summary['download_attempts']
    summary['network'] = {'filename': name, 'sha256': digest, 'size': net.stat().st_size}
    binaries = {}
    for variant, revision in [('original', BASE), ('fixed', FIX)]:
        checkout = OUT / variant
        run(['git', 'worktree', 'add', '--detach', str(checkout), revision], ROOT, 'worktree-' + variant)
        src = checkout / 'src'
        shutil.copyfile(net, src / name)
        command = ['make', '-j2', 'profile-build', 'ARCH=x86-64-vnni512', 'COMP=mingw', 'COMPCXX=g++']
        _, build_text = run(command, src, 'build-' + variant, timeout=780)
        assert '-fprofile-generate=profdir' in build_text and '-fprofile-use=profdir' in build_text
        assert not re.search(r'warning:.*(missing-profile|coverage-mismatch)', build_text), 'PGO profile warning'
        training_nodes = check_nodes(build_text, 1559611)
        binaries[variant] = src / 'stockfish.exe'
        summary['builds'][variant] = {'revision': revision, 'command': command,
            'training': './stockfish.exe bench (unchanged upstream PGOBENCH; default 16 MiB, one thread, depth 13, default positions)',
            'training_nodes': training_nodes,
            'benchmark_cpp_sha256': hashlib.sha256((src / 'benchmark.cpp').read_bytes()).hexdigest(),
            'binary_sha256': hashlib.sha256(binaries[variant].read_bytes()).hexdigest()}
        save()

    # All subsequent children share one allowed logical CPU. Build work has ended.
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

    for variant in binaries:
        src = binaries[variant].parent
        flags = ['-std=c++17', '-O3', '-DNDEBUG', '-mavx2', '-mavx512f', '-mavx512bw', '-mavx512vnni', '-mavx512dq', '-mavx512vl', '-mbmi', '-mbmi2', '-mpopcnt',
                 '-DUSE_SSE2', '-DUSE_SSSE3', '-DUSE_SSE41', '-DUSE_AVX2', '-DUSE_AVX512', '-DUSE_VNNI', '-DUSE_POPCNT', '-DUSE_PEXT']
        harness = OUT / ('runtime-' + variant + '.exe')
        run(['g++'] + flags + ['-I', str(src), str(HERE / 'runtime.cpp'), '-o', str(harness)], ROOT, 'compile-runtime-' + variant)
        _, result = run([str(harness)], ROOT, 'runtime-' + variant)
        assert '514 layer cases passed' in result
        summary['correctness'][variant] = {'actual_layer_cases': 514, 'standalone_harness': 'GCC -O3 -DNDEBUG, not PGO; actual frozen layer compared to scalar formula', 'output': result}
        summary['builds'][variant]['compiler_info'] = run([str(binaries[variant]), 'compiler'], OUT, 'engine-compiler-' + variant)[1]

    zero = OUT / 'zero.nnue'
    run(['python', str(HERE / 'make_zero_net.py'), str(net), str(zero)], ROOT, 'make-zero-net')
    summary['zero_network'] = {'sha256': hashlib.sha256(zero.read_bytes()).hexdigest(), 'size': zero.stat().st_size}
    for variant in binaries:
        _, trace = run([str(binaries[variant])], OUT, 'zero-net-' + variant,
            input_text='setoption name EvalFile value ' + str(zero) + '\nposition startpos\neval\nquit\n')
        assert not re.search(r'ERROR|error:', trace)
        match = re.search(r'NNUE evaluation\s+([+-]?[0-9.]+)', trace)
        assert match and float(match.group(1)) == 0, trace[-4000:]
        summary['correctness'][variant]['zero_net_raw_nnue'] = float(match.group(1))
    save()

    def bench(variant, depth, label):
        started = time.perf_counter()
        _, text = run([str(binaries[variant]), 'bench', '16', '1', str(depth), 'default', 'depth'], OUT, label, timeout=90)
        return {'nodes': check_nodes(text, 1559611 if depth == 13 else 7659485),
                'milliseconds': int(re.findall(r'Total time \(ms\)\s*:\s*(\d+)', text)[-1]),
                'wall_seconds': time.perf_counter() - started}

    summary['signature'] = {variant: bench(variant, 13, 'signature-' + variant) for variant in binaries}
    for pair in range(6):
        order = ['original', 'fixed'] if pair % 2 == 0 else ['fixed', 'original']
        row = {'pair': pair + 1, 'order': order}
        for variant in order:
            row[variant] = bench(variant, 16, f'warmup-{pair+1:02d}-{variant}')
        summary['warmup'].append(row)
        save()
    for pair in range(40):
        order = ['original', 'fixed'] if pair % 2 == 0 else ['fixed', 'original']
        row = {'pair': pair + 1, 'order': order}
        for variant in order:
            row[variant] = bench(variant, 16, f'pair-{pair+1:02d}-{variant}')
        row['log_speed_ratio'] = math.log(row['original']['milliseconds'] / row['fixed']['milliseconds'])
        summary['pairs'].append(row)
        save()
    logs = [row['log_speed_ratio'] for row in summary['pairs']]
    mean = statistics.mean(logs)
    margin = 2.022691 * statistics.stdev(logs) / math.sqrt(40)
    summary['geometric_speed_percent'] = math.expm1(mean) * 100
    summary['nominal_95_paired_interval_percent'] = [math.expm1(mean-margin)*100, math.expm1(mean+margin)*100]
    summary['status'] = 'completed: six warmup pairs and 40 alternating measured pairs, all retained'
    summary['limitations'] = 'One hosted VM, one independent PGO build pair, fixed training workload; nominal paired interval excludes neither VM effects nor systematic PGO/layout effects. No Elo or universal zero-cost claim. Layer harness release but not PGO; full-engine zero-net check PGO.'
    summary['finish_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save()
    print(json.dumps(summary, indent=2), flush=True)
except Exception as error:
    summary['status'] = 'failed: ' + repr(error)
    save()
    print(json.dumps(summary, indent=2), flush=True)
    raise
