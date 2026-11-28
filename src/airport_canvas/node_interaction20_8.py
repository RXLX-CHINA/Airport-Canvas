"""Shift constraints, axis snapping and control-point hover cursors."""
import math
import scene_geometry as g

def resolve(scene,q,anchor,shift,tolerance,exclude=None,tangent=None,visible=None):
    import model20
    from geometry11 import LineString,Point
    axes=model20.axes(scene);axes.update({aid:a for aid,a in scene.assets.items() if a['kind']=='ROAD'})
    if visible:axes={oid:row for oid,row in axes.items() if visible(oid)}
    if shift:
        perpendicular=[]
        for aid,a in axes.items():
            if aid==exclude:continue
            distance,_,_=g.project(a['points'],q)
            if distance<=tolerance:
                _,station,p=g.project(a['points'],anchor)
                # The foot must lie inside a segment, rather than extending its cap.
                _,u=g.at(a['points'],station);d=[p[k]-anchor[k] for k in (0,1)]
                if abs(sum(d[k]*u[k] for k in (0,1)))<1e-5:perpendicular.append((distance,aid,station,p))
        if perpendicular:
            hit=min(perpendicular,key=lambda row:(row[0],row[1]));return hit[3],hit
        q=__import__('project10').constrain(anchor,q,tangent)
    rows=[]
    for aid,a in axes.items():
        if aid==exclude:continue
        if shift:
            u=g.unit(anchor,q)
            if g.distance(anchor,q)<1e-9:continue
            line=LineString([[anchor[k]-u[k]*1e7 for k in (0,1)],[anchor[k]+u[k]*1e7 for k in (0,1)]])
            intersection=line.intersection(LineString(a['points']))
            if intersection is None or intersection.is_empty:continue
            target=intersection.interpolate(intersection.project(Point(q))) if intersection.geom_type in ('LineString','MultiLineString') else min([intersection] if intersection.geom_type=='Point' else [p for p in getattr(intersection,'geoms',[]) if p.geom_type=='Point'],key=lambda p:p.distance(Point(q)),default=None)
            if target is None:continue
            p=[target.x,target.y];distance=g.distance(q,p);station=g.project(a['points'],p)[1]
        else:distance,station,p=g.project(a['points'],q)
        if distance<=tolerance:rows.append((distance,aid,station,p))
    hit=min(rows,key=lambda row:(row[0],row[1])) if rows else None
    return (hit[3] if hit else q),hit

def hover(app,e):
    d=app.__dict__
    if d.get('mode') not in ('SELECT','NODES'):return
    points=[]
    for row in d.get('_polygon_handles20_7',[]):points.append((row[0],row[1],'sizing'))
    for row in d.get('_corner_handles12',[]):points.append((row[0],row[1],'hand2' if row[3]!='VERTEX' else 'sizing'))
    for key in ('_entry_handle20','_bridge_handle20_6'):
        row=d.get(key)
        if row:points.append((row[0],row[1],'sizing'))
    for x,y,h in d.get('_semantic_handles14',[]):points.append((x,y,'hand2'))
    if d.get('selection') in app.scene.movements:
        geometry=app.control_geometry()
        if geometry:
            for p in geometry[:2]:
                x,y=app.screen(p);points.append((x,y,'sizing'))
            for p in geometry[2]:
                x,y=app.screen(p);points.append((x,y,'crosshair'))
    cursor=next((cursor for x,y,cursor in reversed(points) if math.hypot(e.x-x,e.y-y)<=10),None)
    if cursor:app.canvas.configure(cursor=cursor);d['_node_cursor20_8']=True
    elif d.pop('_node_cursor20_8',False) or d.get('mode')=='NODES':app.canvas.configure(cursor='')


def edge_insertion(points,point,tolerance,closed=False):
    """Return the nearest interior projection on an editable edge."""
    from math import dist
    edges=zip(points,points[1:]+(points[:1] if closed else []))
    candidates=[]
    for index,(a,b) in enumerate(edges,1):
        dx,dy=b[0]-a[0],b[1]-a[1]
        length2=dx*dx+dy*dy
        if not length2:continue
        t=((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length2
        if not 1e-6<t<1-1e-6:continue
        q=[a[0]+t*dx,a[1]+t*dy]
        candidates.append((dist(point,q),index,q))
    if candidates:
        distance,index,q=min(candidates)
        if distance<=tolerance:return index,q
