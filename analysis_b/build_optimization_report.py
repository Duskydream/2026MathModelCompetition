"""Generate report and plots without rerunning or selecting favorable cases."""
from pathlib import Path
import csv,json,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont

B=Path(__file__).resolve().parent;O=B/'optimization_results'
summaries={phase:json.loads((O/f'{phase}_summary.json').read_text()) for phase in ['development','holdout','stress']}
for summary in summaries.values():
    for name,digest in summary['code_sha256'].items():
        assert hashlib.sha256((B/name).read_bytes()).hexdigest()==digest,'Evaluated code changed'
params=dict(second_forward_m=650,second_lateral_candidates_m=[-250,250],shared_min_station_separation_m=100,shared_max_estimated_distance_m=1300,shared_min_estimated_crossing_sine=.12,shared_max_extra_measures_per_source=4,shared_stop_positive_bearings=3,finish_without_dedicated_station_after_positive_bearings=2,seed_development_start=20260910,seed_holdout_start=20270910,seed_stress_start=20280910,bootstrap_seed=20290910)
(O/'optimization_parameters.json').write_text(json.dumps(params,indent=2),encoding='utf-8')
def table(phase):
    lines=['|题型|方案|案例数|平均秒/源|P95秒/源|相对B1降幅|清除比例|','|---|---|---:|---:|---:|---:|---:|']
    for r in summaries[phase]['results']:
        lines.append(f"|问题{r['question']}|{r['variant']}|{r['cases']}|{r['mean_s']:.2f}|{r['p95_s']:.2f}|{r['reduction']:.2%}|{r['cleared']/r['sources']:.0%}|")
    return '\n'.join(lines)

holdout=list(csv.DictReader((O/'holdout.csv').open(encoding='utf-8-sig')))
baseline={(r['seed'],r['question']):r for r in holdout if r['variant']=='B1'}
regressions=[]
for r in holdout:
    if r['variant']!='shared':continue
    b=baseline[(r['seed'],r['question'])];delta=float(r['seconds_per_source'])-float(b['seconds_per_source'])
    if delta>1e-8:
        regressions.append(dict(seed=r['seed'],question=r['question'],n_sources=r['sources'],extra_seconds_per_source=delta,**{f'delta_{k}':float(r[k])-float(b[k]) for k in ['move_s','measure_s','switch_s','optical_s']}))
regressions.sort(key=lambda r:r['extra_seconds_per_source'],reverse=True)
with (O/'holdout_regressions.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(regressions[0]));w.writeheader();w.writerows(regressions)
ci='\n'.join(f"- 问题{r['question']}：100例中{r['improved_cases']}例改善；平均节约的配对bootstrap 95%区间为[{r['ci_saved_s'][0]:.2f}, {r['ci_saved_s'][1]:.2f}]秒/源。" for r in summaries['holdout']['results'] if r['variant']=='shared')
worst=regressions[0]
report=f'''# 第三四问优化试验报告

本轮推荐把路线排序与多目标共用测站的组合版 shared 作为下一阶段候选。原有案例和独立新增案例均观察到平均耗时下降；全清除和可行域检查通过，但部分第四问实例变慢，尚不能声称逐例更优或全局最优。全部结果来自本地合成环境，不是官方演练成绩。

## 改了什么

保留25站的第三问覆盖、49站的第四问方向覆盖、20米最小包围圆清除条件、25米光学方格兜底及原终止判据。

1. route 版：本站发现多个目标后，按狗到该目标下一行动点的距离动态选择处理顺序。第二测站允许在原前进650米、侧移250米位置的左右镜像中选择离狗更近的一侧。这个消融同时包含顺序与左右侧选择，不能把全部收益归因于排序单一因素。
2. shared 版：在选中目标的第二测站，以及完成一个目标清除的位置，顺便测量其他待处理频道。如果它们也可见，就把新读数加入各自的多边形，从而共用一次移动。只有满足最小站间距100米、估计距离不超过1300米、估计交角正弦≥0.12的频道才尝试。每源额外尝试最多4次，收集到3次有效方位后不再附带检测。
3. 对已由共享测站获得两次有效方位的目标，直接使用已有交集清除，不再机械地去专属第二站；半径未达20米时仍执行原光学覆盖。near在对应位置直接清除。无信号不删除位置，不用于虚构方向或距离。

交角和距离门槛仅是节省检测的启发式，并非真实位置或接收保证；它们由当前多边形包围圆中心估算。实际接收与否由反馈决定，所有保证来自保持真源的多边形与完整覆盖。算法没有读取源真值。

## 原有案例上的消融比较

每问40个原有案例，三个版本配对，共240次运行。B1的重新计算值与上一轮完全相同。

{table('development')}

路线改动已经带来主要收益，共用测站继续改善。这一版实现与参数在独立验证前冻结，没有根据后续测试结果再调参。

## 独立新增案例

新增种子20270910至20271009，每问100例，B1与shared配对，共400次运行。两问每个方案各清除1310个源。以下比较发生在同一批新案例内，不能把这里的653.11直接与旧案例的764.71相比计算降幅。

{table('holdout')}

{ci}

bootstrap按案例进行5000次重采样，种子20290910。这些区间只描述本地生成分布；当前独立集使用新的种子但仍是相同生成分布，不等于对官方未知分布的验证。

优化版在新增案例中第三问的平均移动时间从600.65下降到528.09秒/源，第四问从741.82下降到685.61秒/源。与平均总耗时降低70.70及55.08秒/源相对应，主要收益确实来自减少移动。

## 压力试验

每问5类各10个案例：边界且最小接收半径、中心聚簇、最小接收半径、第四问全体定向朝外、光滑空间相关误差。每个案例跑两个方案，共200次运行。第三问的all_directional标签不改变全向源类型，仅复用场景标签。相同种子在多个压力类型中复用，因此汇总置信区间不能当作完全独立案例的严格统计推断；此处以覆盖条件检查和分类比较为主。

{table('stress')}

## 哪些情况会退步

独立集第三问10例、第四问24例shared变慢。最严重的是第四问种子{worst['seed']}，{worst['n_sources']}个源，比B1增加{worst['extra_seconds_per_source']:.2f}秒/源。逐项增加：移动{worst['delta_move_s']:.2f}秒、检测{worst['delta_measure_s']:.2f}秒、切换{worst['delta_switch_s']:.2f}秒、光学尝试{worst['delta_optical_s']:.2f}秒，均为该局总增量。

这不是仅多做几次附带检测造成的。侧移与处理顺序改变了后续轨迹及观测位置，移动和光学兜底共同增加。局部最近邻没有考虑后续搜索路线，且“已有两次方位就清除”并不总比追加一次测向省时。所有退步案例保存在holdout_regressions.csv，完整行动轨迹在对应日志中。未剔除不利结果，也未在同一验证集继续调参。

第四问P95仅由1251.31降至1243.69秒/源，尾部收益比平均值改善小。压力试验中优化版的最大单局耗时也可能高于B1，不能仅凭均值宣称最坏情况改善。

## 正确性与限制

本轮共840次运行，其中优化方案460次、基准380次。所有清除数等于真值；源真值仅用于事后评分；每条动作重新计算时钟；所有清除成功距离≤20米；全部保存多边形与包围圆包含真源；全部运行在虚拟时间限制内。

额外测向只将多边形与有效楔形相交，不扩大位置范围；无信号不删真源；蛇形光学覆盖不变。新测站左右镜像满足原全向接收证明。额外检测均在已到达的位置，不产生额外移动，每源最多4次，因此原默认虚拟时间保守上界178152秒可加16×4×6=384秒，得到178536秒，仍小于360000秒。这是宽松上界，不是性能预测，也不是现实HTTP期限保证。

有限案例全清除不能代替数学证明，证明仍依赖静止源、闭180°覆盖、有界误差及确定性光学阈值。新增100例/问并不大，官方分布未知。现有HTTP客户端仍默认B1；本轮没有启动官方模拟器或消耗正式测试机会。

## 后续优先改进

建议保留shared作为候选，下一轮重点比较“追加测向”与“直接光学覆盖”的剩余时间，再把处理目标后的落点和下一测站纳入两步路线评分。第四问尤其需要减少失联后的长光学兜底。随后再做未发现频道的区域排除证书，减少尾段全域巡查。每次改动都应使用新的独立种子，并保留当前冻结版本作对照。

## 复现与文件

在项目根目录执行：

```powershell
& F:/Python/python.exe analysis_b/optimize_experiments.py --phase development
& F:/Python/python.exe analysis_b/optimize_experiments.py --phase holdout
& F:/Python/python.exe analysis_b/optimize_experiments.py --phase stress
& F:/Python/python.exe analysis_b/build_optimization_report.py
```

optimized.py为优化策略；optimize_experiments.py为配对试验；optimization_results下的三个CSV保存逐例数据，三个JSONL.GZ保存真值、行动和可行域。各summary.json保存配置、Python版本和被运行代码的SHA-256。optimization_parameters.json列出冻结的启发式常量，实际执行定义在optimized.py中。策略代码仍使用先前requirements.txt中的依赖。

holdout_comparison.png直接由独立集汇总绘制。原始题目事实和假设来源沿用审题与基准模型报告引用的题目及两份附件，未新增外部数据或文献。
'''
(B.parent/'docs').mkdir(exist_ok=True)
(B.parent/'docs/优化试验报告.md').write_text(report,encoding='utf-8')
im=Image.new('RGB',(1150,600),'white');draw=ImageDraw.Draw(im);font=lambda n:ImageFont.truetype('C:/Windows/Fonts/arial.ttf',n)
draw.text((30,20),'Frozen policy | 100 new paired cases per question',font=font(28),fill='#192b43')
draw.text((30,65),'Local synthetic tests. Mean virtual seconds per source.',font=font(23),fill='#475569')
for i,r in enumerate(summaries['holdout']['results']):
    y=145+i*100;draw.text((30,y),f"Q{r['question']}  {r['variant']}",font=font(24),fill='#192b43')
    width=r['mean_s']*.75;draw.rectangle((220,y,220+width,y+50),fill='#94a3b8' if r['variant']=='B1' else '#2563eb')
    draw.text((230+width,y+10),f"{r['mean_s']:.2f}",font=font(23),fill='#192b43')
draw.text((30,555),'All sources cleared in every run. Not official simulator results.',font=font(22),fill='#475569');im.save(O/'holdout_comparison.png')
print('Frozen evaluation hashes verified; report and plots generated.')
