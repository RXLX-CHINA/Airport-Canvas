"""Detailed apron variants from MH5001 section 6.2.18--6.2.22."""
import math
import scene_geometry as g

WHITE='#ffffff';RED='#cf383e'

def extend_catalog(add,catalog,fields):
    for key,name,width,length in [('BELT','传送带车位',3,10),('TRACTOR','飞机牵引车位',4.5,10),('BUS','摆渡车位',4.5,14),('PLATFORM','平台车位',5,12),('SERVICE','通用保障车位',4,10)]:
        add('VEHICLE_'+key,name,'机坪车位预设','6.2.20(6) 表6.2.20','POINT','apron_vehicle',dict(width=width,bay_length=length,line_width=.125,text_height=.75,text=name.replace('位',''),direction_arrow=True))
    add('BRIDGE_COMPOSITE','廊桥区域＋回位点','机坪安全与设备','6.2.20(4)','AREA','apron_bridge',dict(line_width=.125,spacing=2,home_diameter=3,home_dx=0,home_dy=0,show_home=True))
    for key,shape in [('BRIDGE_AREA','apron_bridge'),('TRANSFER','apron_transfer'),('TEMP_WAIT','apron_temp')]:catalog[key]['shape']=shape
    catalog['BRIDGE_AREA']['defaults'].update(show_home=False,home_diameter=3,home_dx=0,home_dy=0)
    for spec in catalog.values():
        if spec['shape'].startswith('apron_'):
            spec['renderer']='apron'
            if spec['shape']=='apron_vehicle':spec['extra_fields']=[('bay_length','车位长度 m','float',10),('direction_arrow','停车方向箭头','bool',True)]
            elif spec['shape']=='apron_bridge':spec['extra_fields']=[('show_home','显示回位圆','bool',False),('home_diameter','回位圆外径 m','float',3),('home_dx','回位点横移 m','float',0),('home_dy','回位点纵移 m','float',0)]
            elif spec['shape']=='apron_transfer':spec['extra_fields']=[('row_spacing','内部行距 m','float',2)]
    fields.update(apron_vehicle={'width','line_width','text','text_height'},apron_bridge={'line_width','spacing'},apron_transfer={'line_width','text','text_height'},apron_temp={'line_width','text','text_height'})

def render_apron(asset,spec):
    from marking_catalog import hatch_segments
    p=asset['props'];pts=asset['points'];oid=asset['id'];shape=spec['shape'];lw=p.get('line_width',.125);out=[]
    u=g.unit(pts[0],pts[1] if spec['mode']=='AREA' else pts[-1]);v=(-u[1],u[0]);angle=math.degrees(math.atan2(u[1],u[0]));origin=pts[0]
    def xy(x,y):return [origin[k]+u[k]*x+v[k]*y for k in (0,1)]
    def line(points,color=WHITE,dash=None):out.append(dict(type='line',oid=oid,points=points,stroke=color,width=lw,dash=dash))
    def polygon(points,color=WHITE,dash=None):out.append(dict(type='polygon',oid=oid,points=points,fill=None,stroke=color,width=lw,dash=dash))
    def text(value,point,height,rotation,width=None):out.append(dict(type='text',oid=oid,points=[point],text=value,fill=WHITE,size=height,rotation=rotation,world_text=True,text_width=width,font='hei'))
    def circle(center,diameter):
        radius=max(.001,(diameter-lw)/2);polygon([[center[0]+radius*math.cos(i*math.pi/48),center[1]+radius*math.sin(i*math.pi/48)] for i in range(96)],RED)
    if shape=='apron_vehicle':
        length=p.get('bay_length',10);width=p['width'];x=length/2-lw/2;y=width/2-lw/2
        polygon([xy(-x,-y),xy(x,-y),xy(x,y),xy(-x,y)])
        if p.get('direction_arrow',True):
            tip=length/2-.4;arm=min(1.5,(width-.3)/math.sqrt(3));line([xy(tip-arm/2,-arm*math.sqrt(3)/2),xy(tip,0),xy(tip-arm/2,arm*math.sqrt(3)/2)])
        h=p.get('text_height',.75);text(p.get('text','车辆'),xy(-length*.15,0),h,angle-90,min(width-.5,max(h,len(p.get('text','车辆'))*h*.65)))
        return out
    polygon(pts,RED if shape=='apron_bridge' else WHITE,[1,1] if shape=='apron_temp' else None)
    if shape=='apron_bridge':
        center=[sum(q[k] for q in pts)/len(pts)+u[k]*p.get('home_dx',0)+v[k]*p.get('home_dy',0) for k in (0,1)]
        center=p.get('home_center',center)
        diameter=p.get('home_diameter',3)
        home=[[center[0]+diameter/2*math.cos(i*math.pi/48),center[1]+diameter/2*math.sin(i*math.pi/48)] for i in range(96)]
        from marking_standards import outside_segments
        for segment in hatch_segments(pts,p.get('spacing',2)+lw,45):
            for clipped,_ in outside_segments(segment,[home] if p.get('show_home',False) else [],lw/2):line(clipped,RED)
        if p.get('show_home',False):
            if p.get('home_white19',False):out.append(dict(type='polygon',oid=oid,points=home,fill=WHITE,stroke=None))
            circle(center,diameter)
    else:
        if shape=='apron_transfer':
            for segment in hatch_segments(pts,p.get('row_spacing',2),angle):
                middle=[sum(q[k] for q in segment)/2 for k in (0,1)]
                if min(g.project([a,b],middle)[0] for a,b in zip(pts,pts[1:]+pts[:1]))>.2:line(segment,WHITE,[1,1])
        center=[sum(q[k] for q in pts)/len(pts) for k in (0,1)];height=p.get('text_height',.75);value=p.get('text') or ('车辆中转区' if shape=='apron_transfer' else '临时作业等待区')
        for a,b in zip(pts,pts[1:]+pts[:1]):
            length=g.distance(a,b)
            if length<2:continue
            direction=g.unit(a,b);normal=(-direction[1],direction[0]);middle=[(a[k]+b[k])/2 for k in (0,1)]
            if sum((center[k]-middle[k])*normal[k] for k in (0,1))<0:normal=[-x for x in normal]
            q=[middle[k]+normal[k]*(.5+height/2) for k in (0,1)]
            text(value,q,height,math.degrees(math.atan2(direction[1],direction[0])),min(length-1,len(value)*height*.9))
    return out

def create_apron_kit(scene,apron_id,anchor=None):
    """Place independently editable candidate components, not an approved layout."""
    apron=scene.assets[apron_id]
    if apron['kind']!='APRON':raise ValueError('请先选择机坪或在机坪内点击。')
    pts=apron['points'];u=g.unit(pts[0],pts[1]);v=(-u[1],u[0]);center=[sum(p[k] for p in pts)/len(pts) for k in (0,1)]
    if sum((center[k]-pts[0][k])*v[k] for k in (0,1))<0:v=tuple(-x for x in v)
    anchor=anchor or [pts[0][k]+12*u[k]+12*v[k] for k in (0,1)]
    types=['VEHICLE_BELT','VEHICLE_TRACTOR','VEHICLE_BUS','VEHICLE_PLATFORM','VEHICLE_SERVICE','CHOCKS','WORK_WAIT','TEMP_WAIT','BRIDGE_COMPOSITE','EQUIPMENT_ZONE','PALLETS','TRANSFER','HYDRANT','PIT']
    from marking_catalog import CATALOG
    created=[];skipped=[]
    with scene.transaction('添加机坪配套候选标记组'):
        group=scene.create_group('机坪配套标记（候选布局）',apron_id)
        for i,key in enumerate(types):
            cx,cy=(i%4)*26,(i//4)*24
            def point(x,y):return [anchor[k]+u[k]*(cx+x)+v[k]*(cy+y) for k in (0,1)]
            markpts=[point(-8,-5),point(8,-5),point(8,5),point(-8,5)] if CATALOG[key]['mode']=='AREA' else [point(0,0),point(10,0)]
            footprint=[point(-9,-6),point(9,-6),point(9,6),point(-9,6)]
            if not all(g.inside(q,pts) for q in footprint):skipped.append(key);continue
            mid=scene.create_marking(key,markpts);scene.reparent(mid,group);created.append(mid)
    return group,created,skipped
