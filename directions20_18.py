"""Distinct MH5001-2013 pavement information and physical direction boards.

Automatic placements are planning aids. Review board table32/appendixH clearances.
"""
import math
import scene_geometry as g
YELLOW='#ffdb64';BLACK='#171c20'

def board_text(name,arrows):
    left=[a for a in arrows if a in ('←','↖','↙')]
    return ''.join(left)+name+''.join(a for a in arrows if a not in left)

def pavement_text(name,arrows):return name+' '+''.join(arrows)

def closed(scene,aid):
    if aid in scene.assets:return scene.is_closed(aid)
    m=scene.movements.get(aid)
    return not m or not m.get('enabled',True) or any(scene.is_closed(m[k]['asset']) for k in ('from','to'))

def outgoing(a,s):
    L=g.length(a['points']);flow=a['props'].get('flow','BOTH');out=[]
    for sign in (-1,1):
        if flow=='FORWARD' and sign<0 or flow=='REVERSE' and sign>0:continue
        if (s if sign<0 else L-s)<1:continue
        q,_=g.at(a['points'],s);target,_=g.at(a['points'],max(0,min(L,s+sign*min(10,L/4))));out.append(g.unit(q,target))
    return out

def arrow(u,v):
    angle=math.atan2(u[0]*v[1]-u[1]*v[0],sum(u[k]*v[k] for k in (0,1)))
    if abs(angle)>math.pi*.85:return None
    from signs21_2 import arrow as quantize
    return quantize(u,v)

def generated(scene):
    import segments18 as logical
    from pavement_geometry import crossings
    from automatic_markings import synthetic
    meta=scene.data['meta'];ground=meta.get('auto_information20_18',True);boards=meta.get('auto_boards20_18',True)
    if not ground and not boards:return {}
    routes=logical.routes(scene);neighbors={aid:[] for aid in routes};out={}
    def add(aid,bid,s,t):
        if aid in routes and bid in routes and aid!=bid:neighbors[aid].append((s,bid,t))
    for j in crossings(scene):
        a,b=j['assets'];s,t=j['stations'];add(a,b,s,t);add(b,a,t,s)
    for mid,m in scene.movements.items():
        if mid not in routes or closed(scene,mid):continue
        for side,index in [('from',0),('to',-1)]:
            p=m[side];s=0 if index==0 else g.length(routes[mid]['points']);add(p['asset'],mid,p['station'],s);add(mid,p['asset'],s,p['station'])
    for aid,a in routes.items():
        p=a['props'];L=g.length(a['points']);width=p.get('width',23)
        if L<=4 or closed(scene,aid) or not p.get('auto_direction20_18',True):continue
        for sign in (-1,1):
            if p.get('flow')=='FORWARD' and sign<0 or p.get('flow')=='REVERSE' and sign>0:continue
            choices=[]
            for station,bid,t in neighbors[aid]:
                b=routes[bid]
                if closed(scene,bid):continue
                name=logical.piece_at(b,t)['name'];own=logical.piece_at(a,station)['name']
                _,u=g.at(a['points'],station);u=[x*sign for x in u];arrows=list(dict.fromkeys(v for v in (arrow(u,du) for du in outgoing(b,t)) if v))
                if arrows:choices.append((abs(station-L/2),station,bid,t,name,own,arrows))
            if not choices:continue
            ground_choices=[c for c in choices if c[4]!=c[5] and (c[1]-L/2)*sign>=-.001]
            layout=[]
            if ground and L>=20 and ground_choices:
                layout.append((False,min(ground_choices,key=lambda c:c[:3]),None))
            if boards:
                seen=set()
                for choice in sorted(choices,key=lambda c:(c[1],c[2],c[3])):
                    for branch,symbol in enumerate(choice[-1]):
                        key=(round(choice[1],3),choice[2],symbol)
                        if key in seen:continue
                        seen.add(key)
                        layout.append((True,(*choice[:-1],[symbol]),branch))
            for board,(_,station,bid,t,name,own,arrows),branch in layout:
                available=station if sign>0 else L-station
                before=(60 if (p.get('code_number') or meta.get('code_number',4)) in (3,4) else 40) if board else max(12,width)
                if board:
                    # A marked intermediate holding position takes precedence over
                    # the generic 60/40m approach station (9.7.4.3.10).
                    holds=[]
                    for mark in scene.assets.values():
                        if mark['props'].get('mark_type') not in ('INTERMEDIATE','INTERMEDIATE_POINT'):continue
                        d,hs,_=g.project(a['points'],mark['points'][0])
                        if d<=width/2 and (station-hs)*sign>0:holds.append(hs)
                    if holds:before=min((station-hs)*sign for hs in holds)
                if board and available>4:before=min(before,available-2)
                if available<before+2:continue
                at=station-sign*before;q,u=g.at(a['points'],at);u=[x*sign for x in u];v=[-u[1],u[0]];h=.4 if board else min(2,(width/2-2-len(arrows)*3)/max(.6,len(name)*.6))
                if not board and h<2:continue
                tw=(len(name)*.6+len(arrows)*.55)*h if board else len(name)*.6*h+len(arrows)*3;lateral=width/2+11+tw/2 if board else -(1+tw/2);q=[q[k]+v[k]*lateral for k in (0,1)]
                text=board_text(name,arrows) if board else pavement_text(name,arrows);suffix=('BOARD20_18:'+str(sign)+':'+bid+':'+str(round(station,3))+':'+str(branch)
                        if board else 'DIRECTION20_18:'+str(sign))
                m=synthetic(aid,'DIRECTION',[q,[q[k]+u[k]*10 for k in (0,1)]],suffix,text=text,text_height=h,information_profile20_18='BOARD' if board else 'PAVEMENT',direction_name20_18=name,direction_arrows20_18=arrows,location_name20_18=own if board else '',destination_asset20_18=bid,auto_direction20_18=True,standard_clause20_18='9.7.4.3' if board else '8.2.13')
                m['name']='方向标记牌组' if board else '道面方向信息标志';out[m['id']]=m
    out.update(__import__("signs21_2").extra(scene,routes,ground,boards))
    if boards:
        from boards24 import runway_number_boards
        out.update(runway_number_boards(scene,routes,synthetic))
    return out

def intersection_panels(choices,station,location,width):
    """Combine branches of the same junction into a direction/position assembly."""
    approaches={}
    for _,at,_,_,name,_,arrows in choices:
        if abs(at-station)<=max(2,width*.2):
            approaches.setdefault(name,set()).update(arrows)
    if len(approaches)<2:return None
    ordering='↙←↖↑↗→↘↓'
    left=[]
    right=[]
    for name,arrows in approaches.items():
        for symbol in arrows:
            panel=dict(kind='yellow',label=name,arrows=[symbol])
            (left if symbol in '↙←↖' else right).append(panel)
    rank=lambda panel:(ordering.index(panel['arrows'][0]),panel['label'])
    return sorted(left,key=rank)+[dict(kind='location',label=location,arrows=[])]+sorted(right,key=rank)


def primitives(asset):
    if asset['props']['information_profile20_18']=='BOARD':
        from boards24 import faces
        return faces(asset)
    p=asset['props'];o=asset['points'][0];u=g.unit(asset['points'][0],asset['points'][-1]);v=[-u[1],u[0]];out=[];oid=asset['id'];h=p.get('text_height',4);board=p['information_profile20_18']=='BOARD'
    def xy(x,y):return [o[k]+u[k]*x-v[k]*y for k in (0,1)]
    def box(x0,y0,x1,y1,fill,stroke=BLACK):out.append(dict(type='polygon',oid=oid,points=[xy(x0,y0),xy(x0,y1),xy(x1,y1),xy(x1,y0)],fill=fill,stroke=stroke,width=.025 if board else .1))
    def text(s,y,w,color=BLACK):out.append(dict(type='text',oid=oid,points=[xy(0,y)],text=s,fill=color,size=h,text_width=w,rotation=math.degrees(math.atan2(u[1],u[0]))-90,world_text=True,font='normal'))
    from signs21_2 import ARROWS, ordered
    name=p.get('direction_name20_18','')
    arrows=ordered(p.get('direction_arrows20_18',['↑']))
    rows=p.get('sign_ground_rows') or [dict(label=name,arrows=arrows)]
    tokens=[]
    for index,row in enumerate(rows):
        if index:tokens.append(('',.35*h,False))
        left=[a for a in ordered(row['arrows']) if ARROWS[a][1]<0]
        right=[a for a in ordered(row['arrows']) if a not in left]
        tokens.extend([(a,.9*h,True) for a in left])
        tokens.append((row['label'],max(.6,len(row['label'])*.6)*h,False))
        tokens.extend([(a,.9*h,True) for a in right])
    total=sum(width for _,width,_ in tokens)
    mandatory=p.get('sign_role23') in ('HOLD_BOARD','FREQUENCY','FREQUENCY_PAVEMENT')
    pad=.45
    box(-h/2-pad,-total/2-pad,h/2+pad,total/2+pad,'#cf383e' if mandatory else YELLOW)
    y=-total/2
    for value,width,is_arrow in tokens:
        center=y+width/2
        if is_arrow:
            # Closed, solid arrow outline; rotate from its locally forward pose.
            dx,dy=ARROWS[value]
            shape=[(-.38,-.09),(.04,-.09),(.04,-.23),(.38,0),(.04,.23),(.04,.09),(-.38,.09)]
            points=[xy(h*(dx*x-dy*z),center+h*(dy*x+dx*z)) for x,z in shape]
            out.append(dict(type='polygon',oid=oid,points=points,fill=BLACK,direction_vector21_2=True))
        elif value:
            text(value,center,width,'#ffffff' if mandatory else BLACK)
        y+=width
    own=p.get('location_name20_18','')
    if board and own:
        lw=max(.6,len(own)*.6)*h
        edge=-total/2-pad
        box(-h/2-pad,edge-lw-2*pad,h/2+pad,edge,BLACK,YELLOW)
        text(own,edge-pad-lw/2,lw,YELLOW)
    return [dict(item,sign_board21_2=board) for item in out]
