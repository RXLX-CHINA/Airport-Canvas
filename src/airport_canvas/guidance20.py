"""Enhancement follows the visible rounded junction network, never hidden stubs."""
import hashlib,math
from collections import defaultdict
import scene_geometry as g
TAXIS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')
def junction_cuts(scene,junctions,axes,guides_by_junction=None):
    """Trim junction stubs without consuming another guide's contact."""
    from pavement_geometry import turn_guides

    cuts=defaultdict(list)
    contacts=defaultdict(list)
    for junction in junctions:
        jid=junction['id']
        config=scene.data.get('junctions',{}).get(jid,{})
        guides=(turn_guides(scene,junction) if guides_by_junction is None
                else guides_by_junction.get(jid,()))
        if not guides:continue
        for index,oid in enumerate(junction['assets']):
            axis=axes.get(oid)
            if not axis or axis['kind']=='RUNWAY':continue
            points=axis['points']
            total=g.length(points)
            station=junction['stations'][index]
            edge=0 if index==0 else -1
            joins=[g.project(points,guide['points'][edge])[1] for guide in guides]
            contacts[oid].extend(joins)
            inward=[s for s in joins if s>station+1e-6]
            outward=[s for s in joins if s<station-1e-6]
            if station<1 and inward:
                cuts[oid].append((0.,min(inward)))
            elif total-station<1 and outward:
                cuts[oid].append((max(outward),total))
            elif not config.get(f'straight_{index}',True):
                cuts[oid].append((max(outward,default=station),min(inward,default=station)))

    # Explicit connectors also land on the parent axis, including at its ends.
    for movement in scene.movements.values():
        if movement.get('legacy_attachment') or not movement.get('guide_visible',True):continue
        for side in ('from','to'):
            port=movement[side]
            if port['asset'] in cuts:
                contacts[port['asset']].append(port['station'])

    result={}
    for oid,gaps in cuts.items():
        total=g.length(axes[oid]['points'])
        safe=[]
        for lo,hi in gaps:
            # Keep a short visible span at contacts shared with nearby junctions.
            if lo<=1e-6:
                hi=min(hi,min((s-.02 for s in contacts[oid] if s<hi-1e-6),default=hi))
            elif hi>=total-1e-6:
                lo=max(lo,max((s+.02 for s in contacts[oid] if s>lo+1e-6),default=lo))
            elif any(lo+1e-6<s<hi-1e-6 for s in contacts[oid]):
                continue
            if hi-lo>1e-6:safe.append((lo,hi))
        start_edge=max((hi for lo,hi in safe if lo<=1e-6),default=0.)
        end_edge=min((lo for lo,hi in safe if hi>=total-1e-6),default=total)
        if 0<start_edge<=end_edge<total and end_edge-start_edge<.02:
            safe=[(lo,min(hi,max(0.,end_edge-.02))) if lo<=1e-6 else (lo,hi)
                  for lo,hi in safe]
        if safe:result[oid]=[(lo,hi) for lo,hi in safe if hi-lo>1e-6]
    return result

def visible_intervals(axis):
    end=g.length(axis['points'])
    cursor=0
    for lo,hi in sorted(axis.get('guidance_cuts',())):
        if lo>cursor+1e-6:yield cursor,lo
        cursor=max(cursor,hi)
    if end>cursor+1e-6:yield cursor,end

def project_visible(axis,q):
    if not axis.get('guidance_cuts'):
        return g.project(axis['points'],q)
    return min(((d,lo+s,p) for lo,hi in visible_intervals(axis)
                for d,s,p in [g.project(g.subpath(axis['points'],lo,hi),q)]),
               default=None,key=lambda result:result[0])

def span(axis,station,length,direction):
    window=next(((lo,hi) for lo,hi in visible_intervals(axis)
                 if lo-1e-6<=station<=hi+1e-6),(station,station))
    lo,hi=window
    return (station,min(hi,station+length)) if direction=='END' else (max(lo,station-length),station)

def connector_curves(scene,base):
    """Use the same derived branch geometry as the painted connector guides."""
    from junction_routes import branches
    from marks11 import legacy_reverse_routes

    def curve(oid,owner,target,points):
        axis=base[owner]
        return dict(id=oid,name=axis['name'],kind='TAXIWAY',points=points,
                    props=dict(guidance_parents=(owner,target),guidance_owner20=owner,
                               width=axis['props']['width'],flow='BOTH'))

    for mid,movement in scene.movements.items():
        if (mid not in base or not movement.get('guide_visible',True)
                or not movement.get('join_reverse_visible',True)):
            continue
        for branch in branches(scene,movement):
            target=movement[branch['side']]['asset']
            if target in base:
                yield curve(branch['oid'],mid,target,branch['points'])
    for oid,branch in legacy_reverse_routes(scene).items():
        owner,target=branch['owner'],branch['target']
        if owner in base and target in base:
            yield curve(oid,owner,target,branch['points'])

def routes(scene):
    key=(id(scene.data),scene.revision);cache=getattr(scene,'_guidance20',None)
    if not scene._transaction_depth and cache and cache[0]==key:return cache[1]
    from pavement_geometry import crossings,turn_guides
    from model20 import axes
    base={k:dict(a,points=[list(p) for p in a['points']],props=dict(a['props'])) for k,a in axes(scene).items() if a['kind'] in TAXIS and not a['props'].get('closed')};curves={}
    junctions=crossings(scene)
    cuts=junction_cuts(scene,junctions,base)
    from scene_render import junction_guide_path
    for j in junctions:
        parents=tuple(aid if aid in base else None for aid in j['assets'])
        if not any(parents):continue
        if any(aid is None and scene.assets.get(source,{}).get('kind')!='RUNWAY'
               for aid,source in zip(parents,j['assets'])):continue
        axes=[base[aid] for aid in parents if aid is not None]
        for guide in turn_guides(scene,j):
            points=[list(q) for q in junction_guide_path(scene,j,guide)]
            for index,parent in zip((0,-1),parents):
                if parent is not None:points[index]=g.project(base[parent]['points'],points[index])[2]
            oid='G20-'+hashlib.sha1((j['id']+guide['key']).encode()).hexdigest()[:14]
            curves[oid]=dict(id=oid,name=' ↔ '.join(a['name'] for a in axes),kind='TAXIWAY',
                             points=points,props=dict(guidance_parents=parents,
                             width=min(a['props']['width'] for a in axes),
                             flow='BOTH',guidance_owner20=axes[0]['id'],junction20=j['id']))
    for aid,a in base.items():
        total=g.length(a['points'])
        gaps=sorted(cuts.get(aid,()))
        lo,hi=0.,total
        for start,end in gaps:
            if start<=lo+1e-6:lo=max(lo,end)
        for start,end in reversed(gaps):
            if end>=hi-1e-6:hi=min(hi,start)
        if hi-lo>1e-6:
            a['points']=g.subpath(a['points'],lo,hi)
            a['guidance_cuts']=[(max(0,start-lo),min(hi,end)-lo)
                                for start,end in gaps if end>lo+1e-6 and start<hi-1e-6]
        else:
            a['guidance_cuts']=[(0,total)]
    curves.update((a['id'],a) for a in connector_curves(scene,base))
    base.update(curves)
    # Shared tangent anchors must be identical despite trigonometric roundoff.
    for a in base.values():a['points']=[[round(x,7) for x in q] for q in a['points']]
    if not scene._transaction_depth:scene._guidance20=(key,base)
    return base

def snap(scene,q,tolerance,visible=None):
    rows=[]
    for aid,a in routes(scene).items():
        if visible and not all(visible(key) for key in a['props'].get('guidance_parents',(aid,))):continue
        hit=project_visible(a,q)
        if hit and hit[0]<=tolerance:rows.append((hit[0],aid,hit[1],hit[2]))
    return min(rows,key=lambda x:x[0]) if rows else None

class AxisHit(tuple):
    def __new__(cls,row,source,tangent):
        hit=super().__new__(cls,row)
        hit.source=source
        hit.tangent=tangent
        return hit

def snap_axis(scene,q,assets,tolerance,pavement=False):
    visible=routes(scene)
    hits=[]
    for oid,path in visible.items():
        if not path['props'].get('center_visible',path['props'].get('guide_visible',True)):
            continue
        parents=[aid for aid in path['props'].get('guidance_parents',(oid,)) if aid in assets]
        if not parents:
            continue
        hit=project_visible(path,q)
        if not hit:continue
        d,s,p=hit
        if d>max(tolerance,path['props']['width']/2 if pavement else 0):
            continue
        aid=min(parents,key=lambda parent:g.project(assets[parent]['points'],p)[0])
        _,station,_=g.project(assets[aid]['points'],p)
        _,u=g.at(path['points'],s)
        hits.append(AxisHit((d,aid,station,p),(oid,s),u))
    for aid,a in assets.items():
        if a['kind'] in TAXIS and (aid in visible or a['props'].get('closed')):
            continue
        d,s,p=g.project(a['points'],q)
        if d<=max(tolerance,a['props']['width']/2 if pavement else 0):
            hits.append((d,aid,s,p))
    from pavement_geometry import crossings
    nodes=[]
    if assets and tolerance>0:
        for junction in crossings(scene):
            point=junction['point']
            distance=g.distance(q,point)
            if distance>tolerance*.6:continue
            choices=[]
            for index,aid in enumerate(junction['assets']):
                if aid not in assets or assets[aid]['props'].get('closed'):continue
                station=junction['stations'][index]
                _,tangent=g.at(assets[aid]['points'],station)
                choices.append((g.project(assets[aid]['points'],q)[0],
                                AxisHit((distance,aid,station,point),(aid,station),tangent)))
            if choices:nodes.append(min(choices,key=lambda choice:choice[0])[1])
    if nodes:return min(nodes,key=lambda hit:hit[0])
    return min(hits,key=lambda hit:hit[0],default=None)

def attachment_pose(scene,asset,station,source=None):
    if source:
        oid,distance=source
        route=routes(scene).get(oid)
        if route:
            return g.at(route['points'],distance)
    return g.at(asset['points'],station)

def select(scene,hit,length=47,direction='END'):
    if not math.isfinite(length) or length<=0:raise ValueError('增强长度必须大于0')
    _,source,s,q=hit;a=routes(scene)[source];lo,hi=span(a,s,length,direction)
    if hi-lo<.01:raise ValueError('该方向没有可绘制中线')
    return scene.create_marking('TWY_ENHANCED',g.subpath(a['points'],lo,hi),enhanced_anchor19=True,enhanced_source20=source,enhanced_origin20=q,label_asset=a['props'].get('guidance_owner20',source),enhanced_station19=s,enhanced_length19=length,enhanced_direction19=direction)

def sync_mark(scene,mark):
    p=mark['props'];source=p.get('enhanced_source20') or p.get('label_asset');a=routes(scene).get(source)
    if not a:p['enhanced_orphan20']=True;return
    p.pop('enhanced_orphan20',None)
    if 'enhanced_origin20' not in p:
        original=scene.assets.get(source)
        p['enhanced_origin20']=g.at(original['points'],p['enhanced_station19'])[0] if original else list(mark['points'][0])
    hit=project_visible(a,p['enhanced_origin20'])
    if not hit:p['enhanced_orphan20']=True;return
    _,s,_=hit
    lo,hi=span(a,s,p['enhanced_length19'],p['enhanced_direction19'])
    # Other waiting positions bound the visible main segment as well as propagation.
    for m in scene.assets.values():
        if m['props'].get('mark_type') not in ('HOLD_A','HOLD_B'):continue
        d,t,_=g.project(a['points'],m['points'][0])
        if d<.5:
            if p['enhanced_direction19']=='END' and s+.01<t<hi:hi=t
            if p['enhanced_direction19']=='START' and lo<t<s-.01:lo=t
    if hi-lo<=.001:p['enhanced_orphan20']=True;return
    mark['points']=g.subpath(a['points'],lo,hi)
    p['enhanced_source20']=source
