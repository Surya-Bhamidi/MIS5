"""Read public CAM-LDS ZIP directories only; no outcome analysis."""
import json
import zipfile
import requests
from fetch_endpoint_evidence import RangeReader
from evidence_pilot import ROOT

def run():
    directory=ROOT/'data/research/cam_lds'
    directory.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    metadata=session.get('https://zenodo.org/api/records/18390561',timeout=40)
    metadata.raise_for_status()
    record=metadata.json()
    (directory/'record_metadata.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    wanted=['scenario_1_sudo_localaccount.zip','scenario_2_cron.zip','scenario_3_ssh_apt.zip',
            'scenario_4.zip','scenario_5.zip','scenario_6_macro_binary.zip']
    result=[]
    for key in wanted:
        item=next(f for f in record['files'] if f['key']==key)
        reader=RangeReader(item['links']['self'],item['size'],session)
        with zipfile.ZipFile(reader) as archive:
            members=[{'name':m.filename,'size':m.file_size,'compressed':m.compress_size}
                     for m in archive.infolist()]
        row={'archive':key,'members':members,'directory_bytes':reader.downloaded}
        result.append(row)
        print(key,json.dumps([m for m in members if any(k in m['name'].lower()
            for k in ['attackmate','alerts.json','aminer','audit.log'])]),flush=True)
    (directory/'directories.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

if __name__=='__main__':run()
