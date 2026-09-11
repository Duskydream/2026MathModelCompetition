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
    count_text=input('请输入连续测试次数（直接回车为1）：').strip() or '1'
    if not count_text.isdigit() or not 1<=int(count_text)<=100:
        print('测试次数必须是1至100之间的整数。');return 1
    count=int(count_text)
    from practice_robot import main
    results=[]
    for index in range(1,count+1):
        print(f'\n===== 第 {index}/{count} 次测试 =====')
        print('请在模拟器中启动对应的演练测试，等待接口就绪。')
        input('接口就绪后按回车开始本次连接：')
        code=main(['--question',str(question),'--robot-id',robot_id,'--base-url',f'http://127.0.0.1:{port}','--connect'])
        results.append(code)
        print(f'第 {index} 次测试完成。' if code==0 else f'第 {index} 次测试未完成（退出码 {code}）。')
        if index<count:
            input('请在模拟器中启动下一次演练，完成后按回车继续：')
    failed=sum(code!=0 for code in results)
    print(f'连续测试结束：共 {count} 次，成功 {count-failed} 次，失败 {failed} 次。')
    return 0 if failed==0 else 1
