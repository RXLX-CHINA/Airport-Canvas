"""Reference A/D circular lobes and an explicit fuselage neck on safety lines."""
import math
import scene_geometry as g
from stand11 import frame,dimensions

def design(a,scene=None):
    from stand11 import design as previous
    result=previous(a,scene);p=a['props'];kind=p.get('lead_type','A')
    if kind=='B':
        o,u,v=frame(a);world=lambda q:[o[k]+u[k]*q[0]+v[k]*q[1] for k in (0,1)];vector=lambda q:[u[k]*q[0]+v[k]*q[1] for k in (0,1)]
        R=result['effective_radius'];h=p.get('number_height',4);body=5*h/4;head=2*h/4;paths=[];numbers=[]
        allowed=(1,) if p.get('lead_direction')=='LEFT' else (-1,) if p.get('lead_direction')=='RIGHT' else (-1,1)
        for side in allowed:
            arc=[world([R*(1-math.cos(math.pi/2*i/128)),side*R*(1-math.sin(math.pi/2*i/128))]) for i in range(129)];L=g.length(arc);station=L/2;q,d=g.at(arc,station);numbers.append(dict(point=q,direction=list(d),text_rotation_offset=0))
            for suffix,lo,hi in [('ENTRY',0,station-body/2-1),('TURN',station+body/2+head+1,L)]:
                if hi>lo:paths.append(dict(key=suffix+':'+str(side),points=g.subpath(arc,lo,hi)))
        merge=world([R,0]);paths.append(dict(key='ALIGN',points=[merge,world([max(g.length(a['points']),R+.05),0])]))
        result.update(paths=paths,numbers=numbers,merge=merge);return result
    if kind not in ('A','D'):return result
    o,u,v=frame(a);world=lambda q:[o[k]+u[k]*q[0]+v[k]*q[1] for k in (0,1)]
    vector=lambda q:[u[k]*q[0]+v[k]*q[1] for k in (0,1)]
    # Plate axis is 45..75 degrees to the TAXI axis, not to the stand axis.
    alpha=math.radians(max(45,min(75,p.get('lead_label_angle',75))))
    beta=math.pi/2-alpha;gamma=math.pi/3;h=p.get('number_height',4);body=5*h/4;head=2*h/4
    G=p.get('lead_g',1);H=p.get('lead_h',2);I=p.get('lead_i',1);R=result['effective_radius']
    needed=2*(H+(body+head+G+I)*math.sin(beta))
    R=max(R,needed);y0=R*(1-math.cos(gamma));inner=(y0-(body+head+G+I)*math.sin(beta))/math.cos(beta)
    paths=[];numbers=[];allowed=(1,) if p.get('lead_direction')=='LEFT' else (-1,) if p.get('lead_direction')=='RIGHT' else (-1,1)
    for side in allowed:
        d=[math.cos(beta),side*math.sin(beta)];end=[inner*(1-math.sin(beta)),side*inner*math.cos(beta)];q=[end[k]+d[k]*(body/2+G) for k in (0,1)]
        if kind=='A':stub=[world([inner*(1-math.cos((math.pi/2-beta)*j/64)),side*inner*math.sin((math.pi/2-beta)*j/64)]) for j in range(65)]
        else:
            start=world([0,-side*(y0+5)]);target=world(end);t=vector([0,side]);parent=scene.assets.get(p.get('entry_asset')) if scene else None
            if parent and p.get('entry_attached',True):
                _,station,start=g.project(parent['points'],start);_,t=g.at(parent['points'],station)
                if sum((target[k]-start[k])*t[k] for k in (0,1))<0:t=[-x for x in t]
            stub=g.cubic(start,target,t,vector(d),min(R*.4,g.distance(start,target)*.3),steps=48)
        paths.append(dict(key='ENTRY_STUB:'+str(side),points=stub));numbers.append(dict(point=world(q),direction=vector(d),text_rotation_offset=0))
        start=[q[k]+d[k]*(body/2+head+I) for k in (0,1)]
        arc=[]
        for j in range(97):
            t=gamma*j/96
            arc.append(world([start[0]+R*math.sin(t),side*R*(math.cos(t)-math.cos(gamma))]))
        paths.append(dict(key='TURN:'+str(side),points=arc))
    merge=paths[-1]['points'][-1];length=g.length(a['points']);mx=sum((merge[k]-o[k])*u[k] for k in (0,1))
    paths.append(dict(key='ALIGN',points=[merge,world([max(length,mx+.05),0])]))
    result.update(paths=paths,numbers=numbers,merge=merge,effective_radius=R,radius=R)
    return result

def safety(scene,a):
    d=dimensions(scene,a);q=a['points'][-1];_,u,v=frame(a)
    neck=max(.5,min(a['props'].get('safety_neck',6), (d['front']-d['wing'])*.8));n=d['front']-neck
    pts=[(d['tail'],-d['wide']),(d['wing'],-d['wide']),(n,-d['narrow']),(d['front'],-d['narrow']),
         (d['front'],d['narrow']),(n,d['narrow']),(d['wing'],d['wide']),(d['tail'],d['wide'])]
    return [[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in pts]

def support(scene,a):
    from automatic_markings import synthetic
    if not a['props'].get('stand_support',True):return {}
    from geometry11 import Polygon,polygons
    from stand11 import bridge
    d=dimensions(scene,a);q=a['points'][-1];_,u,v=frame(a);p=a['props'];side=-1 if p.get('bridge_side','LEFT')=='LEFT' else 1
    world=lambda x,y:[q[k]+u[k]*x+v[k]*y for k in (0,1)]
    x=d['wing']-max(4,p.get('work_wait_length',10));y=side*(d['wide']+1)
    rect=[world(x,y),world(x+8,y),world(x+8,y+side*5),world(x,y+side*5)]
    mark=synthetic(a['id'],'WORK_WAIT',rect,'WORK_WAIT',line_width=.1,spacing=2,stand_part=True)
    c=world(x-2,y+side*1);chock=synthetic(a['id'],'CHOCKS',[c,[c[k]+u[k]*3 for k in (0,1)]],'CHOCKS',width=1.5,text='轮挡',text_height=.5,stand_part=True)
    return {mark['id']:mark,chock['id']:chock}
