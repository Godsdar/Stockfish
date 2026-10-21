"""Uninstrumented24pair frozen native timing. Usage: base candidate output_dir."""
from pathlib import Path
import hashlib,json,math,platform,re,statistics,subprocess,sys,time
base,candidate,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True)
if any(out.iterdir()):raise SystemExit('Output must be empty; never overwrite prior timing.')
engines={'base':base.resolve(),'candidate':candidate.resolve()}
report={'platform':platform.platform(),'python':sys.version,'binaries':{k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in engines.items()},'command':['bench','16','1','16','default','depth'],'warmups':[],'pairs':[],'status':'running'}
def run(name,tag):
    started=time.perf_counter_ns()
    p=subprocess.run([str(engines[name]),*report['command']],cwd=engines[name].parent,capture_output=True,text=True,timeout=600)
    elapsed=(time.perf_counter_ns()-started)/1e6
    (out/f'{tag}-{name}.stdout').write_text(p.stdout);(out/f'{tag}-{name}.stderr').write_text(p.stderr)
    if p.returncode:raise RuntimeError((tag,name,p.returncode))
    def parse(label):
        match=re.search(re.escape(label)+r'\s*:\s*(\d+)',p.stderr)
        if not match:raise ValueError(('missing',label,tag,name))
        return int(match.group(1))
    return {'process_ms':elapsed,'engine_ms':parse('Total time (ms)'),'nodes':parse('Nodes searched'),'nps':parse('Nodes/second'),'returncode':p.returncode}
def analyze(field,rows):
    values=[math.log(p['base'][field]/p['candidate'][field]) for p in rows]
    mean=statistics.mean(values);outcome={'pairs':len(values),'speedup_percent':100*math.expm1(mean)}
    if len(values)==24:
        margin=2.068657610*statistics.stdev(values)/math.sqrt(24)
        outcome['ci95_percent']=[100*math.expm1(mean-margin),100*math.expm1(mean+margin)]
    return outcome
try:
 for round in range(2):
    for name in ['base','candidate']:report['warmups'].append({'round':round+1,'variant':name,**run(name,f'warmup-{round+1}')})
 for i in range(1,25):
    order=['base','candidate'] if i%2 else ['candidate','base'];row={'pair':i,'order':order}
    for name in order:row[name]=run(name,f'pair-{i:02d}')
    if row['base']['nodes']!=row['candidate']['nodes']:raise ValueError(('node mismatch',i,row))
    report['pairs'].append(row);(out/'timing.json').write_text(json.dumps(report,indent=2)+'\n')
    print(i,'pairs complete',flush=True)
 nodes={x[n]['nodes'] for x in report['pairs'] for n in engines}
 if len(nodes)!=1:raise ValueError(('inconsistent nodes',nodes))
 report['analysis']={field:{'full':analyze(field,report['pairs']),'first12':analyze(field,report['pairs'][:12]),'last12':analyze(field,report['pairs'][12:])} for field in ['engine_ms','process_ms']}
 e=report['analysis']['engine_ms'];p=report['analysis']['process_ms']
 report['repeatable_gain_criterion']=bool(e['full']['ci95_percent'][0]>0 and e['first12']['speedup_percent']>0 and e['last12']['speedup_percent']>0 and p['full']['speedup_percent']>0)
 report['status']='complete'
finally:(out/'timing.json').write_text(json.dumps(report,indent=2)+'\n')
