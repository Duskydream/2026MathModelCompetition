# 算法说明与复现

保留的第一轮版本是shared调度＋第三问7站覆盖＋第四问49站方向覆盖；其他策略行为与原版相同。变更仅位于`model.py:survey_points`及选择该方案的配置。

## 伪代码

```text
人工启动对应演练，核对模块与队号
enter，读取实际剩余现实时间
points ← Q3七站 / Q4四十九站
cleared ← 空集
while points非空：
    p ← 离当前位置最近的未访问搜索站，移除p
    扫描所有未清除频道，先当前测向频道
    direction建立首测外包多边形，near记录测点
    while 本站还有已发现而未清除目标：
        按下一行动点最近原则选择目标c
        如需测向，选首测局部(650,+250)/(650,-250)中近者
        direction与原多边形相交；no_signal保留原域；near记录位置
        到站后按原shared筛选条件补测其他已发现目标
        near在记录位置clear；否则计算MEC
        MEC半径足够小：去圆心clear
        否则：按相交光学方格中心蛇形尝试，成功即结束目标
        顺路补测其他已发现目标
    若清除16源：终止
全部站点完成：终止
exit并保存日志
```

当前near可能在同站其他频道测完或共站补测后才处理；这是已审计的待优化行为，伪代码不将其描述成已实现的即时优先。

Discovery由survey_points与站点扫描承担，Localization由track、楔形裁剪承担，Clearing由MEC与optical_cells承担，Scheduling由最近邻与shared_scan承担。无需新建大型状态机；已有cleared、tracks、count、near足以表达本轮状态。未实现逐频道PROVEN_ABSENT与跨搜索站任务联合优化。

## 协议边界

推荐`practice_q3.py`/`practice_q4.py`或`practice_robot.py`。PracticeHTTP负责四接口、请求日志、同字节同ID重试、合法时钟、位置、测向频道和预算。算法不直接写HTTP请求。`http_robot.py`是旧对照入口，缺少完整未决保护，不应用于本轮官方联调。

协议没有查询演练/正式模块的方法。端口监听不能作为演练证据。未获当前演练模式和队号前，自动化脚本不发送enter。本轮只使用LocalSimulator及临时随机端口的回环HTTP测试服务。

## 复杂度

搜索站数m，频道数C≤20，源数n≤16。最近搜索站选择累计O(m²)，全站检测上界mC，共站补测每源至多4次。单个k顶点多边形裁剪约O(k)，直径O(k²)，MEC枚举O(k^4)。光学格数受1500米×2.01°首测区域及25米格距限制，有限步兜底。用7站替换25站直接减少搜索阶段上限，未改变定位复杂度。

## 复现与回退

在项目根目录使用已安装NumPy与SciPy的Python执行：

```powershell
python -m unittest discover -s analysis_b -p 'test_*.py' -v
python experiments/check_round1_geometry.py
python experiments/run_round1.py baseline
python experiments/run_round1.py candidate
python experiments/run_round1.py summarize
```

脚本只写本轮结果目录；重新运行会覆盖同名本轮派生数据，不连接官方模拟器。旧results与optimization_results不覆盖。baseline从已冻结快照加载，candidate从当前analysis_b加载，两者明确设置grid/hexagon，不能仅按当前默认配置猜版本。

回退搜索方案：把研究目录和独立演练包各自`config.json`中的`q3_survey_layout`设为`grid`。完整旧源码和配置在`experiments/round1/baseline/`。修改前后哈希、运行环境与配置分别存档。打包脚本已同步7站说明；旧报告描述的是历史实验，不用它重写本轮数值。

## 本轮边界

完成一次覆盖点消融后停止优化。问题2新补的几何指标用于审计，不改变运行策略；尚未做追踪A/B/C/D、Q4新覆盖、参数权重扫描或多步调度。建议Experiment 2仅研究Q4方向覆盖点数量与路线，保留现有定位兜底，先证明再配对验证。
