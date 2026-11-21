"""Runway-end shoulder cuts use terminal planes, like runway turn-pad cuts."""
import scene_geometry as g
from pavement_geometry import halfplane

def runway_terminal(runway,station):
    length=g.length(runway['points'])
    tolerance=min(length/2,max(60.,runway['props']['width']))
    if min(station,length-station)>tolerance:return None
    inward=1 if station<=length/2 else -1
    end='a' if inward==1 else 'b'
    axis=g.unit(*runway['points'])
    origin=runway['points'][0 if inward==1 else -1]
    stopway=runway['props'].get('stopway_'+end,0.)
    q=[origin[k]-inward*axis[k]*stopway for k in (0,1)]
    return q,[q[0]+axis[1]*inward,q[1]-axis[0]*inward],inward


def runway_cap_planes(scene):
    from collections import defaultdict
    from pavement_geometry import crossings
    caps=defaultdict(list)
    for junction in crossings(scene):
        for aid,station,other in zip(junction['assets'],junction['stations'],reversed(junction['assets'])):
            runway=scene.assets.get(aid,{})
            if runway.get('kind')!='RUNWAY':continue
            end=runway_terminal(runway,station)
            if end:caps[other].append(end[:2])
    for mid,movement in scene.movements.items():
        for name,other in (('from','to'),('to','from')):
            port=movement[name]
            runway=scene.assets[port['asset']]
            if runway['kind']!='RUNWAY':continue
            end=runway_terminal(runway,port['station'])
            if end:
                caps[mid].append(end[:2])
                other_id=movement[other]['asset']
                if scene.assets[other_id]['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                    caps[other_id].append(end[:2])
    return caps


def preview_runway_ends(editor,roots):
    from pavement_geometry import crossings
    scene=editor.scene
    candidates=set()
    for j in crossings(scene):
        for runway,other in zip(j['assets'],reversed(j['assets'])):
            if other in roots and scene.assets.get(runway,{}).get('kind')=='RUNWAY':candidates.add(runway)
    for movement in scene.movements.values():
        for end,other in (('from','to'),('to','from')):
            aid=movement[end]['asset']
            if scene.assets[aid]['kind']=='RUNWAY' and (movement[other]['asset'] in roots or movement['id'] in roots):
                candidates.add(aid)
    canvas=editor.canvas
    for aid in candidates:
        runway=scene.assets[aid]
        length=g.length(runway['points'])
        tolerance=min(length/2,max(60.,runway['props']['width']))
        u=g.unit(*runway['points'])
        v=[-u[1],u[0]]
        half=runway['props']['width']/2
        for station,sign in ((0,1),(length,-1)):
            q,_=g.at(runway['points'],station)
            end,_=g.at(runway['points'],station+tolerance*sign)
            pixels=[x for p,side in ((q,-1),(end,-1),(end,1),(q,1))
                    for x in editor.screen([p[k]+v[k]*side*half for k in (0,1)])]
            canvas.create_polygon(*pixels,outline='#35bbd3',fill='',width=2,dash=(6,4),
                                  tags='runway_end_preview32')
            cap,_,_=runway_terminal(runway,station)
            if g.distance(cap,q)>.01:
                line=[x for side in (-1,1) for x in editor.screen([cap[k]+v[k]*side*half for k in (0,1)])]
                canvas.create_line(*line,fill='#f4b95e',width=2,dash=(6,4),tags='runway_end_preview32')
            x,y=editor.screen(end)
            canvas.create_text(x,y-14,text=f'跑道末端范围 {tolerance:g} m',fill='#35bbd3',
                               font=('Segoe UI',9,'bold'),tags='runway_end_preview32')

def corridor_caps(points,planes):
    return [plane for plane in planes if all(
        (plane[1][0]-plane[0][0])*(y-plane[0][1])-(plane[1][1]-plane[0][1])*(x-plane[0][0])>=-.1
        for x,y in points)]


def clip_caps(polygon,planes):
    for start,end in planes:polygon=halfplane(polygon,start,end)
    return polygon


def clip_end_shoulder(scene,aid,polygon):
    return clip_caps(polygon,runway_cap_planes(scene).get(aid,()))



def snap_stopway(scene,point,zoom):
    hits=[]
    for runway in scene.assets.values():
        if runway['kind']!='RUNWAY':continue
        width=runway['props']['width']
        limit=max(width*.7,min(30,16/max(.01,zoom)))
        for end,q in (('a',runway['points'][0]),('b',runway['points'][-1])):
            distance=g.distance(q,point)
            if distance<=limit:hits.append((distance,runway['id'],end,q))
    return min(hits,key=lambda hit:hit[0],default=None)
