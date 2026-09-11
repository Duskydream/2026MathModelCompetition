"""Real loopback HTTP end-to-end tests. Never connect to the official simulator."""
import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from unittest.mock import patch

from simulator import LocalSimulator,generate
from optimized import OptimizedPolicy
from experiments import validate
from practice_robot import PracticeHTTP,BudgetStop,UncertainAction,ProtocolFailure,main

CFG=json.loads((Path(__file__).parent/'config.json').read_text())

class Harness:
    def __init__(self,q,drop=None,remaining=1200,reject=False):
        self.sources=generate(20270961,q);self.sim=LocalSimulator(self.sources,CFG,20270961)
        self.cache={};self.requests=[];self.active=False;self.exited=False
        self.drop=drop;self.dropped=False;self.remaining=remaining;self.reject=reject
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']));p=json.loads(raw)
                owner.requests.append((self.path,raw));key=p['request_id']
                if key in owner.cache:
                    saved_path,saved_raw,body=owner.cache[key]
                    assert self.path==saved_path and raw==saved_raw
                elif owner.reject:
                    body=dict(accepted=False,real_timestamp_ms=0,virtual_time_s=0)
                else:
                    assert p['arena_id']=='default' and p['robot_id']=='test-team'
                    if self.path=='/enter':
                        assert not owner.active;owner.active=True
                        body=dict(accepted=True,virtual_time_s=0,real_timestamp_ms=0,max_virtual_duration_s=360000,max_real_duration_s=1200,remaining_real_duration_s=owner.remaining)
                    elif self.path=='/exit':
                        assert owner.active;owner.active=False;owner.exited=True
                        body=dict(accepted=True,virtual_time_s=owner.sim.time,real_timestamp_ms=0,exit_reason='user_exit')
                    else:
                        assert owner.active and not owner.exited
                        pos=[p['position']['x'],p['position']['y']]
                        body=(owner.sim.measure if self.path=='/measure' else owner.sim.clear)(pos,p['channel'])
                        body['real_timestamp_ms']=0
                    owner.cache[key]=(self.path,raw,body)
                if self.path==owner.drop and not owner.dropped:
                    owner.dropped=True;self.close_connection=True
                    self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
                rawout=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(rawout)));self.end_headers();self.wfile.write(rawout)
        self.server=HTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*args):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

class PracticeTests(unittest.TestCase):
    def client(self,h,tmp):return PracticeHTTP('test-team',h.url,Path(tmp)/'actions.jsonl',progress=False)
    def test_q3_and_q4_full_http(self):
        for q in (3,4):
            with self.subTest(question=q),tempfile.TemporaryDirectory() as tmp,Harness(q) as h:
                io=self.client(h,tmp)
                try:
                    io.enter();policy=OptimizedPolicy(io,CFG,q);result=policy.run();io.exit()
                    validate(h.sim,policy,h.sources)
                    self.assertEqual(result['cleared_count'],len(h.sources));self.assertEqual(io.cleared,h.sim.removed)
                    self.assertTrue(h.exited);self.assertAlmostEqual(sum(io.parts.values()),h.sim.time,places=6)
                    print(f'Q{q} HTTP: {len(io.cleared)}/{len(h.sources)}, {io.virtual_time:.6f}s, {io.accepted_actions} actions')
                finally:io.log.close()
    def test_lost_response_retries_same_action_once(self):
        for path in ('/enter','/measure','/clear','/exit'):
            with self.subTest(path=path),tempfile.TemporaryDirectory() as tmp,Harness(3,drop=path) as h:
                io=self.client(h,tmp)
                try:
                    io.enter();io.measure([300,400],1);io.clear([0,0],20);io.exit()
                    sent=[raw for p,raw in h.requests if p==path]
                    self.assertEqual(len(sent),2);self.assertEqual(sent[0],sent[1]);self.assertEqual(len(h.sim.log),2)
                    self.assertFalse(io.uncertain);self.assertTrue(h.exited)
                finally:io.log.close()
    def test_short_actual_deadline_and_virtual_budget(self):
        with tempfile.TemporaryDirectory() as tmp,Harness(3,remaining=5) as h:
            io=self.client(h,tmp)
            try:
                io.enter()
                with self.assertRaises(BudgetStop):io.measure([0,0],1)
                self.assertFalse(io.uncertain);io.exit();self.assertEqual(len(h.sim.log),0)
            finally:io.log.close()
        with tempfile.TemporaryDirectory() as tmp,Harness(3) as h:
            io=self.client(h,tmp)
            try:
                io.enter();io.max_virtual=10
                with self.assertRaises(BudgetStop):io.measure([100,0],1)
                io.exit();self.assertEqual(len(h.sim.log),0)
            finally:io.log.close()
    def test_rejection_keeps_last_clock(self):
        with tempfile.TemporaryDirectory() as tmp,Harness(3,reject=True) as h:
            io=self.client(h,tmp)
            try:
                io.virtual_time=25
                with self.assertRaises(ProtocolFailure):io.enter()
                self.assertEqual(io.virtual_time,25)
            finally:io.log.close()
    def test_unresolved_failure_prevents_new_action(self):
        with tempfile.TemporaryDirectory() as tmp,Harness(3) as h:
            io=self.client(h,tmp)
            try:
                io.enter()
                with patch.object(io.opener,'open',side_effect=ConnectionResetError('test')):
                    with self.assertRaises(UncertainAction):io.measure([0,0],1)
                    with self.assertRaises(UncertainAction):io.exit()
                self.assertTrue(io.uncertain)
            finally:io.log.close()
    def test_runner_summary_and_early_stop(self):
        for remaining,expected in [(1200,0),(5,2)]:
            with self.subTest(remaining=remaining),tempfile.TemporaryDirectory() as tmp,Harness(3,remaining=remaining) as h:
                with patch('builtins.print'):
                    code=main(['--question','3','--robot-id','test-team','--base-url',h.url,'--output-dir',tmp,'--connect'])
                self.assertEqual(code,expected);summary=json.loads(next(Path(tmp).rglob('summary.json')).read_text())
                self.assertIsNone(summary['clearance_ratio']);self.assertTrue(summary['ended_by_exit'])
                self.assertEqual(summary['status'],'completed' if expected==0 else 'budget_stop')
    def test_connect_required(self):
        with self.assertRaises(SystemExit) as e:main(['--question','3','--robot-id','test-team'])
        self.assertEqual(e.exception.code,2)

if __name__=='__main__':unittest.main(verbosity=2)
