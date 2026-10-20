"""Compile a baseline-ISA probe, then expose supported AVX512 OS/CPU state."""
import json
import os
from pathlib import Path
import platform
import subprocess

src = Path(__file__).with_name('cpu.cpp').resolve()
windows = platform.system() == 'Windows'
binary = Path('results/cpu-probe' + ('.exe' if windows else '')).resolve()
if windows:
    cmd = ['cl', '/nologo', '/std:c++17', '/EHsc', '/MT', '/O2', '/W3', '/WX',
           str(src), '/Fe:' + str(binary)]
else:
    cmd = ['g++', '-std=c++17', '-O2', '-mxsave', '-Wall', '-Wextra', '-Werror',
           str(src), '-o', str(binary)]
result = subprocess.run(cmd, capture_output=True, text=True)
Path('results/cpu-probe-build.log').write_text(result.stdout + result.stderr)
result.check_returncode()
probe = subprocess.run([str(binary)], capture_output=True, text=True)
Path('results/cpu-capability.log').write_text(probe.stdout + probe.stderr)
assert probe.returncode in (0, 77), probe
supported = probe.returncode == 0
Path('results/capability.json').write_text(json.dumps({'supported': supported,
    'returncode': probe.returncode, 'details': probe.stdout + probe.stderr}, indent=2) + '\n')
with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
    out.write('supported=' + ('true' if supported else 'false') + '\n')
print(probe.stdout, end='')
print('Runtime supported:', supported)
