"""Checker transition covers the protected crossing, not only the pavement width."""
def checker_mask(scene,stand_designs=None):
    from geometry11 import aircraft_routes,LineString,unary_union
    from roads17 import TAXI_DISTANCE,STAND_DISTANCE
    extension=max(0.,scene.data['meta'].get('road_checker_extension18',3.))
    shapes=[]
    for a in aircraft_routes(scene).values():
        code=a['props'].get('code_letter')
        if code not in TAXI_DISTANCE:
            span=scene.scenario['aircraft_wingspan'];code=next((c for b,c in [(15,'A'),(24,'B'),(36,'C'),(52,'D'),(65,'E'),(80,'F')] if span<b),'F')
        clearance=(STAND_DISTANCE if a['kind']=='STAND_TAXILANE' else TAXI_DISTANCE)[code]
        shapes.append(LineString(a['points']).buffer(max(a['props']['width']/2,clearance)+extension,cap_style=2,join_style=1))
    from stand15 import design
    from shapely import STRtree
    roads=[LineString(a['points']).buffer(a['props']['width']/2,cap_style=2)
           for a in scene.assets.values() if a['kind']=='ROAD']
    if not roads:return unary_union(shapes)
    tree=STRtree(roads)
    for stand in scene.assets.values():
        p=stand['props']
        if stand['kind']=='STAND' and not p.get('closed') and p.get('auto_markings',True):
            lead=(stand_designs or {}).get(stand['id'])
            if lead is None:
                lead=design(stand,scene)
            paths=lead.get('full_paths15') or lead['paths']
        elif stand['kind']=='MARKING' and p.get('mark_type') in (
                'LEAD_IN','LEAD_IN_A','LEAD_IN_B','LEAD_IN_C','LEAD_IN_D'):
            from marking_catalog import primitives
            paths=[row for row in primitives(stand) if row['type']=='line']
        else:continue
        code=p.get('code_letter')
        if code not in STAND_DISTANCE:
            span=p.get('maxspan') or scene.scenario['aircraft_wingspan']
            code=next((c for bound,c in ((15,'A'),(24,'B'),(36,'C'),(52,'D'),(65,'E'),(80,'F')) if span<bound),'F')
        for path in paths:
            points=path['points']
            if len(points)<2:continue
            line=LineString(points)
            if len(tree.query(line,predicate='intersects')):
                shapes.append(line.buffer(STAND_DISTANCE[code]+extension,cap_style=2,join_style=1))
    return unary_union(shapes)
