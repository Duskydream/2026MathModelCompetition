"""Create a fully paginated Chinese explanatory PDF from verified results."""
from pathlib import Path
import csv,json,math,hashlib
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.lib.pagesizes import A4

B=Path(__file__).resolve().parent;ROOT=B.parent;WORK=B/'pdf_work';OUT=ROOT/'output/pdf';OUT.mkdir(parents=True,exist_ok=True)
DATA=json.loads((WORK/'report_data.json').read_text());BASE=json.loads((B/'results/summary.json').read_text())
H=json.loads((B/'optimization_results/holdout_summary.json').read_text())['results']
D=json.loads((B/'optimization_results/development_summary.json').read_text())['results']
S=json.loads((B/'optimization_results/stress_summary.json').read_text())['results']
G=json.loads((B/'results/geometry.json').read_text());AUDIT=json.loads((B/'results/audit_checks.json').read_text())
for name,digest in DATA['sources_sha256'].items():assert hashlib.sha256((B/name).read_bytes()).hexdigest()==digest
pdfmetrics.registerFont(TTFont('CN','C:/Windows/Fonts/msyh.ttc'))
pdfmetrics.registerFont(TTFont('CNB','C:/Windows/Fonts/msyhbd.ttc'))
pdfmetrics.registerFontFamily('CN',normal='CN',bold='CNB',italic='CN',boldItalic='CNB')
pdfmetrics.registerFont(TTFont('Code','C:/Windows/Fonts/consola.ttf'))
W,HEIGHT=A4;M=53;CW=W-2*M
NAVY=colors.HexColor('#172D46');BLUE=colors.HexColor('#2367B4');TEAL=colors.HexColor('#168A81');ORANGE=colors.HexColor('#CB6A30');GRAY=colors.HexColor('#607083');LIGHT=colors.HexColor('#EFF4F8');RED=colors.HexColor('#B64343');INK=colors.HexColor('#24384D')
PATH=OUT/'B题背景原理与建模优化详解.pdf'
c=canvas.Canvas(str(PATH),pagesize=A4);c.setTitle('B题背景原理与建模优化详解');c.setAuthor('建模研究记录');c.setSubject('题目理解、几何定位、覆盖搜索及本地优化试验')
body=ParagraphStyle('body',fontName='CN',fontSize=10.3,leading=17.3,textColor=INK,wordWrap='CJK',spaceAfter=0)
small=ParagraphStyle('small',parent=body,fontSize=8.6,leading=13.5,textColor=GRAY)
cellstyle=ParagraphStyle('cell',parent=body,fontSize=9.2,leading=14.8)
pages=[];y=0;page=0

def label(x,y,text,size=9,color=INK,bold=False):
    c.setFont('CNB' if bold else 'CN',size);c.setFillColor(color);c.drawString(x,y,text)
def line(a,b,color=GRAY,width=1,dash=None):
    c.setStrokeColor(color);c.setLineWidth(width);c.setDash(dash or []);c.line(*a,*b);c.setDash([])
def arrow(a,b,color=BLUE,width=1.3):
    line(a,b,color,width);ang=math.atan2(b[1]-a[1],b[0]-a[0]);s=6
    p=c.beginPath();p.moveTo(*b);p.lineTo(b[0]-s*math.cos(ang-.45),b[1]-s*math.sin(ang-.45));p.lineTo(b[0]-s*math.cos(ang+.45),b[1]-s*math.sin(ang+.45));p.close();c.setFillColor(color);c.drawPath(p,fill=1,stroke=0)
def dot(p,color=BLUE,r=3):c.setFillColor(color);c.circle(*p,r,fill=1,stroke=0)
def polygon(points,fill=None,stroke=BLUE,width=1):
    p=c.beginPath();p.moveTo(*points[0])
    for pt in points[1:]:p.lineTo(*pt)
    p.close();c.setLineWidth(width);c.setStrokeColor(stroke)
    if fill:c.setFillColor(fill)
    c.drawPath(p,stroke=1,fill=bool(fill))
def begin(title,kicker='题目理解与迭代优化'):
    global page,y
    if page:
        finish();c.showPage()
    page+=1;y=HEIGHT-88
    label(M,HEIGHT-35,'B题  无线电干扰源的快速自动定位与清除',8.1,GRAY)
    label(M,HEIGHT-57,kicker,9,TEAL)
    label(M,y,title,21,NAVY,True);y-=32
    pages.append({'page':page,'title':title})
def finish():
    if y<48:raise RuntimeError(f'Page {page} overflow y={y}')
    pages[-1]['bottom_content_y']=round(y,2)
    label(M,28,'理解报告 · 本地试验结果不等于官方成绩',8,GRAY)
    c.setFont('CN',8);c.setFillColor(GRAY);c.drawRightString(W-M,28,f'{page:02d}')
def p(text,style=body,gap=9):
    global y
    q=Paragraph(text,style);_,h=q.wrap(CW,800)
    if y-h<48:raise RuntimeError(f'Page {page} paragraph overflow: {text[:50]} y={y}, h={h}')
    q.drawOn(c,M,y-h);y-=h+gap
def sub(text):
    global y
    y-=3;label(M,y,text,12,BLUE,True);y-=22
def note(text):
    global y
    q=Paragraph(text,small);_,h=q.wrap(CW-22,800)
    c.setFillColor(LIGHT);c.roundRect(M,y-h-19,CW,h+17,6,fill=1,stroke=0);q.drawOn(c,M+11,y-h-10);y-=h+29
def table(rows,widths=None):
    global y
    cells=[[Paragraph(escape(str(v)),cellstyle) for v in row] for row in rows]
    t=Table(cells,colWidths=widths or [CW/len(rows[0])]*len(rows[0]),hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#C8D6E1')),('LINEBELOW',(0,1),(-1,-1),.35,colors.HexColor('#E1E8EE'))]))
    _,h=t.wrap(CW,800)
    if y-h<48:raise RuntimeError(f'Page {page} table overflow {h} {y}')
    t.drawOn(c,M,y-h);y-=h+13
def fig(height,draw,caption):
    global y
    bottom=y-height;c.saveState();draw(M,bottom,CW,height);c.restoreState();y=bottom-10;p(caption,small,gap=11)
def world(x,y,w,h,bounds,pad=18):
    xmin,xmax,ymin,ymax=bounds;scale=min((w-2*pad)/(xmax-xmin),(h-2*pad)/(ymax-ymin));ox=x+(w-scale*(xmax-xmin))/2;oy=y+(h-scale*(ymax-ymin))/2
    return lambda q:(ox+(q[0]-xmin)*scale,oy+(q[1]-ymin)*scale),scale
def scene_map(x,y,w,h):
    project,s=world(x,y,w*.58,h,(-2200,2200,-2200,2200));o=project([0,0]);c.setStrokeColor(BLUE);c.setLineWidth(1.3);c.circle(*o,1800*s,fill=0)
    arrow(project([-2100,0]),project([2150,0]),GRAY,.7);arrow(project([0,-2100]),project([0,2150]),GRAY,.7)
    label(*project([1900,50]),'东',8);label(*project([50,1900]),'北',8);dot(o,TEAL,4)
    for src in DATA['worst_case'][0]['sources']:dot(project(src['position']),ORANGE,3)
    label(x+w*.61,y+h-43,'圆内：源可能出现的位置',10,NAVY,True)
    label(x+w*.61,y+h-75,'原点：机器狗出发位置',9.5)
    label(x+w*.61,y+h-105,'橙点：演示案例中的真实源',9.5)
    label(x+w*.61,y+h-135,'程序运行时看不到这些橙点',9.5,RED)
    label(x+w*.61,y+h-165,'源区域半径 1800 米',9.5)
def bearing_pic(x,y,w,h):
    e=DATA['example'];project,s=world(x,y,w*.6,h,(-80,1540,-140,480));polygon([project(v) for v in e['first_polygon']],colors.HexColor('#E5EEF9'),BLUE,.7)
    for i,sta in enumerate(['station1','station2'],1):
        angle=math.radians(e[f'bearing{i}']);distance=math.dist(e[sta],e['true_source'])
        tip=[e[sta][0]+distance*math.cos(angle),e[sta][1]+distance*math.sin(angle)]
        arrow(project(e[sta]),project(tip),BLUE if sta=='station1' else TEAL,.9);dot(project(e[sta]),TEAL,3.5)
    polygon([project(v) for v in e['intersection']],colors.HexColor('#F5DEC9'),ORANGE,1)
    dot(project(e['true_source']),RED,3);label(*project([0,-100]),'第一站',9);label(*project([600,330]),'第二站',9)
    px=x+w*.62;project2,s2=world(px,y+14,w*.38,h-25,(925,1040,-30,55))
    polygon([project2(v) for v in e['intersection']],colors.HexColor('#F5DEC9'),ORANGE,1.5);dot(project2(e['true_source']),RED,3.5)
    label(px+5,y+h-12,'交会区域放大',9.5,NAVY,True);label(px+5,y+5,'红点为自构算例的真位置',8,GRAY)
def triangle_pic(x,y,w,h):
    project,s=world(x,y,w*.58,h,(-7,47,-15,42));cen=project(G['circle_center']);r=G['minimum_circle_radius_m']*s
    c.setStrokeColor(BLUE);c.setLineWidth(1.5);c.circle(*cen,r,stroke=1,fill=0);c.setStrokeColor(GRAY);c.setDash([3,3]);c.circle(*cen,20*s,stroke=1,fill=0);c.setDash([])
    polygon([project(v) for v in G['equilateral_vertices']],None,ORANGE,2);dot(cen,BLUE,2)
    label(x+w*.62,y+h-45,'三角形边长：40 米',10,NAVY,True)
    label(x+w*.62,y+h-78,'区域直径：40 米',10)
    label(x+w*.62,y+h-111,'灰圆半径：20 米',10)
    label(x+w*.62,y+h-144,'蓝圆半径：23.094 米',10,BLUE)
    label(x+w*.62,y+h-181,'灰圆装不下三个顶点',10,RED)
def second_pic(x,y,w,h):
    project,s=world(x,y,w*.68,h,(-120,1150,-340,380));p0=project((0,0));q=project((650,250));qm=project((650,-250))
    arrow(p0,project((1130,0)),GRAY);arrow(p0,project((650,0)),BLUE,2);arrow(project((650,0)),q,TEAL,2)
    dot(p0,BLUE,4);dot(q,TEAL,4);dot(qm,GRAY,3);line(p0,q,GRAY,.6,[3,3]);line(p0,qm,GRAY,.6,[3,3])
    label(*project((30,70)),'第一次读数方向',9);label(*project((220,-70)),'前进 650 米',9,BLUE);label(q[0]+8,q[1]-3,'侧移 250 米',9,TEAL)
    label(x+w*.73,y+h*.65,'原方案：选左侧',9.2);label(x+w*.73,y+h*.45,'优化版：选较近侧',9.2);label(x+w*.73,y+h*.25,'真源距离仍未知',9.2,RED)
def gridpic(x,y,w,h,question=3):
    hgrid=1000 if question==3 else 600;n=2 if question==3 else 3
    project,s=world(x,y,w*.6,h,(-2250,2250,-2250,2250));c.setStrokeColor(GRAY);c.setLineWidth(.45)
    for i in range(-n,n+1):
        line(project((i*hgrid,-n*hgrid)),project((i*hgrid,n*hgrid)),colors.HexColor('#D9E3EB'),.5)
        line(project((-n*hgrid,i*hgrid)),project((n*hgrid,i*hgrid)),colors.HexColor('#D9E3EB'),.5)
        for j in range(-n,n+1):dot(project((i*hgrid,j*hgrid)),BLUE,2.1)
    c.setStrokeColor(ORANGE);c.setLineWidth(1.3);c.circle(*project((0,0)),1800*s,stroke=1,fill=0);dot(project((0,0)),TEAL,4)
    texts=['25 个检测站','格距 1000 米','最近站距离最多 707.11 米','小于最小接收半径 1000 米'] if question==3 else ['49 个检测站','格距 600 米','同格四角均在 848.53 米内','四角同时照顾未知发射方向']
    for i,t in enumerate(texts):label(x+w*.62,y+h-45-i*38,t,9.2,NAVY if i==0 else INK,i==0)
def flowpic(x,y,w,h):
    steps=['到最近的未访问检测站','扫完尚未清除的频道，记录有信号的目标','选择一个目标，补充测向或使用已有信息','能保证 20 米内清除就直接清除，否则分格寻找','处理本站其他目标，然后去下一站','清除 16 个，或完成覆盖与全部已发现目标后退出']
    bw=w-34;bh=34;gap=12;top=y+h
    for i,t in enumerate(steps):
        bottom=top-bh;c.setFillColor(LIGHT if i!=5 else colors.HexColor('#E7F3F0'));c.roundRect(x+17,bottom,bw,bh,5,fill=1,stroke=0);label(x+29,bottom+12,f'{i+1}  {t}',9.4,NAVY)
        if i<5:arrow((x+w/2,bottom-1),(x+w/2,bottom-gap+2),GRAY,1)
        top=bottom-gap
def optical_pic(x,y,w,h):
    project,s=world(x,y,w*.55,h,(-34,34,-30,30));center=project((0,0))
    c.setStrokeColor(BLUE);c.setLineWidth(1.3);c.circle(*center,20*s,stroke=1,fill=0)
    polygon([project(v) for v in [(-12.5,-12.5),(12.5,-12.5),(12.5,12.5),(-12.5,12.5)]],None,TEAL,1.5)
    corner=project((12.5,12.5));dot(center,BLUE,3);dot(corner,ORANGE,3);line(center,corner,ORANGE,1.3)
    label(x+w*.58,y+h-35,'方格边长：25 米',10,NAVY,True)
    label(x+w*.58,y+h-68,'中心到最远角：17.68 米',10)
    label(x+w*.58,y+h-101,'光学清除半径：20 米',10,BLUE)
    label(x+w*.58,y+h-145,'整格都在清除范围里',11,TEAL,True)
def directional_pic(x,y,w,h):
    project,s=world(x,y,w*.62,h,(-1250,1250,-1150,1150));o=project((0,0));rad=1000
    sector=[o]+[project((rad*math.cos(math.radians(t)),rad*math.sin(math.radians(t)))) for t in range(-90,91,3)]+[o]
    polygon(sector,colors.HexColor('#E7F3F0'),TEAL,.7);line(project((0,-1100)),project((0,1100)),TEAL,1)
    dot(o,ORANGE,4);arrow(o,project((800,0)),TEAL,1.5);dot(project((-500,0)),RED,4);dot(project((550,350)),BLUE,4)
    label(*project((-1040,-170)),'背面站：近也没信号',8.4,RED);label(*project((180,570)),'正面站：范围内可见',8.4,BLUE)
    label(x+w*.66,y+h-38,'右半面有无线电信号',9.5,NAVY,True)
    label(x+w*.66,y+h-73,'左半面收不到',9.5)
    label(x+w*.66,y+h-115,'边界线也有信号',9.5,TEAL)
    label(x+w*.66,y+h-156,'光学清除不受正背面影响',9.1)
def square_proof(x,y,w,h):
    project,s=world(x,y,w*.58,h,(-60,660,-80,690));verts=[(0,0),(600,0),(600,600),(0,600)];g=(220,250)
    polygon([project(v) for v in verts],None,BLUE,1.2);dot(project(g),ORANGE,4)
    # A line through g separates the illustrative visible and invisible sides.
    line(project((-20,490)),project((490,-20)),TEAL,1.3);arrow(project(g),project((480,510)),TEAL,1.8)
    for v in verts:dot(project(v),TEAL if v[0]+v[1]>=sum(g) else RED,4)
    label(*project((60,640)),'包含源的一个 600 米方格',9,NAVY)
    for i,t in enumerate(['四个角都足够近','源在四个角围成的区域里','任何过源的直线','都不能把四个角全挡在背面']):label(x+w*.61,y+h-37-i*37,t,9.4,NAVY if i==0 else INK,i==0)
def shared_pic(x,y,w,h):
    nodes={'起点':(x+38,y+38),'已到达的位置':(x+w*.38,y+h*.72),'目标甲':(x+w*.85,y+h*.66),'目标乙':(x+w*.85,y+h*.12)}
    arrow(nodes['起点'],nodes['已到达的位置'],BLUE,2)
    for n in ['目标甲','目标乙']:
        line(nodes['起点'],nodes[n],GRAY,.8,[3,3]);line(nodes['已到达的位置'],nodes[n],TEAL,1.5)
    for n,pt in nodes.items():dot(pt,ORANGE if '目标' in n else BLUE,4);label(pt[0]-10,pt[1]+13,n,9.4)
    label(x+40,y+h-18,'先前方向：灰虚线',9,GRAY);label(x+215,y+h-18,'顺便补测：绿实线',9,TEAL)
def resultbars(x,y,w,h):
    for i,r in enumerate(H):
        yy=y+h-34-i*44;bw=(w-176)*r['mean_s']/1050
        label(x,yy+7,f"第{r['question']}问 {'原方案' if r['variant']=='B1' else '优化版'}",9.2)
        c.setFillColor(colors.HexColor('#9BACBD') if r['variant']=='B1' else BLUE);c.rect(x+105,yy,bw,25,fill=1,stroke=0);label(x+111+bw,yy+7,f"{r['mean_s']:.2f}",9.2)
def real_paths(x,y,w,h):
    for i,r in enumerate(DATA['worst_case']):
        px=x+i*(w/2+5);project,s=world(px,y,w/2-7,h-24,(-2400,2400,-2400,2400),pad=12)
        c.setStrokeColor(colors.HexColor('#CFD9E2'));c.circle(*project((0,0)),1800*s,stroke=1,fill=0)
        points=r['path'];c.setStrokeColor(BLUE if i==0 else TEAL);c.setLineWidth(.45)
        path=c.beginPath();path.moveTo(*project(points[0]))
        for pt in points[1:]:path.lineTo(*project(pt))
        c.drawPath(path)
        for src in r['sources']:dot(project(src['position']),ORANGE,2.6)
        label(px+10,y+h-10,('原方案' if r['row']['variant']=='B1' else '优化版')+f"  {r['row']['move_s']*5/1000:.2f} 公里",10,NAVY,True)

begin('先把题目看成一场找源任务','阅读目的  理解题目、检查做法、继续改进')
p('机器狗要在一片区域里，找到数量未知的无线电干扰源并清除。它没有完整地图，也不能直接询问源的坐标。每走到一个位置，只能选择一个频道，获得“没有信号”“距离很近”或一个带误差的方向。')
p('我们要解决的不只是“算出坐标”，而是连续做决定：<b>先去哪里、测哪个频道、什么时候可以动手清除，以及怎样确认没有漏掉最后一个源。</b>')
note('<b>先看结论：</b>现有方案能够在题目设定下保证搜索与清除不漏源；本地新增案例中，优化版的平均耗时较原方案下降了第3问9.77%、第4问5.59%。但仍有部分案例变慢，官方模拟器测试尚未进行。')
sub('这份报告怎样读')
table([['想先弄清什么','对应页码'],['题目背景与设备到底能告诉我们什么','第2至4页'],['第1、2问怎样支撑后面的搜索','第5至6页'],['第3、4问如何保证找到并清除全部目标','第7至11页'],['这次优化实际改了哪些动作','第12至13页'],['效果有多大、什么情况下会退步','第14至18页'],['下一轮怎么优化、代码与结果在哪里','第19至20页']],[CW*.64,CW*.36])
p('报告会优先用“还可能在哪”“一次移动能做几件事”等直白说法。只有需要复算时才给出公式。原理图会注明是示意；真正的运行轨迹和成绩表来自已经保存的计算结果。',gap=13)
note('版本范围：覆盖第一次基准试验和第二次优化试验。它是一份团队理解与迭代用的报告，不是已经完成正式测试、可以直接提交的竞赛论文。')

begin('题目给了我们一个怎样的世界')
p('无线电干扰会影响正常通信。题目假设前期大范围监测已经把源所在范围缩小到一个半径1800米的圆。现在由一只机器狗从圆心出发，完成最后的找源与清除。[1]')
fig(220,scene_map,'图1  用一个已生成案例说明区域和源的关系。橙点只用于解释，策略运行时不能读取源坐标。')
table([['题目确定的事实','实际含义'],['第3、4问有10至16个源，具体数量未知','清除10个后不能直接认定任务结束'],['频道1至20，每个源的频道不同且不变','频道就是追踪同一个源的标识'],['源位于圆内，机器狗允许走到圆外','圆是源的分布边界，不是狗的活动围栏'],['每个源的接收半径为1000至1500米','不应把所有源的范围都当成1500米']],[CW*.49,CW*.51])
p('文件夹没有一张可直接读取的“目标坐标表”。数量、坐标、接收半径和定向方向都是有意隐藏的信息，不能按普通缺失值填补。两份附件主要是模拟器使用与通信说明。[2][3]',small)

begin('设备能做什么  每一步怎样计时')
p('检测器一次只能看一个频道，移动时不能有效检测。程序提交下一步的位置和频道后，模拟器自动计算移动、切换和检测时间；并不存在一个可以边走边扫描全部频道的动作。[3]')
p('测向时先停下，再转动天线，寻找接收场强最大的朝向。这个朝向就是方向读数的依据，但会受当地环境影响。信号随距离衰减；接口却不返回场强或距离，因此不能凭空套用“用信号强度反推距离”的公式。[1]')
table([['动作或反馈','我们获得的信息','虚拟耗时'],['检测 direction','一个带误差的方向，没有距离','检测5秒'],['检测 no_signal','可能没源，也可能太远或在背面','检测5秒'],['检测 near','在信号覆盖内，且离源不超过5米','检测5秒'],['清除成功 / 失败','20米内有目标 / 本次未找到','5秒 / 3秒'],['移动 / 切换检测频道','位置改变 / 检测频道改变','路程÷5 / 1秒']],[CW*.27,CW*.47,CW*.26])
note('清除指令中的频道只是指定清除哪个源，不改变检测器当前频道。清除失败也耗时3秒。两点若处理错，所有时间比较都会失真。')
sub('一个可以手算核对的例子')
p('从原点走到(300,400)，距离500米，测频道1：100＋5＝105秒。原地测频道2：再加1＋5＝6秒。走到(300,0)尝试清除频道3但失败：再加80＋3＝83秒。原地测频道2：仍是原检测频道，再加5秒。总计<b>199秒</b>，与附件示例及程序验证一致。[2][3]')
p('<b>任务总时间＝总路程÷5＋换频道次数＋5×检测次数＋3×清除尝试次数＋2×成功清除次数。</b>')
p('“虚拟秒”用来比较机器狗任务效率；“程序运行时间”是电脑和网络实际花的时间。官方实际可用时长由进入接口返回，最多20分钟，并受25分钟测试窗口约束。两种时间不能混用。',small)

begin('为什么测到方向仍然找不到准确位置')
p('一次方向读数像是说“源大致在前面这条窄带里”，并没有说它在前方100米还是1000米。题目还允许方向偏差最多1°。距离越远，同样角度偏差对应的横向位置差越大。')
fig(210,bearing_pic,'图2  自构算例：源在(1000,0)，首读数0.60°，第二站按既定方案选择。右侧是两次读数共同允许的位置范围，所有顶点由代码计算。')
sub('两次读数怎样一起使用')
p('每次读数都给出一个“源还可能在这里”的窄扇形。真正的源必须同时满足两次读数，所以只保留两个范围重叠的部分。后面若再获得新方向，就继续缩小这个范围。')
p(f"图中算例的共同范围直径为{DATA['example']['diameter_m']:.2f}米，能装下它的最小圆半径为{DATA['example']['radius_m']:.2f}米。已经比第一次窄扇形小很多，但还不能保证站在某一点，就离其中所有位置都不超过20米。")
note('我们没有把读数当成准确直线，也没有给源位置随意指定概率分布。程序保留整个可能范围。取误差界1.005°，是为“两位小数取整”额外留出0.005°余量；题目是否已将取整包含在±1°中，仍可在官方演练中核对。')
p('同一个位置反复检测，题目规定误差不会改变。因此“原地多测几次再平均”不是这里有效的提精度办法。[1]第2页',small)

begin('第1问  范围有多大  怎样才装得下')
p('第1问首先要求算出定位范围的直径：在这个范围里，找相距最远的两点。对于由直边围成的凸多边形，最远点可以在顶点中找到，所以小规模时直接比较所有顶点对就足够。')
p('程序先把每次方向限制写成两条边，再求所有限制共同允许的区域。若读数互相矛盾，应报告“没有共同区域”；若只靠这些读数还限制不了最远距离，应报告“无界”，不能私自加一个大方框后当成答案。')
fig(235,triangle_pic,'图3  可实现的反例。三角形顶点、三组测站和读数保存于results/geometry.json。灰圆只是用来展示半径20米不够，蓝圆是计算得到的最小包围圆。')
p('这个正三角形的任意两点最远只有40米，但能装下它的最小圆半径是40÷√3＝23.094米。因此，<b>“范围直径不超过40米”不等于“存在一个点，离范围内所有位置都不超过20米”。</b>')
p('用于清除的正确判断是：找到能装下整个可能范围的最小圆，只有其半径不超过20米，才可以放心去圆心清除。这是后面所有策略都保留的条件。')

begin('第2问  第二次应该站在哪里测')
p('如果第二站仍沿着第一次读数方向前后移动，两次方向通常近乎重合，距离仍不容易确定。往侧面移动能让两次方向从不同角度夹住源；但走得太远会耗时，还可能收不到信号。')
fig(175,second_pic,'图4  第二站的局部坐标方案。650米、250米是当前策略参数，不是由题目直接给出的最优位置。图中没有假装知道真实源距离。')
p('基准选择“沿读数前进650米、再侧移250米”。对于全向源，我们推导了一个保守候选范围：其中的点无论真实源在第一次窄扇形的哪里，都能继续收到信号。上述第二站及其另一侧的镜像点都满足这个条件。')
table([['前进 / 侧移（米）','移动时间（秒）','抽样中的最大定位直径（米）'],['250 / 100','53.85','631.03'],['650 / 250','139.28','230.30'],['750 / 450','174.93','138.06']],[CW*.31,CW*.28,CW*.41])
p('上表每个候选点计算189种距离与误差组合。走远一些确实可能换来更小的定位范围，但并不自动让整个任务更快。“抽样最大值”也不是所有连续位置的严格最大值。')
note('可复核的接收条件：设前进距离a、侧移距离b，误差界为ε，则同时满足 a²＋b²≤1000²，以及 a²＋b²≤2000(a cosε－|b| sinε)，是保证全向源第二次可见的充分条件。它约束“能否收到”，并不证明时间最优。')

begin('第3问  先保证一定能发现所有源')
p('全向源向四周都有信号，只要检测站足够近就能发现。我们先用一套容易检查的站点安排打底，再优化实际访问顺序。横、纵坐标都取−2000、−1000、0、1000、2000米，共25站。')
fig(255,lambda x,y,w,h:gridpic(x,y,w,h,3),'图5  第3问的25个检测站。橙色圆是源区域，蓝点是检测站。圆外检测站合法，绿色点为起点。')
sub('为什么这25站不会留下空白')
p('任意源都可以找到一个最近的格点。两个坐标方向最多各差500米，所以到该格点的距离最多为√(500²＋500²)＝707.11米。这小于所有源都至少拥有的1000米接收半径。')
p('因此，只要每个尚未清除的频道最终都在这些站检测过，就不会漏掉一个还在发射的全向源。实际程序总是从当前位置去最近的未访问站，不是固定先绕圆一周。')
note('“有保证”不代表“最省站”。25站是一套清楚、可运行的保底安排，还没有为最短总路程做整体设计。后面仍有减少排查点与提前确认结束的空间。')

begin('第3问  程序实际怎样一步步运行')
fig(276,flowpic,'图6  搜索与清除的主循环。每次执行后，下一步都根据狗的新位置和最新读数重新决定。')
sub('为什么要先扫完本站频道再离开')
p('假设本站同时听到三个源。若听到第一个就走过去清除，再回来听第二个，会不断折返。当前做法先把本站能听到的目标记下来，再依次处理；优化版还会调整处理顺序。')
sub('什么时候可以结束')
p('<b>情况一：</b>已经成功清除16个，达到题目给出的上限。<br/><b>情况二：</b>全部覆盖站已经访问；每个没清除的频道都在那里检测过；所有发现的目标都已清除。由于站点保证能听到任何剩余源，所以此时不会再有漏源。')
note('清除了10个不能结束，因为可能实际有16个。只在原点扫完20个频道也不能结束，因为可能有源在接收范围之外。连续若干次“无信号”同样不足以证明任务完成。')

begin('为什么光学方格寻找能保证收尾')
p('两次测向后，定位范围有时仍然太大，或者定向源在第二站听不到。此时不猜一个点就认定找到，而是把剩余范围分成小格，去相关格子的中心逐个尝试。')
fig(210,optical_pic,'图7  光学覆盖的几何依据。正方形边长25米，中心到最远角为25÷√2＝17.68米，整个格子都在20米清除圆内。')
p('只保留与可能位置范围相交的方格。真实源一定在其中至少一个格子内；走到这个格子的中心，光学清除一定成功。把格子按列蛇形排列，可避免每次回到一端重走。')
p('每次失败花3秒，成功花5秒。第一轮最简单的B0方案只测一次方向就开始分格寻找，虽然容易证明可靠，但会做很多失败的尝试。B1增加第二次测向，先减少要找的格子，因此显著减少了失败清除。')
table([['原40例/问的平均失败清除次数','只测一次 B0','测两次 B1'],['第3问，每局平均','609.13','22.13'],['第4问，每局平均','633.30','110.80']],[CW*.52,CW*.24,CW*.24])
p('这里统计的是“每局平均次数”，不是每个源的次数。分格寻找是可靠的兜底方法，但如果范围仍然很长，再补一次测向可能更便宜，这正是下一轮要优化的决策。',small)

begin('第4问  近不一定能听见')
p('定向源只向一个半平面发射，方向未知。按题目设定，在正面180°范围内有信号，边界也包含在内，背面没有无线电信号。机器狗在背面时，就算离得很近也可能收到no_signal。[1][3]')
fig(245,directional_pic,'图8  定向源原理示意，发射方向朝右。示意半径取题目下限1000米；实际源的半径未知，可能更大。')
sub('一次无信号到底能说明什么')
p('它可能表示这个频道没有未清除源，也可能是站得太远，还可能是站在定向源背面。因此第四问不能把“本站无信号”等同于“本站附近没有源”。')
sub('我们的处理')
p('发现阶段使用另一套能照顾未知方向的测站。定位阶段仍尝试第二次测向；如果失联，就保留第一次读数形成的位置范围，继续光学分格寻找，不把范围删掉。')
note('光学定位与清除不受发射方向影响。只要距离不超过20米，即使机器狗在定向源背面，也能清除。这条题目规则使“先听到一次，再用光学兜底”成立。')

begin('第4问  四个角怎样照顾所有方向')
p('第4问使用600米格距，横、纵坐标取−1800至1800米的7个值，共49个站。任意源都在某个闭方格里；源在边界时可选相邻方格。')
fig(200,square_proof,'图9  一个格子的方向覆盖解释。橙点是自构示意源，绿色箭头表示某个可能的发射方向。绿色顶点在正面，红色顶点在背面。')
p('<b>先看距离：</b>一个格子内，源到任意角最远都不超过格子对角线，即600√2＝848.53米，小于最小接收半径1000米。')
p('<b>再看方向：</b>源被四个角围在中间。画任意一条经过源的直线，都不可能让四个角全部严格落在背面。因此至少一个角在有信号的一侧或边界上。')
p('这两件事一起成立，才保证定向源至少在一个检测站被发现。即使源在区域边缘并朝外发射，也仍然成立。题目规定“边界有信号”，在这里非常重要。')
table([['第3问要保证什么','第4问还要多保证什么'],['每个可能源附近有一个够近的测站','一组够近的站能从不同方向包围源'],['只需要解决距离覆盖','需要同时解决距离和方向覆盖']],[CW/2,CW/2])
note('49站仍是保守基准。方向未知让最后的排查更费时间，也是第4问当前平均耗时高于第3问的原因之一。')

begin('优化的核心  一次移动多做几件事')
p('原B1方案逐个源安排专属第二测站，处理顺序主要跟着发现顺序走。即使已经走到一个很适合观察其他源的位置，也可能没有利用它。优化首先针对这些多余移动。')
fig(205,shared_pic,'图10  共用测站的原理示意，不是某一次实测轨迹。从已经到达的位置，分别切频道补测甲、乙，可让两者都获得新的观察方向。')
sub('先改路线，再加顺便测量')
p('<b>路线版：</b>每次选离下一行动点较近的目标；第二站可以在左侧250米和右侧250米中选较近的一侧。这里同时改了顺序和左右侧选择，不能把全部收益只算给“排序”。')
p('<b>共用测站版：</b>到达某个目标的第二站、或完成一次清除后，看看其他待处理目标是否值得在这里补测。如果测到有效方向，就更新它们各自的可能范围。')
p('有的目标已经靠这些顺便测量获得两次方向，就不必再专程去它的固定第二站。之后仍使用原来的20米判断和光学兜底，不降低清除标准。')
note('顺便测量也不是免费的：每次检测至少5秒，换频道还要1秒。所以不是在每个位置都扫全部频道，而是先做筛选，并限制次数。')

begin('优化版每次怎样决定要不要顺便测')
p('为了保持简单，我们使用以下固定筛选条件。它们是已经运行的程序规则，不是题目给出的物理定律，也没有声称这些数值最优。')
table([['当前规则','为什么这样做'],['与该目标以前的检测点至少相隔100米','太接近的站容易重复获得相似方向'],['到当前估计位置的距离不超过1300米','避免大量尝试明显很远的目标；仍可能收不到'],['估计交角的正弦至少0.12','两条估计方向太接近重合时，优先不测'],['每个源最多额外尝试4次','防止附带检测反而拖慢任务'],['获得3次有效方位后不再附带测','控制收益越来越小的重复观测']],[CW*.52,CW*.48])
p('“估计位置”采用能装下当前可能范围的最小圆的圆心。它只帮助安排下一步，不被当成真坐标。估计交角也只用于筛选，实际有无信号由检测反馈决定。')
sub('哪些情况仍走保底流程')
p('near：在对应点清除。第二站无信号：保留已有范围。最小圆半径超过20米：分格寻找。两次读数没有共同范围，或者原本保证成功的清除失败：报错并保留日志，不偷偷换一个猜测位置掩盖矛盾。')
note('目前仍有一个简单但不一定省时的规则：已有两次有效方位，就可以开始光学清除。下一轮应比较“再测一次”与“现在就找”的剩余总时间。')

begin('我们怎样测试  哪些信息是自己假设的')
p('目前没有运行官方模拟器。我们按照附件的检测、清除、频道与计时规则，建立本地环境。环境保存源真值，策略只能调用检测和清除；测试结束后再用真值判断是否漏源、是否算错时间。')
table([['本地生成时的选择','它不是题目保证的事实'],['源数量在10至16中均匀抽取','官方的数量分布未公开'],['源在圆盘内按面积均匀生成','官方可能有边缘聚集或其他分布'],['接收半径在1000至1500米间均匀生成','只知道范围，不知道官方分布'],['第4问每源以0.5概率为定向源，朝向均匀','官方定向比例与方向分布未知'],['用种子、频道和坐标确定方向误差','保证可重复，但不复刻官方电磁环境']],[CW*.53,CW*.47])
sub('比较时为什么要使用相同案例')
p('两种方案面对同一批源，才知道省时是策略造成的，还是碰巧遇到了容易的案例。同一地点的误差在比较中保持一致；两种方案走到不同地点时，可能看到不同误差，这是轨迹差异的正常结果。')
p('先用旧案例做拆分比较，再固定程序与参数，用全新的种子验证。独立验证后没有继续按照这一批案例调参。新种子仍来自同一个生成方式，所以还需要压力案例与官方演练补充。')
note('最初基准阶段共250次运行。优化阶段共840次运行：旧案例拆分比较240次、新案例配对400次、压力案例配对200次。次数包含相同案例跑不同策略，不能把它们都称作独立新案例。')

begin('同一批旧案例上  改动分别值不值得')
p('下表使用原有每问40个案例。每个数先算“该局总时间÷清除数”，再在40局之间取平均。单位都是虚拟秒/源，越低越好。')
orig={(r['question'],r['strategy']):r for r in BASE['main']};dev={(r['question'],r['variant']):r for r in D}
table([['方案','第3问','第4问'],['B0  只测一次，再分格找',f"{orig[3,'sweep']['mean_case_average_s']:.2f}",f"{orig[4,'sweep']['mean_case_average_s']:.2f}"],['B1  每源两次测向',f"{dev[3,'B1']['mean_s']:.2f}",f"{dev[4,'B1']['mean_s']:.2f}"],['路线版  改顺序和侧移方向',f"{dev[3,'route']['mean_s']:.2f}",f"{dev[4,'route']['mean_s']:.2f}"],['共用测站版  在路线版上顺便测',f"{dev[3,'shared']['mean_s']:.2f}",f"{dev[4,'shared']['mean_s']:.2f}"]],[CW*.56,CW*.22,CW*.22])
sub('从表里能得到什么判断')
p('第一，增加第二次测向，比长时间盲目分格找更划算。B0到B1，第3问减少21.79%，第4问减少12.16%。')
p('第二，调整顺序与侧移方向之后，平均时间继续下降，相对B1分别减少6.25%和2.74%。')
p('第三，在路线版上共用测站，进一步下降。组合版相对B1减少7.49%和4.57%。说明多目标确实能利用一些共同的观察位置。')
note('这些是在旧案例上的比较，用来理解改动作用。推荐是否保留，主要还要看下一页的独立新案例，而不是只挑这一批上的最好数字。所有这些运行都清除了全部源。')
p('这里的“路线版”同时改变了目标顺序和左右测站选择，尚未进一步拆开两者各自的贡献。若后续要写“某个单一改动带来多少提升”，需要再做对应的单独对照。',small)

begin('新案例上  改善还能保留下来吗')
p('参数固定后，每问新增100个案例，原B1与共用测站版逐例配对。每问每个方案都清除了1310个源，没有漏源。')
fig(195,resultbars,'图11  新案例的平均虚拟秒/源。数值直接读取holdout_summary.json，未跨不同案例集合计算降幅。')
table([['题型','平均时间下降','变快的案例','P95 原方案→优化版'],['第3问','9.77%','90 / 100','921.63 → 887.14'],['第4问','5.59%','76 / 100','1251.31 → 1243.69']],[CW*.15,CW*.24,CW*.23,CW*.38])
p('P95表示把100局的每源时间从小到大排列，大约95%的案例不超过这个位置的数值。它帮助观察慢案例；不是所有情况的最大时间保证。第4问的P95改善很小，说明尾部难例仍需要处理。')
p('第3问平均移动耗时从600.65降到528.09秒/源，第4问从741.82降到685.61秒/源。总时间平均分别减少70.70和55.08秒/源，主要省在移动上。')
note('不要用这一页的653.11与旧案例上的764.71直接计算优化幅度，因为案例换了。本页的正确第3问对照是723.82与653.11。')

begin('优化为什么有时反而更慢')
p('新案例中，第3问有10例、第4问有24例变慢。最严重的是第4问种子20270961，10个源。原方案1251.15秒/源，优化版1454.73秒/源，增加203.58秒/源。我们没有把这例从结果中删掉。')
fig(230,real_paths,'图12  上述不利案例的真实行动路线。橙点是真实源，折线来自完整日志。公里数按移动耗时×5换算；仅用于事后解释，策略不能看真值。')
table([['增加的项目','这一局增加多少秒'],['移动','1336.80'],['检测与切换','312.00'],['光学寻找','387.00']],[CW*.64,CW*.36])
p('这说明问题不只是“顺便多测了几次”。处理顺序与侧移方向改变了之后的路径，也改变了在哪些点获得方向。某些定向源更容易失联，或者形成的剩余范围仍很长，于是移动与光学寻找一起变多。')
note('下一步不能只继续贪心选最近的目标。还应该看清除后停在哪里、下一站离哪里近，以及再补一次测向是否能避免一段长搜索。')

begin('哪些可靠性检查已经做过')
p('检查的不只是“程序跑完了”。每次运行都重新计算动作时间，核对每次成功清除的实际距离，确认没有重复成功，并检查保存的定位范围与包围圆是否包含真源。')
table([['检查内容','已经得到的结果'],['原基准阶段250次本地运行','全部清除，包含性与计时检查通过'],['优化阶段840次本地运行','全部清除，包含性与计时检查通过'],['边界、最小半径、聚簇、定向朝外、相关偏差','优化阶段200次压力配对运行通过'],['附录计时例、重复误差、5米和20米边界','专项检查通过'],['客户端超时重试、拒绝响应、剩余时长','3项不联网测试通过，未官方联调']],[CW*.54,CW*.46])
p('原基准还测试了不同误差幅度：当实际误差扩大时，同时把程序容许范围扩大，仍能完成清除。但如果实际误差达到1.5°，程序却只相信1.005°，就可能把真源排除。不能把“正确放宽误差界后的成功”解释成“误差界填错也没关系”。')
sub('能保证什么  不能保证什么')
p('在题目规定的静止源、有界误差、闭180°方向覆盖、无障碍移动和确定性20米清除规则下，覆盖站与方格兜底给出不漏源的理由。优化版每源附带检测次数有上限，因此不会无休止补测。')
p('默认参数下，优化版的宽松虚拟时间上界为178536秒，小于100小时限制。它不是实际平均时间，也不能保证网络一定让程序在现实20分钟内跑完。真实网络、官方分布和边界数值处理仍要通过官方演练核验。',small)

begin('下一轮怎样优化才容易看出原因')
p('建议先解决已经看到的变慢原因，再考虑更复杂的方法。每轮只改一小组相关规则，保留原版本，并换一批没有调过参数的新案例验证。')
table([['下一项改动','具体比较什么','怎样避免破坏可靠性'],['决定要不要再测一次','现在分格找的路程与尝试数，对比补测再清除的预计时间','预测只用于选动作，最终仍保留全部可能位置'],['目标顺序多看一步','处理当前目标后的位置，到下一个目标或检测站还要走多远','保持所有已发现源最终都被处理'],['减少最后的全域排查','对每个未发现频道，记录哪些区域已被可靠排除','整个可能区域被排除前不能宣布不存在'],['第4问利用正背面信息','哪些发射方向还与全部检测反馈相容','无信号包含多个原因，不能直接删一个近邻圆']],[CW*.23,CW*.4,CW*.37])
sub('用什么成绩判断是否保留新版本')
p('首先看清除比例和几何检查，不能用漏源换时间。然后一起看平均每源时间、P95、最大单局时间、变慢案例数、请求数以及电脑真实运行时间。最好保留每次移动、检测、清除的分项时间，才能知道到底省在哪里。')
note('目前已实现：覆盖搜索、两次测向、光学兜底、动态目标顺序、左右测站选择、多目标共用测站。尚未实现：按剩余时间决定追加测向、两步路线评分、按位置和方向排除未发现频道。')
p('新案例应继续来自独立种子；如果根据某批“独立验证”结果修改了参数，这批案例就变成了开发材料，下一版需要再换新的验证案例。',small)

begin('材料在哪里  如何核验与继续使用')
p('所有程序和结果在项目的analysis_b目录下。原题、两份附件和论文格式文件保留原样。报告图表使用保存的结果重新绘制，没有生成或代填官方案例编码。')
table([['文件或目录','用途'],['model.py / simulator.py','原策略与本地环境，真值只由环境持有'],['optimized.py','路线与共用测站的冻结实现'],['config.json / optimization_results/optimization_parameters.json','物理常量和本轮筛选参数'],['optimization_results/*.csv','每次运行、退步案例及各项耗时'],['optimization_results/*_logs.jsonl.gz','完整本地源真值、行动与定位范围'],['results/ 与两份 Markdown 报告','第一阶段数值、详细推导及优化试验说明']],[CW*.53,CW*.47])
sub('重新计算优化比较')
p('在项目根目录，用已安装NumPy、SciPy、Pillow的Python运行。当前计算解释器是F:/Python/python.exe，完整命令见优化试验报告。下面三项依次运行即可重建开发、独立与压力比较。',small)
for phase in ['development','holdout','stress']:
    p(f'python analysis_b/optimize_experiments.py --phase {phase}',ParagraphStyle('code',fontName='Code',fontSize=8.1,leading=12,textColor=INK),gap=5)
y-=10
sub('引用与下一阶段')
p('[1] B题.pdf，4页：题目、源特征、设备规则及测试要求。<br/>[2] 附件1.docx《模拟器使用说明》：动作计时、操作、登录与日志。<br/>[3] 附件2.docx《模拟器通信接口说明及编程指南》：接口字段、反馈、重试与时限。<br/>[4] format2026.doc：最终论文及支撑材料的格式要求。',small)
p('这些文件均来自用户提供目录，其SHA-256保存在source_extract/manifest.json。数值来源的哈希另存于pdf_work/report_data.json。图中自构几何示例与实际日志有明确区分。',small)
note('正式成绩仍空缺。下一阶段应先完成官方演练，再进行题目要求的每问三次正式测试，导出原名加密日志。题目规定2026年9月13日17:30后不能启动新测试，建议15:30前完成正式测试。[1][2]')

finish();c.save()
(WORK/'layout_manifest.json').write_text(json.dumps({'pdf':str(PATH),'pages':pages,'page_count':page},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pdf':str(PATH),'pages':page,'min_content_y':min(p['bottom_content_y'] for p in pages)},ensure_ascii=False))
