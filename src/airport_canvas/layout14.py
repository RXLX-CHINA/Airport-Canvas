"""Shared model fixes for crossings, paint connections, resize and surfaces."""
import copy,math
import scene_geometry as g

def sync(scene):
    from scene_render import COLORS
    from geometry11 import polygon,Point
    for a in scene.assets.values():
        p=a['props']
        if p.get('deice_layout12') and p.get('deice_inherit14',True):
            shape=polygon(a['points']);center=shape.representative_point();background=[]
            for b in scene.assets.values():
                if b['id']==a['id'] or b['kind']!='APRON' or b['props'].get('deice_layout12'):continue
                poly=polygon(b['points'])
                if poly.covers(center):background.append((poly.area,b))
            parent=min(background,key=lambda x:x[0])[1] if background else scene.assets.get(p.get('deice_parent'))
            if parent:p['pavement_color']=parent['props'].get('pavement_color',COLORS['apron'] if parent['kind']=='APRON' else COLORS['taxiway'])
        if a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):p.setdefault('hold_include_shoulders13',True)
    # Keep explicit attached waiting marks on the full pavement + shoulder span.
    for m in scene.assets.values():
        p=m['props'];parent=scene.assets.get(p.get('label_asset'))
        if p.get('mark_type') in ('HOLD_A','HOLD_B') and parent and not p.get('hold_width_manual'):
            p['width']=parent['props']['width']+2*parent['props'].get('shoulder',0)

def crossing(scene,p,tolerance):
    options=[]
    for aid,a in scene.assets.items():
        if a['kind'] not in ('ROAD','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):continue
        d,s,q=g.project(a['points'],p)
        if d<=max(tolerance,a['props']['width']/2):options.append((d,0 if a['kind']=='ROAD' else 1,aid,s,q))
    if not options:return None
    d,_,aid,s,q=min(options);a=scene.assets[aid];q,u=g.at(a['points'],s)
    return dict(hit=(d,aid,s,q),asset=a,point=q,direction=u,width=a['props']['width'])

def clip_apron_edges(scene,items,generated):
    from geometry11 import polygon,LineString,unary_union,lines,Point
    from marking_catalog import YELLOW
    aprons=[polygon(a['points']) for a in scene.assets.values() if a['kind']=='APRON' and not a['props'].get('turn_pad')]
    if not aprons:return items
    # Clear the painted stroke, not just its mathematical centre. Also remove
    # manual/generated TWY_EDGE variants, which bypassed the shared edge pass.
    mask=unary_union(aprons).buffer(.46,join_style=2);out=[]
    for item in items:
        mark=generated.get(item.get('oid')) or scene.assets.get(item.get('oid'));key=mark.get('props',{}).get('mark_type') if mark else None
        root=scene.assets.get(mark.get('owner')) if mark else None
        if root and root['kind']=='APRON':out.append(item);continue
        edge=item.get('taxi_edge11') or key=='TWY_EDGE'
        if not edge or item['type']!='line':out.append(item);continue
        line=LineString(item['points'])
        for segment in lines(line.difference(mask)):
            pts=[list(q) for q in segment.coords]
            if segment.length>.01:out.append(dict(item,points=pts,dash_offset=item.get('dash_offset',0)+line.project(Point(pts[0]))))
    return out

def solid_safety(items):
    # Geometry clipping can split a polyline at every corner. Joined round
    # buffers close raster/export seams without joining the deliberately open mouth.
    from geometry11 import LineString,polygons
    out=[]
    for item in items:
        if not item.get('continuous_safety14') or item.get('dash'):out.append(item);continue
        for poly in polygons(LineString(item['points']).buffer(item.get('width',.1)/2,cap_style=1,join_style=1)):
            out.append(dict(item,type='polygon',points=[list(q) for q in poly.exterior.coords][:-1],fill=item['stroke'],stroke=None))
    return out

def scale(scene,roots,box,target):
    from transform11 import members
    from automatic_markings import generated_markings,update_generated
    x0,y0,x1,y1=box;xx0,yy0,xx1,yy1=target;sx=(xx1-xx0)/max(.01,x1-x0);sy=(yy1-yy0)/max(.01,y1-y0)
    if min(sx,sy)<.02:raise ValueError('尺寸太小')
    ids=members(scene,roots);f=lambda q:[xx0+(q[0]-x0)*sx,yy0+(q[1]-y0)*sy]
    with scene.transaction('拖动外框调整尺寸'):
        auto=generated_markings(scene)
        for oid in ids:
            if oid in auto:
                m=auto[oid];update_generated(scene,oid,m['name'],[f(q) for q in m['points']],m['props']);continue
            a=scene.assets.get(oid)
            if not a:continue
            p=a['props'];old=copy.deepcopy(a['points']);u=g.unit(old[0],old[-1]);v=[-u[1],u[0]];long=math.hypot(u[0]*sx,u[1]*sy);wide=math.hypot(v[0]*sx,v[1]*sy)
            for key in ('points','design_vertices','pad_guide'):
                if a.get(key):a[key]=[f(q) for q in a[key]]
            for n in a.get('curve_nodes',[]):
                for key in ('p','incoming','outgoing'):n[key]=f(n[key])
            if a['kind']=='STAND':
                if p.get('entry_attached',True) and p.get('entry_asset') not in ids:
                    origin=old[0];delta=[origin[k]-a['points'][0][k] for k in (0,1)];a['points']=[[q[k]+delta[k] for k in (0,1)] for q in a['points']]
                p['aircraft_length']=p.get('aircraft_length',scene.scenario['aircraft_length'])*long;p['aircraft_span']=p.get('aircraft_span',scene.scenario['aircraft_wingspan'])*wide
                if 'wing_station' in p:p['wing_station']*=long
                for key,q in p.get('junction_edits14',{}).items():p['junction_edits14'][key]=[q[0]*long,q[1]*wide]
            elif a['kind'] in ('ROAD','RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):p['width']*=wide;p['shoulder']=p.get('shoulder',0)*wide
            if a['kind'] in ('ROAD','RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                ratio=g.length(a['points'])/max(.01,g.length(old))
                for m in scene.movements.values():
                    for side in ('from','to'):
                        if m[side]['asset']==oid:m[side]['station']*=ratio
                from stand10 import refresh_entries
                refresh_entries(scene,oid)
        __import__('deice12').refresh(scene)
    return ids

def nice_length(zoom,unit=1.):
    target=110/max(zoom,.000001)/unit;power=10**math.floor(math.log10(target));length=max((n*power for n in (1,2,5) if n*power<=target*(1+1e-12)),default=power/2)
    return length,length*unit*zoom
