"""Stand construction in one approach frame: open wide entry, closed nose end."""
import copy
import math
import scene_geometry as g

def uses_drawn_lead(a):
    props=a['props']
    return props.get('stand_polyline',False)

def frame(a):
    points=a['points'];o=points[0]
    start=points[-2] if uses_drawn_lead(a) else o
    u=g.unit(start,points[-1])
    return o,u,[-u[1],u[0]]

def design(a,scene=None):
    from stand_layout9 import design as legacy
    b=copy.deepcopy(a);p=b['props'];length=g.length(a['points'])
    p['lead_radius']=min(p.get('lead_radius',20),max(2,(length-18)*.7))
    result=legacy(b);o,u,v=frame(a);kind=p.get('lead_type','A');R=p['lead_radius']
    def local(q):return [sum((q[k]-o[k])*axis[k] for k in (0,1)) for axis in (u,v)]
    def world(q):return [o[k]+u[k]*q[0]+v[k]*q[1] for k in (0,1)]
    if kind in ('A','D'):
        # A single quadrant on each side. The previous opposed arcs introduced
        # an inflection and produced the visibly asymmetric upper/lower lobes.
        starts=[local(part['points'][0])[0] for part in result['paths'] if part['key'].startswith('TURN:')]
        start=starts[0];merge=start+R
        for part in result['paths']:
            if part['key'].startswith('TURN:'):
                side=int(part['key'].split(':')[-1]);part['points']=[world([start+R*math.sin(math.pi/2*i/64),side*R*math.cos(math.pi/2*i/64)]) for i in range(65)]
            elif part['key']=='ALIGN':part['points']=[world([merge,0]),world([max(length,merge+.05),0])]
        result['merge']=world([merge,0])
    if kind=='C':
        for number in result['numbers']:number['text_rotation_offset']=0
    aid=p.get('entry_asset')
    if scene and aid in scene.assets and p.get('entry_attached',True):
        parent=scene.assets[aid]
        # Only the approach stubs touch the real taxiway. Never warp the two
        # outer arcs independently: their mirrored construction stays exact.
        for part in result['paths']:
            if not part['key'].startswith('ENTRY_STUB:'):continue
            if kind=='D':
                end=part['points'][-1];_,station,start=g.project(parent['points'],part['points'][0]);_,t=g.at(parent['points'],station)
                if sum((end[k]-start[k])*t[k] for k in (0,1))<0:t=[-x for x in t]
                direction=g.unit(part['points'][-2],end);part['points']=g.cubic(start,end,t,direction,min(R,g.distance(start,end)*.35),steps=32)
            else:part['points'][0]=list(o)
    if scene:result['paths']=[part for part in result['paths'] if part['key']!='TAXI_BASE']
    result['effective_radius']=R
    return result

def dimensions(scene,a):
    p=a['props'];length=p.get('aircraft_length',scene.scenario['aircraft_length']);span=p.get('aircraft_span',scene.scenario['aircraft_wingspan']);clear=p.get('safety_clearance',4.5);nose=p.get('nose_to_nosewheel',4);wing=p.get('wing_station',length*.45)
    return dict(tail=nose-length-clear,wing=nose-wing+clear,front=nose+clear,wide=span/2+clear,narrow=p.get('fuselage_width',4)/2+clear)

def safety(scene,a):
    d=dimensions(scene,a);q=a['points'][-1];_,u,v=frame(a)
    # The approach comes from negative X. The entire wide side is open;
    # the narrow end beyond the nose-wheel stopping point is closed.
    pts=[(d['tail'],-d['wide']),(d['wing'],-d['wide']),(d['front'],-d['narrow']),(d['front'],d['narrow']),(d['wing'],d['wide']),(d['tail'],d['wide'])]
    return [[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in pts]

def bridge(a,scene=None):
    if not a['props'].get('has_bridge'):return {}
    from automatic_markings import synthetic
    # Use the same station/envelope dimensions as the safety line.
    scene=scene or type('GeometryContext',(),{'scenario':dict(aircraft_length=40,aircraft_wingspan=36)})()
    d=dimensions(scene,a);q=a['points'][-1];_,u,v=frame(a);p=a['props'];side=-1 if p.get('bridge_side','LEFT')=='RIGHT' else 1;gap=max(.2,p.get('bridge_gap',.5));outer=d['wide']+gap+p.get('bridge_width',8)
    front=d['front']-max(.5,min(p.get('safety_neck',6),(d['front']-d['wing'])*.8))
    dx=front-d['wing'];dy=d['narrow']-d['wide'];scale=math.hypot(dx,dy);nx=-dy/scale;ny=dx/scale;offset_gap=gap/max(ny,.1);x0=d['wing']+nx*offset_gap;x1=front+nx*offset_gap
    pts=[(x0,side*(d['wide']+ny*offset_gap)),(x1,side*(d['narrow']+ny*offset_gap)),(x1,side*outer),(x0,side*outer)]
    poly=[[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in pts]
    mark=synthetic(a['id'],'BRIDGE_COMPOSITE',poly,'BRIDGE',stand_part=True);return {mark['id']:mark}
