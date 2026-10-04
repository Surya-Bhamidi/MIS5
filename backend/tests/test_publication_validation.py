"""Meaningful independent contracts for publication evidence and causal scoring."""
import io
import itertools
import sys
import unittest
from pathlib import Path

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import audit_endpoints as audit
import published_hmm_baseline as baseline
from fetch_endpoint_evidence import RangeReader,LIMIT
from gru_baseline import checks as gru_checks

class Response:
    def __init__(self,status,content_range,data):
        self.status_code=status;self.headers={'Content-Range':content_range};self._data=data
        self.content_accessed=False
    @property
    def content(self):self.content_accessed=True;return self._data
    def __enter__(self):return self
    def __exit__(self,*args):pass

class Session:
    def __init__(self,response):self.response=response
    def get(self,*args,**kwargs):return self.response

class TestPublicationValidation(unittest.TestCase):
    def test_range_refuses_full_archive_before_body(self):
        response=Response(200,'',b'full archive')
        with self.assertRaises(ValueError):RangeReader('url',100,Session(response)).read(10)
        self.assertFalse(response.content_accessed)

    def test_range_validates_length_bounds_and_positions(self):
        reader=RangeReader('url',100,Session(Response(206,'bytes 5-7/100',b'abc')))
        reader.seek(5);self.assertEqual(reader.read(3),b'abc');self.assertEqual(reader.tell(),8)
        with self.assertRaises(ValueError):reader.seek(-1)
        with self.assertRaises(ValueError):RangeReader('url',LIMIT+1,Session(None)).read()
        with self.assertRaises(ValueError):RangeReader('url',100,Session(Response(206,'bytes 0-9/100',b'x'))).read(10)

    def test_success_endpoint_requires_attack_label_session_and_account(self):
        lines=['type=USER_START msg=audit(1.1:1): acct="root" exe="/usr/bin/sudo" res=success',
               'type=USER_AUTH msg=audit(2.1:2): acct="u" exe="/bin/su" res=success',
               'type=USER_START msg=audit(3.1:3): acct="u" exe="/bin/su" res=failed',
               'type=USER_START msg=audit(4.1:4): acct="u" exe="/bin/su" res=success',
               'type=USER_START msg=audit(5.1:5): acct="root" exe="/usr/bin/sudo" res=success']
        labels=[{'line':i,'labels':['escalate']} for i in range(2,6)]
        sessions=audit.audit_sessions(lines,labels)
        self.assertEqual([(s['timestamp'],s['account']) for s in sessions],[(4.1,'u'),(5.1,'root')])
        with self.assertRaises(ValueError):audit.audit_sessions(lines,[{'line':0,'labels':['escalate']}])

    def test_persistent_false_alarm_does_not_become_new_timely_alarm(self):
        ep={'times':np.arange(1,11)*60.,'onset':601.}
        result=audit.strict_warning_metrics(ep,np.ones(10),5,.5)
        self.assertEqual(result['warning_recall'],1)
        self.assertEqual(result['strict_warning_recall'],0)
        self.assertEqual(result['false_warning_episodes'],1)
        p=np.zeros(10);p[6:]=1
        self.assertEqual(audit.strict_warning_metrics(ep,p,5,.5)['strict_warning_recall'],1)

    def test_delay_uses_only_previously_available_predictions(self):
        p=np.arange(20).reshape(10,2)/20
        shifted=audit.delayed(p,2)
        np.testing.assert_array_equal(shifted[:2],0)
        np.testing.assert_array_equal(shifted[2:],p[:-2])
        np.testing.assert_array_equal(audit.delayed(p[:5],2),shifted[:5])

    def test_hmm_likelihood_matches_exhaustive_hidden_paths(self):
        a=np.array([[.8,.2],[.3,.7]]);b=np.array([[.9,.1],[.2,.8]]);pi=np.array([.6,.4])
        obs=np.array([0,1,1,0]);alpha,scales=baseline.forward(obs,a,b,pi)
        probability=0.
        for path in itertools.product(range(2),repeat=len(obs)):
            value=pi[path[0]]*b[path[0],obs[0]]
            for t in range(1,len(obs)):value*=a[path[t-1],path[t]]*b[path[t],obs[t]]
            probability+=value
        self.assertAlmostEqual(np.prod(scales),probability,places=13)
        self.assertTrue(np.allclose(alpha.sum(axis=1),1))
        model={'a':a,'b':b,'pi':pi}
        for mode in ['viterbi','filtered']:
            result=baseline.first_onset_projection(model,obs,np.full(2,.2),mode)
            expected=1-.8**np.array(baseline.study.HORIZONS)
            np.testing.assert_allclose(result,np.tile(expected,(4,1)))

    def test_gru_prefix_causality(self):gru_checks()

if __name__=='__main__':unittest.main()
