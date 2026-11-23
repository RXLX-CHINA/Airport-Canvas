"""CAAC MH5001 section 6.2 pavement-marking families and editable templates.

Catalog coverage is not certification: placement conditions, figure variants and
aircraft/site-specific dimensions remain separately reviewable.
"""
import math

# Two 0.15 m edge stripes with centers 0.075 and 0.375 m from the edge.
TAXI_MARKING_EDGE_CLEARANCE = .55
import re
import scene_geometry as g
from pavement_geometry import offset

WHITE='#ffffff';YELLOW='#ffdb64';RED='#cf383e';BLACK='#151a20'
CATALOG={}

EDITABLE_FIELDS={
 'line':{'line_width'},'dash':{'line_width'},'rwy_center':{'line_width'},'double':{'line_width','spacing'},'wingtip':{'line_width','spacing'},'stagger':{'line_width'},
 'rwy_number':{'text','text_height'},'threshold':{'width'},'arrow':{'width'},'arrow_heads':{'width'},'aim':set(),'tdz':{'width'},
 'circle':{'width','line_width'},'bridge_home':{'width','line_width'},'vor':{'width','line_width'},'chevrons':{'width','line_width'},'enhanced':{'line_width'},
 'hold_a':{'width'},'hold_b':{'width'},'stand_number':{'text','text_height'},
 'red_label':{'text','text_height','background'},'black_label':{'text','text_height','background'},'yellow_label':{'text','text_height','background'},
 'lead_a':{'width','line_width'},'lead_b':{'width','line_width'},'lead_c':{'width','line_width','text'},'lead_d':{'width','line_width','text'},
 'turn_start':{'width','line_width'},'stop':{'width','line_width'},'push_wait':{'width','line_width'},'unguided_stop':{'width','line_width'},
 'shoulder_bars':{'width','spacing','line_width'},'red_hatch':{'line_width','spacing','text','text_height'},'white_hatch':{'line_width','spacing','text','text_height'},
 'white_area':{'line_width','text','text_height'},'temp_wait':{'line_width','text','text_height'},'pallets':{'line_width','spacing','text','text_height'},
 'chocks':{'width','text','text_height'},'hydrant':{'width','text','text_height'},'pit':{'width','line_width','text','text_height'},'zebra':{'width','crossing_depth14','stripe_width14','spacing'},'road_stop':{'width','line_width'},
 'speed':{'width','line_width','text','text_height'},'closed_rwy':{'width','line_width'},'closed_twy':{'width','line_width'},'blast':{'width','text','text_height'},
 'safety':{'line_width'},'road_edge':{'line_width'},'pushback':{'line_width'},
}
def register(key,name,group,clause,mode='PATH',shape='line',**defaults):
    CATALOG[key]=dict(id=key,name=name,group=group,clause=clause,mode=mode,shape=shape,
        status='PARAMETRIC_TEMPLATE',review='放置条件、图内细节及场地相关参数需结合原文核对。',
        defaults=dict(line_width=.15,text_height=4.,spacing=2.,width=18.,text='',**defaults))

# Independent drawing tools for each family/major variant, not review placeholders.
def add(key,name,group,clause,mode,shape,defaults=None):
    d=dict(line_width=.15,text_height=4.,spacing=2.,width=18.,text='');d.update(defaults or {})
    CATALOG[key]=dict(id=key,name=name,group=group,clause=clause,mode=mode,shape=shape,
        status='PARAMETRIC_TEMPLATE',review='参数化绘制；适用条件、图中细节和专项数据见独立审阅。',defaults=d)

for row in [
 ('RWY_NUMBER','跑道号码','跑道标记','6.2.2','POINT','rwy_number',{'text':'09','text_height':9}),
 ('RWY_CENTER','跑道中线','跑道标记','6.2.3','PATH','rwy_center',{'line_width':.9}),
 ('RWY_CIRCLE','跑道中心圆','跑道标记','6.2.3(5)','POINT','circle',{'width':22.5,'line_width':.9}),
 ('RWY_THRESHOLD','入口条纹','跑道标记','6.2.4','POINT','threshold',{'width':45}),
 ('THRESHOLD_BAR','内移入口横线','跑道标记','6.2.4(4)','PATH','line',{'line_width':1.8}),
 ('DISPLACED_ARROW','内移长箭头','跑道标记','6.2.4','POINT','arrow',{'width':4,'line_width':1}),
 ('THRESHOLD_HEADS','临时入口箭头列','跑道标记','6.2.4 表6.2.4-2','POINT','arrow_heads',{'width':45,'line_width':1}),
 ('AIMING_POINT','瞄准点','跑道标记','6.2.5','POINT','aim',{'width':45,'lda':2400}),
 ('TDZ_BASIC','接地带基本型','跑道标记','6.2.6','POINT','tdz',{'width':22.5,'coded':False}),
 ('TDZ_CODED','接地带距离编码','跑道标记','6.2.6','POINT','tdz',{'width':22.5,'coded':True,'bars':3}),
 ('RWY_EDGE','跑道边线','跑道标记','6.2.7','PATH','line',{'line_width':.9}),
 ('PRETHRESHOLD','入口前黄色折线','跑道标记','6.2.25','POINT','chevrons',{'width':45,'line_width':.9}),
 ('VOR','VOR校准圆','跑道标记','6.2.26','POINT','vor',{'width':6,'line_width':.15,'directional':False}),
 ('VOR_DIRECTION','VOR方向校准','跑道标记','6.2.26','POINT','vor',{'width':6,'directional':True}),
 ('TWY_CENTER','滑行中线','滑行道标记','6.2.8','PATH','line',{}),
 ('TWY_ENHANCED','增强型中线','滑行道标记','6.2.8(6)','PATH','enhanced',{}),
 ('TURN_PAD_GUIDE','掉头坪引导线','滑行道标记','6.2.9','PATH','line',{}),
 ('HOLD_A','跑道等待 A型','滑行道标记','6.2.10','POINT','hold_a',{'width':23,'line_width':.3}),
 ('HOLD_B','跑道等待 B型','滑行道标记','6.2.10','POINT','hold_b',{'width':23,'line_width':.3}),
 ('INTERMEDIATE','中间等待位置','滑行道标记','6.2.11','PATH','dash',{'line_width':.3,'dash':.9,'gap':.9}),
 ('MANDATORY','强制指令文字','滑行道标记','6.2.12','POINT','red_label',{'text':'09-27'}),
 ('NO_ENTRY','禁止进入','滑行道标记','6.2.12(6) 修订案IV','POINT','red_label',{'text':'NO ENTRY'}),
 ('LOCATION','位置文字','滑行道标记','6.2.13','POINT','black_label',{'text':'A'}),
 ('DIRECTION','目的地与方向标识','滑行道标记','6.2.13','POINT','yellow_label',{'text':'APRON →'}),
 ('MAX_SPAN','最大翼展','滑行道标记','6.2.13(6)','POINT','black_label',{'text':'MAX SPAN 36 m'}),
 ('HP','滑行位置识别点','滑行道标记','6.2.13(7)','POINT','black_label',{'text':'HP 1'}),
 ('TWY_EDGE','滑行双边线','滑行道标记','6.2.14','PATH','double',{'spacing':.15}),
 ('TWY_SHOULDER','滑行道道肩条带','滑行道标记','6.2.15','PATH','shoulder_bars',{'width':7.5,'spacing':15,'line_width':.9}),
 ('STAND_NUMBER','机位编号','机位与推出','6.2.16(4) 图6.2.16-2','POINT','stand_number',{'text':'101','text_height':4,'width':5}),
 ('LEAD_IN','机位引入线','机位与推出','6.2.16(5)','PATH','line',{}),
 ('LEAD_IN_A','A型引入线','机位与推出','图6.2.16-3','POINT','lead_a',{'width':20}),
 ('LEAD_IN_B','B型引入线','机位与推出','图6.2.16-4','POINT','lead_b',{'width':20}),
 ('LEAD_IN_C','C型引入线','机位与推出','图6.2.16-5','POINT','lead_c',{'width':20}),
 ('LEAD_IN_D','D型引入线','机位与推出','图6.2.16-6','POINT','lead_d',{'width':20}),
 ('TURN_START','转弯开始线','机位与推出','6.2.16(5)','POINT','turn_start',{'width':6}),
 ('ALIGNMENT','机位对准线','机位与推出','6.2.16(6)','PATH','line',{}),
 ('STAND_STOP','引导机位停止线','机位与推出','6.2.16(7)','POINT','stop',{'width':2}),
 ('UNGUIDED_STOP','无引导停止标志','机位与推出','图6.2.16-8','POINT','unguided_stop',{'width':6,'text':'STOP','text_height':2}),
 ('AUX_LEAD','辅助机位引入线','机位与推出','6.2.16(8)','PATH','dash',{'dash':2,'gap':2}),
 ('LEAD_OUT','机位引出线','机位与推出','6.2.16(5)','PATH','line',{}),
 ('PUSHBACK','飞机推出线','机位与推出','6.2.16(9)','PATH','pushback',{'dash':1,'gap':1}),
 ('PUSH_WAIT','推出等待点','机位与推出','图6.2.16-10','POINT','push_wait',{'width':1}),
 ('STAND_SAFETY','机位安全线','机坪安全与设备','6.2.18','PATH','safety',{'line_width':.1}),
 ('SAFETY_OVERLAP','安全线交叉区域','机坪安全与设备','6.2.18(5)','AREA','red_hatch',{'line_width':.1,'spacing':2}),
 ('WINGTIP','翼尖净距双线','机坪安全与设备','6.2.19','PATH','wingtip',{'line_width':.15,'spacing':.1}),
 ('CHOCKS','轮挡放置区','机坪安全与设备','6.2.20(2)','POINT','chocks',{'width':1,'text':'轮挡','text_height':.5}),
 ('WORK_WAIT','常规作业等待区','机坪安全与设备','6.2.20(3)','AREA','white_hatch',{'line_width':.1,'spacing':2}),
 ('TEMP_WAIT','临时作业等待区','机坪安全与设备','6.2.20(3)','AREA','temp_wait',{'line_width':.1,'text':'临时作业等待区','text_height':1}),
 ('BRIDGE_AREA','廊桥活动区','机坪安全与设备','6.2.20(4)','AREA','red_hatch',{'line_width':.1,'spacing':2}),
 ('BRIDGE_HOME','廊桥回位圆','机坪安全与设备','6.2.20(4)','POINT','bridge_home',{'width':3,'line_width':.1}),
 ('EQUIPMENT_ZONE','设备摆放区','机坪安全与设备','6.2.20(5)','AREA','white_area',{'text':'设备区','text_height':.8}),
 ('VEHICLE_PARK','特种车辆停车位','机坪安全与设备','6.2.20(6)','AREA','white_area',{'text':'车辆','text_height':.8}),
 ('PALLETS','集装箱托盘摆放区','机坪安全与设备','6.2.20(7)','AREA','pallets',{'spacing':2}),
 ('TRANSFER','车辆中转区','机坪安全与设备','6.2.20(8)','AREA','white_area',{'text':'车辆中转区','text_height':.8}),
 ('HYDRANT','消防栓井','机坪安全与设备','6.2.22','POINT','hydrant',{'width':1,'text':'H1','text_height':.2}),
 ('PIT','其他桩井','机坪安全与设备','6.2.22','POINT','pit',{'width':1,'line_width':.2,'text':'J1','text_height':.2}),
 ('ROAD_EDGE','服务车道边线','道路与限制使用','6.2.23','PATH','road_edge',{'line_width':.15}),
 ('ROAD_STAGGER','穿越滑行道交错线','道路与限制使用','6.2.23(3)','PATH','stagger',{'line_width':.15,'dash':.75,'gap':.75}),
 ('PEDESTRIAN','行人步道','道路与限制使用','6.2.21','POINT','zebra',{'width':3,'spacing':.6}),
 ('ROAD_STOP','道路等待停止线','道路与限制使用','6.2.23(2)','POINT','road_stop',{'width':6,'line_width':.3,'text':'停','text_height':2.5}),
 ('SPEED','道路限速','道路与限制使用','6.2.23(4)','POINT','speed',{'width':1.5,'text':'25','text_height':1}),
 ('CLOSED_RWY','跑道关闭 X','道路与限制使用','6.2.24','POINT','closed_rwy',{'width':14.5,'line_width':1.8}),
 ('CLOSED_TWY','滑行道关闭 X','道路与限制使用','6.2.24','POINT','closed_twy',{'width':9,'line_width':1.5}),
 ('JET_BLAST','喷气尾流警示','道路与限制使用','6.2.27','POINT','blast',{'width':.7,'text_height':.12,'text':'小心尾流'}),
]:add(*row)

from apron_markings import extend_catalog
extend_catalog(add,CATALOG,EDITABLE_FIELDS)

add('INTERMEDIATE_POINT','中间等待位置点','滑行道标记','6.2.11','POINT','intermediate_point',{'width':23,'line_width':.3,'dash':.9,'gap':.9})
CATALOG['HOLD_B']['name']='B型跑道等待位置'
for key in ('HOLD_A','HOLD_B'):
    CATALOG[key]['defaults']['background']=False
EDITABLE_FIELDS['hold_a'].add('background');EDITABLE_FIELDS['hold_b'].add('background')
CATALOG['INTERMEDIATE']['name']='中间等待位置线'
CATALOG['PRETHRESHOLD']['name']='入口前不适用铺筑面'
CATALOG['PRETHRESHOLD']['extra_fields']=[('surface_length','铺筑面长度 m','float',90),('surface_color','底色 #RRGGBB','text','#655e50')]
CATALOG['PRETHRESHOLD']['defaults'].update(surface_length=90,surface_color='#655e50')
EDITABLE_FIELDS['intermediate_point']={'width','line_width'}

CATALOG['ROAD_STOP']['extra_fields']=[('red_background','停字红色底色','bool',False)]
CATALOG['HOLD_B']['extra_fields']=[('category','ILS类别（CAT II / CAT III）','text','CAT II')]
CATALOG['HOLD_B']['defaults']['category']='CAT II'

CATALOG['MAX_SPAN'].update(shape='max_span',extra_fields=[('maxspan','允许最大翼展 m','float',36)])
CATALOG['MAX_SPAN']['defaults'].update(maxspan=36)
CATALOG['ROAD_STOP']['defaults']['red_background']=True
CATALOG['ROAD_STOP']['extra_fields']=[('red_background','停字红色矩形底色','bool',True)]
EDITABLE_FIELDS['max_span']={'text_height','background'}
EDITABLE_FIELDS['helipad']={'width','line_width','text_height'}
register('HELI_SAFETY','直升机位安全线','直升机位安全线','机坪安全与设备','PATH','heli_safety',color='#2580cf')
register('HELIPAD','直升机坪','直升机坪','项目绘图','POINT','helipad',color=WHITE)
CATALOG['HELIPAD']['defaults'].update(width=24.,line_width=.3,text_height=4.)

def dashed_polyline(points,dash,gap):
    total=g.length(points);pos=0
    while pos<total:
        yield g.subpath(points,pos,min(total,pos+dash));pos+=dash+gap

def hatch_segments(poly,pitch=2,angle=45,phase=None):
    a=math.radians(angle);u=(math.cos(a),math.sin(a));v=(-u[1],u[0])
    local=[[x*u[0]+y*u[1],x*v[0]+y*v[1]] for x,y in poly]
    lo=min(q[1] for q in local);hi=max(q[1] for q in local);left=min(q[0] for q in local)-1;right=max(q[0] for q in local)+1
    start=lo if phase is None else math.floor(lo/pitch)*pitch+phase%pitch
    count=math.ceil((hi-start)/max(.1,pitch))
    if count>3000:raise ValueError('Hatch exceeds 3000 strips; increase spacing or reduce area')
    for i in range(count+1):
        y=start+i*pitch;hits=[]
        for p,q in zip(local,local[1:]+local[:1]):
            if (p[1]<=y<q[1]) or (q[1]<=y<p[1]):hits.append(p[0]+(y-p[1])*(q[0]-p[0])/(q[1]-p[1]))
        hits.sort()
        for x0,x1 in zip(hits[::2],hits[1::2]):
            yield [[x0*u[0]+y*v[0],x0*u[1]+y*v[1]],[x1*u[0]+y*v[0],x1*u[1]+y*v[1]]]

add('ROAD_DIVIDER','车道分界线','道路与限制使用','6.2.23','PATH','dash',dict(color=WHITE,line_width=.15,dash=3,gap=3))
add('ROAD_ARROW','行车方向箭头','道路与限制使用','项目道路设计','POINT','road_arrow',dict(width=3))

def primitives(asset):
    if asset['props'].get('information_profile20_18'):return __import__('directions20_18').primitives(asset)
    p=asset['props'];spec=CATALOG[p['mark_type']];shape=spec['shape'];pts=asset['points'];oid=asset['id'];out=[]
    if spec.get('renderer')=='apron':
        from apron_markings import render_apron
        return render_apron(asset,spec)
    origin=pts[0];u=g.unit(pts[0],pts[-1]);v=(-u[1],u[0]);angle=math.degrees(math.atan2(u[1],u[0]))
    width=p.get('width',18);lw=p.get('line_width',.15);height=p.get('text_height',4);color=p.get('color') or (WHITE if p['mark_type'].startswith('RWY') or p['mark_type']=='THRESHOLD_BAR' else YELLOW)
    def xy(x,y):return [origin[0]+u[0]*x+v[0]*y,origin[1]+u[1]*x+v[1]*y]
    def stroke(points,c=YELLOW,w=lw,dash=None,local=False):out.append(dict(type='line',oid=oid,points=[xy(*q) for q in points] if local else points,stroke=c,width=w,dash=dash))
    def poly(points,fill=None,c=None,w=lw,local=False,dash=None):out.append(dict(type='polygon',oid=oid,points=[xy(*q) for q in points] if local else points,fill=fill,stroke=c,width=w,dash=dash))
    def box(x0,y0,x1,y1,fill=None,c=None,w=lw):poly([[x0,y0],[x1,y0],[x1,y1],[x0,y1]],fill,c,w,True)
    def text(value,x=0,y=0,c=YELLOW,h=height,font='normal',text_width=None,rotation=None):
        out.append(dict(type='text',oid=oid,points=[xy(x,y)],text=str(value),fill=c,size=h,rotation=angle-90 if rotation is None else rotation,font=font,world_text=True,text_width=text_width))
    def circle(cx,cy,r,c=WHITE,w=lw,fill=None):poly([[cx+r*math.cos(t*math.pi/48),cy+r*math.sin(t*math.pi/48)] for t in range(96)],fill,c,w,True)
    def arrow(x,y,l=30,w=4,c=WHITE):
        stroke([[x,y],[x-l+10,y]],c,.3,local=True);stroke([[x-12,y-w/2],[x,y],[x-12,y+w/2]],c,1,local=True)
    if shape in ('line','dash','safety','road_edge','pushback'):
        c=WHITE if p['mark_type']=='THRESHOLD_BAR' else RED if shape=='safety' else WHITE if shape in ('road_edge','pushback') else color
        if shape=='safety' and p.get('helicopter_safety'):
            stroke(pts+[pts[0]],WHITE,.55)
            stroke(pts+[pts[0]],'#2580cf',.28)
            return out
        if shape=='safety' and p.get('ga_frame_color'):
            for color,width in ((p['ga_outline_color'],.55),(p['ga_frame_color'],.25)):
                for index,(a,b) in enumerate(zip(pts,pts[1:]+pts[:1])):
                    stroke([a,b],color,width)
                    out[-1]['ga_longitudinal_edge']=index in (1,3)
            return out
        if shape=='safety' and p.get('open_stand_nose58') and len(pts)==8:
            stroke(pts[:4],c,lw)
            stroke(pts[4:],c,lw)
        else:
            stroke(pts,c,lw,[p.get('dash') or 1,p.get('gap',1)] if shape in ('dash','pushback') or p.get('dash') else None)
        if shape=='safety':out[-1]['continuous_safety14']=True
    elif shape=='road_arrow':
        from roads11 import arrow as road_arrow
        out.append(road_arrow(oid,origin,u,width=width,length=p.get('arrow_length',4.)))
    elif shape=='heli_safety':
        stroke(pts,'#2580cf',lw)
    elif shape=='helipad':
        circle(0,0,width/2,c=YELLOW,w=lw)
        text('H',c=YELLOW,h=min(height,width*.35))
        if p.get('number'):
            text(p['number'],x=-width*.65,c=YELLOW,h=min(height,width*.19))
    elif shape=='rwy_center':
        from runway import centerline_geometry
        count,segment,gap=centerline_geometry(g.length(pts))
        for i in range(count):stroke(g.subpath(pts,i*(segment+gap),min(g.length(pts),i*(segment+gap)+segment)),WHITE,lw)
    elif shape in ('double','wingtip','stagger'):
        gap=0 if shape=='stagger' else p.get('spacing',.15);d=(gap+lw)/2;c=WHITE if shape in ('wingtip','stagger') else YELLOW
        for side in (-1,1):
            path=offset(pts,side*d)
            if shape=='stagger':
                total=g.length(path);pos=0 if side<0 else p.get('dash',.75)
                while pos<total:
                    stroke(g.subpath(path,pos,min(total,pos+p.get('dash',.75))),c,lw);pos+=p.get('dash',.75)+p.get('gap',.75)
            else:stroke(path,c,lw)
    elif shape=='enhanced':
        stroke(pts,YELLOW,lw)
        out[-1]['enhanced_axis21_2']=True
        for side in (-1,1):stroke(offset(pts,side*.3),YELLOW,.15,[3,1])
    elif shape=='rwy_number':
        match=re.fullmatch(r'(\d{2})([LRC]?)',p.get('text','09').upper())
        number,suffix=match.groups() if match else (p.get('text','09'),'')
        text(number,0,0,WHITE,height,'caac')
        if suffix:text(suffix,-height*15/9,0,WHITE,height,'caac')
    elif shape=='threshold':
        from runway import threshold_geometry
        n,sw=threshold_geometry(width)
        for side in (-1,1):
            for j in range(n//2):
                y=side*(1.5*sw+j*2*sw);box(0,y-sw/2,45,y+sw/2,WHITE)
    elif shape in ('arrow','arrow_heads'):
        if shape=='arrow':arrow(30,0,w=width)
        else:
            count={18:3,23:3,30:4,45:5,60:7}.get(width,5)
            for i in range(count):
                y=(i-(count-1)/2)*width/count;stroke([[-12,y-2],[0,y],[-12,y+2]],WHITE,1,local=True)
    elif shape=='aim':
        from runway import aim_dimensions
        _,l,w,sep=aim_dimensions(p.get('lda',2400),p.get('aim_width'),p.get('aim_gap'),p.get('aim_length'))
        for side in (-1,1):
            a,b=sorted((side*sep/2,side*(sep/2+w)));box(0,a,l,b,WHITE)
    elif shape=='tdz':
        bars=max(1,min(3,int(p.get('bars',3)))) if p.get('coded') else 1;w=1.8 if p.get('coded') else 3
        for side in (-1,1):
            for j in range(bars):
                a,b=sorted((side*(width/2+j*(w+1.5)),side*(width/2+j*(w+1.5)+w)));box(0,a,22.5,b,WHITE)
    elif shape in ('circle','bridge_home'):circle(0,0,max(.001,(width-lw)/2),RED if shape=='bridge_home' else WHITE,lw)
    elif shape=='vor':
        circle(0,0,(width-lw)/2,WHITE,lw)
        if p.get('directional'):
            tip=width/2+6
            stroke([[-width/2,0],[tip,0]],WHITE,.15,local=True)
            poly([[tip,0],[tip-2,-.25],[tip-2,.25]],WHITE,local=True)
    elif shape=='chevrons':
        length=p.get('surface_length',90);box(0,-width/2,length,width/2,p.get('surface_color','#c7cbd0'))
        if length>=60:
            x=width/2
            while x<=length-6:
                stroke([[x-width/2,-width/2],[x,0],[x-width/2,width/2]],YELLOW,max(.9,lw),local=True)
                x+=30
        elif length>0 and p.get('short_stopway_chevrons'):
            depth=min(width/2,length*.65)
            margin=(length-depth)/2
            weight=min(max(.9,lw),margin,width/4)
            span=min(width/2-weight/2,depth)
            stroke([[margin,-span],[margin+depth,0],[margin,span]],YELLOW,weight,local=True)
    elif shape=='intermediate_point':stroke([xy(0,-width/2),xy(0,width/2)],YELLOW,.3,[.9,.9])
    elif shape in ('hold_a','hold_b'):
        if p.get('background',False):box(-1.15,-width/2-.1,1.15,width/2+.1,BLACK)
        if shape=='hold_a':
            for x in (-.9,-.3,.3,.9):stroke([[x,-width/2],[x,width/2]],YELLOW,.3,[.9,.9] if x>0 else None,True)
        else:
            for x in (-.9,.9):stroke([[x,-width/2],[x,width/2]],YELLOW,.3,local=True)
            y=-width/2
            while y<width/2:
                for d in (0,.6):
                    if y+d<width/2:box(-.9,y+d,.9,min(width/2,y+d+.3),YELLOW)
                y+=3.9
            if width>60:
                intervals=math.ceil(width/45)
                for i in range(intervals+1):
                    text(p.get('category','CAT II'),-2.05,-width/2+width*i/intervals,YELLOW,1.8)
    elif shape=='max_span':
        # Fig.6.2.13-3: two 4 m character rows inside a 9.5 m long board.
        match=re.search(r'(\d+(?:\.\d+)?)',p.get('text',''))
        span=p.get('maxspan',float(match.group(1)) if match else 36)
        # Legacy files stored the limit in text only; keep that information.
        if p.get('text') and p.get('maxspan',36)==36 and match:span=float(match.group(1))
        h=height;body=9.5*h/4;tw=max(7*h*.4,len(f'{span:g} m')*h*.4)+1
        if p.get('background',True):box(-body/2,-tw/2,body/2,tw/2,BLACK,YELLOW,.1)
        else:box(-body/2,-tw/2,body/2,tw/2,None,YELLOW,.1)
        text('MAX SPAN',body/4,0,YELLOW,h,text_width=7*h*.4)
        value=f'{span:g} m';text(value,-body/4,0,YELLOW,h,text_width=len(value)*h*.4)
    elif shape.endswith('_label'):
        fg,bg=(WHITE,RED) if shape=='red_label' else (YELLOW,BLACK) if shape=='black_label' else (BLACK,YELLOW)
        values=[value.strip() for value in p.get('text','').replace('\n',' / ').split(' / ')];margin=p.get('margin',.5);tw=max(height*.4,max(len(value) for value in values)*height*p.get('character_ratio',.4));body=len(values)*height+(len(values)-1)*.5
        panel = max(tw+2*margin,p.get('mandatory_panel_width',0))
        if p.get('background',True):box(-body/2-margin,-panel/2,body/2+margin,panel/2,bg,fg,.05)
        for i,value in enumerate(values):text(value,body/2-height/2-i*(height+.5),0,fg,height,text_width=max(height*.4,len(value)*height*p.get('character_ratio',.4)))
    elif shape=='stand_number':
        # 4 m character height, 5 m body and 2 m arrowhead, 0.1 m black border.
        h=height
        value=str(p.get('text','101'))
        body=p.get('body_length',5*h/4)
        head=p.get('head_length',2*h/4)
        glyph_width=max(1,len(value))*h*.4
        half=max(h,glyph_width)/2+.5
        poly([[-body/2,-half],[body/2,-half],[body/2+head,0],[body/2,half],[-body/2,half]],YELLOW,BLACK,.1,True)
        text(value,0,0,BLACK,h,text_width=glyph_width,rotation=angle-90+p.get('text_rotation_offset',0))
    elif shape.startswith('lead_'):
        from stand_profiles import lead_design
        design=lead_design(dict(name=p.get('text') or '101',points=[[0,0],[max(100,width*4),0]],props=dict(lead_type=shape[-1].upper(),lead_radius=width,stand_number=p.get('text') or '101')))
        for part in design['paths']:stroke(part['points'],YELLOW,lw,local=True)
        for n in design['numbers']:
            position=n['point'];direction=n['direction'];anchor=xy(*position);target=[anchor[k]+(u[k]*direction[0]+v[k]*direction[1])*10 for k in (0,1)]
            label=dict(id=oid,points=[anchor,target],props=dict(mark_type='STAND_NUMBER',text=p.get('text') or '101',text_height=4,width=5,text_rotation_offset=n['text_rotation_offset']))
            out.extend(primitives(label))
    elif shape in ('turn_start','stop','push_wait','unguided_stop'):
        c=WHITE if shape=='push_wait' else YELLOW
        span=2 if shape=='unguided_stop' else width
        if shape=='unguided_stop':lw=max(.15,min(.3,lw))
        stroke([[0,-span/2],[0,span/2]],c,max(.15,lw),local=True)
        if shape=='push_wait':stroke([[-1,0],[0,0]],c,max(.15,lw),local=True)
        if shape=='stop' and p.get('stop_shape','T')!='BAR':stroke([[-2,0],[2 if p.get('stop_shape')=='CROSS' else 0,0]],c,max(.15,lw),local=True)
        if shape=='turn_start':stroke([[0,width/2-2],[0,width/2],[-2,width/2]],c,lw,local=True)
        if shape=='unguided_stop':
            board_length=p.get('stop_board_length14',6);board_offset=p.get('stop_board_offset',11)-board_length
            stroke([[0,board_offset],[0,board_offset+board_length]],YELLOW,max(.15,lw),local=True)
            box(.1,board_offset+board_length-2.5,2.6,board_offset+board_length,BLACK)
            text('STOP',1.35,board_offset+board_length-1.25,YELLOW,2,text_width=2.5)
            stroke([[-2,0],[2,0]],YELLOW,max(.15,lw),local=True)
        if shape in ('stop','unguided_stop'):
            codes=(p['aircraft_types'] if p.get('aircraft_types') is not None else p.get('aircraft','').replace(',',' ').split());h=p.get('aircraft_height',.2)
            for i,code in enumerate(codes):
                text(code,-max(.15,lw)/2-.05-h/2-i*(h+.05),span/2+.1+len(code)*h*.2,YELLOW,h,font='stencil',text_width=len(code)*h*.4,rotation=angle+(90 if p.get('aircraft_outward',True) else -90))
                out[-1]['aircraft_label']=True
    elif shape=='shoulder_bars':
        total=g.length(pts);spacing=p.get('spacing',15);s=0
        while s<=total:
            q,t=g.at(pts,s);n=(-t[1],t[0]);stroke([q,[q[0]+n[0]*width,q[1]+n[1]*width]],YELLOW,lw);s+=max(1,spacing)
    elif shape in ('red_hatch','white_hatch','white_area','temp_wait','pallets'):
        c=RED if shape=='red_hatch' else WHITE
        if not p.get('omit_outline',False):poly(pts,None,c,lw,dash=[1,.5] if shape=='temp_wait' else [.5,1] if p['mark_type']=='SAFETY_OVERLAP' else None)
        if shape in ('red_hatch','white_hatch','pallets'):
            angle=p.get('hatch_angle',math.degrees(math.atan2(pts[1][1]-pts[0][1],pts[1][0]-pts[0][0]))+(0 if shape=='pallets' else 45))
            for segment in hatch_segments(pts,p.get('spacing',2)+(lw if shape in ('red_hatch','white_hatch') else 0),angle,p.get('hatch_phase')):stroke(segment,c,lw)
        if p.get('text'):
            center=[sum(q[k] for q in pts)/len(pts) for k in (0,1)];out.append(dict(type='text',oid=oid,points=[center],text=p['text'],fill=c,size=height,rotation=0,world_text=True,font='hei'))
    elif shape=='chocks':box(-width/2+.075,-width/2+.075,width/2-.075,width/2-.075,None,WHITE,.15);text(p.get('text','轮挡'),0,0,WHITE,height,font='hei',rotation=angle+90,text_width=max(.1,min(width-.3,len(p.get('text','轮挡'))*height*.65)))
    elif shape in ('hydrant','pit'):
        if shape=='hydrant':
            from pavement_geometry import subtract_convex
            r=(width+.4)/2
            cover=[[width/2*math.cos(t*math.pi/48),width/2*math.sin(t*math.pi/48)] for t in range(96)]
            for piece in subtract_convex([[-r,-r],[r,-r],[r,r],[-r,r]],cover):poly(piece,RED,local=True)
        else:circle(0,0,(width+.4-lw)/2,RED,lw)
        if p.get('text'):text(p['text'],(width+.4)/2+.2+height/2,0,WHITE,height)
    elif shape=='zebra':
        depth=p.get('crossing_depth14',4.);stripe=p.get('stripe_width14',.4);gap=p.get('spacing',.6);step=max(.1,stripe+gap);y=-width/2
        while y<width/2-1e-7:
            y1=min(width/2,y+stripe);shear=math.tan(math.radians(p.get('crossing_skew13',0)))
            poly([[-depth/2+y*shear,y],[depth/2+y*shear,y],[depth/2+y1*shear,y1],[-depth/2+y1*shear,y1]],WHITE,local=True);out[-1]['crossing_stripe17']=True;y+=step
    elif shape=='road_stop':
        stroke([[0,-width/2],[0,width/2]],WHITE,lw,local=True)
        if p.get('red_background',True):box(-4.75,-1,-1.25,1,RED)
        text(p.get('text','停'),-3,0,WHITE,2.5,text_width=1)
    elif shape=='speed':
        circle(0,0,(width-lw)/2,RED,lw,WHITE)
        fit=math.sqrt(max(.01,(width-2*lw-.04)**2-height**2))
        text(p.get('text','25'),0,0,BLACK,height,text_width=min(width-2*lw,fit))
    elif shape in ('closed_rwy','closed_twy'):
        c=WHITE if shape=='closed_rwy' else YELLOW
        if shape=='closed_rwy':
            length=36*width/14.5;bar=1.8*width/14.5
            # Horizontal end cuts keep the complete painted envelope 36 x 14.5.
            thickness=bar
            for _ in range(12):thickness=bar*math.sqrt(1+((width-thickness)/length)**2)
            for side in (-1,1):
                poly([[-length/2,side*(-width/2)],[-length/2,side*(-width/2+thickness)],[length/2,side*(width/2)],[length/2,side*(width/2-thickness)]],c,local=True)
        else:
            # 9 m along each diagonal, 1.5 m strip width (not a 9 x 3.75 bounding box).
            bar=width/6
            for side in (-1,1):
                a=[-width/(2*math.sqrt(2)),-side*width/(2*math.sqrt(2))];b=[-a[0],-a[1]]
                poly(g.rectangle([a,b],bar),c,local=True)
    elif shape=='blast':
        # Fig.6.2.27: 700 mm high equilateral red field, inset 4 mm white line,
        # two text rows and a nozzle with radiating white jet strokes.
        half=width/math.sqrt(3);triangle=[[width/2,0],[-width/2,-half],[-width/2,half]]
        poly(triangle,RED,local=True)
        center=-width/6;ratio=max(.1,1-.02/(width/3))
        poly([[center+(x-center)*ratio,y*ratio] for x,y in triangle],None,WHITE,.004,True)
        value=p.get('text','小心尾流');cut=math.ceil(len(value)/2)
        for i,row in enumerate((value[:cut],value[cut:])):text(row,width*(.08-.18*i),0,WHITE,min(height,width*.15),font='hei',text_width=width*.45)
        poly([[-width*.35,-width*.24],[-width*.35,width*.04],[-width*.28,width*.12],[-width*.20,width*.04],[-width*.20,-width*.24]],WHITE,local=True)
        for spread in (-.10,0,.10):stroke([[-width*.275,width*.12],[-width*(.275+spread),width*.28]],WHITE,.008,local=True)
    else:raise ValueError('Template has no renderer: '+shape)
    return out
