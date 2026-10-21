"""Portable frozen raw-UCI identity check. Usage: base candidate output_dir."""
from pathlib import Path
import difflib,hashlib,json,re,subprocess,sys,threading,time
ROOT=Path(__file__).resolve().parent
base,candidate,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True)
engines={'base':base.resolve(),'candidate':candidate.resolve()}
cases=json.loads((ROOT/'identity-cases.json').read_text())
def run(name,index,case):
    prefix=out/f'{index:03d}-{name}';commands=[];lines=[];started=time.monotonic()
    with prefix.with_suffix('.stderr').open('w') as stderr:
        proc=subprocess.Popen([str(engines[name])],cwd=engines[name].parent,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,bufsize=1)
        timer=threading.Timer(120,proc.kill);timer.start()
        def send(s):commands.append(s);proc.stdin.write(s+'\n');proc.stdin.flush()
        def until(prefix):
            while True:
                line=proc.stdout.readline()
                if not line:raise RuntimeError((name,index,'EOF',proc.poll()))
                lines.append(line.rstrip())
                if line.startswith(prefix):return
        try:
            send('uci');until('uciok')
            for s in ['setoption name Threads value 1','setoption name Hash value 16','setoption name SyzygyPath value','setoption name UCI_Chess960 value '+str(case['chess960']).lower(),'ucinewgame','setoption name Clear Hash','isready']:send(s)
            until('readyok');send('position fen '+case['fen']);send('go nodes 200000');until('bestmove ')
            send('quit');proc.wait(timeout=10)
            if proc.returncode!=0:raise RuntimeError((name,index,'exit',proc.returncode))
        finally:
            timer.cancel()
            if proc.poll() is None:proc.kill();proc.wait()
            prefix.with_suffix('.stdout').write_text('\n'.join(lines)+'\n')
            prefix.with_suffix('.commands').write_text('\n'.join(commands)+'\n')
    # id name and initial Stockfish line contain compile-date/commit metadata.
    # These are build banners, not search output. All remaining content is kept.
    normalized=[re.sub(r'\b(time|nps) \d+',r'\1 <elapsed>',line) for line in lines if not (line.startswith('Stockfish ') or line.startswith('id name '))]
    prefix.with_suffix('.normalized').write_text('\n'.join(normalized)+'\n')
    return normalized,time.monotonic()-started
report={'sources':'frozen a054f22 against effdc3f','binaries':{k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in engines.items()},'cases':[],'status':'running'}
try:
 for i,case in enumerate(cases,1):
    results={}
    for name in (['base','candidate'] if i%2 else ['candidate','base']):results[name]=run(name,i,case)
    same=results['base'][0]==results['candidate'][0]
    report['cases'].append({'index':i,'input':case,'identical':same,'elapsed':{k:v[1] for k,v in results.items()}})
    if not same:
        (out/f'{i:03d}.diff').write_text('\n'.join(difflib.unified_diff(results['base'][0],results['candidate'][0],fromfile='base',tofile='candidate'))+'\n')
    if i%16==0:print(i,'pairs complete',flush=True)
 report['status']='pass' if all(r['identical'] for r in report['cases']) else 'fail'
finally:(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
if report['status']!='pass':raise SystemExit(1)
