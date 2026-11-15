"""Record actual frontend tool exits together with the checked source hashes."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
FRONT=ROOT/'frontend'


def run():
    paths=[p for p in (FRONT/'src').rglob('*') if p.is_file()]
    paths += [FRONT/name for name in ('package.json','package-lock.json','vite.config.ts','tsconfig.json','tsconfig.app.json','tsconfig.node.json','index.html')]
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    results={}
    for name in ('build','lint'):
        command=['powershell','-NoProfile','-Command',f'npm run {name}'] if sys.platform=='win32' else ['npm','run',name]
        result=subprocess.run(command,cwd=FRONT,capture_output=True,text=True,timeout=120)
        results[name]=dict(command=f'npm run {name}',exit_code=result.returncode,output=result.stdout+result.stderr)
        print(results[name]['output'],flush=True)
    changed=[name for name,digest in hashes.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    output=dict(passed=all(r['exit_code']==0 for r in results.values()) and not changed,results=results,source_sha256=hashes,changed_sources=changed)
    (ROOT/'experiments/operational_improvements/frontend_verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    if not output['passed']:raise SystemExit(1)


if __name__=='__main__':run()
