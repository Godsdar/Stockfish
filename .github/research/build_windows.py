import glob
import json
import pathlib
import subprocess
import sys

for directory in sys.argv[1:]:
    root=pathlib.Path(directory).resolve()
    sources=[p for pattern in ['*.cpp','nnue/*.cpp','nnue/features/*.cpp','syzygy/*.cpp']
             for p in glob.glob(pattern,root_dir=root)]
    command=['cl','/nologo','/std:c++17','/MT','/EHsc','/O2','/MP2','/W3','/WX',
             '/permissive-','/DNDEBUG','/DUSE_POPCNT','/DUSE_SSE2','/DUSE_SSSE3',
             '/DUSE_SSE41','/DUSE_AVX2','/arch:AVX2','/Fe:stockfish.exe',
             *sources,'/link','/STACK:8388608','shell32.lib']
    print('COMMAND',json.dumps(command),flush=True)
    subprocess.run(command,cwd=root,check=True)
