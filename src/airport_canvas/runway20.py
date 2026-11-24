"""Whole-group intersection relocation, with explicit engineering review notes."""
import copy
import scene_geometry as g
from geometry11 import Polygon,LineString,Point,polygon,unary_union
KEYS={'AIMING_POINT','TDZ_BASIC','TDZ_CODED'}
def sync_manual(scene):
    marks={}
    for aid,a in scene.assets.items():
        p=a['props']
        if p.get('mark_type') not in KEYS or p.get('label_asset') not in scene.assets:continue
        if 'intersection_last20' not in p or a['points']!=p['intersection_last20']:p['intersection_base20']=copy.deepcopy(a['points'])
        mark=copy.deepcopy(a);mark['points']=copy.deepcopy(p['intersection_base20']);mark['props'].pop('intersection_shift20',None);mark['props'].pop('whole_group20',None);mark['props'].pop('intersection_unresolved20',None);marks[aid]=mark
    relocate(scene,marks)
    for aid,mark in marks.items():
        a=scene.assets[aid];a['points']=mark['points']
        for key in ('intersection_shift20','whole_group20','intersection_unresolved20'):
            a['props'].pop(key,None)
            if key in mark['props']:a['props'][key]=mark['props'][key]
        a['props']['intersection_last20']=copy.deepcopy(a['points'])
def relocate(scene,result):
    relevant={k:v for k,v in result.items() if v['props'].get('mark_type') in KEYS}
    if not relevant:return result
    from intersections17 import rank
    signature=(id(scene.data),scene.revision,tuple((a['id'],tuple(map(tuple,a['points'])),a['props']['width'],rank(a),a['props'].get('intersection_relocate20',True)) for a in scene.assets.values() if a['kind']=='RUNWAY'),tuple((k,tuple(map(tuple,a['points'])),repr(a['props'])) for k,a in relevant.items()))
    cached=getattr(scene,'_runway_layout20',None)
    if not scene._transaction_depth and cached and cached[0]==signature:
        for oid,state in cached[1].items():result[oid]['points']=copy.deepcopy(state[0]);result[oid]['props'].update(state[1])
        return result
    result=_relocate(scene,result)
    if not scene._transaction_depth:
        states={}
        for oid in relevant:
            m=result[oid];flags={k:m['props'][k] for k in ('intersection_shift20','whole_group20','intersection_unresolved20') if k in m['props']}
            if flags:states[oid]=(copy.deepcopy(m['points']),flags)
        scene._runway_layout20=(signature,states)
    return result

def _relocate(scene,result):
    from intersections17 import rank
    from marking_catalog import primitives
    runways=[a for a in scene.assets.values() if a['kind']=='RUNWAY'];order={a['id']:i for i,a in enumerate(runways)};out=result
    for a in runways:
        if not a['props'].get('intersection_relocate20',True):continue
        blockers=[polygon(g.rectangle(b['points'],b['props']['width'])) for b in runways if b['id']!=a['id'] and (rank(b),-order[b['id']])>(rank(a),-order[a['id']])]
        if not blockers:continue
        mask=unary_union(blockers).buffer(.1);u=g.unit(a['points'][0],a['points'][-1]);L=g.length(a['points'])
        groups={}
        for oid,m in list(out.items()):
            if (m.get('owner') or m['props'].get('label_asset'))!=a['id'] or m['props'].get('mark_type') not in KEYS:continue
            end='b' if ':b:' in oid else 'a' if ':a:' in oid else ('b' if sum(x*y for x,y in zip(g.unit(m['points'][0],m['points'][-1]),u))<0 else 'a')
            groups.setdefault((end,'AIM' if m['props']['mark_type']=='AIMING_POINT' else 'TDZ'),[]).append(m)
        for (end,kind),marks in sorted(groups.items()):
            active_mask=mask
            if kind=='TDZ':
                aim=[]
                for candidate in out.values():
                    if candidate.get('owner')==a['id'] and candidate['props'].get('mark_type')=='AIMING_POINT':
                        aim.extend(polygon(x['points']).buffer(50) for x in primitives(candidate) if x['type']=='polygon' and x.get('fill')=='#ffffff')
                if aim:active_mask=unary_union([mask]+aim)
            shapes=[]
            for m in marks:
                shapes += [polygon(x['points']) for x in primitives(m) if x['type']=='polygon' and x.get('fill')=='#ffffff']
            footprint=unary_union(shapes)
            if not footprint.intersects(active_mask):continue
            sign=1 if end=='a' else -1;direction=[sign*v for v in u];originals={m['id']:copy.deepcopy(m['points']) for m in marks};found=None
            # Moving the entire TDZ set preserves its internal 150m rhythm and paired blocks.
            for offset in [v for n in range(1,601) for v in ((float(n),) if kind=='AIM' else (float(n),-float(n)))]:
                moved=[]
                valid=True
                for m in marks:
                    points=[[q[k]+direction[k]*offset for k in (0,1)] for q in originals[m['id']]]
                    station=g.project(a['points'],points[0])[1];disp=a['props'].get('displaced_'+end,0);relative=station-disp if sign==1 else L-disp-station
                    if relative< (150 if kind=='TDZ' else 0) or relative+max(60,m['props'].get('aim_length',0))>L-disp:valid=False;break
                    probe=dict(m,points=points);ink=[polygon(x['points']) for x in primitives(probe) if x['type']=='polygon' and x.get('fill')=='#ffffff'];moved.extend(ink)
                if valid and moved and not unary_union(moved).intersects(active_mask):found=offset;break
            if found is not None:
                for m in marks:
                    m['points']=[[q[k]+direction[k]*found for k in (0,1)] for q in originals[m['id']]];m['props'].update(intersection_shift20=found,whole_group20=True)
            else:
                # An impossible group must never become a pile of clipped paint fragments.
                for m in marks:m['props']['intersection_unresolved20']=True
    return out

def checks(scene,generated=None):
    from automatic_markings import generated_markings
    out=[];done=set()
    if generated is None:generated=generated_markings(scene)
    for mark in list(generated.values())+list(scene.assets.values()):
        p=mark['props'];owner=mark.get('owner') or p.get('label_asset')
        if not p.get('intersection_shift20') and not p.get('intersection_unresolved20'):continue
        key=(owner,p.get('mark_type'),p.get('intersection_shift20'))
        if key in done:continue
        done.add(key);out.append(dict(object_id=owner,status='REVIEW_REQUIRED',rule='INTERSECTION_STATION20',message='交叉跑道标志整组移动后需核对瞄准点/PAPI起点及接地带站位。' if p.get('intersection_shift20') else '交叉范围无法容纳完整标志组，请人工重新设计；没有裁成碎块。',source='MH5001—2021 6.2.1、6.2.5、6.2.6；项目选择整组避让',actual=p.get('intersection_shift20'),required='按原文及运行条件复核站位'))
    return out
