"""Runway paint priority without moving aiming/TDZ station grids."""
import scene_geometry as g
def rank(a):return (max({'v':0,'0':1,'1':2,'2':2,'3':2}[a['props'].get('level_'+end,'1')] for end in ('a','b')),a['props'].get('runway_priority13',0))
def runway_priority(scene,items,generated):
    from geometry11 import LineString,Point,polygon,lines,polygons,unary_union
    runways=[a for a in scene.assets.values() if a['kind']=='RUNWAY'];order={a['id']:i for i,a in enumerate(runways)};out=[]
    masks={a['id']:unary_union([polygon(g.rectangle(b['points'],b['props']['width'])) for b in runways if b['id']!=a['id'] and (rank(b),-order[b['id']])>(rank(a),-order[a['id']])]) for a in runways}
    for item in items:
        mark=generated.get(item.get('oid')) or scene.assets.get(item.get('oid'),{});owner=mark.get('owner') or mark.get('props',{}).get('label_asset') or item.get('oid');a=scene.assets.get(owner);mask=masks.get(owner)
        if not a or a['kind']!='RUNWAY' or mask is None or mask.is_empty or item.get('surface10') or item.get('surface11') or item['type']=='polygon' and item.get('fill') in ('#454b53','#737b83','#9199a1','#c7cbd0'):out.append(item);continue
        if mark.get('props',{}).get('intersection_unresolved20'):continue
        if mark.get('props',{}).get('whole_group20'):
            out.append(item);continue
        if item['type']=='line':
            axis=LineString(item['points']);half=item.get('width',.15)/2
            for part in lines(axis.difference(mask.buffer(half,join_style=2))):
                pts=[list(q) for q in part.coords];out.append(dict(item,points=pts,dash_offset=item.get('dash_offset',0)+axis.project(Point(pts[0])),intersection_clipped17=True))
        elif item['type']=='polygon':
            if item.get('fill'):
                for part in polygons(polygon(item['points']).difference(mask)):out.append(dict(item,points=[list(q) for q in part.exterior.coords][:-1],intersection_clipped17=True))
            else:
                for part in lines(LineString(item['points']+[item['points'][0]]).difference(mask.buffer(item.get('width',.15)/2))):out.append(dict(item,type='line',points=[list(q) for q in part.coords],intersection_clipped17=True))
        else:
            from paint10 import plate
            if not polygon(plate(item,0)['points']).intersects(mask):out.append(item)
    return out
