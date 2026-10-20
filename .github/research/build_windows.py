import glob
import pathlib
import subprocess
import sys

avx512 = '--avx512' in sys.argv
directories = [a for a in sys.argv[1:] if a != '--avx512']
for directory in directories:
    root = pathlib.Path(directory).resolve()
    sources = [p for pattern in ['*.cpp', 'nnue/*.cpp', 'nnue/features/*.cpp', 'syzygy/*.cpp']
               for p in glob.glob(pattern, root_dir=root)]
    subprocess.run(['cl', '/nologo', '/std:c++17', '/MT', '/EHsc', '/O2', '/MP',
                    '/W3', '/WX', '/permissive-', '/DNDEBUG', '/DUSE_POPCNT', '/DUSE_SSE2',
                    '/DUSE_SSSE3', '/DUSE_SSE41', '/DUSE_AVX2',
                    *(['/DUSE_AVX512', '/DUSE_VNNI', '/arch:AVX512'] if avx512 else ['/arch:AVX2']),
                    '/Fe:stockfish.exe', *sources, '/link', '/STACK:8388608', 'shell32.lib'],
                   cwd=root, check=True)
