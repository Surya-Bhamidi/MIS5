"""Research-critical regressions for labels and future-data contamination."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.ingestion.normalizer import EventNormalizer, classify_signature


def alert(ts,sensor='inside',phase=1):
    return dict(timestamp=ts,timestamp_iso=str(ts),alert_id=str(ts),src_ip='a',
        dst_ip='b',src_port='1',dst_port='33000',service_name='rpc',
        sensor_source=sensor,true_phase_label=phase)


class TestIngestionCausality(unittest.TestCase):
    def test_labels_do_not_change_signatures(self):
        for service,port in [('rpc','33000'),('unknown','50000'),('sadmind','54791')]:
            self.assertEqual(len({classify_signature(service,port,p) for p in range(6)}),1)

    def test_later_sensor_report_does_not_change_prefix(self):
        prior=[alert(100),alert(101,'dmz')]
        self.assertEqual(EventNormalizer.normalize_and_merge(prior),
            EventNormalizer.normalize_and_merge(prior+[alert(102)])[0:2])
        normalized=EventNormalizer.normalize_and_merge(prior)
        self.assertEqual([e['session_cooccurred'] for e in normalized],[0,1])

    def test_future_events_do_not_change_window_features(self):
        current=dict(timestamp=100,dst_ip='b')
        future=[dict(timestamp=101+i,dst_ip=str(i)) for i in range(40)]
        self.assertEqual(EventNormalizer.extract_window_features([],current),
            EventNormalizer.extract_window_features(future,current))


if __name__=='__main__':
    unittest.main()
