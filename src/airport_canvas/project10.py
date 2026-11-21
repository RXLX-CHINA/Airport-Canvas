"""Project preferences, reciprocal designators and stable junction editing."""
import copy
import math
import re
import scene_geometry as g

TAXIS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')
SUBTYPES={'滑行道':'TAXIWAY','联络道':'TAXIWAY','快速脱离道':'TAXIWAY','机坪滑行道':'APRON_TAXIWAY','机坪入口滑行道':'TAXIWAY','机位滑行通道':'STAND_TAXILANE'}

def reciprocal(label):
    m=re.fullmatch(r'(0[1-9]|[12][0-9]|3[0-6])([LRC]?)',str(label).strip().upper())
    if not m:raise ValueError('跑道编号须为01～36，后缀可为L/C/R')
    n,s=m.groups();return f'{(int(n)+17)%36+1:02d}'+dict(L='R',R='L',C='C').get(s,'')

def synchronize(p,changes):
    for side in ('a','b'):
        key='label_'+side
        if key not in changes:continue
        value=str(changes[key]).strip().upper();op=reciprocal(value);other='b' if side=='a' else 'a'
        p[key]=value;previous=p.get('label_'+other,op)
        num=op[:2] if p.get('sync_number',True) else previous[:2]
        suf=op[2:] if p.get('sync_suffix',True) else previous[2:]
        p['label_'+other]=num+suf

def parallel_number(scene):
    from curve_model import runway_heading
    runways=[a for a in scene.assets.values() if a['kind']=='RUNWAY'];groups=[]
    for a in runways:
        angle=runway_heading(scene,a)[0]%180
        group=next((v for v in groups if min(abs(v[0]-angle),180-abs(v[0]-angle))<3),None)
        if group:group[1].append(a)
        else:groups.append((angle,[a]))
    with scene.transaction('平行跑道自动编号'):
        for angle,aa in groups:
            if len(aa)>6:raise ValueError('同一平行组超过6条，须人工确定编号组')
            heading=runway_heading(scene,aa[0])[0]%360;u=g.unit(aa[0]['points'][0],aa[0]['points'][-1]);u=[x*(1 if heading<180 else -1) for x in u];v=[-u[1],u[0]]
            aa.sort(key=lambda a:-sum((a['points'][0][k]+a['points'][-1][k])/2*v[k] for k in (0,1)))
            base=int(math.floor(angle/10+.5));n=base or 36
            patterns={1:[''],2:['L','R'],3:['L','C','R'],4:['L','R','L','R'],5:['L','C','R','L','R'],6:['L','C','R','L','C','R']}
            split=2 if len(aa)==4 else 3
            # Second group uses the next-nearest ten degrees, not always +10.
            adjacent=(base+(1 if angle/10>=base else -1)-1)%36+1
            for i,a in enumerate(aa):
                num=adjacent if len(aa)>=4 and i>=split else n
                label=f'{num:02d}'+patterns[len(aa)][i]
                axis=g.unit(a['points'][0],a['points'][-1]);forward=sum(axis[k]*u[k] for k in (0,1))>=0
                a['props'].update(label_a=label if forward else reciprocal(label),label_b=reciprocal(label) if forward else label,auto_number=False)
    return len(runways)

def constrain(start,p,tangent=None):
    dx,dy=p[0]-start[0],p[1]-start[1];angles=[i*math.pi/4 for i in range(8)]
    if tangent:angles += [math.atan2(tangent[1],tangent[0]),math.atan2(tangent[1],tangent[0])+math.pi]
    choices=[]
    for angle in angles:
        u=[math.cos(angle),math.sin(angle)];u=[0. if abs(v)<1e-12 else math.copysign(1.,v) if abs(abs(v)-1)<1e-12 else v for v in u];d=max(0,dx*u[0]+dy*u[1]);q=[start[k]+d*u[k] for k in (0,1)];choices.append((g.distance(p,q),q))
    return min(choices,key=lambda v:v[0])[1]

def move_endpoint(scene,mid,branch,index,p):
    """One owner per gesture; editing an analytic exit keeps its analytic model."""
    from editor7_model import _legacy_move_anchor as move_anchor
    m=scene.movements[mid]
    if branch!='MAIN':return move_anchor(scene,mid,branch,index,p)
    with scene.transaction('移动交汇点'):
        if m.get('legacy_attachment'):
            from curve_model import editable_vertices,rebuild_rounded,set_nodes
            a=scene.assets[m['to']['asset']];end=0 if index==0 else -1;total=g.length(a['points'])
            binding=next((link for link in scene.movements.values() if link.get('legacy_attachment') and link['to']['asset']==a['id'] and abs(link['to']['station']-(0 if index==0 else total))<.1),None)
            if binding:
                parent=binding['from'];station=g.project(scene.assets[parent['asset']]['points'],p)[1];q,_=g.at(scene.assets[parent['asset']]['points'],station);parent['station']=station
            else:q=list(p)
            if a.get('design_vertices'):
                vertices=copy.deepcopy(editable_vertices(a));vertices[end]=q;rebuild_rounded(scene,a['id'],vertices)
            else:
                nodes=route_nodes(a)
                straight=all(g.project([a['points'][0],a['points'][-1]],point)[0]<1e-6 for point in a['points'])
                delta=[q[k]-nodes[end]['p'][k] for k in (0,1)]
                for key in ('p','incoming','outgoing'):nodes[end][key]=[nodes[end][key][k]+delta[k] for k in (0,1)]
                if straight:
                    from curve_model import node
                    first,last=nodes[0]['p'],nodes[-1]['p'];nodes=[node(first),node(last)]
                    nodes[0]['outgoing']=[first[k]+(last[k]-first[k])/3 for k in (0,1)]
                    nodes[-1]['incoming']=[first[k]+2*(last[k]-first[k])/3 for k in (0,1)]
                set_nodes(scene,a['id'],nodes)
            return
        if m.get('geometry')=='RAPID':
            port=m[('from','to')[index]];port['station']=g.project(scene.assets[port['asset']]['points'],p)[1]
            from smart_routes import configure_rapid
            configure_rapid(scene,mid);return
        if m.get('geometry')=='STRAIGHT':
            port=m[('from','to')[index]]
            port['station']=g.project(scene.assets[port['asset']]['points'],p)[1]
            m.update(follow_existing=False,auto_tangent=False)
            m.pop('bezier_controls',None)
            return
        # A previously auto-followed bend becomes an explicit editable curve.
        m['follow_existing']=False
        move_anchor(scene,mid,branch,index,p)
        m['geometry']='BEZIER'

def route_nodes(a):
    if a.get('curve_nodes'):return copy.deepcopy(a['curve_nodes'])
    from editor7_model import curve_nodes_for
    return curve_nodes_for(a['points'])

def legacy_controls(scene,mid,controls):
    from curve_model import set_nodes,follow_welds
    a=scene.assets[scene.movements[mid]['to']['asset']];nodes=route_nodes(a)
    nodes[0]['outgoing']=list(controls[0]);nodes[-1]['incoming']=list(controls[1])
    with scene.transaction('编辑关联滑行道两端控制柄'):
        set_nodes(scene,a['id'],nodes);follow_welds(scene,a['id'])

def rapid_option(scene,aid,enabled):
    a=scene.assets[aid]
    if a['kind'] not in TAXIS:raise ValueError('请选择连接跑道的滑行道')
    matches=[m for m in scene.movements.values() if aid in (m['from']['asset'],m['to']['asset']) and any(scene.assets[m[s]['asset']]['kind']=='RUNWAY' for s in ('from','to'))]
    if enabled and matches:
        mouths=[g.at(scene.assets[m[s]['asset']]['points'],m[s]['station'])[0] for m in matches for s in ('from','to') if scene.assets[m[s]['asset']]['kind']=='RUNWAY']
        if any(g.distance(mouths[0],q)>2 for q in mouths[1:]):raise ValueError('此路线接入多个不同跑道口，请先用分段工具分出需要设为快速脱离道的这一段')
    with scene.transaction('快速脱离道选项'):
        a['props']['rapid_exit']=bool(enabled)
        for m in matches:
            if enabled:
                m.setdefault('pre_rapid',copy.deepcopy({k:v for k,v in m.items() if k!='pre_rapid'}))
                if scene.assets[m['from']['asset']]['kind']!='RUNWAY':m['from'],m['to']=m['to'],m['from']
                # Drawn exit already has an editable rounded axis. Retain it;
                # this option classifies it rather than inventing another route.
                m.update(role='RAPID_EXIT',auto_signs=True,show_holding=False,bidirectional=False)
                a['props']['flow']='FORWARD' if m['to']['station']<g.length(a['points'])/2 else 'REVERSE'
            elif m.get('pre_rapid'):
                backup=m.pop('pre_rapid');m.clear();m.update(backup)
        if enabled:
            a['props']['rapid_drawn_axis56']=True
            a['props']['rapid_fit_note']='中线采用实际绘制的线形，可用顶点工具调整。'
        if not enabled:
            a['props'].pop('rapid_drawn_axis56',None)
            a['props']['flow']='BOTH'
            original=a['props'].pop('rapid_original',None)
            if original:
                old=g.length(a['points']);new=g.length(original['points'])
                for link in scene.movements.values():
                    for side in ('from','to'):
                        if link[side]['asset']==aid:link[side]['station']*=new/old
                a['points']=original['points']
                for key in ('curve_nodes','design_vertices'):
                    if original.get(key):a[key]=original[key]
                    else:a.pop(key,None)
                for mid,ports in original.get('anchors',{}).items():
                    if mid in scene.movements:scene.movements[mid].update(copy.deepcopy(ports))

def stopway_axes(a):
    props=a['props']
    axis=g.unit(a['points'][0],a['points'][-1])
    for end,sign,origin in [('a',-1,a['points'][0]),('b',1,a['points'][-1])]:
        length=float(props.get('stopway_'+end,0))
        if length>0:
            yield end,[origin[k]+sign*axis[k]*length for k in (0,1)],origin,length


def stopways(a):
    from marking_catalog import primitives
    from automatic_markings import synthetic
    out=[];p=a['props']
    for end,outside,origin,length in stopway_axes(a):
        mark=synthetic(a['id'],'PRETHRESHOLD',[outside,origin],end+':STOPWAY',width=p['width'],surface_length=length,short_stopway_chevrons=True,surface_color=p.get('stopway_color','#c7cbd0'))
        out.extend(primitives(mark))
    return out
