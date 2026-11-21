"""Four distinct lead-in layouts; labels interrupt lines rather than cover them."""
import math
import scene_geometry as g

def design(a):
    p=a['props'];kind=p.get('lead_type','A');R=p.get('lead_radius',20);pts=a['points'];length=g.length(pts)
    origin=pts[0];u=g.unit(origin,pts[-1]);v=[-u[1],u[0]]
    if not math.isfinite(R) or R<=0:raise ValueError('引入半径必须大于零')
    world=lambda q:[origin[k]+u[k]*q[0]+v[k]*q[1] for k in (0,1)]
    vector=lambda q:[u[k]*q[0]+v[k]*q[1] for k in (0,1)]
    allowed=(1,) if p.get('lead_direction')=='LEFT' else (-1,) if p.get('lead_direction')=='RIGHT' else (-1,1)
    paths=[];numbers=[];h=p.get('number_height',4);body=5*h/4;head=2*h/4
    text=p.get('stand_number') or a.get('name','101');tw=max(h,len(text)*h*.4)+1
    G=p.get('lead_g',.5);H=p.get('lead_h',.5);I=p.get('lead_i',1)
    def path(key,points):paths.append(dict(key=key,points=[world(q) for q in points]))
    def number(q,d,rotation=0):numbers.append(dict(point=world(q),direction=vector(d),text_rotation_offset=rotation))
    def arc(key,start_x,side):
        # Circular quarter arc: tangent to transverse approach, then stand axis.
        path(key,[[start_x+R*math.sin(math.pi/2*i/64),side*R*(1-math.cos(math.pi/2*i/64))] for i in range(65)][::-1])
    def quarter(start_x,side):
        return [[start_x+R*(1-math.cos(math.pi/2*i/64)),side*R*(1-math.sin(math.pi/2*i/64))] for i in range(65)]
    def opposite_arcs(start_x,side):
        # Two opposite 60-degree circular arcs retain the requested radius and
        # are tangent to the alignment axis at the merge (no cubic radius guess).
        theta=math.pi/3;path=[]
        for i in range(65):
            t=theta*i/64;path.append([start_x+R*math.sin(t),side*(R-R*(1-math.cos(t)))])
        x,y=path[-1]
        for i in range(1,65):
            t=theta*i/64;path.append([x+R*(math.sin(theta)-math.sin(theta-t)),y-side*R*(math.cos(theta-t)-math.cos(theta))])
        return path
    if kind in ('A','D'):
        angle=math.radians(p.get('lead_label_angle',60));c,s=math.cos(angle),math.sin(angle)
        label_x=H+body/2*c+tw/2*s
        start_x=label_x+max((body/2+head)*c,body/2*c+tw/2*s)+I;merge=start_x+math.sqrt(3)*R
        path('TAXI_BASE',[[0,-R-5],[0,R+5]])
        for side in allowed:
            d=[c,side*s];q=[label_x,side*(R-(body/2+head+I)*s)];number(q,d)
            end=[q[k]-d[k]*(body/2+G) for k in (0,1)]
            if kind=='A':inner=[[0,0],end]
            else:
                # D carries opposed approaches across the axis; A has a V fork.
                start=[0,-side*(R+5)]
                handle=min(R,g.distance(start,end)*.4,max(.05,(end[0]-.05)/max(d[0],.01)))
                inner=g.cubic(start,end,[0,side],d,handle,steps=64)
            path('ENTRY_STUB:'+str(side),inner)
            path('TURN:'+str(side),opposite_arcs(start_x,side))
        path('ALIGN',[[merge,0],[max(length,merge+.05),0]])
    elif kind=='B':
        merge=R;J=p.get('lead_j',1);K=p.get('lead_k',2)
        path('TAXI_BASE',[[0,-R-5],[0,R+5]])
        for side in allowed:path('TURN:'+str(side),quarter(0,side))
        stub=p.get('lead_stub',1)
        path('LABEL_STUB',[[R,0],[R+stub,0]])
        number([R+stub+J+body/2,0],[1,0])
        restart=R+stub+J+body+head+K
        path('ALIGN',[[restart,0],[max(length,restart+.05),0]])
    elif kind=='C':
        L=p.get('lead_l',1);M=p.get('lead_m',1);N=p.get('lead_n',1);P=p.get('lead_p',2)
        merge=0;path('TAXI_BASE',[[0,-max(R,tw+L)],[0,max(R,tw+L)]])
        path('LABEL_STUB',[[0,0],[M,0]])
        for side in allowed:number([N+body/2,side*(tw+L)/2],[1,0],0)
        restart=N+body+head+P
        path('ALIGN',[[restart,0],[max(length,restart+.05),0]])
    else:raise ValueError('未知引入线类型')
    return dict(paths=paths,numbers=numbers,radius=R,merge=world([merge,0]))

def safety(scene,a):
    p=a['props'];length=p.get('aircraft_length',scene.scenario['aircraft_length']);span=p.get('aircraft_span',scene.scenario['aircraft_wingspan']);fuselage=p.get('fuselage_width',4);wing=p.get('wing_station',length*.45);clear=p.get('safety_clearance',4.5)
    if min(length,span,fuselage,clear)<=0 or not 0<wing<length:raise ValueError('机型包络参数无效')
    nose=p.get('nose_to_nosewheel',4);front=nose+clear;body=fuselage/2+clear;tip=span/2+clear;tail=nose-length-clear
    wing_front=nose-wing+clear;wing_back=max(tail+.5,nose-wing-length*.18-clear)
    # Open at the tail. Sloping wing-to-fuselage sides replace rectangular steps.
    local=[(tail,-body),(wing_back,-body),(wing_front,-tip),(front,-tip),(front,0),(front,tip),(wing_front,tip),(wing_back,body),(tail,body)]
    u=g.unit(a['points'][0],a['points'][-1]);v=(-u[1],u[0]);q=a['points'][-1]
    return [[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in local]
