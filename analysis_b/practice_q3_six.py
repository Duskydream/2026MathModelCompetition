"""EXPERIMENTAL Q3 entry: six survey stations, coverage NOT guaranteed. Practice only."""
from practice_launcher import launch

if __name__=='__main__':
    print('=' * 60)
    print('实验入口：第3问 6 站方案。理论上无法覆盖全部目标圆，边界窄带内的干扰源可能漏检。')
    print('仅用于演练对比，正式测试请使用“启动第3问演练.cmd”。')
    print('=' * 60)
    raise SystemExit(launch(3,'config_q3_six.json','第3问演练程序（实验：6站，不保证全部发现）'))
