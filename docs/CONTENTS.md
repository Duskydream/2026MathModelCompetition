# 项目内容索引

从 [项目说明](README.md) 开始；修改算法看 `analysis_b/`，实际演练运行 `B题演练程序/`。本文中的代码路径均相对于仓库根目录，命令也从仓库根目录执行。

## 目录和版本关系

| 路径 | 用途 |
|---|---|
| `docs/` | 项目说明、建模报告、使用说明和各轮实验报告 |
| `analysis_b/` | 算法源码、本地模拟器、测试、实验及报告生成脚本 |
| `B题演练程序/` | 可独立运行的演练副本，双击启动器实际读取这里的算法和参数 |
| `experiments/round1/` 至 `round4/` | 历史实验的基线、结果和验证证据 |
| `experiments/round6/`、`round7/` | 当前 Q4 优化的冻结基线、实验脚本、种子与汇总结果 |
| `experiments/q4_exploration/`、`q4_geometry/` | 25 站方案的探索与几何验证，保留供追溯 |
| `Question B/` | 原始题目和附件 |
| `dist/` | 自动生成的演练 ZIP，本地保留，不纳入 Git |
| `.local_archive/` | 本地实验明细及未采用方案的历史材料，不纳入 Git |

`analysis_b/` 是算法维护入口，`B题演练程序/` 是交付副本。两处同名算法和配置必须一致。冻结的 `baseline/` 是历史对照，不能随当前源码一起更新；其中的旧文档也保持原样。

`.gitattributes` 固定参与哈希核验的文件换行方式，避免 Git 检出时改变字节。不要对冻结基线或已验证的运行文件批量转换换行；修改运行代码后需重新测试并更新演练包清单。

## 阅读顺序

1. [项目说明](README.md)：运行方式、当前参数、成绩口径和限制。
2. [审题与基准模型](审题与基准模型报告.md)：题目事实、假设与基础推导。
3. [第六轮报告](experiment6_report.md)、[第七轮报告](experiment7_report.md)：当前 Q4 的累计优化、配对结果和退步情况。
4. [演练使用说明](演练使用说明.md)：连接模拟器、日志和异常处理。
5. [第一阶段复现说明](REPRODUCTION.md)、[早期优化试验](优化试验报告.md)：按历史版本理解，不能把旧成绩当作当前算法成绩。

## 主要代码

| 文件 | 作用 |
|---|---|
| `analysis_b/model.py` | 基础几何、测向定位和基准策略 |
| `analysis_b/optimized.py` | 优化策略入口，分派 Q3/Q4 调度 |
| `analysis_b/q3_policy.py` | Q3 联合搜索与目标调度 |
| `analysis_b/q4_policy.py` | Q4 的 25 站巡查、选择性重测、等待和补测 |
| `analysis_b/q4_optical.py` | 带覆盖检查的光学条段规划与成本计算 |
| `analysis_b/simulator.py` | 本地合成模拟器，真值只用于评分和约束验证 |
| `analysis_b/practice_robot.py` | 官方 HTTP 客户端及请求重试 |
| `analysis_b/practice_q3.py`、`practice_q4.py` | 交互式演练入口 |
| `analysis_b/test_*.py` | 几何、策略、通信和回归测试 |
| `analysis_b/package_practice.py` | 唯一打包入口，按明确文件清单复制源码和文档 |

## 修改和打包

在仓库根目录执行：

```powershell
python -B -m unittest discover -s analysis_b -p "test_*.py" -v
python -B analysis_b/package_practice.py
```

打包会同步演练源码，将 `docs/演练使用说明.md` 复制到 `B题演练程序/docs/使用说明.md`，更新文件哈希清单，并生成 `dist/B题演练程序.zip`。不要手动编辑生成的说明副本。

第 6、7 轮的实验命令、固定种子与误差设置见各轮报告。汇总结果在 Git 中；详细合成动作记录写入本地归档，可按保存的命令重新生成。复现历史轮次时使用其冻结基线与对应候选版本，不能直接套用当前参数。

## 本地材料与清理规则

真实演练的 `practice_logs/`、官方 `.jlog`、内部审阅 PDF、缓存和 ZIP 不提交。历史合成验证数据与真实演练记录不同，前者中的必要汇总和冻结基线用于追溯算法。

未采用的第 5 轮、文献试验残留及早期研究笔记已集中到 `.local_archive/legacy_q4/`。其中部分试验缺少完整候选代码，只能作为历史参考，不作为当前可复现的结果依据。真实演练记录仍保留在各自的 `practice_logs/`。

后续新增说明统一放入 `docs/`，生成压缩包放入 `dist/`。实验脚本按轮次归档；只有不再被引用的一次性脚本和可重建缓存才作为临时文件清除。
