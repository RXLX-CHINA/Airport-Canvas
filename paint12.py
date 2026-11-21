"""Exact paint footprint interruption; threshold stripes preserve yellow guidance."""
import scene_geometry as g
from geometry11 import LineString,Point,polygon,lines,polygons,unary_union,STRtree

def interrupt(scene,items,generated):
    from marking_standards import permanently_closed
    from marking_catalog import YELLOW,WHITE
    marks={k:a for k,a in scene.assets.items() if a['kind']=='MARKING'};marks.update(generated)
    masks=[];runway_circles=[]
    for item in items:
        a=marks.get(item.get('oid'));key=a['props']['mark_type'] if a else None
        # 6.2.8(3): yellow is continuous across threshold stripes. Other runway
        # paint is kept clear only at its actual painted footprint.
        if key in ('RWY_THRESHOLD','THRESHOLD_BAR'):continue
        wait=key in ('HOLD_A','HOLD_B','INTERMEDIATE','INTERMEDIATE_POINT')
        white=item.get('stroke')==WHITE or item.get('fill')==WHITE
        if not wait and not (white and key in ('RWY_CENTER','RWY_CIRCLE','AIMING_POINT','TDZ_BASIC','TDZ_CODED','DISPLACED_ARROW','THRESHOLD_HEADS','RWY_NUMBER')):continue
        if item['type']=='text':
            from paint10 import plate
            shape=polygon(plate(item,0)['points'])
        elif item['type']=='polygon':
            poly=polygon(item['points']);shape=poly if item.get('fill') else LineString(item['points']+[item['points'][0]]).buffer(item.get('width',.15)/2,cap_style=2,join_style=1)
        elif len(item['points'])>1:
            line=LineString(item['points']);shape=line.buffer(item.get('width',.15)/2,cap_style=2,join_style=1)
            if item.get('dash') and not wait:
                dash,gap=item['dash'][:2];parts=[];s=-item.get('dash_offset',0)%(dash+gap)-(dash+gap)
                while s<line.length:
                    lo=max(0,s);hi=min(line.length,s+dash)
                    if hi>lo:parts.append(LineString(g.subpath(item['points'],lo,hi)).buffer(item.get('width',.15)/2,cap_style=2))
                    s+=dash+gap
                shape=unary_union(parts)
        else:continue
        clearance=.9 if wait or key=='RWY_CENTER' else 0
        masks.append((item['oid'],shape,clearance))
        if key=='RWY_CIRCLE':runway_circles.append((a.get('owner') or a['props'].get('label_asset'),shape))
    out=[];mask_cache={}
    def nearby(line,half):
        if half not in mask_cache:
            shapes=[shape.buffer(max(0,margin+half-1e-7),join_style=1) for oid,shape,margin in masks]
            mask_cache[half]=(shapes,STRtree(shapes))
        shapes,tree=mask_cache[half]
        return [(masks[int(i)][0],shapes[int(i)]) for i in tree.query(line,predicate='intersects')]
    guides={'LEAD_IN','LEAD_OUT','AUX_LEAD','TURN_PAD_GUIDE','TWY_CENTER','TWY_ENHANCED','ALIGNMENT'}
    for item in items:
        a=marks.get(item.get('oid'));key=a['props']['mark_type'] if a else '';owner=(a.get('owner') or a['props'].get('label_asset')) if a else item.get('oid')
        if (permanently_closed(scene,owner) and key not in ('CLOSED_RWY','CLOSED_TWY','NO_ENTRY')
                and (a or {}).get('props',{}).get('sign_role23')!='NO_ENTRY_BOARD'):
            if a or item.get('stroke') or item.get('fill') in (YELLOW,WHITE):continue
        if item['type']!='line' or len(item['points'])<2:out.append(item);continue
        line=LineString(item['points']);cut=[]
        if item.get('stroke')==YELLOW and (not key or key in guides):
            half=item.get('width',.15)/2
            for oid,expanded in nearby(line,half):
                if oid==item.get('oid'):continue
                cut.append(expanded)
        if key=='RWY_CENTER':
            # The centre circle is an open interior. Keep the existing dash phase
            # either side; do not restart a new pattern after clipping.
            for own,shape in runway_circles:
                if own==owner:
                    center=shape.centroid;radius=(shape.bounds[2]-shape.bounds[0])/2
                    runway=scene.assets.get(owner,{});clear=runway.get('props',{}).get('circle_clearance13',3.)
                    cut.append(center.buffer(radius+item.get('width',.15)/2+max(0,clear),quad_segs=64))
        if not cut:out.append(item);continue
        for part in lines(line.difference(unary_union(cut))):
            pts=[list(q) for q in part.coords];station=line.project(Point(pts[0]));out.append(dict(item,points=pts,dash_offset=item.get('dash_offset',0)+station,exact_clearance12=True))
    return out



def top_runway_paint(scene,items,generated):
    """Apply runway foreground after taxi paint without changing guidance geometry."""
    top=[]
    rest=[]
    for item in items:
        oid=item.get('oid')
        mark=generated.get(oid) or scene.assets.get(oid,{})
        p=mark.get('props',{})
        kind=p.get('mark_type','') or ''
        owner=scene.assets.get(mark.get('owner') or p.get('label_asset') or oid,{})
        protected=(kind.startswith('RWY_') or kind in (
            'THRESHOLD_BAR','THRESHOLD_HEADS','DISPLACED_ARROW','AIMING_POINT',
            'TDZ_BASIC','TDZ_CODED','CLOSED_RWY')
            or (owner.get('kind')=='RUNWAY' and item.get('runway_edge11')))
        if protected and not item.get('surface11') and not item.get('sign_board21_2'):
            top.append(item)
        else:
            rest.append(item)
    return rest+top
