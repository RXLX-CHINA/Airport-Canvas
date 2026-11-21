"""One rapid-exit geometry editor for drawn and connected taxiways."""
import math
import scene_geometry as g
from smart_routes import rapid_layout,layout_path,reverse_join,recommended_radius

FIELDS=(
    ('exit_radius','跑道端正向半径',550.),
    ('join_radius','滑行道端正向半径',25.),
    ('rapid_exact_straight','正向直线段（0 为自动）',0.),
    ('rapid_taxi_stub','滑行道侧短联络直线段（0 为直接并入）',0.),
    ('reverse_exit_radius','跑道端反向半径',550.),
    ('reverse_join_radius','滑行道端反向半径',25.),
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
    if not asset or not asset['props'].get('rapid_exit') or asset['props'].get('rapid_drawn_axis56'):return None
    links=[m for m in scene.movements.values() if m.get('legacy_attachment') and m['to']['asset']==oid]
    runway=next((m for m in links if scene.assets[m['from']['asset']]['kind']=='RUNWAY'),None)
    taxi=next((m for m in links if scene.assets[m['from']['asset']]['kind'] in
               ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')),None)
    if not runway or not taxi:return None
    model=dict(runway)
    p=asset['props']
    if p.get('rapid_radius'):model['exit_radius']=p['rapid_radius']
    if p.get('rapid_angle'):model['exit_angle']=p['rapid_angle']
    model.update(p.get('rapid_geometry39',{}))
    model.update(width=asset['props']['width'],**{'from':runway['from'],'to':taxi['from']})
    return model,runway,taxi

def plans(scene,model,values):
    configured=dict(model,**values)
    configured['rapid_auto_radius']=False
    for key,_,_ in FIELDS:
        value=configured.get(key)
        if value is None:continue
        minimum=0 if 'straight' in key or key=='rapid_taxi_stub' else configured['width']/2
        if not math.isfinite(value) or value<minimum or (minimum>0 and value==minimum):
            raise ValueError('半径须大于半幅道面宽度，直线段长度须为非负数。')
    forward=rapid_layout(scene,configured)
    reverse=reverse_join(scene,configured)
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
            taxi['from'].update(station=forward['station'],direction=forward['direction'])
            asset['points']=points
            for key in ('curve_nodes','design_vertices'):asset.pop(key,None)
            asset['props'].update(rapid_geometry39=dict(values),rapid_radius=forward['r'],
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
    window.setWindowTitle('快速脱离道几何')
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
        layout.addRow(label,field)
    message=QtWidgets.QLabel()
    message.setWordWrap(True)
    layout.addRow(message)
    buttons=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Apply|
                                      QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    layout.addRow(buttons)
    apply_button=buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply)
    apply_button.setText('应用')
    timer=QtCore.QTimer(window)
    timer.setSingleShot(True)
    timer.setInterval(70)

    def values():
        return {key:field.value() for key,field in fields.items()}

    def preview():
        canvas=editor.canvas
        canvas.delete('rapid_preview39')
        shared=fields['rapid_taxi_stub'].value()>0
        fields['reverse_exit_radius'].setEnabled(not shared)
        fields['reverse_rapid_exact_straight'].setEnabled(not shared)
        try:
            forward,reverse=plans(editor.scene,model,values())
            if reverse is None and values().get('reverse_rapid_exact_straight') and not shared:
                raise ValueError('无法拟合指定长度的反向直线段。')
            from pavement_geometry import offset
            paths=[(layout_path(forward),'#168ad1')]
            if reverse:paths.append((reverse['points'],'#e25969'))
            for points,color in paths:
                for line in (points,offset(points,model['width']/2),offset(points,-model['width']/2)):
                    canvas.create_line(*[v for q in line for v in editor.screen(q)],
                                       fill=color,width=2,tags='rapid_preview39')
            reverse_text=f'{reverse["layout"]["straight"]:.1f} m' if reverse else '当前几何无可用反向汇入'
            message.setText(f'实际直线段：正向 {forward["straight"]:.1f} m，反向 {reverse_text}')
            apply_button.setEnabled(True)
        except ValueError as error:
            message.setText(str(error))
            apply_button.setEnabled(False)

    def commit():
        try:apply(editor.scene,oid,values())
        except ValueError as error:message.setText(str(error));return
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
