"""One drag snap decision shared by grouped-stand preview and commit."""
import scene_geometry as g
import terminal19 as terminal
from transform11 import members

def stands(scene,roots):
    return sorted(aid for aid in members(scene,roots) if aid in scene.assets and scene.assets[aid]['kind']=='STAND')

def candidate(scene,roots,delta,tolerance):
    rows=[]
    for aid in stands(scene,roots):
        a=scene.assets[aid]
        if not a['props'].get('bridge_snap19',True):continue
        home=terminal.stand_home(scene,a);q=[home[k]+delta[k] for k in (0,1)]
        for b in terminal.buildings(scene):
            if b['props']['building_role19']!='BRIDGE':continue
            tip=terminal.bridge_tip(b);distance=g.distance(q,tip)
            if distance<=tolerance:rows.append((distance,aid,b['id'],[tip[k]-home[k] for k in (0,1)],tip))
    return min(rows,key=lambda row:(row[0],row[1],row[2])) if rows else None

def road_on_apron(scene,patches=None):
    from geometry11 import polygon,polygons,unary_union,LineString
    from roads10 import raw_surface_extras
    aprons=unary_union([polygon(a['points']) for a in scene.assets.values() if a['kind']=='APRON' and not a['props'].get('turn_pad')])
    if aprons.is_empty:return []
    runway=unary_union([LineString(a['points']).buffer(a['props']['width']/2,cap_style=2) for a in scene.assets.values() if a['kind']=='RUNWAY'])
    items=[]
    for a in scene.assets.values():
        if a['kind']=='ROAD':items.append(dict(type='polygon',oid=a['id'],points=__import__('pavement_geometry').corridor(a['points'],a['props']['width']),fill=a['props'].get('pavement_color','#737b83'),stroke=None))
    items.extend(raw_surface_extras(scene) if patches is None else patches);out=[]
    for item in items:
        shape=polygon(item['points']).intersection(aprons).difference(runway)
        for part in polygons(shape):out.append(dict(item,points=[list(q) for q in part.exterior.coords][:-1],road_priority20_5=True,surface10=True))
    return out
