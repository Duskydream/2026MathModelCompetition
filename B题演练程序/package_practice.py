"""Build a standalone practice folder and ZIP without research logs or IDs."""
from pathlib import Path
import hashlib,json,shutil,zipfile

B=Path(__file__).resolve().parent;DEST=B.parent/'B题演练程序';DEST.mkdir(exist_ok=True)
names=['practice_robot.py','practice_launcher.py','practice_q3.py','practice_q4.py','model.py','optimized.py','config.json']
for name in names:shutil.copyfile(B/name,DEST/name)
(DEST/'requirements.txt').write_text('numpy==2.2.6\nscipy==1.15.3\n',encoding='utf-8')
for q in (3,4):
    cmd=f'''@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python practice_q{q}.py
) else (
    py -3 practice_q{q}.py
)
pause
'''
    (DEST/f'启动第{q}问演练.cmd').write_bytes(cmd.replace('\n','\r\n').encode('utf-8'))
readme='''# 第3问和第4问演练程序

默认使用已经验证的优化方案：覆盖搜索、目标顺序调整、左右第二测站选择、多目标共用测站及光学清除兜底。第3问用圆心与六个环形点共7个覆盖站，最坏覆盖距离900米；第4问用49个方向覆盖站。算法仅使用接口反馈，不读取模拟器隐藏数据。将config.json中的q3_survey_layout改为grid可恢复第三问25站对照。

## 一次准备

需要Python 3.10或更新版本。先解压整个文件夹，不要只复制一个脚本。打开该文件夹中的终端，安装依赖：

```powershell
python -m pip install -r requirements.txt
```

如果用Windows的py启动器，请使用 `py -3 -m pip install -r requirements.txt`，确保安装依赖的解释器与运行解释器相同。双击脚本优先使用py -3，否则使用python。如果电脑有多个Python，可直接使用指定解释器运行下面的命令。

## 每次演练

1. 打开官方模拟器并登录。队号在本地输入，不能使用示例队号。
2. 选择“问题3演练测试”或“问题4演练测试”，启动并等待倒计时结束、接口就绪。
3. 双击对应的“启动第3问演练.cmd”或“启动第4问演练.cmd”。输入登录队号和端口（默认2026）。
4. 按提示开始连接，观察终端的已清除数量与虚拟时间。正常完成后程序自动调用 /exit。

注意：协议没有“演练/正式模式”或题号查询接口。程序不能替你确认界面选择是否正确。它会进入当前已经启动的测试，请使用对应演练模块。本包不会启动或选择正式测试，也不能取消已消耗的正式机会。

## 直接用命令运行

在本文件夹终端中执行，替换实际队号：

```powershell
python practice_robot.py --question 3 --robot-id '实际队号' --connect
python practice_robot.py --question 4 --robot-id '实际队号' --connect
```

本机现有环境也可以这样运行：

```powershell
& F:/Python/python.exe practice_q3.py
& F:/Python/python.exe practice_q4.py
```

端口有改动时增加 `--base-url http://127.0.0.1:新端口`。可增加 `--case-code '界面案例编码'` 关联案例；这个值只是人工记录，程序不会声称它已经由服务器验证。不加 --connect 不发送请求。

可选策略：默认 `--strategy shared` 为优化版；`triangulate` 为原两次测向对照；`route` 为只改路线顺序与左右测站选择；`sweep` 为较慢的单次测向基准。正式演练建议先用默认版。

## 日志与结果

每次运行自动在practice_logs下创建独立文件夹，包含：

- actions.jsonl：发送前的原始请求、响应、重试和错误。含队号，不要公开原始文件。
- run_config.json：题号、方案、物理参数、代码SHA-256、Python版本与人工案例编码。
- localization_regions.json：定位区域、圆心、直径与包围圆半径，供定位问题分析。
- summary.json：已清除频道、虚拟总时间、每个已清除源的平均时间、分项时间和完成状态。

`status=completed` 表示策略得到终止证据且成功调用 /exit。`budget_stop` 表示为避免超时提前停止，不能视为完成；`failed` 或 `interrupted` 也不能视为完成。失败情况下平均时间仅是部分进度，不能作为完整任务成绩。

程序不知道真实源总数，因此 `true_source_count` 和 `clearance_ratio` 保持null。演练结束后从模拟器界面读取总数，再按成功清除数/总数计算比例。程序的“全部清除”来自覆盖与终止条件，最终仍应核对官方界面。实际程序耗时包含通信和本地处理，不代替官方显示的运行时间。

这里的自录日志不是模拟器导出的官方加密日志。如果今后进行正式测试，仍需按题目要求导出官方日志，保留原名原内容。

## 超时与网络处理

按 /enter 返回的实际剩余时间控制预算；剩余约8秒时停止发起新的检测或清除，尝试正常退出。发起动作前也检查该动作的最坏虚拟耗时是否超限。

网络超时或响应中断，只重试原封不动的同一请求，默认最多3次，使用相同request_id。不会并发发送不同动作。如果重试仍不能确定动作是否执行，就停下保存日志，不再发送新的清除或 /exit，以避免未确认动作继续改变状态。此时查看模拟器界面；不要重新启动脚本去继续同一局。

若“连接失败”：先核对模拟器是否已启动演练、倒计时是否结束、端口是否相同。若“请求拒绝”：核对队号与登录账号。若定位约束不一致或计时不一致：保留整局日志进行诊断，不要删除异常读数强行继续。Ctrl+C会保存结果；若正好在请求途中中断，执行状态可能不确定。

## 验证范围

此包在本机通过真实回环HTTP端到端测试：第3、4问完整进入、检测、清除与退出，计时与原本地模型一致；同时测试了四种接口执行后丢失响应的幂等重试、短现实预算、虚拟预算、请求拒绝、断线未决保护及结果文件。所用HTTP服务是本地测试服务，不是官方模拟器。

本轮未进行官方演练或正式测试。当前第三问7站方案在新增100个本地配对案例中全部清除，平均虚拟秒/源从654.53降至346.62；另有开发、压力与第四问回归测试。历史840次运行对应修改前的25站版本，不能当作当前代码的实验次数。详见项目docs/experiments_summary.md。
'''
(DEST/'使用说明.md').write_text(readme,encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.iterdir() if p.is_file() and p.name!='manifest.json'}
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(B.parent/'B题演练程序.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in DEST.iterdir():
        if p.is_file():z.write(p,DEST.name+'/'+p.name)
print(DEST)
