"""Plan-view aeronautical ground lighting layouts."""
import math
import scene_geometry as geometry

WHITE = '#f6f4e5'
RED = '#ff6269'
GREEN = '#61ec99'
YELLOW = '#ffd35a'
BLUE = '#6698ff'

NAMES = {
    'papi':'PAPI',
    'approach': '进近灯光', 'edge': '跑道边灯', 'threshold': '跑道入口灯',
    'runway_guard': '跑道警戒灯',
    'runway_hold': '跑道停止排灯', 'intermediate_hold': '中间等待位置灯',
    'deice_hold': '除冰坪出口灯',
    'retil': '快速出口滑行道指示灯', 'stand_center': '机位引入线中线灯',
    'flash': '进近顺序闪光灯', 'apron_flood': '机坪泛光灯',
    'end': '跑道末端灯', 'center': '跑道中线灯', 'touchdown': '接地带灯',
}
TAXIS = ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')
FLASHING = {'flash','guard','runway_hold','runway_guard'}
CONFIGURATIONS = {
    'runway_guard': {'GUARD_A':'构型 A · 滑行道两侧','GUARD_B':'构型 B · 横贯滑行道'},
    'runway_hold': {'STOP':'红色停止排灯', 'STOP_UPRIGHT':'停止排灯＋立式补充灯',
                    'GUARD_A':'A 型跑道警戒灯', 'GUARD_B':'B 型跑道警戒灯',
                    'STOP_GUARD_A':'停止排灯＋A 型警戒灯'},
    'intermediate_hold': {'AMBER':'黄色中间等待位置灯','STOP':'红色停止排灯'},
    'deice_hold': {'AMBER':'黄色出口灯','STOP':'红色停止排灯'},
    'threshold': {'FULL':'整排入口灯','SPLIT':'分为两组','WING':'仅翼排灯','FULL_WING':'整排＋翼排灯'},
}
CUSTOM = {
    'taxi_center': ('滑行道中线灯', GREEN, 15),
    'taxi_edge': ('滑行道边灯', BLUE, 30),
    'stop_bar': ('停止排灯', RED, 3),
    'guard': ('跑道警戒灯', YELLOW, 3),
    'point': ('单个灯具', WHITE, 1),
}


def evenly(first, last, maximum):
    if last <= first:
        return [first]
    count = max(1, math.ceil((last-first)/maximum))
    return [first+(last-first)*i/count for i in range(count+1)]


def stations(length, interval):
    return (interval*i for i in range(1, int(length/interval)+1))


def runway_presets(runway):
    props = runway['props']
    levels = {end: props.get('level_'+end, 'v') for end in 'ab'}
    instrument = any(level != 'v' for level in levels.values())
    yield 'edge', '', True, {'spacing': 60 if instrument else 100}
    yield 'center', '', any(level in ('2','3') for level in levels.values()), {'spacing': 15}
    for end, level in levels.items():
        precise = level in ('1','2','3')
        cat23 = level in ('2','3')
        system = 'CAT23' if cat23 else 'CAT1_B' if precise else 'SIMPLE_B' if instrument and level == '0' else 'SIMPLE_A'
        yield 'approach', end, level != 'v' or props.get('code_number') in (3,4), {
            'system': system, 'length': 900 if precise else 420,
        }
        displaced = props.get('displaced_'+end,0) > 0
        yield 'threshold', end, True, {
            'spacing':3,'count':6 if not precise else 0,
            'configuration':'FULL_WING' if displaced else 'FULL',
            'configuration_choices': ('FULL','FULL_WING') if cat23 else
                ('FULL','SPLIT','FULL_WING','WING') if displaced and not precise else ('FULL','SPLIT','FULL_WING'),
        }
        yield 'end', end, True, {'spacing': 3, 'count': 6}
        yield 'touchdown', end, cat23, {'spacing': 30, 'length': 900}


def rapid_lighting(scene):
    from model20 import axes
    from rules13 import asset_guide, runway_extension

    runways = {asset['id']:asset for asset in scene.assets.values() if asset['kind']=='RUNWAY'}
    attachments = {}
    for mid,movement in scene.movements.items():
        for port,index in (('from',0),('to',-1)):
            runway_port = movement[port]
            if runway_port['asset'] not in runways:
                continue
            other = movement['to' if port=='from' else 'from']
            if movement.get('legacy_attachment'):
                taxi = scene.assets[other['asset']]
                index = 0 if other['station'] <= geometry.length(taxi['points'])/2 else -1
                attachments.setdefault(other['asset'],set()).add((runway_port['asset'],index))
            else:
                attachments.setdefault(mid,set()).add((runway_port['asset'],index))
    for asset in axes(scene).values():
        p = asset['props']
        if not (p.get('rapid_exit') or p.get('rapid_drawn_axis56')
                or p.get('geometry') == 'RAPID' or p.get('role') == 'RAPID_EXIT'):
            continue
        if scene.is_closed(asset['id']):
            continue
        path = asset['points']
        connected = attachments.get(asset['id'])
        if not connected:
            # Unbound older projects can still contain a drawn exit. Choose only
            # its closest actual runway endpoint, never both ends by proximity.
            matches = []
            for rid,runway in runways.items():
                axis = geometry.unit(*runway['points'])
                for index in (0,-1):
                    distance,_,origin = geometry.project(runway['points'],path[index])
                    beyond = sum((path[index][i]-origin[i])*axis[i] for i in (0,1))
                    if distance <= runway['props']['width']/2+.1 and abs(beyond) <= .1:
                        matches.append((distance,rid,index))
            if not matches:
                continue
            _,rid,index = min(matches)
            connected = {(rid,index)}
        for rid,index in sorted(connected):
            runway = runways[rid]
            u = geometry.unit(*runway['points'])
            normal = (-u[1],u[0])
            distance,station,_ = geometry.project(runway['points'],path[index])
            if distance > runway['props']['width']/2+.1:
                continue
            inward = path if index == 0 else path[::-1]
            probe,_ = geometry.at(inward,min(50,geometry.length(inward)))
            dx,dy = [probe[k]-path[index][k] for k in (0,1)]
            cross = dx*normal[0]+dy*normal[1]
            if abs(cross)<1e-5:
                continue
            sign = 1 if dx*u[0]+dy*u[1]>=0 else -1
            if asset['id'] in scene.assets:
                guide = asset_guide(scene,asset)
                if guide == path:
                    guide = runway_extension(scene,path,runway,index,preserve_exterior=True,rapid=True)
            else:
                guide = runway_extension(scene,path,runway,index,direction_hint=sign,rapid=True)
            nearest = guide[index]
            actual_station = geometry.project(runway['points'],nearest)[1]
            if abs(actual_station-station) > 1:
                sign = 1 if actual_station < station else -1
            yield asset,runway,index,station,sign,(1 if cross>0 else -1),guide


def distance_code(runway,station,travel,side):
    points = runway['points']
    length = geometry.length(points)
    axis = geometry.unit(*points)
    normal = (-axis[1],axis[0])
    sites = [(station-travel*distance,count) for distance,count in ((300,3),(200,2),(100,1))]
    if any(not 0<=s<=length for s,_ in sites):
        return
    for s,count in sites:
        origin,_ = geometry.at(points,s)
        for index in range(1,count+1):
            yield ([origin[k]+side*2*index*normal[k] for k in (0,1)],
                   YELLOW, tuple(-travel*v for v in axis), None)


def adapted_stations(trace, straight, curve, all_curved=False):
    if all_curved:
        yield from evenly(0,trace.length,curve)
        return
    points = list(trace.coords)
    corners = []
    position = 0.
    for a,b,c in zip(points,points[1:],points[2:]):
        position += geometry.distance(a,b)
        u,v = geometry.unit(a,b),geometry.unit(b,c)
        if abs(u[0]*v[1]-u[1]*v[0]) > .0087:
            start,end = max(0,position-15),min(trace.length,position+15)
            if corners and start <= corners[-1][1]:
                corners[-1][1] = end
            else:
                corners.append([start,end])
    start = 0.
    yield start
    for lo,hi in corners:
        yield from evenly(start,lo,straight)[1:]
        yield from evenly(lo,hi,curve)[1:]
        start = hi
    yield from evenly(start,trace.length,straight)[1:]


def holding_frame(mark, scene):
    typ = mark['props']['mark_type']
    a,b = mark['points'][0],mark['points'][-1]
    tangent = geometry.unit(a,b)
    width = mark['props'].get('width',23)
    if typ in ('HOLD_A','HOLD_B','INTERMEDIATE_POINT'):
        return a,(-tangent[1],tangent[0]),tuple(-v for v in tangent),width
    q,tangent = geometry.at(mark['points'],geometry.length(mark['points'])/2)
    facing = (-tangent[1],tangent[0])
    owner = scene.assets.get(mark.get('owner'))
    if owner and owner['props'].get('role')=='DEICING':
        from geometry11 import Point,polygon
        coordinates = [q[k]+.3*facing[k] for k in (0,1)]
        if not polygon(owner['points']).covers(Point(*coordinates)):
            facing = tuple(-v for v in facing)
    return q,tangent,facing,geometry.length(mark['points'])


def rows(scene,generated=None,closures=None):
    if closures is None:
        from lighting_closures import lighting_closures
        closures = lighting_closures(scene)
    closed,_,inactive = closures
    for row in plan_rows(scene,generated):
        _,_,asset,_,_,options = row
        affected = False
        if asset:
            owners = (asset['id'],asset.get('owner'),asset['props'].get('label_asset'),
                      asset['props'].get('parent_id'), *asset['props'].get('guidance_parents',()))
            if asset['id'].startswith('AUTO:'):
                owners += tuple(asset['id'].split(':')[1:])
            affected = any(owner in closed for owner in owners)
        elif not inactive and closed:
            paths = options.get('points',())
            # Manual rows have no owner, so resolve closure at their endpoints.
            affected = bool(paths) and any(
                candidate and candidate['kind'] in (*TAXIS,'RUNWAY')
                and any(geometry.project(candidate['points'],point)[0] <= candidate['props']['width']/2
                        for point in (paths[0],paths[-1]))
                for oid in closed for candidate in (scene.assets.get(oid),))
        if affected or inactive:
            options = dict(options,enabled=False,closed=True)
            row = (*row[:-1],options)
        yield row


def plan_rows(scene,generated=None):
    config = scene.data['meta'].get('lighting_f7', {})
    def configured(asset, kind, end, enabled, defaults):
        key = f"{asset['id']}:{kind}:{end}"
        override = config.get('runways', {}).get(key, {})
        number = asset['props'].get('label_'+end, end.upper()) if end else ''
        title = NAMES[kind] if kind in NAMES else CUSTOM[kind][0]
        name = ' '.join(filter(None, (asset['name'],number,title)))
        options = {**defaults, **override, 'enabled': override.get('enabled', enabled),
                   'enabled_override': override.get('enabled')}
        return key, name, asset, kind, end, options

    for asset in scene.assets.values():
        if asset['kind'] == 'RUNWAY':
            for kind, end, enabled, defaults in runway_presets(asset):
                approach = configured(asset,kind,end,enabled,defaults)
                yield approach
                if kind == 'approach':
                    options = approach[-1]
                    yield configured(asset,'flash',end,options['enabled'] and options['system'] in ('CAT1_B','CAT23'),
                                     {'length':options['length'],'spacing':30})
        elif asset['kind']=='APRON':
            yield configured(asset,'apron_flood','',False,{'spacing':60})
    from papi21 import rows as papi_rows
    papi={}
    for asset,end,lamps,direction in papi_rows(scene):
        papi.setdefault((asset['id'],end),[]).extend(
            (q,RED if i<2 else WHITE,direction,None) for i,q in enumerate(lamps))
    for (aid,end),lamps in papi.items():
        yield configured(scene.assets[aid],'papi',end,True,{'fixtures':lamps})
    if generated is None:
        from automatic_markings import generated_markings
        generated = generated_markings(scene)
    rvr = scene.scenario.get('rvr',1000)
    night = scene.scenario.get('night',False)
    dense = config.get('high_traffic',False)
    stop_default = rvr < 550 or (night and rvr > 550)
    for mark in (*scene.assets.values(),*generated.values()):
        typ = mark['props'].get('mark_type')
        if typ in ('HOLD_A','HOLD_B'):
            frame = holding_frame(mark,scene)
            hold = configured(mark,'runway_hold','',stop_default,{'configuration':'STOP','facing':'AUTO','frame':frame})
            state = hold[-1]
            movement = scene.movements.get(mark.get('owner'),{})
            taxi = scene.assets.get(mark.get('owner'),{})
            if movement:
                taxi = next((scene.assets[movement[port]['asset']] for port in ('from','to')
                             if scene.assets[movement[port]['asset']]['kind'] in TAXIS),{})
            props = taxi.get('props',{})
            exit_only = (movement.get('role') in ('RAPID_EXIT','EXIT_ONLY')
                         or props.get('rapid_exit') and props.get('flow','BOTH')!='BOTH')
            legacy_guard = state['enabled'] and 'GUARD' in state['configuration']
            real_stop = state['enabled'] and state['configuration'].startswith('STOP')
            require_a = (rvr < 550 and not real_stop) or (550 <= rvr <= 1200 and dense)
            guard = configured(mark,'runway_guard','',typ=='HOLD_A' and not exit_only and not legacy_guard,
                               {'configuration':'GUARD_A','facing':'AUTO','frame':frame,
                                'taxi_width':props.get('width',movement.get('width',frame[-1])),
                                'upright_stop':state['enabled'] and state['configuration']=='STOP_UPRIGHT'})
            guard_state = guard[-1]
            if rvr<550 or require_a or (real_stop and state['enabled_override'] is True):
                guard_state['configuration_choices'] = ('GUARD_A',)
                guard_state['configuration'] = 'GUARD_A'
            if guard_state['enabled']:
                if guard_state['configuration']=='GUARD_B':
                    state['enabled'] = False
                elif state['enabled_override'] is None and not legacy_guard:
                    state['enabled'] = True
            real_stop = state['enabled'] and state['configuration'].startswith('STOP')
            guard_state.update(stopbar_id=hold[0],stopbar_enabled=real_stop,
                               upright_stop=real_stop and state['configuration']=='STOP_UPRIGHT',
                               stopbar_span=frame[-1] if real_stop else 0)
            if guard_state['enabled'] and legacy_guard:
                if real_stop:
                    state['configuration'] = 'STOP'
                else:
                    state['enabled'] = False
            if real_stop and state['configuration']=='STOP_UPRIGHT':
                state['taxi_width'] = guard_state['taxi_width']
            yield hold
            yield guard
        elif typ in ('INTERMEDIATE','INTERMEDIATE_POINT'):
            kind = 'deice_hold' if 'DEICE' in mark['id'] else 'intermediate_hold'
            yield configured(mark,kind,'',True,{'configuration':'AMBER','facing':'AUTO','frame':holding_frame(mark,scene)})
    rapid_guides = {}
    for asset,runway,index,station,sign,side,guide in rapid_lighting(scene):
        rapid_guides[asset['id']] = guide
        lamps = list(distance_code(runway,station,sign,side))
        if lamps:
            end = 'a' if index == 0 else 'b'
            yield configured(asset,'retil',end,True,{'fixtures':lamps})
    from stand_profiles import lead_design
    for asset in scene.assets.values():
        if asset['kind'] != 'STAND' or scene.is_closed(asset['id']):
            continue
        design = lead_design(asset,scene)
        paths = [part['points'] for part in design.get('full_paths15',design['paths'])]
        from stand15 import remote_exit_lines
        if asset['props'].get('remote_stand') or asset['props'].get('exit_asset') or asset['props'].get('exit_vertices69'):
            paths.extend(remote_exit_lines(asset,scene))
        paths=[path for path in paths if len(path)>1 and geometry.length(path)>.01]
        if paths:
            yield configured(asset,'stand_center','',True,{'spacing':15,'curve_spacing':7.5,'paths':paths})
    from guidance20 import routes
    from geometry11 import taxi_edges
    from scene_render import surface_geometry
    edges={}
    for edge in taxi_edges(scene,surface_geometry(scene),{},lighting=True):
        edges.setdefault(edge['oid'],[]).append(edge['points'])
    for asset in routes(scene).values():
        if asset['kind'] not in TAXIS:
            continue
        guide = rapid_guides.get(asset['id'])
        lighting_axis = dict(asset,points=guide) if guide else asset
        yield configured(lighting_axis,'taxi_center','',True,{'spacing':15,'curve_spacing':7.5})
        if not asset['props'].get('guidance_parents'):
            yield configured(asset,'taxi_edge','',True,{'spacing':30,'curve_spacing':15,'edge_paths':edges.get(asset['id'],())})
    for key, record in config.get('custom', {}).items():
        yield key, record.get('name') or CUSTOM[record['kind']][0], None, record['kind'], '', record


def fixtures(row):
    _, _, runway, kind, end, options = row
    if runway is None:
        pts = options['points']
        if len(pts) == 1:
            yield pts[0], options['color'], None, None
            return
        length = geometry.length(pts)
        for index,station in enumerate(evenly(0, length, options['spacing'])):
            q, tangent = geometry.at(pts, station)
            direction = (-tangent[1], tangent[0]) if kind in ('guard','stop_bar') else None
            yield q, options['color'], direction, index % 2 if kind == 'guard' else None
        return
    if kind in ('runway_hold','runway_guard','intermediate_hold','deice_hold'):
        q, across, facing, span = options['frame']
        configuration = options['configuration']
        if options.get('facing') == 'REVERSE':
            facing = tuple(-v for v in facing)

        def hold_lamp(cross,color,phase=None,offset=0):
            return ([q[k]+cross*across[k]+offset*facing[k] for k in (0,1)],color,facing,phase)

        if configuration.startswith('STOP'):
            for cross in evenly(-span/2,span/2,3):
                yield hold_lamp(cross,RED)
            if configuration == 'STOP_UPRIGHT':
                for sign in (-1,1):
                    for offset in (3,4):
                        yield hold_lamp(sign*(options.get('taxi_width',span)/2+offset),RED)
        if configuration in ('GUARD_A','STOP_GUARD_A'):
            for sign in (-1,1):
                for phase in (0,1):
                    taxi_half = options.get('taxi_width',span)/2
                    outer = taxi_half+5 if options.get('upright_stop') else taxi_half+3
                    outer = max(outer,options.get('stopbar_span',0)/2+.75)
                    yield hold_lamp(sign*(outer+phase),YELLOW,phase)
        elif configuration == 'GUARD_B':
            count = math.floor(options.get('taxi_width',span)/3)+1
            for index in range(count):
                yield hold_lamp((index-(count-1)/2)*3,YELLOW,index%2)
        elif configuration == 'AMBER':
            intervals = math.floor(span/6)
            crosses = (-1.5,0,1.5) if kind == 'intermediate_hold' else [
                (i-intervals/2)*6 for i in range(intervals+1)]
            for cross in crosses:
                yield hold_lamp(cross,YELLOW,offset=.3)
        return
    if kind in ('retil','papi'):
        yield from options['fixtures']
        return
    if kind == 'stand_center':
        emitted = set()
        for path in options['paths']:
            from geometry11 import LineString
            trace = LineString(path)
            for station in adapted_stations(trace,options['spacing'],min(options['spacing'],options['curve_spacing'])):
                q,_ = geometry.at(path,station)
                key = tuple(round(v,5) for v in q)
                if key not in emitted:
                    emitted.add(key)
                    yield q,GREEN,None,None
        return
    if kind in ('taxi_center','taxi_edge','apron_flood'):
        from geometry11 import LineString, polygon
        path = runway['points']
        if kind == 'apron_flood':
            area = polygon(path)
            if area.is_empty:
                return
            target = area.representative_point()
            a,b = max(zip(path, path[1:]+path[:1]), key=lambda pair:geometry.distance(*pair))
            length = geometry.distance(a,b)
            if length > 0:
                for station in evenly(0,length,options['spacing']):
                    q,_ = geometry.at([a,b],station)
                    inward = (target.x,target.y)
                    if geometry.distance(q,inward) > 1e-6:
                        yield q, WHITE, geometry.unit(q,inward), None
            return
        if len(path)<2:
            return
        axis = LineString(path)
        paths = [axis]
        if kind == 'taxi_edge':
            paths = [LineString(points) for points in options.get('edge_paths',())]
        for trace in paths:
            if trace.is_empty or trace.length < .01:
                continue
            for station in adapted_stations(trace,options['spacing'],min(options['spacing'],options['curve_spacing']),
                                            bool(runway['props'].get('guidance_parents'))):
                point = trace.interpolate(station)
                q = (point.x,point.y)
                yield q, GREEN if kind == 'taxi_center' else BLUE, None, None
        return
    points = runway['points']
    p = runway['props']
    length = geometry.length(points)
    u = geometry.unit(*points)
    v = (-u[1], u[0])
    width = p['width']
    displacements = [p.get('displaced_'+side, 0) for side in 'ab']
    lo, hi = displacements[0], length-displacements[1]

    def lamp(station, cross, color, direction=None, phase=None):
        return ([points[0][i]+station*u[i]+cross*v[i] for i in (0,1)],color,direction,phase)

    if kind == 'edge':
        for station in evenly(0, length, options['spacing']):
            for side in (-1,1):
                caution = min(600,length/3)
                if station < lo or station > hi:
                    facing = tuple(-v for v in u) if station < lo else u
                    yield lamp(station,side*width/2,RED,facing)
                    yield lamp(station,side*width/2,YELLOW if min(station,length-station)<=caution else WHITE,
                               tuple(-v for v in facing))
                else:
                    color = YELLOW if min(station,length-station)<=caution else WHITE
                    yield lamp(station,side*width/2,color)
        return
    if kind == 'center':
        if hi <= lo:
            return
        for index, station in enumerate(evenly(lo, hi, options['spacing'])):
            distance = min(station, length-station)
            color = RED if distance <= 300 or distance <= 900 and index % 2 == 0 else WHITE
            yield lamp(station, 0, color)
        return

    threshold = lo if end == 'a' else hi
    inward = 1 if end == 'a' else -1
    outward = tuple(-inward*value for value in u)
    if kind == 'flash':
        pitch = options['spacing']
        for index,distance in enumerate(reversed(list(stations(options['length'],pitch)))):
            yield lamp(threshold-inward*distance,0,WHITE,outward,index)
        return
    if kind in ('threshold','end'):
        station = threshold if kind == 'threshold' else (0 if end == 'a' else length)
        color = GREEN if kind == 'threshold' else RED
        count = options['count']
        offsets = [-width/2+width*i/(count-1) for i in range(count)] if count >= 2 else evenly(-width/2,width/2,options['spacing'])
        direction = outward if kind == 'threshold' else tuple(-v for v in outward)
        configuration = options.get('configuration','FULL')
        if configuration == 'SPLIT':
            gap = min(width/4,7.5)
            per_side = max(3,math.ceil(len(offsets)/2))
            offsets = [sign*(gap+(width/2-gap)*i/(per_side-1))
                       for sign in (-1,1) for i in range(per_side)]
        if configuration != 'WING':
            for cross in offsets:
                yield lamp(station,cross,color,direction)
        if configuration in ('WING','FULL_WING'):
            for sign in (-1,1):
                for offset in (0,2.5,5,7.5,10):
                    if offset or configuration == 'WING':
                        yield lamp(station,sign*(width/2+offset),GREEN,outward)
        return
    if kind == 'touchdown':
        from runway import aim_dimensions
        suffix = '_'+end
        lda = p.get('lda'+suffix) or (length-displacements['ab'.index(end)])
        _, _, _, separation = aim_dimensions(lda, p.get('aim_width'+suffix),
                                             p.get('aim_gap'+suffix),p.get('aim_length'+suffix))
        lateral = separation/2+1.5
        for distance in stations(min(options['length'], max(0, hi-lo)), options['spacing']):
            for side in (-1,1):
                for cross in evenly(lateral-1.5,lateral+1.5,1.5):
                    yield lamp(threshold+inward*distance,side*cross,WHITE,outward)
        return

    system = options['system']
    simple = system.startswith('SIMPLE')
    cat23 = system == 'CAT23'
    color = RED if system == 'SIMPLE_A' else WHITE
    interval = options.get('spacing', 60 if simple else 30)
    bar_length = 3 if simple else 4
    for distance in stations(options['length'], interval):
        station = threshold-inward*distance
        if system == 'SIMPLE_A':
            offsets = [0]
        elif system == 'CAT1_A':
            offsets = [0] if distance <= 300 else [-.75,.75] if distance <= 600 else [-1.5,0,1.5]
        else:
            offsets = evenly(-bar_length/2,bar_length/2,1.5)
        for cross in offsets:
            yield lamp(station,cross,color,None if system == 'SIMPLE_A' else outward)
        if cat23 and distance <= 270:
            for side in (-1,1):
                for cross in evenly(9,12,1.5):
                    yield lamp(station,side*cross,RED,outward)
    bars = {300:30}
    if cat23:
        bars.update({150:18})
    elif system == 'CAT1_A':
        bars.update({150:22.5,450:37.5,600:45,750:52.5})
    for distance, span in bars.items():
        if distance > options['length']:
            continue
        for cross in evenly(-span/2,span/2,3):
            if abs(cross)>bar_length/2:
                yield lamp(threshold-inward*distance,cross,color,None if system == 'SIMPLE_A' else outward)
