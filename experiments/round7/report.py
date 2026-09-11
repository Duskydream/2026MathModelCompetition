"""Write the report using computed summaries, with practice logs kept private."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
NAMES={'random':'随机','boundary':'边界向外','radius_min':'最小接收半径',
       'all_directional':'全部向外定向','cluster':'圆心聚集','random_directional':'全部随机定向'}


def main():
    audit=json.loads((ROOT/'.local_archive/q4_round7/audit.json').read_text(encoding='utf-8'))
    data=json.loads((HERE/'holdout_summary.json').read_text(encoding='utf-8'))
    summary=data['summary'];variant=data['metadata']['args']['variants'][-1]
    group=summary['random'];b=group['baseline'];c=group[variant]
    latest=audit['practice']['7ed28a5c8773237fa1667e46ff37eddbfad825986bd58d093fd2f576ab03c87b']
    lines=['# Q4 第七轮：核验提示，降低光学扫描成本', '',
           '全部算法对比来自本地合成模拟器。演练记录只做当前瓶颈诊断，不冒充配对验证；原始记录和队号不写入本报告。', '',
           '## 提示哪些成立', '',
           '**应当关注移动与尾部耗时，这个方向成立。但“可以省掉几个外环站”和“射线失联说明越过目标”在当前模型中不成立。**', '',
           '1. 连续方向覆盖的确可以作为发现证书，但必须按频道使用实际测过的位置。当前25站布局的每一个外环站都有一个独占反例：将源放在该站的径向边界点、天线朝外，其余24站均在背面。本次用12个这样的源逐一运行验证，均只有相应外环站收到信号。未发现频道的额外定位测点不能凭空计入证书。',
           '2. 最近10局都是第25个巡站才完成外环。因此，按当前观测路线增加检查器，不能凭证书提前省下这些外环站。有限采样加一个未经推导的小余量也不是连续覆盖证明；需要按网格单元界定距离和方向在整个单元上的变化。当前外接多边形的切点还可能具有180度临界方向间隔，强行要求严格小于180度会拒绝本来合法的覆盖。',
           '3. 沿准确的源方向前进，到达源之前位于源与首测站连线段上，可以证明持续可见。但测向有误差，沿读数线并不满足这个前提。已运行反例：源在(1000,0)，首测读数1度，沿读数走200米，到(199.970,3.490)后就无信号，此时距源仍有800.038米。对第一次无信号做二分，只能夹住可见半平面的边界，不能据此夹住源。',
           '4. 使用真实位置区域估计清除成本、收到near及时清除值得测试。当前第6轮代码已经没有expected_fail_time函数，不能再把旧版本的包围圆面积公式当成当前实现。',
           '5. 正12边形的边长论证只限制这种外环构造，不能证明一切非环形或自适应布点都已无改进空间。本轮继续保留25站布局。', '',
           '## 最近演练记录说明了什么', '',
           f"识别到第6轮代码哈希对应的 {latest['cases']} 个完整运行记录。平均 {latest['mean']:.2f} 秒/已清除源，样本标准差 {latest['std']:.2f}，P95 {latest['p95']:.2f}，最大 {latest['maximum']:.2f}。记录未填写真实源总数，所以不能从这些文件独立计算真实清除率。", '',
           f"其中移动平均 {latest['per_source_parts']['move']:.2f} 秒/源，检测 {latest['per_source_parts']['measure']:.2f} 秒/源。对已发现频道的检测中，{100*latest['tracked_silent_fraction']:.1f}% 返回无信号，已经不是旧报告中的约70%。最大连续清除尝试段为 {latest['maximum_clear_attempt_streak']} 次，没有证据说明目前每个失联源都要上百次尝试。", '',
           '不同版本记录没有同场景配对，源数量和场景难度也不同，不能据这些小批次直接得出方差变大的因果结论。本轮独立验证同时报告标准差、P95、最慢10%均值以及最严重配对退步。', '',
           '## 实际改造', '',
           '将可能位置多边形沿首测方向切成连续条段，每段再按横向范围划分矩形。每个矩形用中心作为清除点，要求所有角点距中心不超过19.9米，给20米清除半径留0.1米余量。凸性保证矩形内每一点都满足同一距离限制，条段覆盖保证整个多边形均被覆盖。这个证明不依赖天线朝向或能否继续测到信号。', '',
           '比较几种条段宽度及两个扫描方向，并与原25米网格的完整路径成本比较。完整扫描估计成本没有下降时保留原网格。这里保证的是完整扫描成本，不保证首次命中时间或最终整局时间，因此仍要做配对测试。', '',
           '收到near后，在当前巡站立即清除。圆心补测、等待和共享扫描是否保留，由开发集对比选择；不使用无信号二分删除目标位置区域。', '',
           '补测筛选使用一个明确的时间门槛：如果完整光学路线的移动耗时加上每点3秒基础尝试耗时，不超过“走到圆心的耗时 + 测量5秒 + 基础尝试3秒 + 10秒余量”，就跳过这次补测。成功清除追加的2秒在两边相同，不影响比较；测量切频未计入这一乐观比较，10秒是固定启发式余量，不是概率模型或最优性保证。等待规则、150米补测上限和共享扫描沿用第6轮。', '',
           f'独立验证使用固定候选 `{variant}`；其参数和代码快照见统计文件元数据。', '',
           '## 独立配对结果', '',
           '| 场景 | 案例 | 原均值 | 新均值 | 原/新标准差 | 原/新P95 | 原/新最慢10%均值 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for kind in NAMES:
        b0=summary[kind]['baseline'];c0=summary[kind][variant]
        lines.append(f"| {NAMES[kind]} | {c0['cases']} | {b0['mean']:.2f} | {c0['mean']:.2f} | {b0['std']:.2f}/{c0['std']:.2f} | {b0['p95']:.2f}/{c0['p95']:.2f} | {b0['tail_mean']:.2f}/{c0['tail_mean']:.2f} |")
    total=sum(s[variant]['sources'] for s in summary.values());cleared=sum(s[variant]['cleared'] for s in summary.values())
    worst=max((s[variant]['paired']['worst_delta'],k,s[variant]['paired']['worst_seed']) for k,s in summary.items())
    lines += ['',f"共 {sum(s[variant]['cases'] for s in summary.values())} 案例，候选清除 {cleared}/{total} 个源。随机组配对平均变化 {c['paired']['delta']:+.2f} 秒/源，95% bootstrap 区间 [{c['paired']['ci95'][0]:.2f}, {c['paired']['ci95'][1]:.2f}]。", '',
              f"最严重单例退步：{NAMES[worst[1]]}，种子 {worst[2]}，增加 {worst[0]:.2f} 秒/源。平均改善不能写成每局都会改善。", '',
              '| 随机组分项 | 原版 | 候选 | 变化 |','|---|---:|---:|---:|']
    for key,name in [('move','移动'),('measure','测量'),('switch','切频'),('optical','清除尝试基础耗时'),('laser','成功清除追加耗时')]:
        lines.append(f"| {name} | {b['parts'][key]:.2f} | {c['parts'][key]:.2f} | {c['parts'][key]-b['parts'][key]:+.2f} |")
    lines += ['', '## 开发选择记录', '', '| 变体 | 随机变化 | 随机标准差 | 随机P95 | 最差场景均值变化 |',
              '|---|---:|---:|---:|---:|']
    dev=json.loads((HERE/'development_summary.json').read_text())['summary']
    for name,item in dev['random'].items():
        if name=='baseline':continue
        worst_mean=max(g[name]['paired']['delta'] for g in dev.values())
        lines.append(f"| {name} | {item['paired']['delta']:+.2f} | {item['std']:.2f} | {item['p95']:.2f} | {worst_mean:+.2f} |")
    lines += ['', '## 额外误差检查', '',
              '| 误差模式 | 随机平均变化 | 最差场景均值变化 | 清除数 |',
              '|---|---:|---:|---:|']
    for label in ['negative_error','smooth_error']:
        extra=json.loads((HERE/(label+'_summary.json')).read_text())['summary']
        worst_mean=max(g['cost_gate']['paired']['delta'] for g in extra.values())
        n=sum(g['cost_gate']['sources'] for g in extra.values());cleared_n=sum(g['cost_gate']['cleared'] for g in extra.values())
        lines.append(f"| {label} | {extra['random']['cost_gate']['paired']['delta']:+.2f} | {worst_mean:+.2f} | {cleared_n}/{n} |")
    lines += ['', '固定负1度误差下，边界组仍有平均退步。不能声称对所有误差或场景都改善。两种误差测试有意复用同一批位置，源数不能相加当成独立位置样本。',
              '', '## 复现与局限', '',
              '基线冻结在experiments/round7/baseline；原始合成动作、配置、代码快照和逐例数据在.local_archive/q4_round7。公开统计文件不包含真实演练记录。种子、Python/NumPy/SciPy版本和SHA-256均保存在每次运行元数据中。', '',
              '开发集从2026111000起，独立验证从2026114000起，各场景偏移500；随机验证200例，其他五类各50例。Bootstrap种子2026091207，按整局重采样10000次。', '',
              '本轮没有连接官方模拟器。对真实演练分布的收益与方差变化，仍需用明确版本、相同案例或足够独立案例验证。连续光学覆盖只保证有足够时间执行时最终能找到目标，不消除网络中断和现实预算限制。', '',
              '```powershell',
              'python -B -m unittest discover -s analysis_b -p "test_*.py" -v',
              f'python -B experiments/round7/run.py --suite holdout --variants baseline {variant} --label repeat_holdout',
              'python -B experiments/round7/report.py',
              '```', '', '运行器拒绝覆盖同名结果目录，重跑时指定新的label。旧阶段同名变体按当时快照解释。', '',
              '恢复到你上一轮测试的第6轮版本：把config.json中的q4_strip_cover、q4_immediate_near、q4_scan_cost_gate全部设为false，其他参数保留。', '']
    (ROOT/'docs/experiment7_report.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
