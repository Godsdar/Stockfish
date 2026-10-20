import pathlib
import platform
import subprocess
import sys

root, source, output = [pathlib.Path(p).resolve() for p in sys.argv[1:4]]
if platform.system() == 'Windows':
    objects = [str(p) for p in root.glob('*.obj') if p.stem != 'main']
    command = ['cl', '/nologo', '/std:c++17', '/MT', '/EHsc', '/O2', '/W3',
               '/DUSE_POPCNT', '/DUSE_SSE2', '/DUSE_SSSE3', '/DUSE_SSE41', '/DUSE_AVX2',
               '/arch:AVX2', '/I' + str(root), str(source), *objects,
               '/Fe:' + str(output), '/link', '/STACK:8388608', 'shell32.lib']
else:
    objects = [str(p) for p in root.glob('*.o') if p.stem != 'main']
    command = ['g++', '-std=c++17', '-O2', '-DIS_64BIT', '-DUSE_POPCNT', '-DUSE_SSE2',
               '-DUSE_SSSE3', '-DUSE_SSE41', '-DUSE_AVX2', '-mavx2', '-mpopcnt', '-flto',
               '-I' + str(root), str(source), *objects, '-o', str(output), '-lpthread']
subprocess.run(command, cwd=root, check=True)
