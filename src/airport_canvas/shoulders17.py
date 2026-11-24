"""Shoulder bars come from the exposed boundary of the whole pavement union."""
import math
import scene_geometry as g
def bars(scene,surfaces):
    from geometry11 import polygon,unary_union,LineString,Point,lines,polygons,STRtree,set_precision
    from pavement_geometry import route_objects,shoulder_width
    routes=route_objects(scene)
    pavement=set_precision(unary_union([polygon(p['points']) for p in surfaces['pavement']],grid_size=.0001),.0001)
    # Keep the paint footprint strictly outside the unsnapped pavement too:
    # a 1-mm guard exceeds the sub-mm recovery grid's rounding error.
    shoulder=set_precision(unary_union([polygon(p['points']) for p in surfaces['shoulders']],grid_size=.0001),.0001).difference(pavement.buffer(.001))
    if shoulder.is_empty:return []
    eligible=[a for a in routes.values() if a['kind']!='RUNWAY']
    if not eligible:return []
    axes=[LineString(a['points']) for a in eligible];tree=STRtree(axes)
    route_paths=[g.PathIndex(a['points']) for a in eligible]
    fillet_axes=[LineString(p['arc']) for p in surfaces.get('fillets',[]) if len(p.get('arc',[]))>1]
    from shapely import clip_by_rect, make_valid
    from shapely.prepared import prep
    probe=prep(shoulder.buffer(.01));out=[];used=[]
    holds=__import__('automatic_markings').holding_locations(scene);hold_axes=[]
    for h in holds:
        if 'point' not in h:continue
        q=h['point'];u=h['tangent'];v=[-u[1],u[0]];half=h.get('span',h.get('width',23))/2
        hold_axes.append(LineString([[q[k]-v[k]*half for k in (0,1)],[q[k]+v[k]*half for k in (0,1)]]))
    for m in scene.assets.values():
        if m['kind']=='MARKING' and m['props']['mark_type'] in ('HOLD_A','HOLD_B','INTERMEDIATE_POINT'):
            q=m['points'][0];u=g.unit(m['points'][0],m['points'][-1]);v=[-u[1],u[0]];half=m['props']['width']/2
            hold_axes.append(LineString([[q[k]-v[k]*half for k in (0,1)],[q[k]+v[k]*half for k in (0,1)]]))
    fillets=STRtree(fillet_axes)
    holding=STRtree(hold_axes)
    from marking_catalog import YELLOW
    for boundary in lines(pavement.boundary):
        pts=[list(q) for q in boundary.coords];path=g.PathIndex(pts);L=path.length
        if L<1:continue
        for i in range(max(1,math.ceil(L/12))):
            s=L*i/max(1,math.ceil(L/12));q,u=path.at(s);_,before=path.at(max(0,s-3));_,after=path.at(min(L,s+3))
            if sum(before[k]*after[k] for k in (0,1))>.9995:continue
            point=Point(q);nearest=int(tree.nearest(point));a=eligible[nearest]
            if not a['props'].get('auto_shoulder_bars',True) or shoulder_width(a['kind'],a['props'])<=0:continue
            station=axes[nearest].project(point);route=route_paths[nearest];_,ua=route.at(max(0,station-6));_,ub=route.at(min(route.length,station+6))
            if sum(ua[k]*ub[k] for k in (0,1))>.9999 and not len(fillets.query(point,predicate='dwithin',distance=1.1)):continue
            if axes[nearest].distance(point)>a['props']['width']/2+max(50,a['props'].get('fillet_radius',25)*3):continue
            if any(g.distance(q,p)<7.5 for p in used):continue
            for sign in (-1,1):
                n=[-u[1]*sign,u[0]*sign]
                if not probe.covers(Point(q[0]+n[0]*.25,q[1]+n[1]*.25)):continue
                ray=LineString([q,[q[k]+n[k]*30 for k in (0,1)]])
                x0,y0,x1,y1=ray.bounds
                # Keep the clip boundary outside both the ray and its paint footprint.
                local=clip_by_rect(shoulder,x0-1,y0-1,x1+1,y1+1)
                if not local.is_valid:local=make_valid(local)
                candidates=sorted(lines(ray.intersection(local)),key=lambda p:p.distance(point))
                if not candidates or candidates[0].distance(point)>.3:continue
                reach=candidates[0].length;length=min(7.5,reach if reach<3.5 else max(0,reach-1.5))
                if length<.5:continue
                axis=LineString([q,[q[k]+n[k]*length for k in (0,1)]])
                if len(holding.query(axis,predicate='dwithin',distance=7.5)):continue
                # Clip the full 0.9-m paint footprint, not sparse centre samples.
                ink=axis.buffer(.45,cap_style=2).intersection(local)
                for poly in polygons(ink):
                    if poly.area>.2:out.append(dict(type='polygon',oid=a['id'],points=[list(p) for p in poly.exterior.coords][:-1],fill=YELLOW,width=.9,shoulder_bar17=True))
                used.append(q);break
    return out
