# 支撑材料：最小可复现运行程序

本文件夹是**运行最新算法所需的最小代码集**，可独立运行、复现论文中的搜索—定位—清除策略。

## 一、环境

- Python ≥ 3.10
- 依赖（见 `requirements.txt`）：`numpy==2.2.6`、`scipy==1.15.3`

```bash
pip install -r requirements.txt
```

## 二、文件说明

| 文件 | 作用 |
|---|---|
| `model.py` | 有界误差几何：前向楔形、半平面裁剪、多边形判型、直径、最小包围圆、光学格、测站布局与覆盖校验 |
| `optimized.py` | 在线策略主体：路径排序、共享测站、目标处理 |
| `q3_policy.py` | 第三问：七站布局、`no_signal` 圆盘排除、第二测点、圆心补测、混合贪心调度 |
| `q4_policy.py` | 第四问：22 站凸包方向覆盖、选择性重测、有界等待、补测精化、条带清除 |
| `q4_optical.py` | 认证条带覆盖与扫描路线成本比较 |
| `practice_robot.py` | 官方协议客户端：`/enter`、`/measure`、`/clear`、`/exit`，串行发送、超时原样重试、逐动作日志与预算控制 |
| `practice_launcher.py` | 交互式入口（依赖检查、队号/端口校验、连续测试次数） |
| `practice_q3.py` / `practice_q4.py` | 第 3/4 问启动脚本 |
| `启动第3问演练.cmd` / `启动第4问演练.cmd` | Windows 双击启动 |
| `config.json` | **复现所需全部参数**（含 22 站坐标） |
| `requirements.txt` | 依赖清单 |

## 三、启动方式

**方式 A（推荐）**：双击 `启动第3问演练.cmd`（或 `启动第4问演练.cmd`），按提示输入队号、端口（默认 2026）、测试次数。

**方式 B（命令行）**：先在官方模拟器中登录并启动对应演练/正式测试、等待接口就绪，然后：

```bash
python practice_robot.py --question 3 --robot-id <队号> --case-code <案例编码> --connect
# 第四问：--question 4
```

不加 `--connect` 时程序不发送任何请求，仅做离线检查。

> 说明：程序只与本机官方模拟器接口通信（默认 `http://127.0.0.1:2026`），模拟器由竞赛方提供，不包含在本材料内。

## 四、复现所需参数（`config.json` 关键项）

| 参数 | 取值 | 含义 |
|---|---|---|
| `region_radius_m` | 1800 | 目标区域半径 |
| `receiver_radius_min_m` / `receiver_radius_max_m` | 1000 / 1500 | 接收半径下界（覆盖证明基准）/ 上界 |
| `bearing_bound_deg` | 1.005 | 保守测向误差界 |
| `clear_m` / `near_m` | 20 / 5 | 认证清除半径 / 近场阈值 |
| `optical_grid_m` | 25 | 光学方格边长（$25/\sqrt2<20$） |
| `speed_m_s`,`measure_s`,`switch_s`,`clear_success_s`,`clear_failure_s` | 5,5,1,5,3 | 计时常数 |
| `q3_survey_layout` / `q3_ring_radius_m` | hexagon / 1150 | 第三问七站布局与环半径 |
| `q3_second_forward_m` / `q3_second_lateral_m` | 200 / 100 | 第三问第二测点偏移 |
| `q3_refine_max_m` / `q3_refine_offset_m` | 300 / 60 | 圆心补测上限与横移 |
| `q4_policy` | mixed_ring | 第四问联合调度 |
| `q4_second_forward_m` / `q4_second_lateral_m` | 200 / 100 | 第四问第二测点偏移 |
| `q4_selective_remeasure` | true | 选择性重测 |
| `q4_remeasure_min_sine` / `q4_remeasure_min_gap_m` | 0.3 / 300 | 重测的交会角正弦与测点间距阈值 |
| `q4_wait_for_survey` / `q4_wait_mode` / `q4_wait_stale_m` | true / inner / 1400 | 有界等待与陈旧距离 |
| `q4_strip_cover` / `q4_scan_cost_gate` / `q4_immediate_near` | true | 认证条带覆盖 / 扫描成本门控 / `near` 即清 |
| `q4_station_list` | 22 点 | 第四问认证布局（删除即回退 25 站解析布局） |

> `config.json` 中另有 `second_forward_m=650`、`q3_grid_m`、`q4_grid_m`、`q4_triangle_spacing_m` 等历史/通用参数，不被当前默认路径读取，保留用于一键回退旧版本对照。

## 五、自检结果

- `python -c "import model, optimized, q3_policy, q4_policy, q4_optical, practice_robot"` → 导入通过
- `python practice_robot.py --help` → 参数解析正常
- 无 `--connect` 时不发送请求并按提示退出

## 六、复现 22 站网格证书（可选）

在 `program/` 目录下运行：

```bash
python certify22.py          # 默认 h=1 m，输出最小余量约 1.7331 m（约十余秒）
python certify22.py 100      # 粗网格快检
```

站坐标与证书保存在 `experiments/q4_layout_search/` 下（`ring22_stations.json`、`ring22_certificate.json`），`certify22.py` 会自动读写该相对路径。

