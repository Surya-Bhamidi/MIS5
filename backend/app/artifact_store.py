"""Content-keyed local artifact reads. Checksums detect accidental evidence drift.

Manifests are trusted local files, not signatures or protection from a local writer.
"""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import hashlib
import json

import numpy as np
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]


def file_bytes(relative):
    try:
        return (ROOT / relative).read_bytes()
    except OSError as error:
        raise HTTPException(503, "Required local evidence is unavailable") from error


@lru_cache(maxsize=16)
def decoded_json(content):
    try:
        return json.loads(content, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError) as error:
        raise HTTPException(503, "Local evidence is malformed; rerun its verification") from error


def read_json(relative):
    return decoded_json(file_bytes(relative))


def verified_bytes(relative):
    relative = Path(relative).as_posix()
    try:
        if relative.startswith('experiments/current_version/'):
            manifest = read_json('experiments/current_version/reproducibility.json')['sha256']
            hashes = {name.replace('\\', '/'): digest for name, digest in manifest.items()}
        elif relative.startswith('Plots/Results/mids/'):
            hashes = {'Plots/Results/mids/' + name: digest for name, digest in
                      read_json('Plots/Results/mids/manifest.json')['output_sha256'].items()}
        else:
            manifest = read_json('experiments/operational_improvements/metrics_verification.json')
            if manifest['passed'] is not True:
                raise ValueError('Unverified metrics')
            hashes = manifest['input_sha256']
        expected = hashes[relative]
        content = file_bytes(relative)
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError('Checksum differs')
        return content
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(503, 'Local evidence changed or is unverified; rerun verification') from error


def verified_json(relative):
    return decoded_json(verified_bytes(relative))


@lru_cache(maxsize=8)
def decoded_archive(content):
    try:
        with np.load(BytesIO(content), allow_pickle=False) as data:
            return {key: data[key].copy() for key in ('risk', 'times', 'horizons', 'onset')}
    except (ValueError, KeyError, OSError) as error:
        raise HTTPException(503, 'Frozen forecast evidence is malformed') from error
