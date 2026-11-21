"""Road waiting approaches for every aircraft taxiway subtype."""
import math
import scene_geometry as g
TAXI_DISTANCE=dict(A=15.5,B=20.,C=26.,D=37.,E=43.5,F=51.)
STAND_DISTANCE=dict(A=12.,B=16.5,C=22.5,D=33.5,E=40.,F=47.5)
def generated(scene):
    from roads10 import roads,lane_pose
    from roads11 import intersections,occupied
    from automatic_markings import synthetic
    out={}
    for road in roads(scene):
        if road['props'].get('closed') or not road['props'].get('auto_road_hold17',True):continue
        total=g.length(road['points'])
        for lane in ('A','B'):
            placed=[];taken=occupied(scene,road['id'],lane)
            taken += [(a['props']['crossing_station13'],'PEDESTRIAN') for a in scene.assets.values() if a['props'].get('crossing_asset13')==road['id']]
            taken += [(a['props']['road_station'],'JET_BLAST') for a in __import__('roads11').generated(scene).values() if a['props'].get('road_id')==road['id'] and a['props'].get('lane_side')==lane]
            for j in intersections(scene,road):
                other=j['other']
                if other['kind'] not in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):continue
                code=other['props'].get('code_letter')
                if code not in TAXI_DISTANCE:
                    span=scene.scenario['aircraft_wingspan'];code=next((c for bound,c in [(15,'A'),(24,'B'),(36,'C'),(52,'D'),(65,'E'),(80,'F')] if span<bound),'F')
                distance=(STAND_DISTANCE if other['kind']=='STAND_TAXILANE' else TAXI_DISTANCE)[code]
                distance=max(distance,road['props'].get('road_hold_distance17',0))
                _,u=lane_pose(scene,road,j['station'],lane);_,axis=g.at(road['points'],j['station']);sign=1 if sum(u[k]*axis[k] for k in (0,1))>0 else -1
                _,other_u=g.at(other['points'],g.project(other['points'],j['point'])[1]);sine=max(.05,abs(other_u[1]*u[0]-other_u[0]*u[1]))
                station=j['station']-sign*distance/sine
                for step in range(81):
                    s=station-sign*step
                    if not 3<s<total-3:break
                    q,u=lane_pose(scene,road,s,lane)
                    if g.project(other['points'],q)[0]<distance+.16:continue
                    if any(abs(s-old)<6 for old in placed):break
                    if any(abs(s-old)<6 for old,_ in taken):continue
                    mark=synthetic(road['id'],'ROAD_STOP',[q,[q[k]+u[k]*10 for k in (0,1)]],f'ROAD_HOLD17:{lane}:{other["id"]}',width=road['props']['width']/2*.9,line_width=.3,road_id=road['id'],road_station=s,lane_side=lane,road_hold17=True,aircraft_asset17=other['id'],minimum_distance17=distance,code_letter=code,placement_review17=True)
                    out[mark['id']]=mark;placed.append(s);break
    return out
