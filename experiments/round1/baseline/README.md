# B题第一阶段交付

先阅读[审题与基准模型报告](审题与基准模型报告.md)。这里的全部测试结果来自本地合成环境，官方演练和正式测试尚未进行。

## 复现

在 `F:\Download\MathModelGPT` 下执行以下 PowerShell 命令。计算只依赖 NumPy、SciPy 和 Pillow；本次实际计算环境为 Python 3.10、NumPy 2.2.6、SciPy 1.15.3、Pillow 12.0.0。完整环境见 `results/environment.json`。核心结果由固定种子确定；现实运行时间随机器变化。

```powershell
& F:/Python/python.exe analysis_b/experiments.py
& F:/Python/python.exe analysis_b/derive_checks.py
& F:/Python/python.exe -m unittest discover -s analysis_b -p test_http.py -v
& F:/Python/python.exe analysis_b/build_report.py
```

以上命令覆盖同名派生结果，不改动 `Question B` 原文件，不发送HTTP请求。其他机器可用已安装所需依赖的Python替换绝对解释器路径。第一次完整试验后无需反复运行以选择有利结果。

重新提取输入文本与PDF图片时，使用本机提供的文档依赖：

```powershell
& 'C:/Users/Lxzm/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' analysis_b/extract_sources.py
```

该步骤依赖 pypdf、pypdfium2、lxml。文档文本以UTF-8保存。PDF用PDFium渲染，以避开当前环境缺少PyMuPDF的问题；无须修改原文件或安装其他软件。旧版DOC读取器只承担当前输入文件的文本读取，不是通用DOC排版器。

## 参数和实验设计

参数统一放在 `config.json`。主种子20260910；主试验40例/问，每例两策略；压力种子为主种子＋1000至＋1004；敏感性种子为＋2000至＋2004；bootstrap种子为＋9000。`sweep`是B0，`triangulate`是B1。参数中的1.005°包含0.005°的保守取整余量。压力试验中改变配置的完整副本随每次日志保存。

总共250次本地运行：160次主试验、60次压力测试、30次误差敏感性测试。每次完整源真值、行动和配置已保存；策略不访问这些真值，评分器事后读取。`all_directional`场景仅在第四问令全部源定向；第三问仍然全向。

## 文件清单

| 文件 | 用途 |
|---|---|
| 审题与基准模型报告.md | 审题、假设、公式、证明、计算结果、改进路线 |
| config.json | 物理常量、策略参数和种子 |
| model.py | 半平面交、直径、最小包围圆、搜索与定位策略 |
| simulator.py | 隔离的本地合成环境与生成器 |
| experiments.py | 主试验、稳健性与敏感性试验、逐动作验证、绘图 |
| derive_checks.py | 数据核查、路径与时间上界、耗时分解 |
| http_robot.py | 官方HTTP协议的串行适配器，未官方联调 |
| test_http.py | 无联网客户端单元测试 |
| extract_sources.py | 原文件哈希、DOC/DOCX/PDF文本及PDF页面图 |
| build_report.py | 根据实际结果生成报告并更新代码哈希 |
| source_extract/manifest.json | 四份原文件的哈希和结构清单 |
| results/cases.csv | 160次主试验逐例指标 |
| results/stress_sensitivity.csv | 90次附加试验逐例指标 |
| results/local_runs.jsonl.gz | 250次本地完整日志，压缩JSONL，非官方日志 |
| results/geometry.json | 第一问可实现的三角形反例与退化情况验证 |
| results/second_point_candidates.csv | 第二问12个候选站的189场景比较 |
| results/audit_checks.json | 数据质量、时间上界和模型失配反例 |
| results/summary.json | 主试验汇总及配对bootstrap结果 |
| results/environment.json | 环境、种子、配置与代码SHA-256 |
| results/comparison.png | 直接由逐例表生成的策略比较 |
| results/q1_counterexample.png | 第一问反例几何图 |

## 后续官方演练

当前文件夹不含官方模拟器；下载地址在原附件1第4节。用户在模拟器内登录并选择正确的演练模块、等待接口就绪后，可运行如下命令，其中队号自行替换：

```powershell
& F:/Python/python.exe analysis_b/http_robot.py --question 3 --robot-id '实际队号' --log 'q3_practice_actions.jsonl' --connect
```

第四问将 `--question 3` 改为 `--question 4`。适配器不负责选择演练或正式模块；一旦加`--connect`，会对当前已启动的测试发送`/enter`。不加该参数时不会连接。保存的自录日志含队号，最终匿名支撑材料需使用另行脱敏副本；官方加密日志仍应保留原文件名和原内容。

请先用演练完成真实接口与时钟核验；不能把本地运行数、时间或日志填写为官方结果。题目要求每问三次正式测试及对应导出日志，当前尚未执行这一阶段。
