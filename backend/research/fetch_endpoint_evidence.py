"""Retrieve selected original AIT execution/audit logs via bounded ZIP ranges.

Never downloads/extracts an entire multi-GB archive. Validates range responses,
ZIP member CRCs, bounded expanded sizes, and records SHA-256 for fetched files.
"""
import argparse
import io
import json
import hashlib
import zipfile
from pathlib import Path

import requests
import evidence_pilot as pilot

DEST=pilot.ROOT/'data/research/endpoint_evidence'
RECORD='https://zenodo.org/api/records/5789064'
LIMIT=16*1024*1024


class RangeReader(io.RawIOBase):
    def __init__(self,url,size,session):
        self.url,self.size,self.session=url,size,session
        self.position=0;self.downloaded=0;self.requests=0

    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position

    def seek(self,offset,whence=0):
        destination=offset if whence==0 else (self.position+offset if whence==1 else self.size+offset)
        if destination<0 or destination>self.size:raise ValueError('ZIP seek outside archive')
        self.position=destination;return destination

    def read(self,size=-1):
        size=self.size-self.position if size<0 else min(size,self.size-self.position)
        if size==0:return b''
        if size>LIMIT:raise ValueError('Unbounded remote ZIP read refused')
        start=self.position;end=start+size-1
        with self.session.get(self.url,headers={'Range':f'bytes={start}-{end}'},stream=True,timeout=(15,40)) as response:
            if response.status_code!=206:
                raise ValueError(f'Expected partial response, got {response.status_code}; refused full archive')
            if response.headers.get('Content-Range')!=f'bytes {start}-{end}/{self.size}':
                raise ValueError('Unexpected range content')
            data=response.content
        if len(data)!=size:raise ValueError('Truncated remote range')
        self.position+=size;self.downloaded+=size;self.requests+=1
        return data


def fetch(names):
    DEST.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    response=session.get(RECORD,timeout=30);response.raise_for_status()
    metadata=response.json()
    (DEST/'record_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    files={x['key']:x for x in metadata['files']}
    manifest_path=DEST/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name in names:
        if name in manifest and manifest[name].get('complete'):
            for member in manifest[name]['members']:
                if hashlib.sha256((pilot.ROOT/member['local_path']).read_bytes()).hexdigest()!=member['sha256']:
                    raise ValueError(f'Cached endpoint evidence checksum mismatch: {name}')
            print(f'Cached original endpoint evidence {name}',flush=True);continue
        source=files[name+'.zip'];reader=RangeReader(source['links']['self'],source['size'],session)
        result={'source_record':RECORD,'source_archive':name+'.zip','archive_size':source['size'],
                'published_archive_checksum':source['checksum'],'whole_archive_checksum_verified':False,'members':[]}
        with zipfile.ZipFile(reader) as archive:
            chosen=[]
            for item in archive.infolist():
                member=item.filename
                if member.endswith('gather/attacker_0/logs/attacks.log'):
                    chosen.append(('attacks.log',item))
                elif member.endswith('gather/intranet_server/logs/audit/audit.log'):
                    chosen.append(('intranet_audit.log',item))
                elif member.endswith('labels/intranet_server/logs/audit/audit.log'):
                    chosen.append(('intranet_audit_labels.jsonl',item))
            if not any(local=='attacks.log' for local,_ in chosen):
                raise ValueError(f'Missing documented execution log in {name}')
            for local,item in chosen:
                if max(item.file_size,item.compress_size)>LIMIT:
                    raise ValueError(f'Endpoint member over bounded size: {item.filename}')
                content=archive.read(item)
                path=DEST/name/local;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
                result['members'].append({'member':item.filename,'local_path':str(path.relative_to(pilot.ROOT)),
                    'expanded_bytes':len(content),'compressed_bytes':item.compress_size,'zip_crc32':item.CRC,
                    'sha256':hashlib.sha256(content).hexdigest(),'crc_validated':True})
                print(f'Fetched {name}/{local}: {len(content)} bytes',flush=True)
        result.update(complete=True,downloaded_bytes=reader.downloaded,range_requests=reader.requests)
        manifest[name]=result
        manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Bounded endpoint-evidence fetch complete',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--scenario',choices=pilot.SCENARIOS)
    args=parser.parse_args();fetch([args.scenario] if args.scenario else pilot.SCENARIOS)
