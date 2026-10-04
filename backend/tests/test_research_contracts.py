"""Independent checks for archive decoding, forecast semantics and input isolation."""
import io
import struct
import sys
import unittest
from pathlib import Path

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import extended_study as study
from prepare_extended_data import pcap_records, packet_features, detector_token


def capture(rows,order='<',nanosecond=False):
    magic=(b'\x4d\x3c\xb2\xa1' if nanosecond else b'\xd4\xc3\xb2\xa1') if order=='<' else (
        b'\xa1\xb2\x3c\x4d' if nanosecond else b'\xa1\xb2\xc3\xd4')
    header=magic+struct.pack(order+'HHIIII',2,4,0,0,65535,1)
    data=bytearray(header)
    for second,fraction,packet in rows:
        data+=struct.pack(order+'IIII',second,fraction,len(packet),len(packet))+packet
    return io.BytesIO(data)


def ack(source):
    ethernet=b'\0'*12+b'\x08\x00'
    ip=bytearray(20);ip[0]=0x45;ip[9]=6
    ip[12:16]=source.to_bytes(4,'big');ip[16:20]=bytes([131,84,1,31])
    tcp=bytearray(20);tcp[:4]=struct.pack('>HH',1000,2000);tcp[12]=0x50;tcp[13]=16
    return ethernet+ip+tcp


class TestResearchContracts(unittest.TestCase):
    def test_pcap_time_formats_and_truncation(self):
        for order in ['<','>']:
            for nano in [False,True]:
                scale=10**9 if nano else 10**6
                record=list(pcap_records(capture([(10,scale//4,b'packet')],order,nano)))[0]
                self.assertEqual(record,(10.25,6,b'packet'))
        broken=capture([(10,0,b'packet')]).getvalue()[:-1]
        with self.assertRaises(ValueError):list(pcap_records(io.BytesIO(broken)))

    def test_onset_ignores_earlier_ordinary_ack(self):
        rows=[(10,100000,ack(1))]+[(100,10000+i,ack(1000+i)) for i in range(100)]
        _,metadata=packet_features(capture(rows))
        self.assertEqual(len(metadata['victim_ack_flood_bursts']),1)
        self.assertAlmostEqual(metadata['victim_ack_flood_bursts'][0]['first'],100.01)

    def test_vocabulary_is_fitted_without_test_tokens(self):
        train=dict(names=np.array(['wazuh:known']),counts=np.array([[3.],[1.]]),times=np.array([60.,120.]))
        test=dict(names=np.array(['wazuh:test_only']),counts=np.array([[9.]]),times=np.array([60.]))
        counts,names=study.aligned_counts({'train':train,'test':test},['train'])
        self.assertNotIn('wazuh:test_only',names)
        self.assertEqual(counts['test'][0,names.index('wazuh:OTHER')],9)
        event={'rule':{'id':'1'},'true_phase_label':5}
        token=detector_token(event,0);event['true_phase_label']=0
        self.assertEqual(token,detector_token(event,0))

    def test_forecast_is_future_first_onset_not_current_detection(self):
        model={'a':np.array([[.8,.2],[0.,1.]]),'b':np.full((2,1,5),.2),
               'pi':np.array([1.,0.]),'prior':np.array([1.,0.])}
        risk=study.forecast(model,np.zeros((1,1),dtype=int),'static_bn')[0]
        self.assertTrue(np.allclose(risk,[1-.8**h for h in study.HORIZONS]))
        model['prior']=np.array([0.,1.])
        self.assertTrue(np.allclose(study.forecast(model,np.zeros((1,1),dtype=int),'static_bn'),0,atol=1e-12))


if __name__=='__main__':unittest.main()
