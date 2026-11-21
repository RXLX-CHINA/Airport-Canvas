"""Preserve standard stop markings; optionally expand their safety envelope."""
def reserve_stops(a,scene,d):
    if not a['props'].get('safety_include_stops17',True):return d
    from editor6_geometry import stop_components,stop_rows
    manual=[m for m in scene.assets.values() if m['kind']=='MARKING' and m['props'].get('mark_type')=='UNGUIDED_STOP' and (m['props'].get('stand_id')==a['id'] or m['props'].get('stand_owner13')==a['id'])] if scene and hasattr(scene,'assets') else []
    if not manual and not any(r.get('shape')=='UNGUIDED' and r.get('visible',True) for r in stop_rows(a)):return d
    from marking_catalog import primitives
    from stand11 import frame
    q=a['points'][-1];_,u,v=frame(a);extent=[];forward=[]
    for m in list(stop_components(a).values())+manual:
        if m['props']['mark_type']!='UNGUIDED_STOP':continue
        for part in primitives(m):
            for p in part['points']:
                extent.append(abs(sum((p[k]-q[k])*v[k] for k in (0,1))))
                forward.append(sum((p[k]-q[k])*u[k] for k in (0,1)))
    if extent:
        d['narrow']=max(d['narrow'],max(extent)+.5);d['wide']=max(d['wide'],d['narrow']+1.);d['nose_end']=max(d['nose_end'],max(forward)+.5)
    return d
