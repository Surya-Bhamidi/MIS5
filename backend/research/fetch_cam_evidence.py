"""Fetch complete Wazuh streams and execution logs for six fixed CAM templates."""
import hashlib
import json
import zipfile
import requests
from evidence_pilot import ROOT
from fetch_endpoint_evidence import RangeReader

def run():
    dest=ROOT/'data/research/cam_lds'
    record=json.loads((dest/'record_metadata.json').read_text())
    directories=json.loads((dest/'directories.json').read_text())
    manifest=[];session=requests.Session()
    for directory in directories:
        key=directory['archive'];name=key[:-4]
        source=next(f for f in record['files'] if f['key']==key)
        reader=RangeReader(source['links']['self'],source['size'],session)
        members=[]
        with zipfile.ZipFile(reader) as archive:
            for local,suffix in [('alerts.json','wazuh/logs/alerts/alerts.json'),
                                 ('attackmate.json','attacker/logs/attackmate.json'),
                                 ('attackmate.log','attacker/logs/attackmate.log'),
                                 ('attack_output.log','attacker/logs/output.log')]:
                candidates=[m for m in archive.infolist() if m.filename.endswith(suffix)]
                if len(candidates)!=1:raise ValueError(f'Ambiguous or absent source {name}/{suffix}')
                item=candidates[0]
                if item.file_size>32*1024**2 or item.compress_size>16*1024**2:
                    raise ValueError('Refused unexpectedly large member')
                content=archive.read(item)
                path=dest/name/local;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
                members.append({'member':item.filename,'path':str(path.relative_to(ROOT)),
                    'sha256':hashlib.sha256(content).hexdigest(),'expanded_bytes':len(content),
                    'zip_crc32':item.CRC,'crc_validated':True})
        manifest.append({'scenario':name,'source':source['links']['self'],'archive_size':source['size'],
            'published_checksum':source['checksum'],'whole_archive_checksum_verified':False,
            'members':members,'downloaded_bytes':reader.downloaded})
        (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        print(f'Fetched {name}: {reader.downloaded} compressed bytes',flush=True)

if __name__=='__main__':run()
