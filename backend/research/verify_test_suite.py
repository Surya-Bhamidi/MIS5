"""Run the actual backend suite and retain an observed result, not a manual count."""
from pathlib import Path
import hashlib
import io
import json
import logging
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/operational_improvements'


def run():
    logging.getLogger('httpx').setLevel(logging.WARNING)
    paths=sorted((ROOT/'backend').rglob('*.py'))
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    suite=unittest.defaultTestLoader.discover(str(ROOT/'backend/tests'))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    changed=[p for p,digest in hashes.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=digest]
    output=dict(passed=result.wasSuccessful() and not changed,tests=result.testsRun,failures=[t.id() for t,_ in result.failures],
                errors=[t.id() for t,_ in result.errors],skipped=[t.id() for t,_ in result.skipped],changed_sources=changed,source_sha256=hashes)
    log=ROOT/'data/ui-checks/hardening-tests.log';log.parent.mkdir(parents=True,exist_ok=True);log.write_text(stream.getvalue(),encoding='utf-8')
    (OUT/'test_suite_verification.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k!='source_sha256'},indent=2))
    if not output['passed']:
        print(stream.getvalue()[-12000:]);raise SystemExit(1)


if __name__=='__main__':run()
