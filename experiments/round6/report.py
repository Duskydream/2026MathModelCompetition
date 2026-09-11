"""Generate the Q4 optimization report from verified paired experiment outputs."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NAMES={'random':'普通随机','boundary':'边界向外定向','radius_min':'最小接收半径',
       'all_directional':'全部定向且朝外','cluster':'圆心附近聚集'}


def read(label):
    return json.loads((HERE/(label+'_summary.json')).read_text(encoding='utf-8'))


def main():
    data=read('holdout');summary=data['summary'];metadata=data['metadata']
    old_config=json.loads((HERE/'baseline/config.json').read_text(encoding='utf-8'))
    random=summary['random'];base=random['baseline'];candidate=random['selected']
    gain=base['mean']-candidate['mean'];paired=candidate['paired']
    lines=[
        '# Q4 第六轮：减少无效检测，调整等待与补测',
        '',
        '日期：2026-09-11。全部数值来自本地合成模拟器，不是官方演练成绩。',
        '',
        '## 1. 独立验证结论',
        '',
        f"100 个新随机案例，平均耗时从 **{base['mean']:.2f} 降到 {candidate['mean']:.2f} 秒/源**，减少 **{gain:.2f} 秒/源（{100*gain/base['mean']:.2f}%）**。",
        '',
        f"随机组有 {paired['faster']} 例变快、{paired['slower']} 例变慢；配对变化的 95% bootstrap 区间为 [{paired['ci95'][0]:.2f}, {paired['ci95'][1]:.2f}] 秒/源。变化按候选减基线计算，负值表示更快。该区间反映这个合成分布下的平均收益，不保证每局都变快。",
        '',
        '| 场景 | 案例 | 原版均值 | 优化均值 | 变化 | 原版 / 优化 P95 | 每版清除源数 |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for kind,name in NAMES.items():
        b=summary[kind]['baseline'];c=summary[kind]['selected']
        lines.append(f"| {name} | {c['cases']} | {b['mean']:.2f} | {c['mean']:.2f} | {c['mean']-b['mean']:+.2f} | {b['p95']:.2f} / {c['p95']:.2f} | {c['cleared']}/{c['sources']} |")
    total=sum(summary[k]['selected']['sources'] for k in NAMES)
    worst=max(((v['selected']['paired']['worst_delta'],k,v['selected']['paired']['worst_seed']) for k,v in summary.items()))
    lines += ['',f'共 220 个案例、{total} 个源，两版均全部清除。最严重单例退步发生在{NAMES[worst[1]]}场景，种子 `{worst[2]}`，增加 {worst[0]:.2f} 秒/源。',
              '',f"普通随机组低于 500 秒/源的案例从 {base['below500']}/100 变为 {candidate['below500']}/100。",
              '', '## 2. 实际改了什么', '',
              '1. 未发现频道仍在所有巡站检测。对已发现频道，跳过已能保证清除、明显不在附近，或与旧测点过于重复的检测。多边形距离是候选筛选条件，不代表保证能收到信号。',
              '2. 范围较大的目标可等待后续巡站提供观测；等待受首次发现位置、剩余巡站和离首测站距离限制。外环首次发现的目标不采用这种等待，避免后续站全部位于天线背面时的大幅折返。',
              '3. 当位置范围的包围圆处于设定的补测区间，先到圆心补测；仍未达到清除精度时，沿新方向的垂线最多再偏移 60 米补测一次。遇到无信号，或补测后仍不够准确，继续原光学网格清除。',
              '4. 保留清除前后的额外共享扫描。开发实验中，保留它比关闭它在随机和最小接收半径场景表现更好；因此本版没有直接删除这部分扫描，也没有修改第三问共用的扫描实现。',
              '', '25 站位置、连续域覆盖证书、有界测向误差区域与完整光学清除兜底保持原规则。算法仅使用已经收到的反馈与已知配置。',
              '', '最终新增参数：', '', '```json',
              json.dumps({k:v for k,v in metadata['cfg'].items()
                          if k.startswith('q4_') and old_config.get(k)!=v},ensure_ascii=False,indent=2),
              '```', '', '## 3. 时间节省来自哪里', '',
              '下表按 100 个随机案例逐局计算每源耗时，再对案例取平均。', '',
              '| 时间项 | 原版 | 优化 | 变化 |','|---|---:|---:|---:|']
    for key,name in [('move','移动'),('measure','检测'),('switch','切频'),('optical','每次清除尝试的基础耗时'),('laser','成功清除的追加耗时')]:
        b=base['parts'][key];c=candidate['parts'][key]
        lines.append(f'| {name} | {b:.2f} | {c:.2f} | {c-b:+.2f} |')
    lines += ['', '模拟器把每次清除的 3 秒计入基础耗时，成功时再追加 2 秒。因此基础清除耗时包含成功尝试，不能全部标成“光学失败时间”。',
              '',f"随机组失败清除次数由 {base['failures_per_source']:.2f} 降到 {candidate['failures_per_source']:.2f} 次/源。",
              '', '## 4. 对原报告的复核与开发比较', '',
              '使用原报告的 60 个随机种子重跑后，复现了 P3 约 36 秒/源的收益。但同一组种子下的边界向外定向压力实验出现明显退步，不能沿用“压力集一致改善”的表述。',
              '', '第一阶段逐项去掉改动，以及恢复共享扫描，得到下列变化。负值表示比第 4 轮基线更快，单位秒/源。所有变体用相同场景配对；它们属于开发结果。', '',
              '| 变体 | 随机 | 边界向外 | 最小半径 | 全部定向 | 聚集 |',
              '|---|---:|---:|---:|---:|---:|']
    dev=read('development')['summary']
    variants={'selected':'P3 多边形距离版','center_gate':'P3 原型圆心距离版','no_wait':'去掉等待',
              'no_selective':'去掉选择性重测','no_refine':'去掉圆心补测','shared':'恢复额外共享扫描'}
    for variant,name in variants.items():
        values=[dev[k][variant]['paired']['mean_delta'] for k in NAMES]
        lines.append('| '+name+' | '+' | '.join(f'{v:+.2f}' for v in values)+' |')
    lines += ['', '随后收紧等待条件并比较补测范围。下面仍是开发成绩，最终参数在独立验证前固定。', '',
              '| 变体 | 随机 | 边界向外 | 最小半径 | 全部定向 | 聚集 |',
              '|---|---:|---:|---:|---:|---:|']
    dev=read('development_wait')['summary']
    labels={'selected':'外环不等待，关闭额外共享扫描',
            'shared':'外环不等待，保留额外共享扫描（最终选定）',
            'inner_refine200':'外环不等待，补测上限200米',
            'inner_refine300':'外环不等待，补测上限300米',
            'same_side_wait':'按圆心判断观测同侧',
            'all_sides_wait':'所有区域顶点均要求观测同侧'}
    for variant in sorted(v for v in dev['random'] if v!='baseline'):
        values=[dev[k][variant]['paired']['mean_delta'] for k in NAMES]
        lines.append('| '+labels[variant]+' | '+' | '.join(f'{v:+.2f}' for v in values)+' |')
    lines += ['', '最终选定第二阶段的 shared 变体：开发随机均值由 559.03 降到 518.58 秒/源，减少 40.45 秒/源。后续验证将它固定为 selected。各阶段的代码和配置均已快照，不能拿当前默认值直接重跑旧阶段的同名变体并期待完全相同结果。',
              '', '选择依据是随机集约40秒的收益及四类压力场景均值均未退步；补测上限放宽至200、300米会损害边界表现，未采用。独立验证随后给出较小的34.06秒平均收益及两类压力场景的小幅退步，未据此再次调参。']
    lines += ['', '## 5. 误差与参数敏感性', '',
              '以下集合与开发、独立验证种子分开。参数变化不用于回调已经验证的默认值。', '',
              '| 试验 | 随机平均变化 | 最差场景平均变化 | 全部清除 |',
              '|---|---:|---:|---:|']
    for label in ['sensitivity','constant_positive','constant_negative','smooth_noise']:
        result=read(label)['summary']
        for variant in sorted(v for v in result['random'] if v!='baseline'):
            worst_mean=max(result[k][variant]['paired']['mean_delta'] for k in NAMES)
            count=sum(result[k][variant]['sources'] for k in NAMES)
            cleared=sum(result[k][variant]['cleared'] for k in NAMES)
            lines.append(f"| {label}: {variant} | {result['random'][variant]['paired']['mean_delta']:+.2f} | {worst_mean:+.2f} | {cleared}/{count} |")
    lines += ['', '固定正负 1 度及平滑误差均保持同一位置、同一频道读数固定。额外误差试验中，全部定向组采用每个源独立随机的朝向；同一批位置用于误差比较，不能把它们算成额外独立位置样本。',
              '', '## 6. 正确性、局限和复现', '',
              '实验逐动作核查频道和坐标、耗时累加、成功清除距离、定位证书包含真源、全部清除及终止状态。核查程序可以读取本地生成的真值；策略不读取真值。',
              '', '新增测试覆盖无信号时保留位置区域并退回光学搜索、最多两次补测、未发现频道始终检测、等待有界、外环目标不等待，以及关闭所有新增优化后与原版逐动作一致。全量测试结果见交付记录。',
              '', '等待和补测门槛仍是启发式决策，个别案例会变慢。合成场景不代表官方生成分布；本轮未连接官方模拟器，也没有用真实演练日志调参。官方三局演练仍待实际界面与接口就绪后完成。',
              '', '原报告的“巡站路线约 18.2 公里”是一个路线估计，不是已证明的最短路线下界。检测次数也会随清除顺序改变，因此不能据此严格推出 450 秒下界或 400 秒不可能。本轮只评价固定布局内的实际优化结果。',
              '', f"基线提交：`{metadata['baseline']['commit']}`；完整代码及哈希保存在 `experiments/round6/baseline/`。最终配置、代码哈希、软件版本、种子和逐组统计见 `experiments/round6/holdout_summary.json`。",
              '', '开发集：随机 60 例及每类压力 30 例，种子从 2026095100 起。独立验证从 2026101000 起，各场景偏移 200；敏感性从 2026103000 起，各场景偏移 200。完整集合见运行脚本。Bootstrap 种子 2026091106，按整局重采样 10000 次。',
              '', '原始合成动作、源场景、逐例结果和各次代码快照放在被 Git 忽略的 `.local_archive/q4_round6/`。本轮没有上传任何日志或 PDF，也没有推送 GitHub。',
              '', '在仓库根目录运行：', '', '```powershell',
              'python -B -m unittest discover -s analysis_b -p "test_*.py" -v',
              'python -B experiments/round6/run.py --suite holdout --variants baseline selected --label repeat_holdout',
              'python -B experiments/round6/run.py --suite sensitivity --variants baseline selected refine100 refine200 wait1000 wait1800 --label repeat_sensitivity',
              'python -B experiments/round6/run.py --suite sensitivity --variants baseline selected --noise constant --amplitude 1 --random-orientations --label repeat_constant_positive',
              'python -B experiments/round6/run.py --suite sensitivity --variants baseline selected --noise constant --amplitude -1 --random-orientations --label repeat_constant_negative',
              'python -B experiments/round6/run.py --suite sensitivity --variants baseline selected --noise smooth --random-orientations --label repeat_smooth_noise',
              'python -B experiments/round6/report.py',
              '```', '', '运行器拒绝覆盖同名本地结果目录；再次执行时使用新的 `--label`。报告生成器读取本轮原始标签对应的统计文件，重跑的新标签不会自动替换报告依据。',
              '', '恢复第 4 轮 25 站策略时，保留 `q4_policy: mixed_ring`，设置以下四项；`q4_policy: legacy` 是更早的 27 站版，不是本次基线：', '',
              '```json',json.dumps(dict(q4_selective_remeasure=False,q4_wait_for_survey=False,q4_refine_max_m=0,q4_shared_scan=True),indent=2),'```','']
    path=ROOT/'docs/experiment6_report.md'
    path.write_text('\n'.join(lines),encoding='utf-8')
    print(path)


if __name__=='__main__':main()
