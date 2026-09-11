"""Official-protocol practice runner for questions 3 and 4.

Select the practice module in the simulator yourself. The protocol does not
provide a way to detect whether the current session is practice or formal.
"""
import argparse
import hashlib
import http.client
import json
import math
import socket
import sys
import time
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from model import Policy
from optimized import OptimizedPolicy

class BudgetStop(RuntimeError):
    pass

class ProtocolFailure(RuntimeError):
    pass

class UncertainAction(RuntimeError):
    """A request may already have executed. Do not send a different next action."""
    pass

class PracticeHTTP:
    def __init__(self, robot_id, base_url, log_path, timeout=5., attempts=3, progress=True):
        self.robot_id=robot_id;self.base_url=base_url.rstrip('/')
        self.timeout=timeout;self.attempts=attempts;self.progress=progress
        self.log=Path(log_path).open('x',encoding='utf-8',buffering=1)
        self.opener=build_opener(ProxyHandler({}))
        self.session=uuid.uuid4().hex;self.counter=0;self.virtual_time=0.
        self.deadline=None;self.enter_started=None;self.started=False;self.ended=False
        self.uncertain=False;self.position=[0.,0.];self.channel=1;self.cleared=set()
        self.max_virtual=360000.;self.parts=dict(move=0.,switch=0.,measure=0.,optical=0.,laser=0.)
        self.accepted_actions=0;self.attempted_requests=0;self.latest_remaining=None

    def record(self,event,**data):
        self.log.write(json.dumps(dict(event=event,local_time=datetime.now().isoformat(),**data),ensure_ascii=False,allow_nan=False)+'\n')
        self.log.flush()

    @staticmethod
    def number(value,name):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ProtocolFailure(f'Invalid {name}: {value!r}')
        return float(value)

    def post(self,path,**fields):
        if self.uncertain:raise UncertainAction('Previous action unresolved; stop this run.')
        self.counter+=1
        payload=dict(arena_id='default',robot_id=self.robot_id,request_id=f'{self.session}-{self.counter}',**fields)
        raw=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
        if len(raw)>65536:raise ProtocolFailure('Request too large')
        # Log before sending so an interruption does not hide a possibly executed action.
        self.record('request',path=path,payload=payload)
        last=None
        for attempt in range(1,self.attempts+1):
            remaining=self.timeout if self.deadline is None else self.deadline-time.monotonic()
            reserve=0. if path=='/exit' else 8.
            if self.deadline is not None and remaining<=reserve:
                if attempt>1:
                    self.uncertain=True;raise UncertainAction('Deadline reached before retry could resolve action')
                raise BudgetStop('Actual remaining runtime is nearly exhausted')
            request=Request(self.base_url+path,data=raw,headers={'Content-Type':'application/json'},method='POST')
            self.attempted_requests+=1
            self.uncertain=True
            try:
                with self.opener.open(request,timeout=min(self.timeout,max(.05,remaining-reserve)) if self.deadline else self.timeout) as response:
                    status=response.status;content=response.read()
            except HTTPError as error:
                content=error.read().decode('utf-8',errors='replace')
                self.record('http_error',path=path,request_id=payload['request_id'],status=error.code,body=content)
                # Never start a different action after an ambiguous server error.
                raise ProtocolFailure(f'HTTP {error.code}: {content[:400]}') from error
            except (URLError,OSError,socket.timeout,http.client.HTTPException) as error:
                last=error;self.record('transport_error',path=path,request_id=payload['request_id'],attempt=attempt,error=str(error))
                if attempt<self.attempts:
                    time.sleep(.15)
                    continue
                raise UncertainAction(f'Connection failed after {attempt} attempts; action status unknown: {last}') from error
            try:
                body=json.loads(content.decode('utf-8'))
                if not isinstance(body,dict):raise ValueError('Response must be an object')
            except (ValueError,UnicodeError) as error:
                self.record('invalid_response',path=path,body=content[:2000].decode('utf-8',errors='replace'))
                raise ProtocolFailure('Response is not valid JSON; action status unknown') from error
            self.record('response',path=path,request_id=payload['request_id'],status=status,body=body)
            if status!=200 or body.get('accepted') is not True:
                raise ProtocolFailure(f'Request rejected; stop and check simulator: HTTP {status}, {body}')
            vt=self.number(body.get('virtual_time_s'),'virtual_time_s')
            if vt<0 or vt+1e-6<self.virtual_time:raise ProtocolFailure('Virtual clock went backwards')
            self.virtual_time=vt;self.accepted_actions+=1
            # Caller validates the action-specific fields before releasing the guard.
            return body
        raise UncertainAction(str(last))

    def enter(self):
        self.enter_started=time.monotonic();r=self.post('/enter')
        remaining=self.number(r.get('remaining_real_duration_s'),'remaining_real_duration_s')
        limit=self.number(r.get('max_virtual_duration_s'),'max_virtual_duration_s')
        if not 0<=remaining<=1200 or limit<=0:raise ProtocolFailure('Invalid session limits')
        self.deadline=self.enter_started+remaining;self.latest_remaining=remaining;self.max_virtual=limit
        self.started=True;self.uncertain=False
        if self.progress:print(f'已进入测试，实际可用现实时间 {remaining:.0f} 秒。',flush=True)
        return r

    def check_action(self,p,ch,worst_cost):
        if not self.started or self.ended:raise ProtocolFailure('Session is not active')
        if isinstance(ch,bool) or int(ch)!=ch or not 1<=ch<=20:raise ProtocolFailure('Channel must be an integer in 1..20')
        p=[self.number(float(v),'coordinate') for v in p]
        if len(p)!=2 or any(abs(v)>2000000 for v in p):raise ProtocolFailure('Invalid position')
        move=math.dist(p,self.position)/5
        if self.virtual_time+move+worst_cost>=self.max_virtual-1:raise BudgetStop('Virtual time budget nearly exhausted')
        return p,move

    def account(self,before,delta):
        # Official clock rounds at microsecond resolution. Allow accumulated tiny rounding.
        if abs(self.virtual_time-before-delta)>0.002:raise ProtocolFailure('Official clock disagrees with action accounting')
        self.uncertain=False
        if self.progress and self.accepted_actions%50==0:
            print(f'动作 {self.accepted_actions} | 已清除 {len(self.cleared)} | 虚拟时间 {self.virtual_time:.1f} 秒',flush=True)

    def measure(self,p,ch):
        p,move=self.check_action(p,ch,6);before=self.virtual_time;switch=int(self.channel!=ch)
        r=self.post('/measure',position=dict(x=p[0],y=p[1]),channel=int(ch))
        kind=r.get('measure_result')
        if kind not in ('direction','near','no_signal'):raise ProtocolFailure('Unknown measure_result')
        if kind=='direction':
            angle=self.number(r.get('svd_deg'),'svd_deg')
            if not 0<=angle<360:raise ProtocolFailure('Bearing outside [0,360)')
        self.account(before,move+switch+5);self.position=p;self.channel=int(ch)
        self.parts['move']+=move;self.parts['switch']+=switch;self.parts['measure']+=5
        return r

    def clear(self,p,ch):
        p,move=self.check_action(p,ch,5);before=self.virtual_time
        r=self.post('/clear',position=dict(x=p[0],y=p[1]),channel=int(ch))
        kind=r.get('clear_result')
        if kind not in ('success','no_target_in_range'):raise ProtocolFailure('Unknown clear_result')
        success=kind=='success'
        if success and ch in self.cleared:raise ProtocolFailure('Duplicate successful clear')
        self.account(before,move+3+2*success);self.position=p
        self.parts['move']+=move;self.parts['optical']+=3;self.parts['laser']+=2*success
        if success:
            self.cleared.add(int(ch))
            if self.progress:print(f'清除频道 {ch}，累计 {len(self.cleared)} 个，虚拟时间 {self.virtual_time:.1f} 秒。',flush=True)
        return r

    def exit(self):
        r=self.post('/exit')
        if r.get('exit_reason')!='user_exit':raise ProtocolFailure('Unexpected exit reason')
        self.uncertain=False;self.ended=True;return r

def arguments(argv=None):
    parser=argparse.ArgumentParser(description='第3/4问演练程序：覆盖搜索、路线排序与多目标共用测站。')
    parser.add_argument('--question',type=int,choices=[3,4],required=True)
    parser.add_argument('--robot-id',required=True,help='必须与模拟器登录队号一致')
    parser.add_argument('--base-url',default='http://127.0.0.1:2026')
    parser.add_argument('--strategy',choices=['shared','route','triangulate','sweep'],default='shared')
    parser.add_argument('--output-dir',default=str(Path(__file__).resolve().parent/'practice_logs'))
    parser.add_argument('--timeout',type=float,default=5.)
    parser.add_argument('--attempts',type=int,default=3)
    parser.add_argument('--case-code',default='',help='可选：从模拟器界面抄录，用于关联日志')
    parser.add_argument('--connect',action='store_true',help='连接已经启动且接口就绪的演练测试')
    args=parser.parse_args(argv)
    if not args.connect:parser.error('未发送任何请求。请先在模拟器启动对应演练，接口就绪后加 --connect。')
    if not args.robot_id or len(args.robot_id.encode('utf-8'))>64 or any(unicodedata.category(ch).startswith('C') for ch in args.robot_id):parser.error('队号为空、过长或包含不可见字符')
    url=urlsplit(args.base_url)
    if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1') or url.path not in ('','/') or url.query or url.fragment or url.username or url.password:parser.error('接口地址必须是本机回环HTTP地址，例如 http://127.0.0.1:2026')
    if not math.isfinite(args.timeout) or not .1<=args.timeout<=30 or not 1<=args.attempts<=5:parser.error('timeout必须在0.1至30秒之间，attempts必须在1至5之间')
    return args

def main(argv=None):
    args=arguments(argv);base=Path(__file__).resolve().parent
    cfg=json.loads((base/'config.json').read_text(encoding='utf-8'))
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    run_dir=out/f'q{args.question}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}'
    run_dir.mkdir();io=PracticeHTTP(args.robot_id,args.base_url,run_dir/'actions.jsonl',args.timeout,args.attempts)
    meta=dict(question=args.question,strategy=args.strategy,declared_mode='practice',mode_verified_by_protocol=False,case_code=args.case_code,config=cfg,python=sys.version,code_sha256={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in ['practice_robot.py','model.py','optimized.py','q3_policy.py','q4_policy.py','config.json']})
    (run_dir/'run_config.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'第{args.question}问，策略 {args.strategy}，日志：{run_dir}',flush=True)
    print('接口无法识别演练/正式模式；当前应为模拟器中已启动的对应演练。',flush=True)
    policy=None;result={};status='failed';error=None;code=1
    try:
        io.enter()
        policy=OptimizedPolicy(io,cfg,args.question,args.strategy) if args.strategy in ('shared','route') else Policy(io,cfg,args.question,args.strategy)
        result=policy.run();io.exit();status='completed';code=0
    except (Exception,KeyboardInterrupt) as exc:
        error=f'{type(exc).__name__}: {exc}'
        io.record('run_error',error=error)
        # Exit only when the last action is resolved and a live session is known.
        if io.started and not io.ended and not io.uncertain and io.deadline and time.monotonic()<io.deadline-1:
            try:io.exit()
            except Exception as exit_error:io.record('exit_error',error=str(exit_error))
        if isinstance(exc,KeyboardInterrupt):status='interrupted';code=130
        elif isinstance(exc,BudgetStop):status='budget_stop';code=2
        print(f'本次未确认完成：{error}',file=sys.stderr,flush=True)
    finally:
        summary=dict(status=status,error=error,**result,cleared_channels=sorted(io.cleared),successful_clear_count=len(io.cleared),total_virtual_s=io.virtual_time,average_per_cleared_s=io.virtual_time/len(io.cleared) if io.cleared else None,clearance_ratio=None,true_source_count=None,program_elapsed_s=time.monotonic()-io.enter_started if io.enter_started else None,ended_by_exit=io.ended,unresolved_action=io.uncertain,accepted_actions=io.accepted_actions,http_attempts=io.attempted_requests,time_components_s=io.parts,case_code=args.case_code)
        (run_dir/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        if policy is not None:(run_dir/'localization_regions.json').write_text(json.dumps(policy.certificates,ensure_ascii=False,indent=2),encoding='utf-8')
        io.record('summary',**summary);io.log.close()
    if code==0:print(f'任务完成，清除 {len(io.cleared)} 个，平均 {summary["average_per_cleared_s"]:.2f} 虚拟秒/源。',flush=True)
    print(f'结果已保存：{run_dir / "summary.json"}',flush=True)
    return code

if __name__=='__main__':sys.exit(main())
