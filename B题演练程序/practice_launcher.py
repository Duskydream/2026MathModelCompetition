"""Interactive entry for users who prefer double-clicking a question script."""
import importlib.util
import sys

def launch(question):
    print(f'第{question}问演练程序（优化版）')
    print('请在模拟器中登录，选择对应的演练测试，等待接口就绪。')
    print('接口不能识别演练/正式模式，请确认没有选中正式测试。')
    missing=[name for name in ['numpy','scipy'] if importlib.util.find_spec(name) is None]
    if missing:
        print('当前Python缺少依赖：'+', '.join(missing))
        print(f'请执行："{sys.executable}" -m pip install -r requirements.txt')
        return 1
    robot_id=input('请输入模拟器登录队号：').strip()
    if not robot_id:
        print('没有输入队号，程序未连接。');return 1
    port=input('接口端口（直接回车使用2026）：').strip() or '2026'
    if not port.isdigit() or not 1<=int(port)<=65535:
        print('端口必须在1至65535之间。');return 1
    input('对应演练接口就绪后，按回车开始连接：')
    from practice_robot import main
    return main(['--question',str(question),'--robot-id',robot_id,'--base-url',f'http://127.0.0.1:{port}','--connect'])
