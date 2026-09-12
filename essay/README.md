# 论文源文件说明

2026 高教社杯全国大学生数学建模竞赛 B 题《无线电干扰源的快速自动定位与清除》参赛论文。

## 目录结构

```
output/
├── main.tex              主文件（摘要、宏定义、参考文献、AI 声明）
├── cumcmthesis.cls       模板类文件（取自 CUMCMThesis-master）
├── cumcm2026.sty         2026 年格式补丁（取自 CUMCMThesis-master）
├── sec/                  正文各章
│   ├── 01_restatement.tex   问题重述
│   ├── 02_assumptions.tex   模型假设与符号说明
│   ├── 03_analysis.tex      问题分析与总体框架
│   ├── 04_q1.tex            问题一：交会定位区域的直径算法与覆盖性判定
│   ├── 05_q2.tex            问题二：第二检测点的选择策略与候选区域
│   ├── 06_q3.tex            问题三：全向源的搜索、定位与清除
│   ├── 07_q4.tex            问题四：混合全向源与定向源
│   ├── 08_results.tex       演练与正式测试结果（含题目表 1）
│   ├── 09_evaluation.tex    检验、灵敏度分析与评价
│   └── 10_appendix.tex      附录：支撑材料清单、参数表、全部源程序
├── code/                 附录中 \lstinputlisting 引用的源程序副本
└── figures/              （待放入）图片文件
```

## 编译

必须用 **xelatex**（模板依赖 ctex/xeCJK）：

```bash
latexmk -xelatex main
# 或
xelatex main && xelatex main   # 连编两次以更新 cleveref 交叉引用
```

需要的宏包：模板自带的之外，另需 `algorithm`、`algpseudocode`（TeX Live / Overleaf 默认自带）。

格式已按 2026 年规范配置：`withoutpreface` 去掉封面与编号页（电子版首页即摘要）、无目录、页边距 2.5 cm、参考文献前放 AI 工具使用声明。

## 提交前必做的三件事

1. **填写正式测试结果**（`sec/08_results.tex`，搜索 `TODO`）
   - 表 `tab:formal3`、`tab:formal4` 各三行，填模拟器界面的测试案例编码，以及
     `practice_logs/<局>/summary.json` 中的 `cleared_count`、`average_per_cleared_s`、`program_elapsed_s`。
   - 填完后删除表格上方的 `\noindent\fbox{...}` 【待填写】提示框。
   - 导出三次正式测试的加密日志（**不要改文件名**）放入支撑材料。

2. **补画 10 张图**（见下表），把图片放入 `figures/`，并把对应的
   `\fbox{\parbox...}` 占位块替换成 `\includegraphics`。

3. **检查匿名性**：正文、附录与支撑材料中不得出现姓名、校名、赛区。
   已确认 `code/practice_robot.py` 中队号是命令行参数，无硬编码。

## 待补图清单

| 编号 | 标签 | 所在章节 | 内容 |
|---|---|---|---|
| 1 | `fig:framework` | 3 问题分析 | 总体求解框架流程图（四层色带 + 主流程 + 定理编号） |
| 2 | `fig:q1-counter` | 4 问题一 | 三站交会得到边长 40 m 正三角形的反例；D/2 圆盖不住、最小包围圆 23.094 m |
| 3 | `fig:q2-region` | 5 问题二 | 保证接收候选区域 $\mathcal C_{\rm safe}$（三圆之交）、极值点、等代价线 |
| 4 | `fig:q3-layout` | 6.2 | 七站布局 + Voronoi + 接收圆并集；右图 $d_{\max}(r)$ 曲线与可行区间 |
| 5 | `fig:q3-shrink` | 6.3 | 可行域四步收缩：初始扇形 → 二次交会 → no_signal 排除 → 认证清除 |
| 6 | `fig:q3-track` | 6.7 | 第三问一局完整轨迹 + 累计时间阶梯图（可并排 25 站旧版对照） |
| 7 | `fig:q4-layout` | 7.4 | 22 站布局 + 巡回路径 + 方向覆盖余量热力图（最小余量点 (−1738,−471)） |
| 8 | `fig:q4-strip` | 7.5.4 | 认证条带覆盖 vs 25 m 方格覆盖的点列与路径对比 |
| 9 | `fig:q4-track` | 7.6 | 第四问一局轨迹（含定向扇区）+ 25/22 站逐例配对散点 |
| 10 | `fig:results` | 8.3 | 演练成绩：T–n 散点与回归、$\bar T$–n 双曲线、时间构成堆叠柱 |

绘图数据来源：

- 图 2 的三个检测点与顶点：`analysis_b/results/geometry.json`
- 图 4 的 $d_{\max}(r)$：论文式 (6.2)，可直接用解析式画
- 图 7 的余量热力图：`experiments/q4_layout_search/layout_opt.py` 的 `slack`，站点取 `config.json` 的 `q4_station_list`
- 图 6、9 的轨迹：`B题演练程序/practice_logs/<局>/actions.jsonl`
- 图 10 的数据：论文表 8.1、8.2

## 数据来源与口径

- **官方演练**数据来自 `B题演练程序/practice_logs/`（第三问 14 局 185 源、第四问 10 局 123 源），
  论文中的统计量由这些 `summary.json` 直接汇总。
- **本地配对实验**数据来自 `docs/sl-*.md` 与 `experiments/round*/`、`experiments/q4_layout_search/`，
  已在表注中注明“本地合成模拟器”，不冒充官方成绩。
- 论文描述的算法与 `analysis_b/` 及 `B题演练程序/` 中的代码一致（两目录已核对逐字节相同）。
