"""Terminal-plane clipping for ALL shoulder contributions, including fillets."""
import scene_geometry as g
from pavement_geometry import halfplane

def trim_shoulders(scene,surfaces):
    from marks11 import legacy_reverse_routes
    from pavement_geometry import corridor,exclude_runways
    from geometry11 import polygon,polygons,unary_union
    runways=surfaces['runways'];aprons=unary_union([polygon(a['points']) for a in scene.assets.values() if a['kind']=='APRON'])
    for branch in legacy_reverse_routes(scene).values():
        aid=branch['owner'];p=branch['props'];path=branch['points']
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
        pieces=[corridor(path,p['width'])]
        fork=source+across[1:]+list(reversed(path))[1:]
        from shapely import Polygon
        if len(fork)>2:
            shape=Polygon(fork)
            if shape.is_valid and shape.area>.01:pieces.append(fork)
        for poly in pieces:
            for piece in exclude_runways(poly,runways):
                for shape in polygons(polygon(piece).difference(aprons)):
                    surfaces['pavement'].append(dict(oid=aid+':reverse11',kind='TAXIWAY',points=[list(q) for q in shape.exterior.coords][:-1]))
        from pavement_geometry import shoulder_width
        shoulder=shoulder_width(scene.assets[aid]['kind'],p)
        if shoulder:
            for piece in exclude_runways(corridor(path,p['width']+2*shoulder),runways):surfaces['shoulders'].append(dict(oid=aid+':reverse11',kind='TAXIWAY',points=piece))
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
    result=[]
    from shapely.ops import triangulate
    for piece in surfaces['shoulders']:
        points=piece['points'];oid=piece['oid']
        if piece['kind']!='RUNWAY':
            for aid,mid,q,edge in constraints:
                if aid in oid or oid.startswith(mid):points=halfplane(points,q,edge)
                if not points:break
        if not points:continue
        if piece['kind'] in ('RUNWAY','APRON') or aprons.is_empty:
            result.append(dict(piece,points=points))
            continue
        footprint=polygon(points)
        if not footprint.intersects(aprons):
            result.append(dict(piece,points=points))
            continue
        for shape in polygons(footprint.difference(aprons)):
            parts=[shape] if not shape.interiors else [
                part for triangle in triangulate(shape) for part in polygons(triangle.intersection(shape))]
            result.extend(dict(piece,points=[list(q) for q in part.exterior.coords][:-1]) for part in parts)
    surfaces['shoulders']=result;return surfaces
