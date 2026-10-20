from pathlib import Path
import platform
import subprocess
import sys

source = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
avx512 = '--avx512' in sys.argv
compile_only = '--compile-only' in sys.argv
if platform.system() == 'Windows':
    cmd = ['cl', '/nologo', '/std:c++17', '/O2', '/MT', '/EHsc', '/W3', '/WX',
           '/arch:AVX512' if avx512 else '/arch:AVX2',
           *(['/DEXPECT_AVX512'] if avx512 else []), str(source)]
    if compile_only:
        cmd += ['/c', '/Fo' + str(out)]
    else:
        cmd += ['/Fe:' + str(out)]
else:
    cmd = ['g++', '-std=c++17', '-O3', '-Wall', '-Wextra', '-Werror',
           '-mavx512bw' if avx512 else '-mavx2',
           *(['-DEXPECT_AVX512'] if avx512 else []), str(source)]
    if compile_only:
        cmd += ['-c']
    cmd += ['-o', str(out)]
print('Command:', ' '.join(cmd), flush=True)
subprocess.run(cmd, check=True)
if not compile_only:
    subprocess.run([str(out)], check=True, timeout=30)
