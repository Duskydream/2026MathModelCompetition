"""LOCAL SYNTHETIC emulator. Not the official simulator or formal evidence."""
import hashlib, math
import numpy as np

class LocalSimulator:
    def __init__(self,sources,cfg,seed=0,noise='spatial',amplitude=1):
        self.sources={int(s['channel']):dict(s) for s in sources};self.cfg=cfg
        self.seed=seed;self.noise=noise;self.amplitude=amplitude;self.removed=set()
        self.pos=np.zeros(2);self.channel=1;self.time=0.;self.log=[]
        self.parts=dict(move=0.,switch=0.,measure=0.,optical=0.,laser=0.)
    def _move(self,p):
        p=np.asarray(p,float)
        assert p.shape==(2,) and np.all(np.isfinite(p)) and np.max(abs(p))<=2000000
        dt=float(np.linalg.norm(p-self.pos))/self.cfg['speed_m_s'];self.parts['move']+=dt;self.time+=dt;self.pos=p.copy()
    def _add(self,key,dt):self.parts[key]+=dt;self.time+=dt
    def _record(self,action,ch,response):
        assert self.time<self.cfg['virtual_limit_s']
        response.update(accepted=True,virtual_time_s=self.time)
        self.log.append(dict(action=action,position=self.pos.tolist(),channel=int(ch),response=response.copy()))
        return response
    def measure(self,p,ch):
        assert 1<=ch<=20;self._move(p)
        if self.channel!=ch:self._add('switch',self.cfg['switch_s'])
        self.channel=ch;self._add('measure',self.cfg['measure_s'])
        s=self.sources.get(ch);r={'measure_result':'no_signal'}
        if s is not None and ch not in self.removed:
            delta=self.pos-np.array(s['position']);dist=float(np.linalg.norm(delta))
            visible=s['orientation_deg'] is None or delta@np.array([math.cos(math.radians(s['orientation_deg'])),math.sin(math.radians(s['orientation_deg']))])>=-1e-9
            if dist<=s['radius_m']+1e-9 and visible:
                if dist<=self.cfg['near_m']:r={'measure_result':'near'}
                else:
                    if self.noise=='constant':e=self.amplitude
                    elif self.noise=='zero':e=0.
                    elif self.noise=='smooth':e=self.amplitude*math.sin(self.pos[0]/250+self.pos[1]/380+ch)
                    else:
                        key=f'{self.seed}|{ch}|{self.pos[0]:.9f}|{self.pos[1]:.9f}'.encode()
                        e=self.amplitude*(2*int.from_bytes(hashlib.sha256(key).digest()[:8],'big')/(2**64-1)-1)
                    angle=(math.degrees(math.atan2(-delta[1],-delta[0]))+e)%360
                    r={'measure_result':'direction','svd_deg':round(angle,2)%360}
        return self._record('measure',ch,r)
    def clear(self,p,ch):
        assert 1<=ch<=20;self._move(p);self._add('optical',self.cfg['clear_failure_s'])
        s=self.sources.get(ch)
        good=s is not None and ch not in self.removed and np.linalg.norm(self.pos-np.array(s['position']))<=self.cfg['clear_m']+1e-9
        if good:self.removed.add(ch);self._add('laser',self.cfg['clear_success_s']-self.cfg['clear_failure_s'])
        return self._record('clear',ch,{'clear_result':'success' if good else 'no_target_in_range'})

def generate(seed,question,kind='random'):
    rng=np.random.default_rng(seed);n=int(rng.integers(10,17));channels=rng.choice(np.arange(1,21),n,replace=False)
    result=[]
    for ch in channels:
        a=rng.uniform(0,2*np.pi);r=1800*np.sqrt(rng.random())
        if kind=='boundary':r=1800.
        if kind=='cluster':r=70*np.sqrt(rng.random())
        x,y=r*np.cos(a),r*np.sin(a)
        orient=float(rng.uniform(0,360)) if question==4 and rng.random()<.5 else None
        if kind in ('boundary','all_directional') and question==4:orient=float(np.degrees(a)%360)
        result.append(dict(channel=int(ch),position=[float(x),float(y)],radius_m=1000. if kind in ('boundary','radius_min') else float(rng.uniform(1000,1500)),orientation_deg=orient))
    return result
