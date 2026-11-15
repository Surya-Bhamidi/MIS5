"""Fault tests use isolated evidence copies; never corrupt the research archives."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app import artifact_store as evidence


class TestArtifactIntegrity(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.patch=patch.object(evidence,'ROOT',self.root);self.patch.start()
        self.addCleanup(self.directory.cleanup);self.addCleanup(self.patch.stop)

    def write(self,name,content):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)

    def test_verified_json_rechecks_content_after_cache_hit(self):
        name='experiments/selective_fusion/scored.json';content=b'{"score":0.5}'
        self.write(name,content)
        self.write('experiments/operational_improvements/metrics_verification.json',json.dumps(dict(passed=True,input_sha256={name:hashlib.sha256(content).hexdigest()})).encode())
        self.assertEqual(evidence.verified_json(name),dict(score=.5))
        self.write(name,b'{"score":1.0}')
        with self.assertRaises(HTTPException) as error:evidence.verified_json(name)
        self.assertEqual(error.exception.status_code,503)
        self.write(name,content)
        self.assertEqual(evidence.verified_json(name),dict(score=.5))

    def test_frozen_archive_checked_before_cached_decoding(self):
        name='experiments/current_version/predictions/example.npz';content=b'not a valid npz'
        self.write(name,content)
        self.write('experiments/current_version/reproducibility.json',json.dumps(dict(sha256={name.replace('/','\\'):hashlib.sha256(content).hexdigest()})).encode())
        self.assertEqual(evidence.verified_bytes(name),content)
        with self.assertRaises(HTTPException):evidence.decoded_archive(content)
        self.write(name,b'changed')
        with self.assertRaises(HTTPException):evidence.verified_bytes(name)

    def test_bad_missing_and_nonfinite_json_fail_without_reflecting_contents(self):
        for content in (b'not JSON: SECRET_SENTINEL',b'{"value":NaN}',b'{"value":Infinity}',b'\xff'):
            self.write('report.json',content)
            with self.assertRaises(HTTPException) as error:evidence.read_json('report.json')
            self.assertEqual(error.exception.status_code,503)
            self.assertNotIn('SECRET_SENTINEL',error.exception.detail)
        with self.assertRaises(HTTPException):evidence.read_json('missing.json')

    def test_unverified_manifest_and_unlisted_file_fail_closed(self):
        self.write('experiments/operational_improvements/metrics_verification.json',b'{"passed":false,"input_sha256":{}}')
        with self.assertRaises(HTTPException):evidence.verified_bytes('unlisted.json')
        self.write('experiments/operational_improvements/metrics_verification.json',b'{"passed":true,"input_sha256":{}}')
        with self.assertRaises(HTTPException):evidence.verified_bytes('unlisted.json')


if __name__=='__main__':unittest.main()
