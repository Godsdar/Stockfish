from pathlib import Path
import json,os,subprocess,sys
here=Path(__file__).resolve().parent
src=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(exist_ok=True)
windows=os.name=='nt';suffix='.exe' if windows else ''
# Executable/object stay outside uploaded results.
exe=src/('key-property'+suffix)
if windows:
 flags=['cl','/nologo','/std:c++17','/MT','/EHsc','/O2','/W3','/WX','/permissive-','/DNDEBUG','/DUSE_POPCNT','/DUSE_SSE2','/DUSE_SSSE3','/DUSE_SSE41','/DUSE_AVX2','/arch:AVX2','/I'+str(src)]
 objects=[str(p) for p in sorted(src.glob('*.obj')) if p.name!='main.obj']
 cmd=flags+['/Fe:'+str(exe),str(here/'key_property.cpp'),*objects,'/link','/STACK:8388608','shell32.lib']
else:
 flags=['g++','-std=c++17','-O3','-DNDEBUG','-DIS_64BIT','-DUSE_POPCNT','-DUSE_AVX2','-DUSE_SSE41','-DUSE_SSSE3','-DUSE_SSE2','-m64','-mpopcnt','-mavx2','-mbmi','-msse4.1','-mssse3','-msse2','-I'+str(src)]
 objects=[str(p) for p in sorted(src.glob('*.o')) if p.name!='main.o']
 cmd=flags+[str(here/'key_property.cpp'),*objects,'-lpthread','-o',str(exe)]
(out/'property-build-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (out/'property-build.log').open('w') as log:subprocess.run(cmd,cwd=src,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
p=subprocess.run([str(exe),str(here/'property-corpus.tsv')],cwd=src,capture_output=True,text=True,timeout=120)
(out/'property-results.stdout').write_text(p.stdout);(out/'property-results.stderr').write_text(p.stderr)
assert p.returncode==0,(p.returncode,p.stderr)
assert json.loads(p.stdout)['pass'] is True
