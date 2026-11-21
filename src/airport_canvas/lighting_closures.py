"""Derived closure state for the lighting plan."""
import scene_geometry as g


def lighting_closures(scene, include_partial=True):
    from model20 import axes
    from pavement_geometry import crossings

    runways = {aid for aid,a in scene.assets.items() if a['kind']=='RUNWAY'}
    scenario_closed = set(scene.scenario['closed_assets'])
    explicit = {aid for aid,a in scene.assets.items() if aid in scenario_closed
                or a['props'].get('closed') or include_partial and scene.is_closed(aid)}
    if not explicit:
        return set(),set(),False
    routes = axes(scene)
    closed_runways = explicit & runways
    closed = set(explicit)
    neighbors = {aid:set() for aid in routes if aid not in runways}
    lengths = {aid:g.length(asset['points']) for aid,asset in routes.items()}

    def connect(aid,other):
        if aid in neighbors and aid!=other:
            neighbors[aid].add(other)

    for mid,move in scene.movements.items():
        a,b = (move[key]['asset'] for key in ('from','to'))
        if not move.get('enabled',True):
            closed.add(mid)
            continue
        if move.get('legacy_attachment'):
            connect(a,b)
            connect(b,a)
            if closed_runways.intersection((a,b)):
                closed.add(mid)
        elif mid in neighbors:
            for end in (a,b):
                connect(mid,end)
                connect(end,mid)

    for junction in crossings(scene):
        a,b = junction['assets']
        for index,(aid,other) in enumerate(((a,b),(b,a))):
            if aid not in neighbors:
                continue
            station = junction['stations'][index]
            # An interior runway crossing is not a runway entrance.
            if other not in runways or min(station,lengths[aid]-station)<=.1:
                connect(aid,other)

    from geometry11 import Point, polygon
    aprons = {aid:polygon(asset['points']) for aid,asset in scene.assets.items()
              if asset['kind']=='APRON'}
    for aid,links in neighbors.items():
        asset = routes[aid]
        path = asset['points']
        endpoints = (path[0],path[-1])
        for rid in runways:
            runway = routes[rid]
            axis = g.unit(*runway['points'])
            for point in endpoints:
                distance,_,origin = g.project(runway['points'],point)
                longitudinal = sum((point[k]-origin[k])*axis[k] for k in (0,1))
                if abs(longitudinal)<=.1 and distance<=runway['props']['width']/2+.1:
                    links.add(rid)
        parent = asset['props'].get('parent_id')
        if parent in aprons:
            links.add(parent)
        for apron,area in aprons.items():
            if any(area.covers(Point(*point)) for point in endpoints):
                links.add(apron)

    while True:
        isolated = {aid for aid,links in neighbors.items()
                    if aid not in closed and links and links <= closed}
        if not isolated:
            break
        closed.update(isolated)
    return closed,closed_runways,bool(runways and closed_runways==runways)



def pavement_closures(scene):
    key = (id(scene.data),scene.revision)
    cached = getattr(scene,'_pavement_closures',None)
    if not scene._transaction_depth and cached and cached[0]==key:
        return cached[1]
    closed,_,_ = lighting_closures(scene,include_partial=False)
    closed = frozenset(closed)
    if not scene._transaction_depth:
        scene._pavement_closures = (key,closed)
    return closed
