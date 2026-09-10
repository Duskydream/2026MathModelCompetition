"""Serial official-protocol adapter. Connect only when explicitly invoked.

No simulator login, case generation, formal-test creation, or log export is automated.
"""
from pathlib import Path
import argparse, json, socket, time, uuid
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
from model import Policy

class HTTPRobot:
    def __init__(self,robot_id,base_url,log_path):
        self.robot_id=robot_id;self.base_url=base_url.rstrip('/');self.log_path=Path(log_path)
        self.deadline=None;self.virtual_time=0.;self.max_virtual=360000.;self.counter=0;self.session=uuid.uuid4().hex
    def post(self,path,**fields):
        self.counter+=1
        payload={'arena_id':'default','robot_id':self.robot_id,'request_id':f'{self.session}-{self.counter}',**fields}
        raw=json.dumps(payload,allow_nan=False,separators=(',',':')).encode('utf-8')
        # Exact same path/body/id reused only after transport failures.
        for attempt in range(3):
            remaining=5. if self.deadline is None else self.deadline-time.monotonic()
            reserve=0. if path=='/exit' else 3.
            if remaining<=reserve:raise TimeoutError('Insufficient actual remaining runtime')
            if self.virtual_time>=self.max_virtual-10 and path!='/exit':raise TimeoutError('Virtual time budget exhausted')
            request=Request(self.base_url+path,data=raw,headers={'Content-Type':'application/json'},method='POST')
            try:
                with urlopen(request,timeout=min(5.,remaining-reserve)) as response:
                    status=response.status;body=json.loads(response.read().decode('utf-8'))
            except HTTPError as e:
                self.record(path,payload,{'http_status':e.code,'body':e.read().decode('utf-8',errors='replace')})
                raise RuntimeError(f'HTTP {e.code}; action stopped for diagnosis') from e
            except (URLError,TimeoutError,socket.timeout,ConnectionError) as e:
                self.record(path,payload,{'transport_error':str(e),'attempt':attempt+1})
                if attempt==2:raise
                continue
            self.record(path,payload,{'http_status':status,'body':body})
            if status!=200 or body.get('accepted') is not True:raise RuntimeError(f'Request rejected: {status} {body}')
            vt=body['virtual_time_s']
            if vt+1e-6<self.virtual_time:raise RuntimeError('Non-monotone virtual time')
            self.virtual_time=vt
            return body
        raise RuntimeError('Unreachable')
    def record(self,path,payload,response):
        with self.log_path.open('a',encoding='utf-8') as f:
            f.write(json.dumps({'path':path,'request':payload,'response':response},ensure_ascii=False)+'\n')
    def enter(self):
        # Start clock before request: conservative with network latency.
        before=time.monotonic();r=self.post('/enter');self.deadline=before+r['remaining_real_duration_s'];self.max_virtual=r['max_virtual_duration_s'];return r
    def measure(self,p,ch):return self.post('/measure',position={'x':float(p[0]),'y':float(p[1])},channel=int(ch))
    def clear(self,p,ch):return self.post('/clear',position={'x':float(p[0]),'y':float(p[1])},channel=int(ch))
    def exit(self):return self.post('/exit')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question',type=int,choices=[3,4],required=True)
    parser.add_argument('--robot-id',required=True)
    parser.add_argument('--base-url',default='http://127.0.0.1:2026')
    parser.add_argument('--log',default='robot_actions.jsonl')
    parser.add_argument('--strategy',choices=['sweep','triangulate'],default='triangulate')
    parser.add_argument('--connect',action='store_true',help='Actually enter an already-started simulator test')
    args=parser.parse_args()
    if not args.connect:parser.error('No request sent. Use --connect only after the intended simulator test is ready.')
    cfg=json.loads((Path(__file__).parent/'config.json').read_text())
    io=HTTPRobot(args.robot_id,args.base_url,args.log);io.enter()
    try:
        result=Policy(io,cfg,args.question,args.strategy).run()
    except TimeoutError:
        if io.deadline is not None and time.monotonic()<io.deadline-1:io.exit()
        raise
    io.exit();print(json.dumps({**result,'total_virtual_s':io.virtual_time,'average_per_cleared_s':io.virtual_time/result['cleared_count'] if result['cleared_count'] else None},ensure_ascii=False))

if __name__=='__main__':main()
