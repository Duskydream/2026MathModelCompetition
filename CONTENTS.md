# 项目内容索引

这份索引用来快速判断每个目录和文件的用途。一般阅读从根目录 `README.md` 开始；复现实验和改代码看 `analysis_b/`；只跑第3、4问演练看 `B题演练程序/`。

## 一眼看懂

| 路径 | 类型 | 用途 |
|---|---|---|
| `README.md` | 总说明 | 项目目标、快速开始、结果范围、复现与打包命令 |
| `Question B/` | 原始题目材料 | B题PDF、两份附件和格式规范，建议保持原样 |
| `analysis_b/` | 研究源码与结果 | 建模、仿真、优化、HTTP演练客户端、报告生成和测试 |
| `B题演练程序/` | 可分发演练包 | 从 `analysis_b/` 打包出的独立运行副本，给演练时直接使用 |
| `*.md` 根目录文档 | 阶段性说明 | 模型表述、算法说明、实验摘要和当前方案审查 |

## 推荐阅读顺序

1. `README.md`：先确认项目做了什么，以及哪些结论只来自本地合成环境。
2. `analysis_b/审题与基准模型报告.md`：看题意拆解、建模假设、几何推导和基准方案。
3. `analysis_b/优化试验报告.md`：看优化策略、配对实验、验证结果和退步案例。
4. `analysis_b/REPRODUCTION.md`：需要复现实验、跑测试或打包演练程序时阅读。

## 主要代码

| 文件 | 说明 |
|---|---|
| `analysis_b/model.py` | 基准几何、测向定位、搜索与清除策略 |
| `analysis_b/optimized.py` | 优化后的路线、第二测站选择和多目标共用测站策略 |
| `analysis_b/simulator.py` | 本地合成仿真环境；策略代码不读取隐藏真值 |
| `analysis_b/experiments.py` | 基准试验、稳健性/敏感性试验和图表生成 |
| `analysis_b/optimize_experiments.py` | 优化方案的开发、留出和压力测试 |
| `analysis_b/practice_robot.py` | 官方HTTP接口的串行演练客户端 |
| `analysis_b/practice_q3.py`、`analysis_b/practice_q4.py` | 第3、4问演练入口 |
| `analysis_b/http_robot.py` | 旧版/阶段性HTTP适配器说明与测试对象 |
| `analysis_b/package_practice.py` | 生成 `B题演练程序/` 和压缩包；这是唯一打包入口 |
| `analysis_b/REPRODUCTION.md` | 研究代码文件清单、复现命令和官方演练提醒 |

## 结果与证据文件

| 路径 | 内容 |
|---|---|
| `analysis_b/results/` | 基准方案的逐例CSV、汇总JSON、几何验证、基准对比图和合成日志 |
| `analysis_b/optimization_results/` | 优化方案的开发集、留出集、压力测试、回归案例和留出集对比图 |
| `analysis_b/source_extract/manifest.json` | 原始题目文件的哈希与结构清单 |
| `analysis_b/practice_validation.json` | 演练客户端相关验证摘要 |

这些结果主要来自本地合成环境，不能直接当作官方成绩。官方模拟器导出的加密日志、真实队号日志和正式测试结果应单独保存，不要公开提交。

## 演练包说明

`B题演练程序/` 是给使用者直接运行的生成副本，不再纳入源码仓库。运行 `python analysis_b/package_practice.py` 后会生成：

| 文件 | 用途 |
|---|---|
| `启动第3问演练.cmd`、`启动第4问演练.cmd` | Windows双击启动入口 |
| `practice_q3.py`、`practice_q4.py` | 命令行启动入口 |
| `practice_robot.py` | 连接模拟器并执行策略 |
| `model.py`、`optimized.py`、`config.json` | 运行所需模型与参数 |
| `requirements.txt` | 最小依赖 |
| `manifest.json` | 打包文件哈希 |

如果改了 `analysis_b/` 中的演练代码，重新运行：

```powershell
python analysis_b/package_practice.py
```

再检查生成目录中的 `使用说明.md` 和 `manifest.json` 是否同步。

## 不建议手动改动或提交的内容

| 内容 | 原因 |
|---|---|
| `Question B/` 原始文件 | 保持题目材料原始、可追溯 |
| `practice_logs/`、`*_actions.jsonl`、`*.jlog` | 可能含队号、请求与真实演练信息，已被 `.gitignore` 排除 |
| `output/`、`analysis_b/pdf_work/` | 内部审阅或可再生成材料，已被 `.gitignore` 排除 |
| `*.zip`、`*.rar` | 可由打包脚本再生成，已被 `.gitignore` 排除 |

## 当前整理建议

- 保持现有目录结构：源码、结果、题目附件和演练包已经按用途分开。
- 同名源码以 `analysis_b/` 为准；`B题演练程序/` 是由打包脚本生成的运行副本。
- 后续新增报告优先放在 `analysis_b/` 或根目录，并在本索引补一行说明。
- 后续新增真实演练日志不要放入 Git；如需汇总成绩，建议另建脱敏摘要文件。
