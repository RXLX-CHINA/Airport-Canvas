"""One rapid-exit geometry editor for drawn and connected taxiways."""
import math
from interface_language import tr
import scene_geometry as g
from smart_routes import rapid_layout,layout_path,reverse_join,recommended_radius

FIELDS=(
    ('exit_radius','跑道端正向半径',550.),
    ('join_radius','滑行道端正向半径',25.),
    ('rapid_exact_straight','正向直线段（0 为自动）',0.),
    ('rapid_taxi_stub','滑行道侧短联络直线段（0 为直接并入）',0.),
    ('reverse_join_radius','滑行道端反向半径',25.),
    ('reverse_surface_radius','滑行道端反向道面轴线半径（0 跟随中线）',0.),
    ('reverse_rapid_exact_straight','反向直线段（0 为自动）',0.),
)

def set_connected_type(scene,oid,route_type):
    from project10 import SUBTYPES
    from smart_routes import configure_rapid
    movement=scene.movements.get(oid)
    if not movement or movement.get('legacy_attachment') or route_type not in SUBTYPES:
        raise ValueError('请选择可编辑的连接滑行道类型。')
    if route_type=='快速脱离道':
        from project10 import TAXIS
        kinds=tuple(scene.assets[movement[side]['asset']]['kind'] for side in ('from','to'))
        if kinds[0]=='RUNWAY' and kinds[1] in TAXIS:
            ports={}
        elif kinds[1]=='RUNWAY' and kinds[0] in TAXIS:
            ports={'from':dict(movement['to'],direction=-movement['to']['direction']),
                   'to':dict(movement['from'],direction=-movement['from']['direction'])}
        else:
            raise ValueError('快速脱离道需要连接一条跑道和一条滑行道。')
        configure_rapid(scene,oid,route_type=route_type,taxiway_kind39='TAXIWAY',**ports)
    else:
        kind=SUBTYPES[route_type]
        props=dict(route_type=route_type,taxiway_kind39=kind)
        if movement.get('role')=='RAPID_EXIT':
            props['geometry']='BEZIER'
        if route_type=='机坪入口滑行道':
            props['role']='APRON_ACCESS'
        elif movement.get('role') in ('RAPID_EXIT','APRON_ACCESS'):
            ends=[scene.assets[movement[side]['asset']]['kind'] for side in ('from','to')]
            props['role']='EXIT' if ends[0]=='RUNWAY' else 'ENTRY' if ends[1]=='RUNWAY' else 'TAXIWAY_JOIN'
        scene.update_movement(oid,**props)

def source(scene,oid):
    movement=scene.movements.get(oid)
    if movement and not movement.get('legacy_attachment') and movement.get('geometry')=='RAPID':
        return movement,None,None
    asset=scene.assets.get(oid)
    if not asset or not asset['props'].get('rapid_exit'):return None
    links=[m for m in scene.movements.values() if m.get('legacy_attachment') and m['to']['asset']==oid]
    runway=next((m for m in links if scene.assets[m['from']['asset']]['kind']=='RUNWAY'),None)
    taxi=next((m for m in links if scene.assets[m['from']['asset']]['kind'] in
               ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')),None)
    if (not runway or not taxi) and asset['props'].get('rapid_drawn_axis56'):
        points=asset['points']
        length=g.length(points)
        def endpoint_link(kinds,exclude):
            candidates=[]
            for end,point in enumerate((points[0],points[-1])):
                if end==exclude:continue
                tangent=g.unit(*(points[:2] if end==0 else points[-2:]))
                for target in scene.assets.values():
                    if target['id']==oid or target['kind'] not in kinds:continue
                    distance,station,_=g.project(target['points'],point)
                    if distance>.05:continue
                    _,axis=g.at(target['points'],station)
                    direction=1 if sum(x*y for x,y in zip(axis,tangent))>=0 else -1
                    if (end==1)==('RUNWAY' in kinds):direction=-direction
                    port=dict(asset=target['id'],station=station,direction=direction)
                    own=dict(asset=oid,station=length if end else 0.,direction=1)
                    candidates.append((distance,target['id'],end,{'from':port,'to':own}))
            return min(candidates,key=lambda row:row[:3])[-1] if candidates else None
        runway=runway or endpoint_link(('RUNWAY',),None)
        if runway:
            taxi=taxi or endpoint_link(('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'),
                                       int(runway['to']['station']>length/2))
    if not runway or not taxi:return None
    model=dict(runway)
    p=asset['props']
    if p.get('rapid_radius'):model['exit_radius']=p['rapid_radius']
    if p.get('rapid_angle'):model['exit_angle']=p['rapid_angle']
    model.update(p.get('rapid_geometry39',{}))
    for key in ('reverse_join_radius','reverse_surface_radius'):
        if p.get(key):model[key]=p[key]
    model.update(width=asset['props']['width'],**{'from':dict(runway['from']),'to':dict(taxi['from'])})
    if p.get('rapid_drawn_axis56'):
        from curve_model import editable_vertices
        points=editable_vertices(asset)
        if runway['to']['station']>g.length(asset['points'])/2:points=list(reversed(points))
        runway_axis=g.unit(*scene.assets[model['from']['asset']]['points'])
        normal=(-runway_axis[1],runway_axis[0])
        segments=[]
        for a,b in zip(points,points[1:]):
            delta=[y-x for x,y in zip(a,b)]
            along=sum(d*u for d,u in zip(delta,runway_axis))
            across=sum(d*u for d,u in zip(delta,normal))
            if abs(along)>1e-6 and abs(across)>1e-6:
                segments.append((math.hypot(along,across),along,across,a))
        if not segments:return None
        _,along,across,straight_start=max(segments,key=lambda segment:segment[0])
        from_normal=math.degrees(math.atan2(abs(along),abs(across)))
        model['from']['direction']=1 if along>0 else -1
        taxi_axis=scene.assets[model['to']['asset']]['points']
        _,target_direction=g.at(taxi_axis,model['to']['station'])
        alignment=sum(a*b for a,b in zip(g.unit(points[-2],points[-1]),target_direction))
        if abs(alignment)>1e-6:model['to']['direction']=1 if alignment>0 else -1
        axis=list(asset['points'])
        if runway['to']['station']>g.length(axis)/2:axis.reverse()
        _,station,_=g.project(axis,straight_start)
        model.update(exit_angle=90.-from_normal,rapid_lock_angle39=True,rapid_auto_fit=False,
                     drawn_axis39=axis,drawn_straight_start39=station)
    return model,runway,taxi

def plans(scene,model,values):
    configured=dict(model,**values)
    configured['rapid_auto_radius']=False
    for key,_,_ in FIELDS:
        value=configured.get(key)
        if value is None:continue
        if key=='reverse_surface_radius' and value==0:continue
        minimum=0 if 'straight' in key or key=='rapid_taxi_stub' else configured['width']/2
        if not math.isfinite(value) or value<minimum or (minimum>0 and value==minimum):
            raise ValueError('半径须大于半幅道面宽度，直线段长度须为非负数。')
    forward=rapid_layout(scene,configured)
    reverse=reverse_join(scene,configured)
    from smart_routes import reverse_surface
    reverse_surface(scene,configured,reverse)
    return forward,reverse

def apply(scene,oid,values):
    state=source(scene,oid)
    if not state:raise ValueError('请选择两端已连接的快速脱离道。')
    model,runway,taxi=state
    forward,reverse=plans(scene,model,values)
    if reverse is None and values.get('reverse_rapid_exact_straight') and not values.get('rapid_taxi_stub'):
        raise ValueError('无法拟合指定长度的反向直线段。')
    with scene.transaction('更新快速脱离道几何'):
        if runway is None:
            model.update(values,rapid_auto_radius=False)
            model['from']['station']=forward['runway_station']
            model['to'].update(station=forward['station'],direction=forward['direction'])
            model.pop('branch_controls',None)
            model.pop('branch_anchors',None)
        else:
            asset=scene.assets[oid]
            points=layout_path(forward)
            old=g.length(asset['points'])
            if runway['to']['station']>old/2:points.reverse()
            new=g.length(points)
            for link in scene.movements.values():
                for port in (link['from'],link['to']):
                    if port['asset']==oid:port['station']*=new/old
            runway['from'].update(station=forward['runway_station'],direction=model['from']['direction'])
            taxi['from'].update(station=forward['station'],direction=forward['direction'])
            asset['points']=points
            for link,role in ((runway,'RAPID_EXIT'),(taxi,'TAXIWAY_JOIN')):
                if 'id' not in link:
                    end=new if link['to']['station']>old/2 else 0.
                    scene.connect(link['from'],dict(link['to'],station=end),role,
                                  width=asset['props']['width'],legacy_attachment=True)
            for key in ('curve_nodes','design_vertices'):asset.pop(key,None)
            for key in ('rapid_drawn_axis56','reverse_join_radius','reverse_surface_radius'):
                asset['props'].pop(key,None)
            geometry=dict(values)
            if model.get('drawn_axis39'):
                geometry.update(drawn_axis39=model['drawn_axis39'],
                                drawn_straight_start39=model['drawn_straight_start39'])
            if model.get('rapid_lock_angle39'):
                geometry.update(rapid_lock_angle39=True,rapid_auto_fit=False)
            asset['props'].update(rapid_geometry39=geometry,rapid_radius=forward['r'],
                                  rapid_angle=forward['exit_angle'])

def open_dialog(editor):
    from PySide6 import QtCore,QtWidgets
    oid=editor.selection
    state=source(editor.scene,oid)
    if not state:
        editor.status.set('请选择两端已连接的快速脱离道。')
        return
    model=state[0]
    window=QtWidgets.QDialog(editor.q)
    window.setWindowTitle(tr('快速脱离道几何'))
    window.setMinimumWidth(390)
    layout=QtWidgets.QFormLayout(window)
    fields={}
    defaults={'exit_radius':recommended_radius(editor.scene,model)}
    for key,label,default in FIELDS:
        field=QtWidgets.QDoubleSpinBox()
        field.setDecimals(2)
        field.setRange(0,100000)
        field.setSuffix(' m')
        fallback=key if 'straight' in key or key=='rapid_taxi_stub' else key.removeprefix('reverse_')
        field.setValue(model.get(key,model.get(fallback,defaults.get(fallback,default))))
        fields[key]=field
        layout.addRow(tr(label),field)
    if model.get('drawn_axis39'):fields['exit_radius'].setEnabled(False)
    message=QtWidgets.QLabel()
    message.setWordWrap(True)
    layout.addRow(message)
    if editor.scene.assets.get(oid,{}).get('props',{}).get('rapid_drawn_axis56'):
        notice=QtWidgets.QLabel(tr('手绘倾斜角已锁定（相对跑道法线）：{angle:.2f}°。应用后只按所选半径和直线段重新拟合。').format(angle=90.-model['exit_angle']))
        notice.setWordWrap(True)
        layout.addRow(notice)
    buttons=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Apply|
                                      QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    layout.addRow(buttons)
    apply_button=buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply)
    apply_button.setText(tr('应用'))
    timer=QtCore.QTimer(window)
    timer.setSingleShot(True)
    timer.setInterval(70)

    def values():
        return {key:field.value() for key,field in fields.items()}

    def preview():
        canvas=editor.canvas
        canvas.delete('rapid_preview39')
        shared=fields['rapid_taxi_stub'].value()>0

        fields['reverse_rapid_exact_straight'].setEnabled(not shared or bool(model.get('drawn_axis39')))
        try:
            forward,reverse=plans(editor.scene,model,values())
            if reverse is None and values().get('reverse_rapid_exact_straight') and not shared:
                raise ValueError('无法拟合指定长度的反向直线段。')
            from pavement_geometry import offset
            paths=[(layout_path(forward),'#168ad1')]
            if reverse:
                from smart_routes import reverse_surface
                surface=reverse_surface(editor.scene,dict(model,**values()),reverse)
                paths.append((surface['points'],'#e25969'))
            for points,color in paths:
                axis=reverse['points'] if reverse and color=='#e25969' else points
                for line in (axis,offset(points,model['width']/2),offset(points,-model['width']/2)):
                    canvas.create_line(*[v for q in line for v in editor.screen(q)],
                                       fill=color,width=2,tags='rapid_preview39')
            reverse_text=f'{reverse["layout"]["straight"]:.1f} m' if reverse else tr('当前几何无可用反向汇入')
            message.setText(tr('实际直线段：正向 {forward:.1f} m，反向 {reverse}').format(forward=forward['straight'],reverse=reverse_text))
            apply_button.setEnabled(True)
        except ValueError as error:
            message.setText(tr(str(error)))
            apply_button.setEnabled(False)

    def commit():
        try:apply(editor.scene,oid,values())
        except ValueError as error:message.setText(tr(str(error)));return
        window.accept()
        editor.refresh()

    timer.timeout.connect(preview)
    for field in fields.values():field.valueChanged.connect(lambda _:timer.start())
    apply_button.clicked.connect(commit)
    buttons.rejected.connect(window.reject)
    window.finished.connect(lambda _:editor.canvas.delete('rapid_preview39'))
    window.setModal(True)
    preview()
    editor._rapid_dialog39=window
    window.open()
