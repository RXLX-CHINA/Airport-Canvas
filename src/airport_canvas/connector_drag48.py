"""Application preferences and bound-connector drag support."""
import copy
import scene_geometry as g

def connector_ports(scene,oid,pointer,start,ports):
    first,second=(scene.assets[ports[k]['asset']]['points'] for k in ('from','to'))
    start_station=ports['from']['station']
    q,_=g.at(first,start_station)
    wanted=[q[i]+pointer[i]-start[i] for i in (0,1)]
    _,station,target=g.project(first,wanted)
    delta=[target[i]-q[i] for i in (0,1)]
    old_end,_=g.at(second,ports['to']['station'])
    moved_end=[old_end[i]+delta[i] for i in (0,1)]
    _,finish,new_end=g.project(second,moved_end)
    return dict(ports['from'],station=station),dict(ports['to'],station=finish),delta,new_end

def slide_connector(scene,oid,ports,delta):
    with scene.transaction('沿起点中线滑动连接道'):
        moved=scene.movements[oid]
        moved.update(zip(('from','to'),ports))
        if moved.get('bezier_controls'):
            moved['bezier_controls']=[[p[i]+delta[i] for i in (0,1)] for p in moved['bezier_controls']]
        scene.movement_path(oid)
