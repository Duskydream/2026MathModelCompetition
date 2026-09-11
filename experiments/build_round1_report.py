"""Build first-round Markdown and plots from saved evidence, without rerunning policies."""
import csv
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'experiments/round1';FIG=OUT/'figures';FIG.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'analysis_b'))
from model import initial_polygon,bearing_halfplanes,clip

def csvread(path):
    with path.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))

summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
hold=next(r for r in summary if r['phase']=='holdout')
rows=csvread(ROOT/'experiments/results.csv');coverage=csvread(OUT/'coverage.csv')
geo=json.loads((OUT/'coverage_geometry.json').read_text(encoding='utf-8'))
q2=csvread(OUT/'q2_candidates.csv');regress=csvread(OUT/'regressions.csv')
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})

def savefig(fig,name):
    fig.savefig(FIG/name,bbox_inches='tight');plt.close(fig)

def map_axes(ax,title,lim=3100):
    ax.add_patch(Circle((0,0),1800,fill=False,color='#e87924',lw=1.5,label='Source domain'))
    ax.set(xlim=(-lim,lim),ylim=(-lim,lim),xlabel='x (m)',ylabel='y (m)',title=title);ax.set_aspect('equal');ax.grid(alpha=.15)

fig,axes=plt.subplots(1,3,figsize=(14,4.6),layout='constrained')
for ax,name in zip(axes[:2],['grid','hexagon']):
    p=np.array(geo['q3'][name]['points']);map_axes(ax,'Q3 '+name,3100)
    for v in p:ax.add_patch(Circle(v,1000,fill=False,color='#2563eb',alpha=.15,lw=.7))
    ax.scatter(*p.T,s=15,color='#2563eb');ax.plot(0,0,'o',color='#059669')
    ax.text(.02,.02,'Exact max nearest distance: '+('707.107 m' if name=='grid' else '900 m'),transform=ax.transAxes,fontsize=9)
p=np.array(geo['q4']['points']);map_axes(axes[2],'Q4 unchanged: 49 stations',2500)
axes[2].scatter(*p.T,s=13,color='#2563eb');axes[2].plot([0,600,600,0,0],[0,0,600,600,0],color='#059669',lw=2)
axes[2].text(.02,.02,'Each containing-cell vertex <= 848.528 m',transform=axes[2].transAxes,fontsize=9)
savefig(fig,'coverage.png')

fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
a=np.linspace(-100,1050,500);b=np.linspace(-1050,1050,600);x,y=np.meshgrid(a,b);eps=math.radians(1.005)
safe=(x*x+y*y<=1e6)&(x*x+y*y<=2000*(x*math.cos(eps)-abs(y)*math.sin(eps)))
axes[0].contourf(x,y,safe.astype(int),levels=[.5,1.5],colors=['#dbeafe'])
axes[0].contour(x,y,safe.astype(int),levels=[.5],colors=['#2563eb'],linewidths=.7)
for r in q2:axes[0].plot(float(r['forward_m']),float(r['lateral_m']),'o',color='#e87924',ms=4)
axes[0].plot(650,250,'*',color='#dc2626',ms=12);axes[0].set(title='Q2 sufficient reception region',xlabel='forward a (m)',ylabel='lateral b (m)');axes[0].set_aspect('equal')
scenarios=csvread(OUT/'q2_scenarios.csv')
for aa,bb in [(250,100),(650,250),(750,450)]:
    rr=[r for r in scenarios if int(r['forward_m'])==aa and int(r['lateral_m'])==bb]
    axes[1].scatter([float(r['acute_crossing_angle_deg']) for r in rr],[float(r['diameter_m']) for r in rr],s=10,alpha=.45,label=f'({aa}, {bb})')
axes[1].set(title='Discrete geometry scenarios (not probabilities)',xlabel='Acute crossing angle (deg)',ylabel='Feasible-region diameter (m)');axes[1].legend()
savefig(fig,'q2_candidates.png')

bs=[r for r in rows if r['phase']=='holdout' and r['strategy_version']=='baseline-shared']
cs=[r for r in rows if r['phase']=='holdout' and r['strategy_version']=='candidate-shared']
fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
a=np.array([float(r['average_clear_time']) for r in bs]);b=np.array([float(r['average_clear_time']) for r in cs])
axes[0].scatter(a,b,c=np.where(b>a,'#dc2626','#2563eb'),s=22);axes[0].plot([0,1100],[0,1100],'--',color='gray')
axes[0].set(xlim=(0,1100),ylim=(0,1100),xlabel='Baseline (virtual s/source)',ylabel='7 stations (virtual s/source)',title='100 paired synthetic holdout cases')
bottom=np.zeros(2)
for key,label,color in [('move_s','Movement','#2563eb'),('measure_s','Measure','#14b8a6'),('switch_s','Switch','#94a3b8'),('optical_s','Optical','#f59e0b'),('laser_s','Laser','#ef4444')]:
    vals=[np.mean([float(r[key])/int(r['cleared_count']) for r in rr]) for rr in [bs,cs]]
    axes[1].bar(['Baseline','7 stations'],vals,bottom=bottom,label=label,color=color);bottom+=vals
axes[1].set(ylabel='Mean virtual s/source',title='Time components (same holdout cases)');axes[1].legend(fontsize=8)
savefig(fig,'performance.png')

examples={}
for version in ['baseline','candidate']:
    with gzip.open(OUT/f'{version}_logs.jsonl.gz','rt',encoding='utf-8') as f:
        for r in map(json.loads,f):
            if r['row']['seed'] in [2026091100,2026093100]:examples[version,r['row']['question']]=r
fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
for ax,key in zip(axes,[('baseline',3),('candidate',3),('candidate',4)]):
    r=examples[key];p=np.array([[0,0]]+[a['position'] for a in r['actions']]);s=np.array([v['position'] for v in r['sources']])
    map_axes(ax,f'Q{key[1]} {key[0]} | seed {r["row"]["seed"]}',2700)
    ax.plot(*p.T,color='#2563eb',alpha=.65,lw=.6);ax.scatter(*s.T,s=18,color='#e87924');ax.plot(0,0,'o',color='#059669')
savefig(fig,'sample_paths.png')

r=examples['candidate',3];ch=next(a['channel'] for a in r['actions'] if a['action']=='measure' and a['response']['measure_result']=='direction')
polys=[];poly=None;cfg=json.loads((ROOT/'analysis_b/config.json').read_text(encoding='utf-8'))
for a in r['actions']:
    if a['channel']!=ch:continue
    if a['action']=='clear' and a['response']['clear_result']=='success':break
    if a['action']=='measure' and a['response']['measure_result']=='direction':
        p=np.array(a['position']);deg=a['response']['svd_deg']
        if poly is None:poly=initial_polygon(p,deg,cfg)
        else:A,z=bearing_halfplanes(p,deg,1.005);poly=clip(poly,A,z)
        polys.append(poly.copy())
fig,axes=plt.subplots(1,2,figsize=(10,4.4),layout='constrained')
g=np.array(next(s['position'] for s in r['sources'] if s['channel']==ch))
for ax in axes:
    for i,p in enumerate(polys):ax.fill(*p.T,alpha=.2,label=f'After direction {i+1}');ax.plot(*np.vstack([p,p[0]]).T,lw=.8)
    ax.plot(*g,'*',color='#dc2626',ms=10,label='Source (scoring only)');ax.set_aspect('equal');ax.set(xlabel='x (m)',ylabel='y (m)');ax.legend(fontsize=7)
axes[0].set_title(f'Saved run: feasible-region updates, channel {ch}')
first=polys[0];mid=(first.min(axis=0)+first.max(axis=0))/2
extent=max(np.ptp(first[:,0]),np.ptp(first[:,1]))*.56
axes[0].set(xlim=(mid[0]-extent,mid[0]+extent),ylim=(mid[1]-extent,mid[1]+extent))
last=polys[-1];span=max(np.ptp(last[:,0]),np.ptp(last[:,1]),20)*.7;c=last.mean(axis=0)
axes[1].set(xlim=(c[0]-span,c[0]+span),ylim=(c[1]-span,c[1]+span),title='Final region zoom')
savefig(fig,'localization.png')

table=['| 数据集 | 配对案例 | 旧版秒/源 | 新版秒/源 | 降幅 | 旧/新全清除 |','|---|---:|---:|---:|---:|---|']
names={'development':'第三问开发集','holdout':'第三问独立验证集','stress':'第三问压力集','q4_regression':'第四问回归集'}
for r in summary:table.append(f"| {names[r['phase']]} | {r['cases']} | {r['baseline_mean']:.2f} | {r['candidate_mean']:.2f} | {r['reduction']:.2%} | {r['baseline_cleared']}/{r['baseline_sources']}；{r['candidate_cleared']}/{r['candidate_sources']} |")
table='\n'.join(table)
retreat='\n'.join(f"- {r['case_id']}：{float(r['baseline_s_per_source']):.2f}→{float(r['candidate_s_per_source']):.2f}秒/源，增加{float(r['extra_s_per_source']):.2f}。" for r in regress)
report=f'''# 第一轮实验汇总

结论：KEEP第三问7站搜索。对照为现有shared优化版，不是更早的triangulate。只变搜索点集合，定位、光学兜底、频道、HTTP与第四问保持原策略。本轮完成后停止继续优化。

## 修改前后

{table}

共160对、320次离线运行。每版累计2091个源均清除；第三问每版1964个、第四问每版127个。100个独立验证案例的单局T/清除数再平均，得到654.53→346.62秒/源；不是先合并所有时间再除总源数。平均下降47.04%，98例改善、2例退步。单局总虚拟时间均值8292.90→4466.31秒，降幅与平均秒/源略有不同。

验证集平均移动距离33580.40→18653.61米，平均测量次数243.17→101.66，频道切换222.97→97.51，清除尝试37.28→34.54，失败清除24.20→21.46。主要收益来自搜索路线缩短和尾部扫描减少，不是改变清除判据。

P95为{hold['baseline_p95']:.2f}→{hold['candidate_p95']:.2f}秒/源；配对bootstrap的平均节约95%区间为[{hold['ci_saved_s'][0]:.2f}, {hold['ci_saved_s'][1]:.2f}]秒/源，5000次重采样。该区间仅针对本地生成分布。

## 不利案例

{retreat}

这两例未删除，完整日志和分项计时均保存。当前贪心路线与不同测站观测会改变目标处理顺序及局部误差；7站不是逐例必胜，也不声称最优。

## 正确性证据

- 七站连续域最坏覆盖距离精确为900米，留100米接收余量；421474个空间检查点得到900.0000000000005米，差值为浮点舍入。旧方案精确上界707.107米。
- 第四问49站有闭凸包方向覆盖证明；{geo['q4']['sample_count']}个位置检查最大方向间隙≤180°，反例数0。七站用于第四问会漏掉边界朝外源，已有明确反例，因此禁止套用。
- 每个离线动作重算计时，全部成功清除距离≤20米，多边形与包围圆都含真源，清除数等于真值，虚拟时间在限制内。
- 第四问10个新案例的完整动作序列哈希逐例一致，不只是总时间相同。
- 原版10项测试通过；最终15项通过，涵盖真实回环HTTP、四动作响应丢失重试、拒绝时钟、预算、角度跨界、空/无界/点/线段、三角形反例、七站极值和定向边界。
- 最终Q3回环HTTP固定测试案例10/10，4144.269191虚拟秒、132动作；原25站为8672.846287秒、372动作。Q4仍为12927.693634秒、743动作。此服务是本机临时测试服务，非官方模拟器。

## 覆盖与第二问核查

只走搜索站、不插入定位任务的最近邻几何路线：25站24000米，7站9353.07米。若每站检测全部20频道，检测数500→140；相应无目标纯巡查成本7775→2703.61秒。这里是假想路线成本，不是题设10至16源的实际成绩，不纳入案例均值。

第二问补齐12候选点×189情景的面积、直径、MEC半径与交角。650/250候选的情景最坏面积4201.00平方米、直径230.30米、MEC半径115.15米，移动139.28秒；750/450的相应值2651.49、138.06、69.03和174.93。说明定位尺寸更小可能增加移动成本，尚不能仅据此替换第二测点。

本轮没有参数扫描或多策略追踪实验。环半径来自解析证明，不是调种子；固定第二站和共站阈值的灵敏度仍待后续单独研究。

## 图与数据

![第三问覆盖与第四问保留方案](../experiments/round1/figures/coverage.png)

![第二检测点候选区域与交角](../experiments/round1/figures/q2_candidates.png)

![同案例对照与时间组成](../experiments/round1/figures/performance.png)

![预先固定首个验证案例的路径示例](../experiments/round1/figures/sample_paths.png)

![保存日志重建的可行域收缩](../experiments/round1/figures/localization.png)

案例级总表：`experiments/results.csv`；逐动作日志：`experiments/round1/baseline_logs.jsonl.gz`与`candidate_logs.jsonl.gz`；汇总、退步案例、环境哈希、覆盖验证、Q2逐情景值均在同目录。图由这些保存结果生成。

## 真实演练状态

检查时默认2026端口没有监听；未获得当前演练模式、队号与案例编码，也未发送官方HTTP动作。需要启动一次演练测试，人工核对对应问题的演练模块并提供队号和端口；结束后补录真实源总数。没有伪造官方结果，没有消耗正式测试机会。

## 下一轮建议

Experiment 2建议只研究第四问方向覆盖搜索点与路线：49站依旧保守，可在保持“近距离测站凸包包含任意源”的证明条件下比较三角网格或含区外点的候选。先做连续证明和反例搜索，再与当前版配对；暂不同时修改定位追踪。更小的修复项是near即时clear，可单独成轮，不混入覆盖收益。
'''
(ROOT/'docs/experiments_summary.md').write_text(report,encoding='utf-8')

log=f'''# 实验日志

## Experiment 1

### Hypothesis

把第三问25格点搜索替换成圆心＋六环点，在1000米最坏接收半径下保持严格覆盖，并减少搜索尾部移动和频道扫描时间。

### Change

`analysis_b/model.py:survey_points`新增hexagon选项；`config.json`选择hexagon。旧代码快照先冻结。定位、清除、shared、HTTP和第四问不改。同步独立演练包及打包说明。只验证一个算法假设。

### Baseline

现有shared＋25站；快照与SHA-256保存在round1/baseline和original_manifest.json。原10项测试通过。与新版使用相同Python、NumPy、SciPy及源生成器、空间误差场。

### New Result

{table}

### Difference

独立验证平均秒/源下降47.04%；移动距离均值减少14926.79米；测量均值减少141.51次。98/100改善，2例退步，最大增加24.82秒/源。详见round1/regressions.csv，不删不利结果。

### Correctness

900米连续覆盖证明＋421474点验证；最小包围圆清除与光学兜底不变；320次全部清除且逐动作/几何检查通过；第四问10对完整动作相同；最终15项测试通过。新算法不访问隐藏真值，模拟器和事后验证器才读取真值。

### Decision

KEEP。当前7站版是离线验证后的演练候选，尚无本轮官方联调成绩。原版可将q3_survey_layout恢复grid或从快照恢复。第一轮结束，停止继续添加其他优化。

### Reproducibility

开发种子2026090100至2026090119；冻结验证2026091100至2026091199；压力三类各10例，起点2026092100、2026092200、2026092300；Q4回归2026093100至2026093109。bootstrap种子2026091199。先预注册再执行，不根据这批验证改参数。

每问每版由run_round1.py记录完整配置、代码哈希、版本和所有动作。results.csv的data_source均为local_synthetic，case_id前缀local，不冒充官方案例编码。real_program_time仅为本地策略运行＋校验时间，非官方程序运行时间。

### Official practice

未执行。默认端口检查未发现监听；必须人工启动一次对应演练并核对模式，不能只因端口开放就进入。真实演练的总源数需结束后从界面补录，未知时留空，绝不记成100%。official_results_template.csv仅有列名，等待实际结果。
'''
(ROOT/'docs/experiment_log.md').write_text(log,encoding='utf-8')
with (ROOT/'experiments/official_results_template.csv').open('w',encoding='utf-8-sig',newline='') as f:
    csv.writer(f).writerow(['data_source','case_id','question','true_source_count','cleared_count','clear_ratio','virtual_time','average_clear_time','real_program_time','movement_distance','measure_count','channel_switch_count','clear_attempt_count','failed_clear_count','strategy_version','parameters','notes'])
print('Reports and 5 figures built from saved evidence.')
