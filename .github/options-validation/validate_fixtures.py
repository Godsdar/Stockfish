"""Compile and execute frozen OptionsMap fixtures; no engine searches here."""
from pathlib import Path
import json, os, subprocess, sys

here=Path(__file__).resolve().parent
out=Path(sys.argv[1]).resolve();out.mkdir(exist_ok=True)
rows=[]
for label,source in [('baseline',sys.argv[2]),('candidate',sys.argv[3])]:
    src=Path(source).resolve()
    windows=os.name=='nt'
    suffix='.exe' if windows else ''
    if windows:
        flags=['cl','/nologo','/std:c++17','/MT','/EHsc','/O2','/W3','/WX','/permissive-','/DNDEBUG',
               '/DUSE_POPCNT','/DUSE_SSE2','/DUSE_SSSE3','/DUSE_SSE41','/DUSE_AVX2','/arch:AVX2','/I'+str(src)]
        objsuffix='.obj'
    else:
        flags=['g++','-std=c++17','-O3','-DNDEBUG','-DIS_64BIT','-DUSE_POPCNT','-DUSE_AVX2','-DUSE_SSE41',
               '-DUSE_SSSE3','-DUSE_SSE2','-m64','-mpopcnt','-mavx2','-mbmi','-msse4.1','-mssse3','-msse2','-I'+str(src)]
        objsuffix='.o'
    for fixture in ['engine_options_repro','options_cases']:
        exe=out/(label+'-'+fixture+suffix)
        sources=[str(here/(fixture+'.cpp'))]
        if fixture=='engine_options_repro':
            sources += [str(p) for p in sorted(src.glob('*'+objsuffix)) if p.name!='main'+objsuffix]
        else:
            sources += [str(src/'ucioption.cpp')]
        if windows:cmd=flags+['/Fe:'+str(exe)]+sources+['/link','/STACK:8388608','shell32.lib']
        else:cmd=flags+sources+['-lpthread','-o',str(exe)]
        (out/(label+'-'+fixture+'-command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
        with (out/(label+'-'+fixture+'-build.log')).open('w') as log:
            subprocess.run(cmd,cwd=src,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        cases=[None] if fixture=='engine_options_repro' else ['empty','single','sequential','interleaved','lifetime','combo','callback','duplicate']
        for case in cases:
            r=subprocess.run([str(exe)]+([case] if case else []),cwd=src,capture_output=True,text=True,timeout=30)
            expected=0
            if case=='duplicate' or (label=='baseline' and case not in ['empty','single']):expected=1
            record={'label':label,'fixture':fixture,'case':case,'returncode':r.returncode,'expected_returncode':expected,'stdout':r.stdout,'stderr':r.stderr}
            rows.append(record)
            (out/'fixture-results.json').write_text(json.dumps(rows,indent=2)+'\n')
            assert r.returncode==expected,record
            if case=='duplicate':assert 'Option "HASH" was already added!' in r.stderr,record
            elif case is None:
                first=r.stdout.split('FIRST',1)[1].split('SECOND',1)[0]
                second=r.stdout.split('SECOND',1)[1]
                assert first.count('option name ')==19,record
                assert second.count('option name ')==(0 if label=='baseline' else 19),record
            else:assert ('PASS' if expected==0 else 'FAIL') in r.stdout,record
print('PASS native fixtures: expected baseline failures, fixed scenarios and unchanged controls.')
