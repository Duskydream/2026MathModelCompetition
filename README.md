# MathModelCompetition · B题建模与演练

无线电干扰源定位与清除的数学建模项目，包含第1、2问几何分析，第3、4问算法、演练客户端与本地配对实验。算法只使用接口观测，不读取模拟器隐藏源位置。

## 快速开始

实际使用入口位于 **B题演练程序/**。需要 Python 3.10 或更新版本，在仓库根目录安装依赖：

```powershell
python -m pip install -r "B题演练程序/requirements.txt"
```

1. 在模拟器中登录，选择相应的演练测试，启动并等待接口就绪。
2. 双击 [启动第3问演练.cmd](B题演练程序/启动第3问演练.cmd) 或 [启动第4问演练.cmd](B题演练程序/启动第4问演练.cmd)。
3. 输入队号、端口（默认2026）和连续测试次数（1–100）。
4. 按提示逐局启动模拟器演练并确认接口就绪；不需要每次重新打开CMD。当前启动器不会自动点击模拟器或自动创建下一局。

也可从仓库根目录运行交互入口：

```powershell
python "B题演练程序/practice_q3.py"
python "B题演练程序/practice_q4.py"
```

直接指定参数时，可记录界面显示的案例编码：

```powershell
python "B题演练程序/practice_robot.py" --question 3 --robot-id YOUR_TEAM_ID --case-code YOUR_CASE_CODE --connect
python "B题演练程序/practice_robot.py" --question 4 --robot-id YOUR_TEAM_ID --case-code YOUR_CASE_CODE --connect
```

端口变化时增加 `--base-url http://127.0.0.1:端口`。没有 `--connect` 不会发送请求。接口无法识别当前是演练还是正式模式，也无法查询界面题号，请在连接前核对模拟器选择。

## 当前默认算法

| 项目 | 问题3 | 问题4 |
|---|---|---|
| 默认策略 | `shared`，启用Q3混合调度 | `shared`，启用Q4混合调度 |
| 搜索布局 | 圆心加六环点，共7站 | 圆心加内外双12环，共25站 |
| 关键配置 | 环半径1150米；第二测点前向200米、侧向100米 | 内环999米，外环1800/cos(15°)米；第二测点200/100米 |
| 定位 | 混合安排搜索站与已发现目标；利用目标圆和历史无信号约束保守缩小区域 | 保留目标轨迹，联合安排搜索和定位；仅用目标圆与正测向约束 |
| 清除 | 包围圆认证；区域较大时用25米网格光学搜索兜底 | 同样保留认证和完整光学兜底 |

问题3的策略实现位于 [q3_policy.py](B题演练程序/q3_policy.py)，由 [optimized.py](B题演练程序/optimized.py) 接入。问题3专用的无信号距离约束不会用于定向发射的第四问。

第四问新方案见 [第四轮报告](docs/experiment4_report.md)：100个独立随机案例平均792.16→566.30秒/源，P95为712.57秒，另有60个压力案例，均全部清除。尚未达到稳定500秒/源。设置 `q4_policy=legacy` 可恢复main的27站算法。

在目标圆半径1800米、最小接收半径1000米的条件下，问题3当前搜索布局的连续域最坏覆盖距离为988.5114米。它仍保留全部搜索站和清除兜底；仅在已清除题设上限16个源时提前结束。参数不满足覆盖条件时程序拒绝运行。

问题4需要保留目标圆外的部分搜索站，不能把27站简单裁剪到圆内，否则会破坏定向覆盖。几何证明和配对结果见 [Experiment 2报告](docs/experiment2_report.md)。

演练目录与 `analysis_b/` 中的 `model.py`、`optimized.py`、`q3_policy.py`、`config.json`、`practice_robot.py` 保持同步。实际双击入口读取演练目录中的文件；仅修改研究副本不会自动影响双击入口。

## 当前本地验证结果

以下均为本地合成模拟器结果，**不是官方演练成绩**。平均秒/源采用“各案例总虚拟时间÷该案例真实源数，再对案例取平均”的口径。配对的两版均清除了表中全部源。

| 实验 | 案例数 | 对照平均秒/源 | 当前候选平均秒/源 | 下降 | 每版清除源数 |
|---|---:|---:|---:|---:|---:|
| Q3新验证集 | 100 | 343.73 | 263.86 | 23.24% | 1315/1315 |
| Q3压力集 | 70 | 336.31 | 281.83 | 16.20% | 890/890 |
| Q4三角网格验证集 | 100 | 928.46 | 767.64 | 17.32% | 1310/1310 |
| Q4三角网格压力集 | 50 | 916.49 | 727.66 | 20.60% | 670/670 |

问题3新验证集100例均比对照快，81例不超过300秒/源；压力集有2例退步，最多增加2.72秒/源。**平均225秒的目标尚未达到**，也不保证每一局都低于300秒。当前问题3修改后，另20个问题4回归案例的完整动作序列与对照逐例一致。

问题4三角网格有5个普通案例和2个压力案例退步，因此上述结果不表示逐例必胜。两问的本地平均数也不能直接替代真实演练测量。

结果证据：

- [问题3汇总](experiments/round3/summary.json)、[逐局配对数据](experiments/round3/paired.csv)、[覆盖检查](experiments/round3/coverage.json)、[退步案例](experiments/round3/regressions.json)。
- [问题4汇总](experiments/round2/summary.json)、[逐局配对数据](experiments/round2/paired.csv)、[几何检查](experiments/round2/geometry.json)。
- 每轮目录中的 `actions.jsonl.gz` 是本地合成实验动作记录，包含生成的源真值和定位证书；不是用户演练日志。
- `experiments/round3/failed_attempt_01/` 保留一次几何证书验证失败及修复原因，不计入通过案例。修复后重新完成了同一验证集。

## 日志与清除率

正常从演练目录启动时，日志写入 `B题演练程序/practice_logs/`，每局一个独立目录。从研究副本启动时，日志写入 `analysis_b/practice_logs/`。

| 文件 | 内容 |
|---|---|
| `actions.jsonl` | 原始请求、响应、重试及错误，可能包含队号 |
| `run_config.json` | 题号、配置、代码SHA-256与人工案例编码 |
| `summary.json` | 完成状态、清除数量、虚拟时间、average与时间分项 |
| `localization_regions.json` | 定位多边形与包围圆证书 |

`status=completed` 表示程序正常完成策略并退出；`budget_stop`、`failed`、`interrupted` 不应作为完整成绩。当前接口不提供真实源总数，`true_source_count` 和 `clearance_ratio` 可能仍为空；请记录界面总源数后核对清除率，不能用成功请求率替代清除率。

**所有层级的 `practice_logs/` 均通过 `.gitignore` 排除，不应提交或推送。** Git忽略规则不影响已经被跟踪的文件，因此提交前还应确认 `git ls-files -- '*practice_logs*'` 没有输出。不要通过 `git add -f` 或网页拖拽上传真实演练日志、队号文件或官方 `.jlog`。

## 目录用途

| 路径 | 用途 |
|---|---|
| `B题演练程序/` | 实际运行目录：CMD入口、客户端、模型、算法与配置 |
| `analysis_b/` | 同步算法副本、本地模拟器、实验与测试脚本 |
| `analysis_b/simulator.py` | 本地合成环境；生成真值仅用于验证 |
| `analysis_b/package_practice.py` | 从研究副本复制必要文件并生成演练ZIP |
| `experiments/round1/` | 历史问题3七站优化及对照证据 |
| `experiments/round2/` | 问题4三角网格、基线快照与配对结果 |
| `experiments/round3/` | 当前问题3混合调度、基线、开发及验证记录 |
| `experiments/round3/development/` | 开发原型归档，不是演练入口 |
| `docs/` | 建模说明、历史审计和实验报告 |
| `Question B/` | 题目与附件 |

历史报告按生成时版本阅读，当前默认参数以两份 `config.json` 为准。本README描述当前交付状态。

## 阅读索引

- [项目内容索引](CONTENTS.md)：目录、源码和结果文件用途。
- [研究复现说明](analysis_b/REPRODUCTION.md)：沿用main分支整理后的文件名。
- [审题与基准模型报告](analysis_b/审题与基准模型报告.md)及[历史优化试验报告](analysis_b/优化试验报告.md)：按报告对应的历史版本阅读。

## 测试与复现

在仓库根目录运行全部测试：

```powershell
python -B -m unittest discover -s analysis_b -p "test_*.py" -v
```

当前27项测试已通过，涵盖几何边界、保守约束、Q3/Q4隔离、通信重试、预算和端到端调用。测试使用本机临时回环HTTP服务，不连接官方模拟器。

运行独立实验：

```powershell
python -B analysis_b/experiment2.py
python -B analysis_b/experiment3.py
```

脚本会拒绝覆盖已有结果，重跑前应自行另存对应轮次的输出。每轮的配置、种子和代码哈希保存在 `specification.json`、`environment.json` 或该轮清单中。

`experiment2.py` 读取当前算法文件。精确复现历史问题4布局试验时，应使用该轮记录的代码版本；在当前问题3算法上直接重跑，不应期待历史问题3回归序列仍不变。`experiment3.py` 从 `round3/baseline/` 加载固定对照，并用当前代码执行候选。

较早的 `experiments.py`、`optimize_experiments.py` 会生成或覆盖历史派生数据；其输出不应混称为当前round2/round3结果。

打包入口为：

```powershell
python analysis_b/package_practice.py
```

它会覆盖演练目录中的对应源码和说明，并生成 `B题演练程序.zip`；先确认两份代码已同步。`q3_policy.py` 必须随算法一起复制。演练源码目录已纳入Git，生成的ZIP、缓存和真实演练日志不纳入。

## 恢复对照配置

仅恢复问题3到本轮优化前的七站算法时，在演练目录 `config.json` 中设置：

```json
{
  "q3_policy": "legacy",
  "q3_survey_layout": "hexagon",
  "q3_ring_radius_m": 1558.8457268119896
}
```

只把 `q3_policy` 改成 `legacy` 而保留1150米环，属于中间对照，不是完整原版。问题4的49站对照使用 `q4_survey_layout: grid`、`q4_grid_m: 600`；当前27站为 `q4_survey_layout: triangular`、`q4_triangle_spacing_m: 950`。修改单问时保留另一问配置。

## 远程协作

本仓库已建立Git，远程为 [Duskydream/MathModelCompetition](https://github.com/Duskydream/MathModelCompetition)。在实际工作分支上提交源码、测试、文档和可公开的合成实验数据，推送前检查暂存区，避免加入真实演练记录或嵌套仓库。
