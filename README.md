# MathModelCompetition · 2026 高教社杯 B 题

《无线电干扰源的快速自动定位与清除》的参赛论文、可复现运行程序与官方测试数据。
算法只使用接口观测，不读取模拟器隐藏源位置。

## 目录结构

```
MathModelGPT/
├── essay/               论文 LaTeX 源、图、数据与附录源码
├── program/             最小可复现运行程序（官方协议客户端 + 策略）
└── official_practice/   官方演练/正式测试导出数据与加密日志
```

| 路径 | 用途 |
|---|---|
| `essay/` | 论文正文（`main.tex` / `main.pdf`）、章节源、10 张插图、结果数据 |
| `program/` | 实际运行入口：CMD 启动、客户端、模型、Q3/Q4 算法与配置 |
| `official_practice/` | 官方测试导出的汇总 JSON、逐局 CSV 与 `.jlog` 日志 |

## 论文（`essay/`）

参赛论文，按 2026 年格式规范配置（去封面、无目录、首页为摘要）。用 **xelatex** 编译：

```powershell
latexmk -xelatex main        # 在 essay/ 目录下
# 或
xelatex main; xelatex main   # 连编两次以更新交叉引用
```

| 路径 | 内容 |
|---|---|
| `main.tex` / `main.pdf` | 主文件与编译结果 |
| `sec/01`–`sec/10` | 问题重述、假设、总体框架、问题一至四、结果、评价、附录 |
| `code/` | 附录 `\lstinputlisting` 引用的源程序副本（与 `program/` 同步） |
| `data/` | `official_runs.json`、`q3_runs.csv`、`q4_runs.csv` 结果数据 |
| `figures/` | `fig-framework`、`fig-q1-counter` … `fig-results` 共 10 张图 |

## 运行程序（`program/`）

**运行最新算法所需的最小代码集**，可独立运行、复现搜索—定位—清除策略。

- Python ≥ 3.10
- 依赖（`requirements.txt`）：`numpy==2.2.6`、`scipy==1.15.3`

```powershell
python -m pip install -r program/requirements.txt
```

### 启动方式

**方式 A（推荐）**：双击 `program/启动第3问演练.cmd` 或 `program/启动第4问演练.cmd`，
按提示输入队号、端口（默认 2026）、测试次数。

**方式 B（命令行）**：先在官方模拟器中登录并启动对应测试、等待接口就绪，然后：

```powershell
python program/practice_robot.py --question 3 --robot-id <队号> --case-code <案例编码> --connect
# 第四问：--question 4
```

不加 `--connect` 时程序不发送任何请求，仅做离线检查。端口变化时加
`--base-url http://127.0.0.1:<端口>`。程序只与本机官方模拟器接口通信（默认
`http://127.0.0.1:2026`），模拟器由竞赛方提供，不包含在本仓库内。

### 文件说明

| 文件 | 作用 |
|---|---|
| `model.py` | 有界误差几何：前向楔形、半平面裁剪、多边形判型、最小包围圆、光学格、测站布局与覆盖校验 |
| `optimized.py` | 在线策略主体：路径排序、共享测站、目标处理 |
| `q3_policy.py` | 第三问：七站布局、`no_signal` 圆盘排除、第二测点、圆心补测、混合贪心调度 |
| `q4_policy.py` | 第四问：22 站凸包方向覆盖、选择性重测、有界等待、补测精化、条带清除 |
| `q4_optical.py` | 认证条带覆盖与扫描路线成本比较 |
| `practice_robot.py` | 官方协议客户端：`/enter`、`/measure`、`/clear`、`/exit`，串行发送、超时原样重试、逐动作日志与预算控制 |
| `practice_launcher.py` | 交互式入口（依赖检查、队号/端口校验、连续测试次数） |
| `practice_q3.py` / `practice_q4.py` | 第 3/4 问启动脚本 |
| `启动第3问演练.cmd` / `启动第4问演练.cmd` | Windows 双击启动 |
| `config.json` | 复现所需全部参数（含 22 站坐标） |
| `certify22.py` / `layout_opt.py` | 22 站布局证书校验与优化搜索 |
| `experiments/q4_layout_search/` | `ring22_stations.json`、`ring22_certificate.json` 布局与证书 |

### 关键参数（`config.json`）

| 参数 | 取值 | 含义 |
|---|---|---|
| `region_radius_m` | 1800 | 目标区域半径 |
| `receiver_radius_min_m` / `receiver_radius_max_m` | 1000 / 1500 | 接收半径下界（覆盖证明基准）/ 上界 |
| `bearing_bound_deg` | 1.005 | 保守测向误差界 |
| `clear_m` / `near_m` | 20 / 5 | 认证清除半径 / 近场阈值 |
| `optical_grid_m` | 25 | 光学方格边长（$25/\sqrt2<20$） |
| `q3_survey_layout` / `q3_ring_radius_m` | hexagon / 1150 | 第三问七站布局与环半径 |
| `q3_second_forward_m` / `q3_second_lateral_m` | 200 / 100 | 第三问第二测点偏移 |
| `q4_policy` | mixed_ring | 第四问联合调度 |
| `q4_station_list` | 22 点 | 第四问认证布局（删除即回退 25 站解析布局） |

### 自检与证书复现

```powershell
python -c "import model, optimized, q3_policy, q4_policy, q4_optical, practice_robot"
python program/practice_robot.py --help
python program/certify22.py        # 22 站网格证书，最小余量约 1.7331 m（约十余秒）
python program/certify22.py 100    # 粗网格快检
```

`certify22.py` 自动读写 `experiments/q4_layout_search/` 下的站坐标与证书。

## 官方测试数据（`official_practice/`）

| 路径 | 内容 |
|---|---|
| `模拟测试导出数据/` | 演练批量导出：`q3_runs.csv`、`q4_runs.csv`（各 70 局逐局记录） |
| `正式测试导出数据/` | `official_runs.json` 汇总（含 `excluded` 排除说明）与 6 个正式测试局目录（q3×3、q4×3），每局含 `actions.jsonl`、`localization_regions.json`、`run_config.json`、`summary.json` |
| `正式测试日志/` | 6 个加密 `.jlog` 正式日志（本地保留，已被 `.gitignore` 排除） |

`official_runs.json` 汇总（已排除与当前配置不一致的历史局）：

| 问题 | 局数 | 源数 | 平均秒/源 | 中位数 | P95 |
|---|---:|---:|---:|---:|---:|
| 第三问 | 50 | 667 | 252.0 | 251.5 | 301.6 |
| 第四问 | 70 | 887 | 511.19 | 515.8 | 644.6 |

逐局 CSV 的列包括 `sources_cleared`、`total_virtual_s`、`seconds_per_source`、
`move_s` / `measure_s` / `switch_s` / `optical_s` / `laser_s`、`actions`、
`program_s`、`stations` 及两问策略哈希。

## 数据与隐私

- `*.jlog`、`**/practice_logs/`、`*_actions.jsonl`、`robot_actions.jsonl` 均由 `.gitignore` 排除，
  不应提交或推送；这些文件可能包含队号与原始请求。
- 已跟踪的官方导出数据仅含结果统计与动作记录，不含队伍身份信息。
- Git 忽略规则不影响已被跟踪的文件，提交前可用
  `git ls-files -- '*practice_logs*' '*.jlog'` 确认没有输出。
