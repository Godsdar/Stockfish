"""Alternating fixed-depth screening, preserving every stdout/stderr and pair."""
import argparse
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('base')
p.add_argument('candidate')
p.add_argument('output')
p.add_argument('--depth', type=int, default=16)
p.add_argument('--pairs', type=int, default=20)
a = p.parse_args()
binary = {'base': str(Path(a.base).resolve()), 'candidate': str(Path(a.candidate).resolve())}
out = Path(a.output)
raw = out.parent / 'raw-bench'
raw.mkdir(parents=True, exist_ok=True)

def bench(name, tag):
    start = time.monotonic()
    run = subprocess.run([binary[name], 'bench', '16', '1', str(a.depth), 'default', 'depth'],
                         capture_output=True, text=True, timeout=180)
    wall = time.monotonic() - start
    (raw / f'{tag}-{name}.stdout').write_text(run.stdout, encoding='utf-8')
    (raw / f'{tag}-{name}.stderr').write_text(run.stderr, encoding='utf-8')
    run.check_returncode()
    result = {'wall_seconds': wall}
    for label, key in [('Total time (ms)', 'ms'), ('Nodes searched', 'nodes')]:
        match = re.search(re.escape(label) + r'\s*:\s*(\d+)', run.stderr)
        assert match, run.stderr[-2000:]
        result[key] = int(match[1])
    return result

warmup = {name: bench(name, 'warmup') for name in binary}
assert warmup['base']['nodes'] == warmup['candidate']['nodes'], warmup
data = {'depth': a.depth, 'threads': 1, 'hash_mib': 16, 'binaries': binary,
        'warmup': warmup, 'pairs': []}
for i in range(a.pairs):
    names = ['base', 'candidate'] if i % 2 == 0 else ['candidate', 'base']
    pair = {'index': i + 1, 'order': names}
    for name in names:
        pair[name] = bench(name, f'{i + 1:02d}')
    assert pair['base']['nodes'] == pair['candidate']['nodes'], pair
    pair['speedup_percent'] = 100 * (pair['base']['ms'] / pair['candidate']['ms'] - 1)
    data['pairs'].append(pair)
    out.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(pair), flush=True)

logs = [math.log(x['base']['ms'] / x['candidate']['ms']) for x in data['pairs']]
mean = statistics.mean(logs)
# Conservative approximate Student t multiplier; paired screening only.
margin = 2.201 * statistics.stdev(logs) / math.sqrt(len(logs))
data['summary'] = {'geometric_speedup_percent': 100 * math.expm1(mean),
                   'approx_95_percent_interval': [100 * math.expm1(mean - margin),
                                                  100 * math.expm1(mean + margin)]}
out.write_text(json.dumps(data, indent=2) + '\n')
print(json.dumps(data['summary']), flush=True)
