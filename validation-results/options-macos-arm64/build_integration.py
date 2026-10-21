from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parent
src=root.parents[1]/'baseline/src'
sdk='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
flags=['clang++','-std=c++17','-O3','-DNDEBUG','-isysroot',sdk,'-DIS_64BIT','-DUSE_POPCNT','-DUSE_NEON=8','-march=armv8.2-a+dotprod','-DUSE_NEON_DOTPROD','-I',str(src)]
cmds=[]
for name in ['base','fixed']:
 objs=[str(p) for p in src.glob('*.o') if p.name not in {'main.o','ucioption.o'}]
 uci=src/'ucioption.cpp' if name=='base' else root/'Stockfish-options/src/ucioption.cpp'
 cmd=flags+[str(root/'engine_options_repro.cpp'),str(uci),*objs,'-lpthread','-o',str(root/f'engine-options-{name}')]
 cmds.append(cmd)
 with (root/f'build-integration-{name}.log').open('w') as log:subprocess.run(cmd,cwd=src,stdout=log,stderr=subprocess.STDOUT,check=True)
 r=subprocess.run([str(root/f'engine-options-{name}')],cwd=src,text=True,capture_output=True,timeout=20)
 (root/f'engine-options-{name}.stdout').write_text(r.stdout);(root/f'engine-options-{name}.stderr').write_text(r.stderr)
 print(name,'exit',r.returncode,'options',r.stdout.count('option name '),flush=True)
(root/'integration-commands.json').write_text(json.dumps(cmds,indent=2)+'\n')
