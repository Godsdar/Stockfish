from pathlib import Path
import subprocess,os,json,hashlib,re,datetime
root=Path(__file__).resolve().parent
repo=root/'Stockfish-options';out=root/'macos';out.mkdir(exist_ok=True)
sdk='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
env=os.environ.copy();env['CXXFLAGS']='-isysroot '+sdk+' -Werror';env['LDFLAGS']='-isysroot '+sdk
python='/Users/godsdar/Documents/Codex/2026-10-20/i-gave-you-a-research-research/work/venv/bin/python'
commands=[(['make','-C',str(repo/'src'),'-j2','build','ARCH=apple-silicon','COMP=clang'],root,'build.log'),
          ([str(repo/'src/stockfish'),'bench'],repo,'bench.log'),
          ([python,str(repo/'tests/instrumented.py'),'--none',str(repo/'src/stockfish')],repo,'instrumented.log'),
          ([python,str(root.parents[1]/'smoke_uci.py'),str(repo/'src/stockfish'),str(out/'smoke.json')],root,'smoke.log')]
meta={'start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),'commands':[[cmd,str(cwd),log] for cmd,cwd,log in commands],'CXXFLAGS':env['CXXFLAGS'],'LDFLAGS':env['LDFLAGS']}
(out/'execution.json').write_text(json.dumps(meta,indent=2)+'\n')
for cmd,cwd,log in commands:
 with (out/log).open('w') as f: subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
 print(log,'PASS',flush=True)
assert re.search(r'Nodes searched\s*:\s*1559611',(out/'bench.log').read_text())
s=re.sub(r'\x1b\[[0-9;]*m','',(out/'instrumented.log').read_text());assert '75 passed, 0 failed, 75 total' in s
assert len(json.loads((out/'smoke.json').read_text())['results'])==180
meta.update(end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,bench=1559611,binary_sha256=hashlib.sha256((repo/'src/stockfish').read_bytes()).hexdigest())
(out/'execution.json').write_text(json.dumps(meta,indent=2)+'\n')
print('macOS full-engine validation PASS',flush=True)
