"""Analytical rapid-exit fitting, with finite segment and tangent constraints."""
import math
import scene_geometry as g

def recommended_radius(scene,m):
    return 275. if scene.assets[m['from']['asset']]['props'].get('code_number') in (1,2) else 550.

def valid_exit_angle(m,angle):
    if m.get('rapid_lock_angle39'):return math.isfinite(angle) and 0<angle<90
    return math.isfinite(angle) and 25<=angle<=45


def _solve(scene,m,angle,direction,join_limit=175,wanted=None):
    runway=scene.assets[m['from']['asset']];taxi=scene.assets[m['to']['asset']]
    flow=taxi['props'].get('flow','BOTH')
    if flow=='FORWARD' and direction<0 or flow=='REVERSE' and direction>0:return None
    start,u=g.at(runway['points'],m['from']['station']);u=[x*m['from']['direction'] for x in u]
    target,_=g.at(taxi['points'],m['to']['station']);normal=[-u[1],u[0]]
    side=1 if sum((target[i]-start[i])*normal[i] for i in (0,1))>=0 else -1;n=[side*x for x in normal]
    r=recommended_radius(scene,m) if m.get('rapid_auto_radius',False) else float(m.get('exit_radius',recommended_radius(scene,m)))
    r2=float(m.get('join_radius',25));theta=math.radians(angle)
    if not valid_exit_angle(m,angle) or not 0<r<=100000 or not m['width']/2<r2<=100000:raise ValueError('快速出口角须为25～45°；半径须有限，接入半径须大于半幅道面宽度。')
    first=[r*math.sin(theta),r*(1-math.cos(theta))];w=[math.cos(theta),math.sin(theta)]
    options=[];offset=0
    def local(p):return [sum((p[k]-start[k])*axis[k] for k in (0,1)) for axis in (u,n)]
    for a,b in zip(taxi['points'],taxi['points'][1:]):
        seglen=g.distance(a,b)
        if seglen<1e-8:continue
        axis=g.unit(a,b);v=[direction*x for x in axis]
        stub=float(m.get('rapid_taxi_stub',0))
        receiving_normal=[-axis[1],axis[0]]
        if sum(receiving_normal[k]*n[k] for k in (0,1))<0:receiving_normal=[-x for x in receiving_normal]
        tangent=receiving_normal if stub else v
        vl=[sum(tangent[k]*basis[k] for k in (0,1)) for basis in (u,n)]
        line_direction=[sum(axis[k]*basis[k] for k in (0,1)) for basis in (u,n)]
        offset_point=[a[k]-(stub+r2)*receiving_normal[k] for k in (0,1)] if stub else a
        beta=math.atan2(vl[1],vl[0]);delta=(beta-theta+math.pi)%(2*math.pi)-math.pi
        if abs(delta)>math.radians(join_limit):offset+=seglen;continue
        sign=1 if delta>=0 else -1
        join=[r2/sign*(math.sin(theta+delta)-math.sin(theta)),r2/sign*(math.cos(theta)-math.cos(theta+delta))]
        f=[first[k]+join[k] for k in (0,1)];aa=local(offset_point)
        den=w[0]*line_direction[1]-w[1]*line_direction[0]
        if abs(den)<1e-8:offset+=seglen;continue
        d=[aa[k]-f[k] for k in (0,1)];straight=(d[0]*line_direction[1]-d[1]*line_direction[0])/den
        shift=0.
        if wanted is not None:
            if abs(line_direction[1])>1e-8:
                shift=(straight-wanted)*den/line_direction[1]
            elif abs(wanted-straight)>.001:
                offset+=seglen
                continue
            straight=wanted
        runway_station=m['from']['station']+shift*m['from']['direction']
        if not 0<=runway_station<=g.length(runway['points']):
            offset+=seglen
            continue
        origin=[p+shift*v for p,v in zip(start,u)]
        if straight<max(.05,float(m.get('rapid_min_straight',1))):offset+=seglen;continue
        finish=[origin[k]+u[k]*(f[0]+straight*w[0])+n[k]*(f[1]+straight*w[1]) for k in (0,1)]
        connection=None
        if stub:
            connection=finish
            finish=[connection[k]+(stub+r2)*receiving_normal[k]+r2*v[k] for k in (0,1)]
        station=sum((finish[k]-a[k])*axis[k] for k in (0,1))
        if not -.001<=station<=seglen+.001:offset+=seglen;continue
        station=offset+max(0,min(seglen,station));endpoint,_=g.at(taxi['points'],station)
        options.append(dict(start=origin,runway_station=runway_station,u=u,n=n,theta=theta,r=r,r2=r2,straight=straight,finish=endpoint,station=station,direction=direction,
            join_delta=delta,exit_angle=angle,extension=30 if runway['props'].get('code_number') in (1,2) else 60,
            requested_angle=m.get('exit_angle',30),recommended_radius=recommended_radius(scene,m),
            connection=connection,taxi_stub=stub,receiving_normal=receiving_normal,receiving_tangent=v))
        offset+=seglen
    return min(options,key=lambda p:abs(p['station']-m['to']['station'])) if options else None

def _fit_straight(scene,m,direction,wanted,preferred):
    """Fit the specified straight length by varying the exit angle."""
    if m.get('rapid_lock_angle39'):
        return _solve(scene,m,preferred,direction,wanted=wanted)
    candidates=[]
    previous=None
    for angle in sorted(set([float(a) for a in range(25,46)]+[preferred])):
        current=_solve(scene,m,angle,direction)
        if current is not None:
            difference=current['straight']-wanted
            if abs(difference)<=.001:
                candidates.append(current)
            elif previous and previous[1]*difference<0:
                lo,flo=previous
                hi=angle
                for _ in range(24):
                    mid=(lo+hi)/2
                    trial=_solve(scene,m,mid,direction)
                    if trial is None:break
                    gap=trial['straight']-wanted
                    if abs(gap)<=.001:
                        candidates.append(trial)
                        break
                    if flo*gap>0:lo,flo=mid,gap
                    else:hi=mid
            previous=(angle,difference)
        else:
            previous=None
    return min(candidates,key=lambda row:abs(row['exit_angle']-preferred),default=None)

def drawn_axis_turn(scene,m,radius,direction,straight=None):
    axis=m['drawn_axis39']
    total=g.length(axis)
    start=m.get('drawn_straight_start39',0.)
    if straight is None:
        straight=max(0.,total-start-max(radius,10.))
    station=start+straight
    if not 0<=station<total-.05:
        raise ValueError('Turn point must lie on the original centreline.')
    point,tangent=g.at(axis,station)
    taxi=scene.assets[m['to']['asset']]['points']
    preferred=m['to']['station']
    stub=m.get('rapid_taxi_stub',0.)
    prefix=g.subpath(axis,0.,station)[:-1]
    from shapely.geometry import LineString
    candidates=[]
    offset=0.
    for a,b in zip(taxi,taxi[1:]):
        length=g.distance(a,b)
        if length<1e-8:continue
        tangent_taxi=g.unit(a,b)
        receiving=[u*direction for u in tangent_taxi]
        normal=[-receiving[1],receiving[0]]
        if sum((q-r)*n for q,r,n in zip(point,a,normal))<0:normal=[-n for n in normal]
        incoming=[-n for n in normal] if stub else receiving
        origin=[q+(stub+radius)*n for q,n in zip(a,normal)] if stub else a
        determinant=tangent[0]*receiving[1]-tangent[1]*receiving[0]
        if abs(determinant)>1e-8:
            dx,dy=(q-r for q,r in zip(origin,point))
            travel=(dx*receiving[1]-dy*receiving[0])/determinant
            if travel>.05:
                corner=[q+travel*u for q,u in zip(point,tangent)]
                turn=math.acos(max(-1.,min(1.,sum(u*v for u,v in zip(tangent,incoming)))))
                lead=radius*math.tan(turn/2)
                if turn<math.radians(175):
                    join=corner if stub else [q+lead*u for q,u in zip(corner,receiving)]
                    arc_start=[q-stub*n for q,n in zip(join,normal)] if stub else join
                    target=[q-radius*n+radius*u for q,n,u in zip(arc_start,normal,receiving)] if stub else join
                    on_segment=sum((q-r)*u for q,r,u in zip(target,a,tangent_taxi))
                    if 0<=on_segment<=length:
                        handle=min(travel*.55, radius, g.distance(point,join)*.45)
                        curve=g.cubic(point,join,tangent,incoming,handle,steps=48)
                        if stub:
                            curve.append(arc_start)
                            curve.extend(stub_turn(dict(connection=arc_start,receiving_normal=incoming,
                                                        receiving_tangent=receiving,taxi_stub=0.,r2=radius),
                                                   radius,1)[1:])
                        path=prefix+curve
                        if LineString(path).is_simple:
                            target_station=offset+on_segment
                            candidates.append((abs(target_station-preferred),path,target_station,curve))
        offset+=length
    if not candidates:raise ValueError('No forward turn fits from this point to the receiving taxiway.')
    _,path,target_station,curve=min(candidates,key=lambda row:row[0])
    return path,target_station,straight,curve


def rapid_layout(scene,m):
    if m.get('drawn_axis39'):
        radius=m.get('join_radius',25.)
        direction=m['to']['direction']
        path,station,straight,_=drawn_axis_turn(scene,m,radius,direction,m.get('rapid_exact_straight') or None)
        return dict(drawn_path=path,station=station,straight=straight,direction=direction,
                    r=m.get('exit_radius',recommended_radius(scene,m)),r2=radius,
                    runway_station=m['from']['station'],exit_angle=m['exit_angle'])
    preferred=float(m.get('exit_angle',30))
    if not valid_exit_angle(m,preferred):raise ValueError('快速出口目标角度须为25～45°。')
    auto=m.get('rapid_auto_fit',True) and not m.get('rapid_lock_angle39');angles=[preferred]
    if auto:angles+=sorted((a for a in range(25,46) if a!=preferred),key=lambda a:abs(a-preferred))
    directions=[m['to']['direction']]+([-m['to']['direction']] if auto else [])
    solutions=[]
    requested=m.get('rapid_exact_straight',0)
    if requested:
        solutions=[p for direction in directions if (p:=_fit_straight(scene,m,direction,requested,preferred))]
        if not solutions:raise ValueError('固定锚点与半径下无法拟合指定的正向直线段。')
        return min(solutions,key=lambda row:(abs(row['exit_angle']-preferred),
                                            row['direction']!=m['to']['direction']))
    def score(p):return (abs(p['exit_angle']-preferred)+.15*math.degrees(abs(p['join_delta']))+(3 if p['direction']!=m['to']['direction'] else 0),abs(p['station']-m['to']['station']))
    for angle in angles:
        candidates=[]
        for direction in directions:
            found=_solve(scene,m,angle,direction)
            if found:candidates.append(found)
        if candidates:
            best=min(candidates,key=score)
            if angle==preferred and abs(best['join_delta'])<=math.pi/2:return best
            solutions.extend(candidates)
    if solutions:return min(solutions,key=score)
    raise ValueError('目标滑行道范围内无可用的圆弧—直线解；请调整转出点、目标道路、半径或最小直线长度。')

def arc_steps(radius,angle):
    # Bound chord error rather than oversampling short or small-radius arcs.
    step=2*math.acos(max(-1.,1-.018/radius))
    return max(2,min(800,math.ceil(abs(angle)/step)))

def layout_path(p):
    if 'drawn_path' in p:return p['drawn_path']
    start,u,n,theta,r,r2,straight=[p[k] for k in ('start','u','n','theta','r','r2','straight')]
    def point(x,y):return [start[i]+u[i]*x+n[i]*y for i in (0,1)]
    steps=arc_steps(r,theta);points=[point(r*math.sin(theta*j/steps),r*(1-math.cos(theta*j/steps))) for j in range(steps+1)]
    x0=r*math.sin(theta);y0=r*(1-math.cos(theta));x1=x0+straight*math.cos(theta);y1=y0+straight*math.sin(theta)
    points.append(point(x1,y1));delta=p['join_delta'];sign=1 if delta>=0 else -1
    steps=arc_steps(r2,delta)
    for j in range(1,steps+1):
        heading=theta+delta*j/steps
        points.append(point(x1+r2/sign*(math.sin(heading)-math.sin(theta)),y1+r2/sign*(math.cos(theta)-math.cos(heading))))
    if p.get('connection'):
        points[-1]=p['connection']
        points.extend(stub_turn(p,p['r2'],1))
    else:points[-1]=list(p['finish'])
    return points

def stub_turn(plan,radius,direction):
    normal,tangent=plan['receiving_normal'],plan['receiving_tangent']
    start=[plan['connection'][k]+normal[k]*(plan['taxi_stub']+plan['r2']-radius)
           for k in (0,1)]
    points=[]
    steps=arc_steps(radius,math.pi/2)
    for i in range(steps+1):
        angle=math.pi*i/(2*steps)
        points.append([start[k]+radius*(normal[k]*math.sin(angle)
                       +direction*tangent[k]*(1-math.cos(angle))) for k in (0,1)])
    return points

def rapid_path(scene,m):return layout_path(rapid_layout(scene,m))

def reverse_join(scene,m):
    main=rapid_layout(scene,m)
    if m.get('drawn_axis39'):
        direction=-main['direction']
        if scene.assets[m['to']['asset']]['props'].get('flow','BOTH')!='BOTH':return None
        try:
            _,station,straight,curve=drawn_axis_turn(scene,m,m.get('reverse_join_radius',main['r2']),
                                                     direction,m.get('reverse_rapid_exact_straight') or main['straight'])
        except ValueError:return None
        return dict(points=curve,station=station,direction=direction,layout=dict(straight=straight))
    if main.get('connection'):
        taxi=scene.assets[m['to']['asset']]
        if taxi['props'].get('flow','BOTH')!='BOTH':return None
        radius=m.get('reverse_join_radius',main['r2'])
        if radius>main['taxi_stub']+main['r2']:return None
        path=stub_turn(main,radius,-1)
        distance,station,end=g.project(taxi['points'],path[-1])
        if distance>1e-5:return None
        path[-1]=end
        return dict(points=path,station=station,direction=-main['direction'],
                    layout=dict(main,straight=main['taxi_stub']+main['r2']-radius,r2=radius))
    candidate=dict(m,exit_radius=main['r'],rapid_auto_radius=False,
                   **{'from':dict(m['from'],station=main['runway_station'])},
                   join_radius=m.get('reverse_join_radius',main['r2']),
                   rapid_min_straight=m.get('reverse_rapid_min_straight',m.get('rapid_min_straight',1)))
    requested=m.get('reverse_rapid_exact_straight',0)
    p=(_fit_straight(scene,candidate,-main['direction'],requested,main['exit_angle']) if requested
       else _solve(scene,candidate,main['exit_angle'],-main['direction'],175))
    if not p or abs(p['runway_station']-main['runway_station'])>.001:return None
    points=layout_path(p)
    # Share the runway-side arc and start the branch on the common straight.
    axis=layout_path(main)
    steps=arc_steps(p['r'],p['theta'])
    start=g.length(points[:steps+1])+min(p['straight'],main['straight'])
    points=g.subpath(points,start,g.length(points))
    _,_,contact=g.project(axis,points[0])
    points[0]=contact
    branch=points
    return dict(points=branch,station=p['station'],direction=p['direction'],layout=p)

def reverse_surface(scene,model,guide):
    radius=model.get('reverse_surface_radius',0)
    if not radius or not guide:return guide
    surface=reverse_join(scene,dict(model,reverse_join_radius=radius))
    if surface is None:raise ValueError('反向道面半径无法连接接收滑行道。')
    return dict(guide,points=surface['points'],station=surface['station'])

def configure_rapid(scene,mid,**props):
    with scene.transaction('快速出口自动拟合'):
        m=scene.movements[mid];m.update(props,geometry='RAPID',role='RAPID_EXIT',bidirectional=False,auto_branches=True)
        m.pop('bezier_controls',None);m.pop('follow_existing',None)
        p=rapid_layout(scene,m);m['to']['station']=p['station'];m['to']['direction']=p['direction']
    return p
