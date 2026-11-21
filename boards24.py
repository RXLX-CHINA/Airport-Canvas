"""Sign safety placement and board-face tool definitions."""
import math
from geometry11 import polygon, unary_union

TEMPLATES = (
    ('RUNWAY_NUMBER','跑道号码／位置组合牌','07–25'),
    ('CAT_HOLD','跑道 CAT 等待位置牌','25 CAT II'),
    ('NO_ENTRY_BOARD','禁止进入标记牌',''),
    ('ROAD_STOP_BOARD','道路等待位置标记牌','停'),
    ('LOCATION_BOARD','位置标记牌','A'),
    ('VACATED','脱离跑道／位置组合牌','A'),
    ('RUNWAY_EXIT','跑道出口标记牌','G2'),
    ('POSITION_HP','滑行位置识别点标记牌','HP3'),
    ('DIRECTION_GROUP','组合方向／位置牌','←C | @B | B↗ | C→'),
    ('DESTINATION_GROUP','组合目的地牌','←04 | 22→'),
)
MANDATORY={'RUNWAY_NUMBER','CAT_HOLD','NO_ENTRY_BOARD','ROAD_STOP_BOARD','HOLD_BOARD','FREQUENCY'}
LOCATION={'LOCATION_BOARD','POSITION_HP'}


def pavement(scene,surfaces=None):
    key=(id(scene.data),scene.revision)
    cached=getattr(scene,'_board_pavement24',None)
    if not scene._transaction_depth and cached and cached[0]==key:return cached[1]
    if surfaces is None:
        from scene_render import surface_geometry
        surfaces=surface_geometry(scene)
    from geometry11 import road_union
    shapes=[polygon(e['points']) for e in surfaces['pavement']+surfaces['shoulders']]
    import scene_geometry as g
    for runway in surfaces['runways']:
        u=g.unit(*runway['points'])
        for end,index,sign in (('a',0,-1),('b',-1,1)):
            length=runway['props'].get('stopway_'+end,0)
            if length:
                start=runway['points'][index]
                finish=[start[k]+sign*u[k]*length for k in (0,1)]
                shapes.append(polygon(g.rectangle([start,finish],runway['props']['width'])))
    result=unary_union([*shapes,road_union(scene)],grid_size=.0001)
    if not scene._transaction_depth:scene._board_pavement24=(key,result)
    return result


def group_faces(items):
    groups={}
    for item in items:
        if item.get('sign_board21_2'):groups.setdefault(item['oid'],[]).append(item)
    return groups


def face_bounds(items,gap):
    xs,ys=zip(*(p for e in items for p in e['points']))
    stroke=max((e.get('width',0) for e in items if e.get('stroke')),default=0)/2+gap
    return min(xs)-stroke,min(ys)-stroke,max(xs)+stroke,max(ys)+stroke


def layout_faces(groups,mask,gap=.035,max_shift=None,local_auto=False):
    """Pack complete faces against the prepared pavement and preceding boards."""
    from shapely import box, intersects, prepare
    import numpy as np
    if mask is not None:prepare(mask)
    use_mask=mask is not None and not mask.is_empty
    occupied=[]
    offsets={}
    headings=[(math.cos(i*math.tau/16),math.sin(i*math.tau/16)) for i in range(16)]
    ordered = sorted(groups.items(),key=lambda row:not row[1][0].get('board_pose_locked'))
    for oid,items in ordered:
        if items[0].get('board_pose_locked'):
            occupied.append(face_bounds(items,gap))
            offsets[oid] = (0.,0.)
            continue
        local=local_auto and oid.startswith('AUTO:')
        local_limit=3. if ":NO_ENTRY_BOARD:" in oid else 12.
        shift_limit=min(local_limit,max_shift) if local and max_shift is not None else local_limit if local else max_shift
        bounds=face_bounds(items,gap)
        x0,y0,x1,y1=bounds
        step=max(gap,min(x1-x0,y1-y0)*.32)
        vx,vy=items[0].get('board_normal24') or (1.,0.)
        deltas=sorted(((u,v) for u,v in headings if u*vx+v*vy>=-.05),
                      key=lambda d:-(vx*d[0]+vy*d[1]))
        previous=np.asarray(occupied)

        def free(shifts):
            frame=np.asarray(shifts)
            limits=frame[:,[0,1,0,1]]+bounds
            if len(previous):
                hits=np.flatnonzero(~((limits[:,None,0]<=previous[None,:,2]) &
                                      (limits[:,None,2]>=previous[None,:,0]) &
                                      (limits[:,None,1]<=previous[None,:,3]) &
                                      (limits[:,None,3]>=previous[None,:,1])).any(axis=1))
            else:hits=np.arange(len(shifts))
            if len(hits) and use_mask:hits=hits[~intersects(mask,box(*limits[hits].T))]
            if not len(hits):return None
            index=hits[0]
            occupied.append(limits[index])
            return shifts[index]

        delta=free([(0.,0.)])
        if delta is None:
            for start in (0,4,8):
                rings=(1,2,3,4,6,9,14,22,35,56,92,150)[start:start+4]
                shifts=[(u*step*r,v*step*r) for r in rings for u,v in deltas
                        if shift_limit is None or step*r<=shift_limit]
                if shifts:delta=free(shifts)
                if delta is not None:break
        if delta is None:
            if local:continue
            if max_shift is not None:return None
            solids=([mask.bounds] if use_mask else [])+occupied
            cx,cy=(x0+x1)/2,(y0+y1)/2
            far=max(((x-cx)*vx+(y-cy)*vy for a,b,d,e in solids
                     for x in (a,d) for y in (b,e)),default=0)
            distance=max(0,far)+max(x1-x0,y1-y0)+step
            dx,dy=delta=(vx*distance,vy*distance)
            occupied.append((x0+dx,y0+dy,x1+dx,y1+dy))
        offsets[oid]=delta
    return offsets


def shift_face(items,offset):
    dx,dy=offset
    if not dx and not dy:return items
    return [dict(item,points=[[x+dx,y+dy] for x,y in item['points']],
                 board_layout_delta=(item.get('board_layout_delta',(0,0))[0]+dx,
                                     item.get('board_layout_delta',(0,0))[1]+dy)) for item in items]


def clear_boards(items,mask):
    groups=group_faces(items)
    groups=dict(sorted(groups.items(),key=lambda row:(':NO_ENTRY_BOARD:' not in row[0],
                                                     row[0].startswith('AUTO:'))))
    offsets=layout_faces(groups,mask,local_auto=True)
    return [shift_face([item],offsets[item['oid']])[0] if item.get('sign_board21_2') else item
            for item in items if not item.get('sign_board21_2') or item['oid'] in offsets]


def scaled_face(items,zoom):
    height=max((e.get('face_height24',0) for e in items),default=0)
    height=height or max(e.get('size',0) for e in items) or .4
    return scale_face(items,20/(max(zoom,.0001)*height))


def scale_face(items,factor):
    points=[p for e in items for p in e['points']]
    origin=[sum(p[i] for p in points)/len(points) for i in (0,1)]
    result=[]
    for e in items:
        row=dict(e,points=[[origin[i]+(p[i]-origin[i])*factor for i in (0,1)] for p in e['points']])
        for key in ('size','width','text_width','face_height24'):
            if row.get(key):row[key]*=factor
        result.append(row)
    return result


def project_augmentation(scene,items,mask):
    from scene_render import bounds
    x0,y0,x1,y1=bounds(scene)
    configured=scene.data["meta"].get("board_enlarge_factor")
    fixed=isinstance(configured,(int,float)) and math.isfinite(configured) and 1<=configured<=10
    preference=configured if fixed else max(1.5,min(3.,max(x1-x0,y1-y0)/1000.))
    groups=group_faces(items)
    for fraction in ((1.,) if fixed else (1.,.75,.5,.25,.125)):
        factor=1+(preference-1)*fraction
        scaled={oid:scale_face(group,factor) for oid,group in groups.items()}
        offsets=layout_faces(scaled,mask,max_shift=None if fixed else 3.,local_auto=True)
        if offsets is None:continue
        if len(offsets)!=len(scaled) and not fixed:continue
        faces={oid:iter(shift_face(scaled[oid],delta)) for oid,delta in offsets.items()}
        return [next(faces[e['oid']]) if e.get('sign_board21_2') else e for e in items
                if not e.get('sign_board21_2') or e['oid'] in faces]
    return items


def faces(asset):
    from signs21_2 import ARROWS, ordered
    import scene_geometry as g
    p=asset['props']
    role=p.get('sign_role23')
    h=p.get('text_height',.4)
    o=asset['points'][0]
    u=g.unit(o,asset['points'][-1])
    right=(u[1],-u[0])
    angle=math.degrees(math.atan2(u[1],u[0]))-90
    yellow,black,red,white='#ffdb64','#171c20','#cf383e','#ffffff'
    normal=right if p.get('direction_side21_2')=='RIGHT' else (-right[0],-right[1])
    if role=='VACATED':
        u=(-u[0],-u[1])
        right=(-right[0],-right[1])
        angle+=180
    rows=[]

    def point(x,y):
        return [o[k]+x*right[k]+y*u[k] for k in (0,1)]

    def shape(coords,fill=None,stroke=None,width=.018,kind='polygon'):
        rows.append(dict(type=kind,oid=asset['id'],points=[point(x,y) for x,y in coords],
                         fill=fill,stroke=stroke,width=width,sign_board21_2=True,face_height24=2*h))

    def text(label,x,w,color):
        rows.append(dict(type='text',oid=asset['id'],points=[point(x,0)],text=label,
                         fill=color,size=h,text_width=w,rotation=angle,font='normal',
                         world_text=True,sign_board21_2=True,face_height24=2*h,
                         black_outline=p.get('sign_black_ink24',False) and color==white))

    def arrow(symbol,x,color):
        forward,rightward=ARROWS[symbol]
        outline=[(-.4,-.085),(.08,-.085),(.08,-.23),(.4,0),(.08,.23),(.08,.085),(-.4,.085)]
        shape([(x+h*(rightward*a+forward*b),h*(forward*a-rightward*b)) for a,b in outline],color)
        rows[-1]['direction_vector21_2']=True

    name=p.get('direction_name20_18','')
    own=p.get('location_name20_18','')
    arrows=ordered(p.get('direction_arrows20_18',[]))
    side=p.get('direction_side21_2','LEFT')
    panels=p.get('sign_panels24')
    if panels:
        panels=[(entry['kind'],entry['label'],ordered(entry.get('arrows',[]))) for entry in panels]
    elif role=='RUNWAY_NUMBER':
        panels=[('red',name,[])]
        if own:
            at=0 if side=='LEFT' else 1
            panels.insert(at,('location',own,[]))
    elif role=='VACATED':
        loc=('location',own or name,[])
        emblem=('VACATED','',[])
        panels=[loc,emblem] if side=='LEFT' else [emblem,loc]
    elif role in ('NO_ENTRY_BOARD','ROAD_STOP_BOARD'):
        panels=[(role,name,[])]
    elif role in LOCATION:
        panels=[('location',name,[])]
    elif role in MANDATORY:
        panels=[('red',name,[])]
    elif own:
        left=[a for a in arrows if ARROWS[a][1]<0]
        tail=[a for a in arrows if a not in left]
        if len(arrows)==2 and left and tail:
            panels=[('location',own,[]),('yellow',name,arrows)]
        else:
            panels=([('yellow',name,left)] if left else [])+[('location',own,[])]+([('yellow',name,tail)] if tail else [])
        if not arrows:panels.append(('yellow',name,[]))
    else:
        panels=[('yellow',name,arrows)]

    widths=[2*h if kind in ('NO_ENTRY_BOARD','ROAD_STOP_BOARD') else
            max(1.6*h if kind=='VACATED' else h,
                (.6*len(label)+.9*len(aa)+.5)*h)
            for kind,label,aa in panels]
    x=-sum(widths)/2
    for (kind,label,aa),width in zip(panels,widths):
        end=x+width
        center=(x+end)/2
        hi=h
        bg,fg=(black,yellow) if kind=='location' else ((red,white) if kind in ('red','NO_ENTRY_BOARD','ROAD_STOP_BOARD') else (yellow,black))
        if kind=='ROAD_STOP_BOARD':
            for k,fill,stroke in ((1.,red,black),(.92,None,white)):
                s=hi*k
                coords=[(center+dx*s,dy*s) for dx,dy in ((-.414,1),(.414,1),(1,.414),(1,-.414),(.414,-1),(-.414,-1),(-1,-.414),(-1,.414))]
                shape(coords,fill,stroke)
            text(label or '停',center,min(width*.8,max(h,len(label)*.55*h)),white)
        else:
            shape([(x,-hi),(end,-hi),(end,hi),(x,hi)],bg,yellow if kind=='location' else black)
            if kind=='NO_ENTRY_BOARD':
                ring=[(center+h*.54*math.cos(i*math.tau/48),h*.54*math.sin(i*math.tau/48)) for i in range(49)]
                if p.get('sign_black_ink24'):
                    shape(ring,stroke=black,width=.15*h,kind='line')
                shape(ring,stroke=white,width=.1*h,kind='line')
                if p.get('sign_black_ink24'):
                    shape([(center-.37*h,-.085*h),(center+.37*h,-.085*h),(center+.37*h,.085*h),(center-.37*h,.085*h)],black)
                shape([(center-.34*h,-.055*h),(center+.34*h,-.055*h),(center+.34*h,.055*h),(center-.34*h,.055*h)],white)
            elif kind=='VACATED':
                for j,y in enumerate((-.22,-.06,.12,.28) if role=='VACATED' else (.22,.06,-.12,-.28)):
                    if j<2:
                        shape([(x+.12*h,y*h),(end-.12*h,y*h)],stroke=black,width=.05*h,kind='line')
                    else:
                        for n in range(5):
                            a=x+width*(n+.2)/5
                            b=x+width*(n+.7)/5
                            shape([(a,y*h),(b,y*h)],stroke=black,width=.05*h,kind='line')
            else:
                leading=[a for a in aa if ARROWS[a][1]<0]
                trailing=[a for a in aa if a not in leading]
                cursor=x+.25*h
                for a in leading:
                    arrow(a,cursor+.45*h,fg);cursor+=.9*h
                tw=max(.6,len(label)*.6)*h
                text(label,center if not aa else cursor+tw/2,tw,fg)
                cursor+=tw
                for a in trailing:
                    arrow(a,cursor+.45*h,fg);cursor+=.9*h
        x=end
    return [dict(e,board_normal24=normal) for e in rows]


def parse_panels(expression,group):
    from signs21_2 import ARROWS
    panels=[]
    for piece in expression.split('|'):
        token=piece.strip()
        if not token:continue
        location=token.startswith('@')
        arrows=[key for key in token if key in ARROWS]
        name=''.join(key for key in token.removeprefix('@') if key not in ARROWS).strip().upper()
        if not name or (location and (arrows or group=='DESTINATION_GROUP')) or (not location and not arrows):
            raise ValueError('组合牌请输入 @位置编号 或 带箭头的编号，例如 ←C | @B | C→')
        panels.append(dict(kind='location' if location else 'yellow',label=name,arrows=arrows))
    if not panels or len(panels)>12:raise ValueError('组合牌需要 1 至 12 个牌面')
    return panels


CAT_LEVELS={'1':'CAT I','2':'CAT II','3':'CAT III','2/3':'CAT II/III'}


def runway_connections(scene,source):
    from pavement_geometry import crossings
    connections={}
    for junction in crossings(scene):
        if source not in junction['assets']:
            continue
        for aid in junction['assets']:
            asset=scene.assets.get(aid)
            if asset and asset['kind']=='RUNWAY':
                connections[aid]=asset
    for mid,movement in scene.movements.items():
        endpoints=[scene.assets[movement[end]['asset']] for end in ('from','to')]
        if source!=mid and all(asset['id']!=source for asset in endpoints):
            continue
        for asset in endpoints:
            if asset['kind']=='RUNWAY':
                connections[asset['id']]=asset
    return connections


def cat_labels(runway):
    p=runway['props']
    return [f"{p['label_'+end]} {CAT_LEVELS[p['level_'+end]]}"
            for end in ('a','b') if p.get('label_'+end) and p.get('level_'+end) in CAT_LEVELS]


def b_holds(scene,axis,hold):
    import scene_geometry as g
    station=g.project(axis['points'],hold['point'])[1]
    for mark in scene.assets.values():
        p=mark['props']
        if p.get('mark_type')!='HOLD_B':
            continue
        owner=p.get('label_asset')
        distance,offset,q=g.project(axis['points'],mark['points'][0])
        if distance>.5 or (owner and owner!=axis['id']):
            continue
        _,tangent=g.at(axis['points'],offset)
        toward=sum(a*b for a,b in zip(tangent,hold['tangent']))
        if (offset-station)*toward<=.01:
            yield abs(offset-station),mark['id'],q


def runway_number_boards(scene,network,synthetic):
    from automatic_markings import holding_locations
    from directions20_18 import closed
    from signs21_2 import sign_props
    from segments18 import piece_at
    import scene_geometry as g
    result={}
    holds=holding_locations(scene)
    for hold in holds:
        owner=hold['owner']
        axis=network.get(owner)
        movement=scene.movements.get(owner)
        if axis is None and movement:
            axis=next((network[movement[end]['asset']] for end in ('from','to')
                       if movement[end]['asset'] in network),None)
        if not axis or not hold['auto_signs'] or closed(scene,owner) or closed(scene,hold['runway']):
            continue
        runway=scene.assets[hold['runway']]
        q,u=hold['point'],hold['tangent']
        v=(-u[1],u[0])
        candidates=sorted(candidate for candidate in b_holds(scene,axis,hold)
                          if min((other for other in holds if other['owner']==owner),
                                 key=lambda other:g.distance(other['point'],candidate[2])) is hold)
        if candidates and candidates[0][0]<=15:
            q=candidates[0][2]
        elif candidates:
            for number,label in enumerate(cat_labels(runway)):
                _,bid,point=candidates[0]
                for side,sign in (('LEFT',1),('RIGHT',-1)):
                    props=sign_props(label,[],True,side,hold['width'])
                    props.update(sign_role23='CAT_HOLD',standard_clause20_18='9.7.3.9')
                    offset=max(hold['width']/2+11,hold['span']/2+1)+1
                    anchor=[point[i]+v[i]*sign*offset for i in (0,1)]
                    mark=synthetic(owner,'DIRECTION',[anchor,[anchor[i]+u[i]*10 for i in (0,1)]],
                                   f"CAT_BOARD:{hold['key']}:{bid}:{number}:{side}",**props)
                    result[mark['id']]=mark
        numbers=[runway['props'].get('label_'+end,'') for end in ('a','b')]
        runway_axis=g.unit(*runway['points'])
        if sum(v[i]*runway_axis[i] for i in (0,1))>0:numbers.reverse()
        name='–'.join(n for n in numbers if n)
        location=piece_at(axis,g.project(axis['points'],q)[1])['name']
        for side,sign in (('LEFT',1),('RIGHT',-1)):
            props=sign_props(name,[],True,side,hold['width'],location)
            props.update(sign_role23='RUNWAY_NUMBER',standard_clause20_18='9.7.3.3')
            offset=max(hold['width']/2+11,hold['span']/2+1)+max(1,len(name)*.13)
            anchor=[q[i]+v[i]*sign*offset for i in (0,1)]
            mark=synthetic(owner,'DIRECTION',[anchor,[anchor[i]+u[i]*10 for i in (0,1)]],
                           'RUNWAY_BOARD24:'+hold['key']+':'+side,**props)
            result[mark['id']]=mark
        if movement and movement.get('role') in ('ENTRY','STAND_ENTRY') and not movement.get('bidirectional',False):
            continue
        if not movement and axis['props'].get('flow') in ('FORWARD','REVERSE'):
            _,tangent=g.at(axis['points'],g.project(axis['points'],q)[1])
            travel=1 if axis['props']['flow']=='FORWARD' else -1
            if sum(u[i]*tangent[i]*travel for i in (0,1))>0:continue
        # The vacated face is read while leaving the runway. Place it just
        # beyond the hold line in that direction, separate from the number boards.
        q=hold['point']
        props=sign_props(location,[],True,'LEFT',hold['width'],location)
        props.update(sign_role23='VACATED',standard_clause20_18='9.7.4.6')
        offset=max(hold['width']/2+11,hold['span']/2+1)+1
        anchor=[q[i]-u[i]*7-v[i]*offset for i in (0,1)]
        mark=synthetic(owner,'DIRECTION',[anchor,[anchor[i]-u[i]*10 for i in (0,1)]],
                       'VACATED_BOARD25:'+hold['key'],**props)
        mark['name']='脱离跑道／位置标记牌 · '+location
        result[mark['id']]=mark
    return result
