"""Clip stand safety overlaps without closing the visible tail boundary."""
import math
import scene_geometry as g
from pavement_geometry import area,halfplane

def triangles(points):
    pts=[list(p) for p in points];changed=True
    while changed and len(pts)>3:
        changed=False
        for i,p in enumerate(pts):
            a,b=pts[i-1],pts[(i+1)%len(pts)]
            if abs((p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0]))<1e-8:pts.pop(i);changed=True;break
    if area(pts)<0:pts.reverse()
    out=[]
    while len(pts)>3:
        for i,p in enumerate(pts):
            a,b=pts[i-1],pts[(i+1)%len(pts)]
            if (p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0])<=1e-8:continue
            tri=[a,p,b]
            if any(g.inside(q,tri) for j,q in enumerate(pts) if j not in ((i-1)%len(pts),i,(i+1)%len(pts))):continue
            out.append(tri);pts.pop(i);break
        else:return []
    if len(pts)==3:out.append(pts)
    return out

def intersection(a,b):
    result=[]
    for ta in triangles(a):
        for tb in triangles(b):
            clipped=list(ta)
            for c,d in zip(tb,tb[1:]+tb[:1]):clipped=halfplane(clipped,c,d)
            if clipped and abs(area(clipped))>1e-6:result.append(clipped)
    return result

def safety_marks(marks):return [a for a in marks.values() if a['props']['mark_type']=='STAND_SAFETY']

def derived(marks,merge_pairs=()):
    from automatic_markings import synthetic
    result={};safety=safety_marks(marks)
    for i,a in enumerate(safety):
        ax=[p[0] for p in a['points']];ay=[p[1] for p in a['points']]
        for b in safety[i+1:]:
            if pair_key(a.get('owner'),b.get('owner')) in merge_pairs:continue
            bx=[p[0] for p in b['points']];by=[p[1] for p in b['points']]
            if max(ax)<=min(bx) or max(bx)<=min(ax) or max(ay)<=min(by) or max(by)<=min(ay):continue
            for j,poly in enumerate(intersection(a['points'],b['points'])):
                axis=g.unit(a['points'][0],a['points'][1]);angle=math.degrees(math.atan2(axis[1],axis[0]))+45
                mark=synthetic(a['owner'],'SAFETY_OVERLAP',poly,'SAFETY_OVERLAP:'+b['owner']+':'+str(j),line_width=.1,spacing=2,omit_outline=True,hatch_angle=angle,hatch_phase=0)
                mark['name']='相邻机位安全线交叉区 '+str(j+1);result[mark['id']]=mark
    return result

def paint_boundaries(items,marks):
    from marking_standards import outside_segments
    safety=safety_marks(marks);lookup={a['id']:a for a in safety};out=[]
    for item in items:
        a=lookup.get(item.get('oid'))
        if not a or item['type']!='line':out.append(item);continue
        polygons=[b['points'] for b in safety if b['id']!=a['id']]
        length=g.length(item['points']);outside=list(outside_segments(item['points'],polygons));inside=[];cursor=0
        for points,station in outside:
            if station>cursor+1e-7:inside.append((cursor,station))
            cursor=station+g.length(points);out.append(dict(item,points=points,dash_offset=item.get('dash_offset',0)+station))
        if length>cursor+1e-7:inside.append((cursor,length))
        for lo,hi in inside:out.append(dict(item,points=g.subpath(item['points'],lo,hi),dash=[.5,1],dash_offset=item.get('dash_offset',0)+lo))
    return out

def pair_key(a,b):
    return '|'.join(sorted((a,b))) if a and b and a!=b else None


def overlap_regions(scene,marks,merged_only=False):
    from geometry11 import STRtree,polygon,polygons,unary_union
    styles=scene.data['meta'].get('object_display',{})
    pairs=scene.data['meta'].get('merged_stand_overlaps',{})
    if merged_only and not pairs:return {}
    candidates=[]
    for mark in safety_marks(marks):
        owner=mark.get('owner')
        if scene.assets.get(owner,{}).get('kind')!='STAND':continue
        if any(styles.get(oid,{}).get('hidden') or styles.get(oid,{}).get('opacity',1)<=0
               for oid in (mark['id'],owner)):continue
        shape=polygon(mark['points'])
        if not shape.is_empty:candidates.append((owner,shape))
    shapes=[shape for _,shape in candidates]
    tree=STRtree(shapes)
    regions={}
    for i,(a,shape) in enumerate(candidates):
        for j in tree.query(shape,predicate='intersects'):
            if j<=i:continue
            b,other=candidates[j]
            key=pair_key(a,b)
            if not key or (merged_only and key not in pairs):continue
            overlap=shape.intersection(other)
            if overlap.area>1e-6:
                regions.setdefault(key,[]).extend(polygons(overlap))
    return {key:unary_union(parts) for key,parts in regions.items()}


def clip_merged_stand_lines(scene,items,marks):
    from geometry11 import LineString,lines,unary_union
    regions=overlap_regions(scene,marks,merged_only=True)
    if not regions:return items
    masks={}
    for pair,shape in regions.items():
        for owner in pair.split('|'):masks.setdefault(owner,[]).append(shape)
    masks={owner:unary_union(shapes) for owner,shapes in masks.items()}
    result=[]
    for item in items:
        oid=item['oid']
        mark=marks.get(oid,{})
        owner=mark.get('owner') or oid
        mask=masks.get(owner)
        if mask is None or item['type'] not in ('line','polygon') or not item.get('stroke'):
            result.append(item)
            continue
        points=item['points']
        polygon_outline=item['type']=='polygon'
        path=LineString(points+[points[0]] if polygon_outline else points)
        if not path.intersects(mask):
            result.append(item)
            continue
        if polygon_outline and item.get('fill'):
            result.append(dict(item,stroke=None))
        for segment in lines(path.difference(mask)):
            coords=[list(q) for q in segment.coords]
            station=g.project(points+[points[0]] if polygon_outline else points,coords[0])[1]
            result.append(dict(item,type='line',points=coords,fill=None,
                               dash_offset=item.get('dash_offset',0)+station))
    return result
