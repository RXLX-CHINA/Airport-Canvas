"""Terminal-plane clipping for ALL shoulder contributions, including fillets."""
import scene_geometry as g
from pavement_geometry import halfplane

def trim_shoulders(scene,surfaces):
    from marks11 import legacy_reverse_routes
    from pavement_geometry import corridor_parts,exclude_runways,shoulder_width
    from geometry11 import polygon,polygons,unary_union
    runways=surfaces['runways'];aprons=unary_union([polygon(a['points']) for a in scene.assets.values() if a['kind']=='APRON'])
    for branch in legacy_reverse_routes(scene).values():
        aid=branch['owner'];p=branch['props'];path=branch['points']
        if p.get('rapid_geometry39',{}).get('reverse_surface_radius'):
            from rapid_editor39 import source
            from smart_routes import reverse_surface
            state=source(scene,aid)
            if state:path=reverse_surface(scene,state[0],branch)['points']
        target=scene.assets[branch['target']]['points']
        receiver,_=g.at(target,branch['target_from'])
        trunk=branch['source_path']
        if g.distance(trunk[0],receiver)<g.distance(trunk[-1],receiver):
            trunk=list(reversed(trunk))
        _,split,_=g.project(trunk,path[0])
        source=g.subpath(trunk,split,g.length(trunk))
        _,main_end,_=g.project(target,source[-1])
        _,reverse_end,_=g.project(target,path[-1])
        lo,hi=sorted((main_end,reverse_end));across=g.subpath(target,lo,hi)
        if main_end>reverse_end:across.reverse()
        pieces=corridor_parts(path,p['width'])
        fork=source+across[1:]+list(reversed(path))[1:]
        from shapely import Polygon
        if len(fork)>2:
            shape=Polygon(fork)
            if shape.is_valid and shape.area>.01:pieces.append(fork)
        for poly in pieces:
            for piece in exclude_runways(poly,runways):
                for shape in polygons(polygon(piece).difference(aprons)):
                    surfaces['pavement'].append(dict(oid=aid+':reverse11',kind='TAXIWAY',points=[list(q) for q in shape.exterior.coords][:-1]))
        shoulder=shoulder_width(scene.assets[aid]['kind'],p)
        if shoulder:
            for outline in corridor_parts(path,p['width']+2*shoulder):
                for piece in exclude_runways(outline,runways):
                    surfaces['shoulders'].append(dict(oid=aid+':reverse11',kind='TAXIWAY',points=piece))
    constraints=[]
    for m in scene.movements.values():
        for side,other in [('from','to'),('to','from')]:
            port=m[side];r=scene.assets[port['asset']]
            if r['kind']!='RUNWAY':continue
            total=g.length(r['points']);station=port['station'];near=max(60,r['props']['width'])
            if min(station,total-station)>near:continue
            start=station<total/2;q=r['points'][0 if start else -1];u=g.unit(r['points'][0],r['points'][-1]);v=[-u[1],u[0]]
            edge=[q[k]+v[k]*(-1 if start else 1) for k in (0,1)]
            constraints.append((m[other]['asset'],m['id'],q,edge))
    from pavement_geometry import crossings,route_objects
    routes=route_objects(scene)
    banks={}
    junction_widths={}
    for junction in crossings(scene):
        pair=[routes[key] for key in junction['assets']]
        junction_widths[junction['id']]=max(
(shoulder_width(route['kind'],route['props']) for route in pair
             if route['kind']!='RUNWAY'), default=0.)
        for runway,connector in (pair,pair[::-1]):
            if runway['kind']!='RUNWAY' or connector['kind']=='RUNWAY':continue
            start,end=runway['points']
            ux,uy=g.unit(start,end)
            offsets=[ux*(y-start[1])-uy*(x-start[0]) for x,y in connector['points']]
            half=runway['props']['width']/2
            if max(offsets)>half and min(offsets)>=-half:
                plane=(start,end)
            elif min(offsets)<-half and max(offsets)<=half:
                plane=(end,start)
            else:continue
            for owner in (junction['id'],connector['id']):
                banks.setdefault(owner,[]).append(plane)
    bearing=unary_union([polygon(piece['points']) for piece in surfaces['pavement']])
    envelopes={}
    result=[]
    from shapely.ops import triangulate
    for piece in surfaces['shoulders']:
        points=piece['points'];oid=piece['oid']
        if piece['kind']!='RUNWAY':
            owner=oid
            while owner:
                for start,end in banks.get(owner,()):
                    points=halfplane(points,start,end)
                owner=owner.rpartition(':')[0]
            for aid,mid,q,edge in constraints:
                if aid in oid or oid.startswith(mid):points=halfplane(points,q,edge)
                if not points:break
        if not points:continue
        if piece['kind'] in ('RUNWAY','APRON'):
            result.append(dict(piece,points=points))
            continue
        footprint=polygon(points)
        junction=oid.removesuffix(':core')
        limit=junction_widths.get(junction)
        if piece['kind']=='FILLET' and limit is not None:
            if limit<=0:continue
            # Independent outer fillets can overshoot at acute or clipped joins.
            # Keep only the configured shoulder band next to the bearing surface.
            if limit not in envelopes:envelopes[limit]=bearing.buffer(limit)
            envelope=envelopes[limit]
            if not envelope.covers(footprint):footprint=footprint.intersection(envelope)
        if not aprons.is_empty and footprint.intersects(aprons):
            footprint=footprint.difference(aprons)
        for shape in polygons(footprint):
            parts=[shape] if not shape.interiors else [
                part for triangle in triangulate(shape) for part in polygons(triangle.intersection(shape))]
            result.extend(dict(piece,points=[list(q) for q in part.exterior.coords][:-1]) for part in parts)
    surfaces['shoulders']=result;return surfaces
