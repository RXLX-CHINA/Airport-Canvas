"""Export geometry for the editing display modes."""
import math
import scene_geometry as g

MODES = {'MAP':'普通机场图','F5':'标记牌-F5','F6':'彩色分段-F6','F7':'助航灯光-F7','F8':'航图-F8'}


def stopway_contours(runway):
    from project10 import stopway_axes
    for _,outside,origin,_ in stopway_axes(runway):
        ring=g.rectangle([outside,origin],runway['props']['width'])
        yield '#8295a5',[*ring,ring[0]]


def contours(scene):
    from scene_render import surface_geometry
    from geometry11 import polygon,unary_union,lines
    s=surface_geometry(scene);out=[]
    for kind,color in [('shoulders','#a4abb2'),('pavement','#445461')]:
        shape=unary_union([polygon(p['points']) for p in s[kind]])
        for line in lines(shape.boundary):out.append((color,[list(q) for q in line.coords]))
    hidden=scene.data['meta'].get('object_display',{})
    for aid,asset in scene.assets.items():
        if asset['kind']=='RUNWAY' and not hidden.get(aid,{}).get('hidden'):
            out.extend(stopway_contours(asset))
    return out

def lighting_wireframe(scene,lighting_rows,closed):
    from geometry11 import LineString
    from guidance20 import routes
    paths,labels = [],[]

    def line(points,color):
        if len(points)>1:
            paths.append((tuple(points),color))
    from rules13 import asset_guide
    from airport_scene import AREA_KINDS
    from model20 import axes
    for aid, asset in {**scene.assets, **axes(scene)}.items():
        kind = asset['kind']
        props = asset['props']
        points = asset['points']
        if scene.data['meta'].get('object_display', {}).get(aid,{}).get('hidden') or len(points)<2:
            continue
        taxi = kind in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')
        if taxi or kind in ('RUNWAY','ROAD'):
            axis = LineString(points)
            edge = axis.buffer(props['width']/2,cap_style=2)
            for poly in getattr(edge,'geoms',(edge,)):
                line(poly.exterior.coords,'#536574')
            if kind=='RUNWAY':
                for color,ring in stopway_contours(asset):
                    line(ring,color)
            line(asset_guide(scene,asset) if taxi and aid in scene.assets else points,'#8b9aa8')
            label = props.get('designation') or (f"{props['label_a']}/{props['label_b']}" if kind == 'RUNWAY' and 'label_a' in props else asset['name'])
            labels.append((g.at(points,g.length(points)/2)[0],label))
        elif kind in AREA_KINDS:
            line([*points,points[0]],'#536574')
    for route in routes(scene).values():
        parents = route['props'].get('guidance_parents')
        if parents and not any(aid in closed for aid in parents):
            line(route['points'],'#8b9aa8')
    for row in lighting_rows:
        if row[3] == 'stand_center':
            for points in row[-1]['paths']:
                line(points,'#8b9aa8')
    return paths,labels

def mode_items(scene, mode, regular):
    if mode == 'MAP':
        return regular, []
    if mode == 'F8':
        from chart_f8 import chart_items
        return chart_items(scene,regular)[0], []
    from model20 import axes
    from segments18 import pieces
    from segments16 import color_name
    from guidance20 import routes
    from scene_render import rapid_f6_guides
    items = []
    animated = []

    def line(oid,points,color,width=.2):
        if len(points)>1:
            items.append(dict(oid=oid,type='line',points=points,stroke=color,width=width))

    def label(oid,point,name,color):
        items.append(dict(oid=oid,type='text',points=[point],text=name,fill=color,
                          size=7,rotation=0,world_text=True))

    if mode in ('F5','F6'):
        for color,points in contours(scene):
            items.append(dict(oid='EXPORT_WIREFRAME',type='line',points=points,stroke=color,width=.2,screen_line=True))
    if mode=='F7':
        from lighting_model import rows,fixtures
        from lighting_closures import lighting_closures
        closures = lighting_closures(scene)
        lighting_rows = list(rows(scene,closures=closures))
        paths,labels = lighting_wireframe(scene,lighting_rows,closures[0])
        for points,color in paths:
            items.append(dict(oid='EXPORT_WIREFRAME',type='line',points=points,stroke=color,width=.2,screen_line=True))
        for point,name in labels:
            label('EXPORT_WIREFRAME',point,name,'#becbd7')
    axis_map = axes(scene)
    rapid = rapid_f6_guides(regular)
    for aid,axis in (() if mode=='F7' else axis_map.items()):
        if scene.data['meta'].get('object_display',{}).get(aid,{}).get('hidden'):
            continue
        points = axis['points']
        length = g.length(points)
        if length<=0:
            continue
        if (mode=='F6' or aid in rapid) and axis['kind']!='RUNWAY':
            for part in pieces(axis):
                color = color_name(part['name'])
                if aid not in rapid:
                    line(aid,g.subpath(points,part['lo']*length,part['hi']*length),color,.7)
                midpoint,_ = g.at(points,(part['lo']+part['hi'])*length/2)
                label(aid,midpoint,part['name'],color)
            for path in rapid.get(aid,()):
                from segments18 import piece_at
                midpoint,_ = g.at(path,g.length(path)/2)
                station = g.project(points,midpoint)[1]
                line(aid,path,color_name(piece_at(axis,station)['name']),.7)
        else:
            color = '#91a5b5' if mode=='F7' else '#526c7c'
            line(aid,points,color,.35)
            for path in rapid.get(aid,()):
                line(aid,path,color,.35)
            if mode=='F7' or (mode=='F6' and axis['kind']=='RUNWAY'):
                name = axis['name']
                if axis['kind']=='RUNWAY':
                    name = '/'.join(axis['props'].get('label_'+side,'') for side in 'ab')
                label(aid,g.at(points,length/2)[0],name,color)
    for oid,route in (() if mode=='F7' else routes(scene).items()):
        if route['props'].get('guidance_parents'):
            owner = axis_map.get(route['props'].get('guidance_owner20'))
            color = color_name(owner['name']) if mode=='F6' and owner else '#778d9b'
            if mode=='F7':
                from lighting_closures import pavement_closures
                if any(aid in pavement_closures(scene) for aid in route['props']['guidance_parents']):
                    continue
            line(oid,route['points'],color,.45)
    if mode=='F5':
        from automatic_markings import generated_markings
        markings = {**scene.assets,**generated_markings(scene)}
        items.extend(item for item in regular if item.get('sign_board21_2') or
                     markings.get(item.get('oid'),{}).get('props',{}).get('information_profile20_18')=='PAVEMENT')
    elif mode=='F6':
        from stand_profiles import lead_design
        for aid,asset in scene.assets.items():
            if asset['kind']=='STAND':
                for lead in lead_design(asset,scene)['paths']:
                    line(aid,lead['points'],'#887544')
                label(aid,asset['points'][-1],asset['name'],'#887544')
    elif mode=='F7':
        animation = scene.data['meta'].get('lighting_f7',{}).get('animate',True)
        for key,_,asset,kind,end,options in lighting_rows:
            if not options.get('enabled',True):
                continue
            lights = list(fixtures((key,'',asset,kind,end,options)))
            for (x,y),color,direction,phase in lights:
                angle = math.atan2(direction[1],direction[0]) if direction else 0
                sweep = math.pi if direction else math.tau
                radius = 1.4 if kind=='flash' else 1
                points = [[x+radius*math.cos(angle+sweep*(i/16-.5)),
                           y+radius*math.sin(angle+sweep*(i/16-.5))] for i in range(17)]
                item = dict(oid=key,type='polygon',points=points,fill=color,lamp_center=(x,y),lamp_radius=radius)
                items.append(item)
                if phase is not None and animation and options.get('animate',True):
                    animated.append((item,kind,phase,len(lights),options.get('configuration')))
    return items,animated

