"""Exact, shared pavement unions. GEOS wheels are bundled for this Windows build."""
from pathlib import Path
import sys
import os
if os.name=='nt' and sys.version_info[:2]==(3,12):
    vendor=Path(__file__).with_name('_vendor')
    if vendor.is_dir() and str(vendor) not in sys.path:sys.path.insert(0,str(vendor))
from shapely import Polygon,LineString,Point,GeometryCollection,unary_union as _union_raw,make_valid,line_merge,STRtree,set_precision
from shapely.errors import GEOSException
import scene_geometry as g

def unary_union(geometries,grid_size=None,**kwargs):
    """Retry overlay topology failures on a sub-millimetre drawing grid.

    Scene coordinates are never modified. Materialize iterators once so that
    the recovery attempt cannot accidentally union an exhausted generator.
    """
    geometries=list(geometries)
    try:
        return _union_raw(geometries,**dict(kwargs,**({'grid_size':grid_size} if grid_size is not None else {})))
    except GEOSException as exc:
        if 'TopologyException' not in str(exc):raise
        precision=max(.0001,grid_size or 0)
        repaired=[set_precision(make_valid(shape),precision) for shape in geometries if shape is not None and not shape.is_empty]
        return _union_raw(repaired,grid_size=precision,**kwargs)

def polygon(points):
    if len(points)<3:return GeometryCollection()
    return make_valid(Polygon(points))

def parts(geometry,kind=None):
    if geometry is None or geometry.is_empty:return []
    if hasattr(geometry,'geoms'):return [part for child in geometry.geoms for part in parts(child,kind)]
    return [geometry] if kind is None or geometry.geom_type in kind else []

def lines(geometry):return parts(geometry,('LineString','LinearRing'))
def polygons(geometry):return parts(geometry,('Polygon',))

def ownership_vertices(coords,routes):
    """Keep short numbered segments selectable after a geometric union."""
    endpoints=[a['points'][i] for a in routes for i in (0,-1)]
    result=[]
    for p,q in zip(coords,coords[1:]):
        dx,dy=q[0]-p[0],q[1]-p[1];length2=dx*dx+dy*dy
        cuts={0.,1.}
        if length2>1e-12:
            for e in endpoints:
                t=((e[0]-p[0])*dx+(e[1]-p[1])*dy)/length2
                if 1e-8<t<1-1e-8:cuts.add(t)
        result.extend([[p[0]+t*dx,p[1]+t*dy] for t in sorted(cuts)[:-1]])
    if coords:result.append(list(coords[-1]))
    return result

def aircraft_routes(scene):
    from pavement_geometry import route_objects
    from marks11 import legacy_reverse_routes
    result={aid:a for aid,a in route_objects(scene).items() if a['kind']!='RUNWAY'}
    for aid,a in list(result.items()):
        root=aid.split(':')[0]
        if root in scene.movements:result[aid]=dict(a,owner=root)
    result.update(legacy_reverse_routes(scene));return result

def aircraft_union(scene):
    return unary_union([LineString(a['points']).buffer(a['props']['width']/2,cap_style=2,join_style=1) for a in aircraft_routes(scene).values()])

def clip_extras(scene,items):
    mask=unary_union([polygon(g.rectangle(a['points'],a['props']['width']) if a['kind']=='RUNWAY' else a['points']) for a in scene.assets.values() if a['kind'] in ('RUNWAY','APRON')])
    out=[]
    for item in items:
        for p in polygons(polygon(item['points']).difference(mask)):
            out.append(dict(item,points=[list(q) for q in p.exterior.coords][:-1]))
    return out

def road_bend_patches(scene):
    from pavement_geometry import corridor
    roads=[a for a in scene.assets.values() if a['kind']=='ROAD']
    if not roads:return []
    filled=unary_union(polygon(corridor(a['points'],a['props']['width'])) for a in roads)
    extra=road_union(scene).difference(filled)
    result=[]
    from apron_ops20_18 import simple_parts
    for part in simple_parts(extra):
        if part.area<.00001:continue
        point=part.representative_point()
        owner=min(roads,key=lambda a:g.project(a['points'],[point.x,point.y])[0])
        result.append(dict(oid=owner['id'],points=[list(p) for p in part.exterior.coords][:-1],
                           kind='ROAD',type='polygon',fill=owner['props'].get('pavement_color','#737b83'),
                           surface10=True))
    return result


def road_union(scene):
    revision=(id(scene.data),scene.revision)
    cached=getattr(scene,'_road_union21_2',None)
    if not scene._transaction_depth and cached and cached[0]==revision:return cached[1]
    road=[a for a in scene.assets.values() if a['kind']=='ROAD']
    base=[LineString(a['points']).buffer(a['props']['width']/2,cap_style=2,join_style=1) for a in road]
    # Offset sampled halves jointly at smooth shared endpoints. Independent
    # flat caps otherwise expose a triangular internal edge at the join.
    from roads13 import is_smooth_bend
    for i,a in enumerate(road):
        for b in road[i+1:]:
            for ia in (0,-1):
                q=a['points'][ia]
                for ib in (0,-1):
                    if g.distance(q,b['points'][ib])<.05 and is_smooth_bend(a,b,q):
                        pa=a['points'] if ia==-1 else list(reversed(a['points']))
                        pb=b['points'] if ib==0 else list(reversed(b['points']))
                        base.append(LineString(pa+pb[1:]).buffer(min(a['props']['width'],b['props']['width'])/2,cap_style=2,join_style=1))
    # Recreate the junction fill without apron clipping for the edge topology.
    from roads10 import raw_surface_extras
    base.extend(polygon(item['points']) for item in raw_surface_extras(scene))
    result=unary_union(base,grid_size=.0001)
    if not scene._transaction_depth:scene._road_union21_2=revision,result
    return result

def taxi_edges(scene,surfaces,holds,lighting=False):
    from pavement_geometry import crossings, route_objects
    routes={k:a for k,a in route_objects(scene).items() if a['kind']!='RUNWAY'}
    joined_ends=set()
    for junction in crossings(scene):
        for aid,station in zip(junction['assets'],junction['stations']):
            if aid in routes:
                length=g.length(routes[aid]['points'])
                if min(station,length-station)<.5:joined_ends.add((aid,station>length/2))
    for movement in scene.movements.values():
        if not movement.get('pavement_visible',True):continue
        for end in ('from','to'):
            port=movement[end]
            aid=port['asset']
            if aid in routes:
                length=g.length(routes[aid]['points'])
                station=port['station']
                if min(station,length-station)<.5:joined_ends.add((aid,station>length/2))
    geometries=[polygon(piece['points']) for piece in surfaces['pavement'] if piece['kind'] not in ('RUNWAY','APRON','ROAD')]
    if lighting:
        # Surface drawing omits the lane fill where it lies inside an apron.
        apron=unary_union([polygon(a['points']) for a in scene.assets.values() if a['kind']=='APRON'])
        geometries.extend(LineString(a['points']).buffer(a['props']['width']/2,cap_style=2,join_style=1)
                          .intersection(apron)
                          for a in routes.values() if a['kind']=='APRON_TAXIWAY')
        geometries.extend(polygon(piece['points']).intersection(apron)
                          for piece in surfaces['fillets'] if len(piece['points'])>=3)
    union=unary_union(geometries,grid_size=.0001)
    mask=[polygon(a['points']).buffer(.46,join_style=2) for a in scene.assets.values() if a['kind']=='APRON']
    # Taxi pavement was cut at the runway perimeter. Suppress the inset
    # boundary of that cut on all four sides, including at a runway end.
    if lighting:
        mask=[LineString(a['points']).buffer(a['props']['width']/2+.1,cap_style=2,join_style=1)
              for a in scene.assets.values() if a['kind']=='ROAD']
    insets = (-.10,) if lighting else (.075, .375)
    runway_clearance = max(.1,max(insets) + .075 + .01)
    mask.extend(polygon(g.rectangle(a['points'], a['props']['width'])).buffer(
        runway_clearance, join_style=2) for a in scene.assets.values() if a['kind']=='RUNWAY')
    for runway in surfaces.get('runways',()):
        u=g.unit(*runway['points'])
        for end,sign,q in (('a',-1,runway['points'][0]),('b',1,runway['points'][-1])):
            length=runway['props'].get('stopway_'+end,0)
            if length:
                tip=[q[k]+sign*u[k]*length for k in (0,1)]
                mask.append(polygon(g.rectangle([q,tip],runway['props']['width'])).buffer(
                    runway_clearance,join_style=2))
    for h in holds.values():
        q=h['point'];u=h['tangent'];half=h.get('half',1.05)+.15
        mask.append(polygon(g.rectangle([[q[k]-u[k]*half for k in (0,1)],[q[k]+u[k]*half for k in (0,1)]],h['span']+.2)))
    blocked=unary_union(mask)
    indexes={aid:g.PathIndex(a['points']) for aid,a in routes.items()};ids=list(routes);axes=[LineString(routes[aid]['points']) for aid in ids];tree=STRtree(axes);out=[]
    if not ids:return out
    from shapely import points as make_points, line_locate_point
    for inset in insets:
        boundary=union.buffer(-inset,join_style=1).boundary.difference(blocked)
        for path in lines(boundary):
            coords=ownership_vertices(list(path.coords),routes.values());chunks=[];chunk=[];chunk_owner=None
            pairs=list(zip(coords,coords[1:]))
            if not pairs:continue
            midpoints=make_points([((p[0]+q[0])/2,(p[1]+q[1])/2) for p,q in pairs])
            nearest_ids=tree.nearest(midpoints)
            stations=line_locate_point(tree.geometries.take(nearest_ids),midpoints)
            for (p,q),nearest,station in zip(pairs,nearest_ids,stations):
                aid=ids[nearest]
                _,axis=indexes[aid].at(station)
                tangent=g.unit(p,q)
                length=indexes[aid].length
                cap=(min(station,length-station)<.5 and (aid,station>length/2) not in joined_ends
                     and abs(sum(axis[k]*tangent[k] for k in (0,1)))<.15)
                if cap:
                    if len(chunk)>1:chunks.append((chunk_owner,chunk))
                    chunk=[];chunk_owner=None
                else:
                    own=routes[aid].get('owner',aid)
                    if chunk and own!=chunk_owner:
                        if len(chunk)>1:chunks.append((chunk_owner,chunk))
                        chunk=[]
                    if not chunk:chunk=[p];chunk_owner=own
                    chunk.append(q)
            if len(chunk)>1:chunks.append((chunk_owner,chunk))
            for aid,chunk in chunks:out.append(dict(type='line',oid=aid,points=chunk,stroke='#ffdb64',width=.15,taxi_edge11=True))
    return out

def runway_edges(scene,surfaces):
    from pavement_geometry import offset
    aa=[a for a in scene.assets.values() if a['kind']=='RUNWAY'];out=[]
    mouth=unary_union([polygon(s['points']) for s in surfaces['pavement'] if s['kind'] not in ('RUNWAY','ROAD')]+[LineString(a['points']).buffer(a['props']['width']/2,cap_style=2,join_style=1) for a in aircraft_routes(scene).values()])
    for a in aa:
        if not a['props'].get('edges_visible',True):continue
        w=.9 if a['props']['width']>=30 else .45
        blocked=unary_union([polygon(g.rectangle(b['points'],b['props']['width']+.05)) for b in aa if b['id']!=a['id']]+[mouth.buffer(w/2+.05)])
        for side in (-1,1):
            path=LineString(offset(a['points'],side*(min(30,a['props']['width']/2)-w/2)))
            for line in lines(path.difference(blocked)):
                out.append(dict(type='line',oid=a['id'],points=[list(q) for q in line.coords],stroke='#ffffff',width=w,runway_edge11=True))
    return out
