"""No network used: retry identity, rejected-state handling and actual deadline."""
import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from http_robot import HTTPRobot

class Response:
    status=200
    def __init__(self,body):self.body=body
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return json.dumps(self.body).encode()

class ProtocolTests(unittest.TestCase):
    def test_retry_preserves_exact_body(self):
        with tempfile.TemporaryDirectory() as d:
            io=HTTPRobot('local-test','http://127.0.0.1:2026',Path(d)/'log')
            with patch('http_robot.urlopen',side_effect=[URLError('test'),Response({'accepted':True,'virtual_time_s':5})]) as send:
                io.measure([0,0],1)
                self.assertEqual(send.call_args_list[0].args[0].data,send.call_args_list[1].args[0].data)
                self.assertEqual(io.virtual_time,5)
    def test_rejection_does_not_reset_clock(self):
        with tempfile.TemporaryDirectory() as d:
            io=HTTPRobot('local-test','http://127.0.0.1:2026',Path(d)/'log');io.virtual_time=25
            with patch('http_robot.urlopen',return_value=Response({'accepted':False,'virtual_time_s':0})):
                with self.assertRaises(RuntimeError):io.measure([0,0],1)
            self.assertEqual(io.virtual_time,25)
    def test_enter_uses_remaining_budget(self):
        with tempfile.TemporaryDirectory() as d:
            io=HTTPRobot('local-test','http://127.0.0.1:2026',Path(d)/'log');before=time.monotonic()
            with patch('http_robot.urlopen',return_value=Response({'accepted':True,'virtual_time_s':0,'remaining_real_duration_s':100,'max_virtual_duration_s':360000})):
                io.enter()
            self.assertLessEqual(io.deadline,time.monotonic()+100)
            self.assertGreaterEqual(io.deadline,before+100)

if __name__=='__main__':unittest.main()
