# MathModelGPT · B题建模与演练

无线电干扰源自动定位与清除的数学建模研究，包括第1、2问的几何方法，第3、4问的搜索策略、配对试验、演练客户端与解释报告。

目前推荐的候选策略是：覆盖搜索、目标顺序调整、第二测站左右选择、多目标共用测站，以及光学分格清除兜底。所有性能结论注明数据来源，保留失败和退步案例。

## 快速开始

使用 Python 3.10 或更新版本，在仓库根目录运行：

```bash
python -m pip install -r analysis_b/requirements.txt
python analysis_b/practice_q3.py
# 第4问
python analysis_b/practice_q4.py
```

运行前先登录官方模拟器，选择对应的**演练测试**并等待接口就绪。交互入口会询问队号和端口。接口无法判断当前是演练还是正式模块，请在模拟器界面选择正确模块。

也可以直接指定参数：

```bash
python analysis_b/practice_robot.py --question 3 --robot-id YOUR_TEAM_ID --connect
python analysis_b/practice_robot.py --question 4 --robot-id YOUR_TEAM_ID --connect
```

默认策略为 `shared`；`--strategy triangulate` 使用原两次测向方案。运行日志保存到 `analysis_b/practice_logs/`，已设置为 Git 忽略。程序不知道真实总数，因此清除比例保持空值，需与模拟器演练结束界面核对。

## 阅读材料

- [项目内容索引](CONTENTS.md)：按目录和文件类型快速查找内容。
- [审题与基准模型报告](analysis_b/审题与基准模型报告.md)：题目事实、假设、几何证明和基准结果。
- [优化试验报告](analysis_b/优化试验报告.md)：改动、配对对照、独立验证和退步案例。
- [研究代码说明](analysis_b/REPRODUCTION.md)：文件清单与复现细节。

背景原理详解 PDF 仅供内部审阅，不纳入公开仓库。

## 结果的适用范围

以下是**本地合成环境**每问100个新增案例的配对结果，不是官方成绩：

| 问题 | 原方案平均秒/源 | 优化版平均秒/源 | 平均下降 |
|---|---:|---:|---:|
| 第3问 | 723.82 | 653.11 | 9.77% |
| 第4问 | 984.83 | 929.75 | 5.59% |

优化版分别在90/100、76/100个案例上更快，全部完成清除。部分案例变慢，完整记录保存在 `analysis_b/optimization_results/`。数据生成分布是建模假设，不代表官方分布。历史报告中的“尚未官方联调”描述的是撰写时的状态；真实演练原始日志在本地保存，不作为公开合成试验混入上述统计。

## 目录

| 路径 | 内容 |
|---|---|
| `Question B/` | 用户提供的题目、两份附件及格式规范 |
| `analysis_b/model.py` | 基准几何、测向定位、搜索与清除策略 |
| `analysis_b/optimized.py` | 已冻结的路线、第二测站选择与共用测站策略 |
| `analysis_b/simulator.py` | 本地模拟环境；策略不读取其隐藏真值 |
| `analysis_b/practice_robot.py` | 串行HTTP演练客户端与错误处理 |
| `analysis_b/results/` | 基准的逐例结果、图表与合成日志 |
| `analysis_b/optimization_results/` | 优化试验、独立验证与压力测试结果 |
| `output/` | 内部审阅材料，仅保存在本地，不纳入公开仓库 |

更完整的文件清单见 [CONTENTS.md](CONTENTS.md)。

## 复现计算

```bash
python analysis_b/experiments.py
python analysis_b/derive_checks.py
python analysis_b/build_report.py
python analysis_b/optimize_experiments.py --phase development
python analysis_b/optimize_experiments.py --phase holdout
python analysis_b/optimize_experiments.py --phase stress
python analysis_b/build_optimization_report.py
```

运行会覆盖对应派生结果；种子与参数随代码和JSON保存，电脑实际运行时间随机器改变。画图脚本目前使用Windows字体路径；在其他系统运行绘图或PDF生成前，需要替换为当地安装的字体。模型和HTTP客户端不依赖字体。

内部 PDF 的生成材料仅保存在本地，不纳入公开仓库；演练和复现计算不依赖这些工具。

## 验证与打包

```bash
python -m unittest discover -s analysis_b -p "test_*.py" -v
python analysis_b/package_practice.py
```

测试只启动临时本机回环HTTP服务，不连接官方模拟器。打包命令生成独立的 `B题演练程序/` 和 ZIP，二者不重复纳入源码仓库。

## 提交前核对

`.gitignore` 已排除真实演练日志、`.jlog`、内部 PDF、缓存、临时页面图和重复压缩包。研究所用的 `.jsonl.gz` 是自行生成的合成试验记录，作为结果证据保留。不要使用 `git add -f` 强行加入被忽略的真实日志或内部审阅材料；普通Git忽略规则不作用于网页手动拖拽上传，网页上传时也需跳过这些本地目录。

本目录已经是 Git 仓库；提交和推送前请再次核对 `git status`，确认没有把真实演练日志、队号信息或内部审阅材料加入版本控制。
