"""Screen work-area sizing, shape-preserving resize, true crossing shear."""
import copy,math
import scene_geometry as g

def work_area(widget):
    if __import__('sys').platform=='win32':
        try:
            import ctypes
            from ctypes import wintypes
            class RECT(ctypes.Structure):_fields_=[('left',wintypes.LONG),('top',wintypes.LONG),('right',wintypes.LONG),('bottom',wintypes.LONG)]
            rect=RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030,0,ctypes.byref(rect),0):return rect.left,rect.top,rect.right,rect.bottom
        except (OSError,AttributeError):pass
    return 0,0,widget.winfo_screenwidth(),widget.winfo_screenheight()-48
def window_geometry(area):
    x0,y0,x1,y1=area;aw=max(240,x1-x0);ah=max(180,y1-y0);w=min(1540,int(aw*.94));h=min(1000,int(ah*.92));return w,h,x0+(aw-w)//2,y0+(ah-h)//2
def uniform_target(box,target,handle):
    x0,y0,x1,y1=box;xx0,yy0,xx1,yy1=target;w=max(.01,x1-x0);h=max(.01,y1-y0);sx=(xx1-xx0)/w;sy=(yy1-yy0)/h
    scale=sx if handle in ('E','W') else sy if handle in ('N','S') else max(sx,sy) if sx>=1 and sy>=1 else min(sx,sy);scale=max(.02,scale)
    width,height=w*scale,h*scale;cx=(x0+x1)/2;cy=(y0+y1)/2
    if 'W' in handle:xx0,xx1=x1-width,x1
    elif 'E' in handle:xx0,xx1=x0,x0+width
    else:xx0,xx1=cx-width/2,cx+width/2
    if 'N' in handle:yy0,yy1=y0,y0+height
    elif 'S' in handle:yy0,yy1=y1-height,y1
    else:yy0,yy1=cy-height/2,cy+height/2
    return xx0,yy0,xx1,yy1
def resize_target(box,target,handle,shift=False):
    if not shift:
        return target
    x0,y0,x1,y1=box
    if handle=='E':return x0,y0,x0+y1-y0,y1
    if handle=='W':return x1-y1+y0,y0,x1,y1
    if handle=='N':return x0,y0,x1,y0+x1-x0
    if handle=='S':return x0,y1-x1+x0,x1,y1
    return uniform_target(box,target,handle)

def shear(scene,aid,q):
    a=scene.assets[aid];p=a['props'];parent=scene.assets[p['crossing_asset13']];center,u=g.at(parent['points'],p['crossing_station13']);offset=sum((q[k]-center[k])*u[k] for k in (0,1));p['crossing_skew13']=max(-80,min(80,math.degrees(math.atan2(offset,parent['props']['width']/2))))
def shear_handle(scene,a):
    p=a['props'];parent=scene.assets[p['crossing_asset13']];q,u=g.at(parent['points'],p['crossing_station13']);v=[-u[1],u[0]];half=parent['props']['width']/2;dx=half*math.tan(math.radians(p.get('crossing_skew13',0)));return [q[k]+u[k]*dx+v[k]*half for k in (0,1)]
def sync(scene):
    from stand13 import envelope
    for a in scene.assets.values():
        p=a['props']
        if 'snap_tolerance15' in p and (not math.isfinite(p['snap_tolerance15']) or p['snap_tolerance15']<0):raise ValueError('吸附距离须为非负有限值')
        if a['kind']=='STAND' and 'safety_slope15' not in p:
            d=envelope(a,scene);p['safety_slope15']=(d['wide']-d['narrow'])/max(.1,d['neck_start']-d['wing'])
        if p.get('crossing_full13') and p.get('crossing_asset13') in scene.assets:
            if not math.isfinite(p.get('crossing_skew13',0)) or abs(p.get('crossing_skew13',0))>80:raise ValueError('横道剪切角应在-80°～80°之间')
            parent=scene.assets[p['crossing_asset13']];q,u=g.at(parent['points'],min(g.length(parent['points']),p['crossing_station13']));a['points']=[q,[q[k]+u[k]*10 for k in (0,1)]];p['width']=parent['props']['width']
def terminal(scene,aid,station,keep='START',enabled=True,jid=None):
    from rules13 import set_terminal
    from curve_model import nodes_for,split_curve_nodes,evaluate
    a=scene.assets[aid];original=copy.deepcopy(a);L=g.length(a['points'])
    with scene.transaction('精确截断并保持曲线半径'):
        set_terminal(scene,aid,station,keep,enabled,jid)
        if enabled:
            if original.get('curve_nodes'):
                left,right=split_curve_nodes(original['curve_nodes'],station);nodes=left if keep=='START' else right;a['curve_nodes']=nodes;a['points']=evaluate(nodes)
            a.pop('design_vertices',None)
            actual=g.length(a['points']);expected=station if keep=='START' else L-station
            if expected>0:
                for movement in scene.movements.values():
                    for side in ('from','to'):
                        if movement[side]['asset']==aid:movement[side]['station']=min(actual,movement[side]['station']*actual/expected)
            a['props']['terminal_edge_radius15']=max(.5,a['props'].get('turn_radius',25)-a['props']['width']/2)
            a['props']['terminal_outer_radius15']=a['props'].get('turn_radius',25)+a['props']['width']/2
        else:
            a['props'].pop('terminal_edge_radius15',None);a['props'].pop('terminal_outer_radius15',None)

def resize(scene,roots,box,target):
    from layout14 import scale
    sx=(target[2]-target[0])/max(.01,box[2]-box[0])
    sy=(target[3]-target[1])/max(.01,box[3]-box[1])
    factor=math.sqrt(sx*sy)
    with scene.transaction('调整组件尺寸'):
        ids=scale(scene,roots,box,target)
        for aid in ids:
            a=scene.assets.get(aid)
            if not a:continue
            p=a['props']
            for key in ('lead_radius','corner_radius','fillet_radius','turn_radius','safety_clearance','safety_neck','nose_to_nosewheel','fuselage_width'):
                if key in p:p[key]*=factor
    return ids
