"""Place a row of attached stands with a lightweight mouse preview."""
import scene_geometry as g
import model20

def edit_stop_rows(parent, initial):
    from PySide6.QtWidgets import (QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,
                                  QHBoxLayout,QHeaderView,QLabel,QPushButton,QTableWidget,QVBoxLayout)
    dialog=QDialog(parent)
    dialog.setWindowTitle('机型停止线编辑器')
    dialog.resize(460,310)
    layout=QVBoxLayout(dialog)
    table=QTableWidget(0,2)
    table.setHorizontalHeaderLabels(['机型','偏移（米）'])
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    layout.addWidget(table)
    layout.addWidget(QLabel('偏移以机位停止点为零，负值朝引入点。'))
    controls=QHBoxLayout()
    add=QPushButton('添加停止线')
    remove=QPushButton('删除选中行')
    controls.addWidget(add);controls.addWidget(remove);controls.addStretch()
    layout.addLayout(controls)
    error=QLabel();layout.addWidget(error)
    result=[]

    def append(aircraft='',offset=0.):
        index=table.rowCount()
        table.insertRow(index)
        model=QComboBox()
        model.setEditable(True)
        model.addItems(['C172','A319','A320','A321','A330','A350','A380','B737','B738','B747','B777','B787','C919'])
        model.setEditText(aircraft)
        table.setCellWidget(index,0,model)
        distance=QDoubleSpinBox()
        distance.setRange(-9999,9999)
        distance.setDecimals(3)
        distance.setValue(offset)
        table.setCellWidget(index,1,distance)
        table.setCurrentCell(index,0)
        return model

    def add_row():
        offsets=[table.cellWidget(i,1).value() for i in range(table.rowCount())]
        append(offset=min(offsets)-3 if offsets else 0).setFocus()

    def accept():
        rows=[]
        for index in range(table.rowCount()):
            aircraft=table.cellWidget(index,0).currentText().strip().upper()
            offset=table.cellWidget(index,1).value()
            if not aircraft or any(abs(row['offset']-offset)<.001 for row in rows):
                error.setText(f'第 {index+1} 行须填写机型，且偏移不能与其他行重复。')
                table.setCurrentCell(index,0)
                return
            number=str(index+1)
            rows.append(dict(id=number,name=number,aircraft=aircraft,offset=offset,lateral=0.,
                             rotation=0.,shape='T',length=2.,width=.15,visible=True))
        if not rows:
            error.setText('请至少添加一条停止线。')
            return
        result.extend(rows)
        dialog.accept()

    for row in initial:append(row['aircraft'],row['offset'])
    add.clicked.connect(add_row)
    remove.clicked.connect(lambda:table.removeRow(table.currentRow()) if table.currentRow()>=0 else None)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    return result if dialog.exec() else None


class StandRow:
    def __init__(self,editor):
        self.app=editor
        self.anchor=None
        self.extent=None
        self.remote=False
        self.head_to_head=False
        self.work_zones={}
        self.exit_rows=None

    def start(self):
        from PySide6.QtWidgets import QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,QFormLayout,QLineEdit,QMessageBox,QPushButton,QSpinBox
        app=self.app
        from user_settings34 import batch_stand_preferences,save_batch_stand_preferences
        saved=batch_stand_preferences(app._preferences34)

        def restore_number(widget,key,default):
            value=saved.get(key)
            widget.setValue(value if type(value) is type(default) else default)

        def restore_choice(widget,text):
            index=widget.findText(text) if isinstance(text,str) else -1
            if index>=0:widget.setCurrentIndex(index)

        dialog=QDialog(app.q)
        dialog.setWindowTitle('批量绘制机位')
        form=QFormLayout(dialog)
        count=QSpinBox();count.setRange(1,150);restore_number(count,'count',6)
        first=QSpinBox();first.setRange(1,99999);restore_number(first,'first',101)
        from editor6_geometry import stop_rows
        kinds=('bridge','remote','ga','helicopter','ga_opposed')
        stored_stops=saved.get('stops')
        if not isinstance(stored_stops,dict):stored_stops={}
        stops_by_kind={}
        for kind in kinds:
            rows=stored_stops.get(kind)
            if not isinstance(rows,list) or not all(
                    isinstance(row,dict) and isinstance(row.get('id'),str) for row in rows):
                rows=stop_rows({'props':{'guidance':'GUIDED','ga_stand':kind in ('ga','ga_opposed')}})
            stops_by_kind[kind]=rows
        self.stop_rows=stops_by_kind['bridge']
        aircraft=QPushButton('编辑停止线…（1 条）')
        def edit_stops():
            updated=edit_stop_rows(dialog,self.stop_rows)
            if updated is not None:
                stops_by_kind[kinds[stand_kind.currentIndex()]]=updated
                self.stop_rows=updated
                aircraft.setText(f'编辑停止线…（{len(updated)} 条）')
        aircraft.clicked.connect(edit_stops)
        span=QDoubleSpinBox();span.setRange(5,110);restore_number(span,'span',36.);span.setSuffix(' m')
        size=QDoubleSpinBox();size.setRange(8,120);restore_number(size,'length',40.);size.setSuffix(' m')
        stand_kind=QComboBox();stand_kind.addItems(['廊桥机位','远机位','通航机场机位','直升机坪','头对头双排通航机位'])
        form.addRow('机位类型',stand_kind)
        from stand13 import WORK_ZONES59
        zones={}
        stored_zones=saved.get('work_zones')
        if not isinstance(stored_zones,dict):stored_zones={}
        for key,label in [('work_zone','作业区类型'),('work_zone_left','左侧作业区类型'),('work_zone_right','右侧作业区类型')]:
            field=QComboBox();field.addItems(list(WORK_ZONES59));form.addRow(label,field)
            restore_choice(field,stored_zones.get(key))
            zones[key]=(field,form.labelForField(field))
        from stand13 import GA_FIELDS
        ga_controls={}
        stored_ga=saved.get('ga')
        if not isinstance(stored_ga,dict):stored_ga={}
        for key,(label,default) in GA_FIELDS.items():
            value=stored_ga.get(key)
            field=QLineEdit(value if isinstance(value,str) else default)
            form.addRow(label,field)
            ga_controls[key]=field
        gap=QDoubleSpinBox()
        gap.setRange(0.,100.)
        gap.setSuffix(' m')
        restore_number(gap,'opposed_gap',2.)
        form.addRow('两排框间净距',gap)
        def show_zones(index):
            self.stop_rows=stops_by_kind[kinds[index]]
            aircraft.setText(f'编辑停止线（{len(self.stop_rows)} 条）')
            for field in ga_controls.values():form.setRowVisible(field,index in (2,4))
            form.setRowVisible(gap,index==4)
            for key,(field,label) in zones.items():
                visible=index in (0,1) and (key=='work_zone')==(index==0)
                field.setVisible(visible);label.setVisible(visible)
        stand_kind.currentIndexChanged.connect(show_zones)
        kind=saved.get('kind')
        stand_kind.setCurrentIndex(kinds.index(kind) if kind in kinds else 0)
        show_zones(stand_kind.currentIndex())
        lead=QComboBox();lead.addItems(list('ABCD'))
        restore_choice(lead,saved.get('lead'))
        for label,control in (('数量',count),('起始机位号',first),('停止线机型',aircraft),
                              ('翼展',span),('机身长度',size),('引入线类型',lead)):
            form.addRow(label,control)
        def update_dimension(index):
            form.labelForField(count).setText("每排数量" if index==4 else "数量")
            form.labelForField(span).setText('机位直径' if index==3 else '翼展')
        stand_kind.currentIndexChanged.connect(update_dimension)
        update_dimension(stand_kind.currentIndex())
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if not dialog.exec():return
        values=dict(kind=kinds[stand_kind.currentIndex()],count=count.value(),first=first.value(),
                    span=span.value(),length=size.value(),lead=lead.currentText(),opposed_gap=gap.value(),
                    stops=stops_by_kind,
                    work_zones={key:field.currentText() for key,(field,_) in zones.items()},
                    ga={key:field.text() for key,field in ga_controls.items()})
        try:
            save_batch_stand_preferences(app._preferences34,values)
        except OSError as exc:
            QMessageBox.warning(app.q,'批量绘制机位',str(exc))
        app.set_mode('SELECT')
        self.head_to_head=stand_kind.currentIndex()==4
        self.opposed_gap=gap.value()
        self.helicopter=stand_kind.currentIndex()==3
        self.remote=stand_kind.currentIndex() in (1,2)
        self.ga={key:field.text() for key,field in ga_controls.items()} if stand_kind.currentIndex() in (2,4) else None
        self.work_zones={key:field.currentText() for key,(field,_) in zones.items()
                         if not self.helicopter and self.ga is None and (key!='work_zone')==self.remote}
        self.options=(count.value(),first.value(),self.stop_rows,span.value(),size.value(),lead.currentText())
        app._stand_row=self
        app.status.set('批量绘制机位：选择滑行道中线上的起点。')

    def point(self,event):
        return self.app.world(event.x,event.y)

    def hit(self,event):
        app=self.app
        axes={oid:axis for oid,axis in model20.axes(app.scene).items()
              if axis['kind'] in model20.TAXIS and (self.anchor is None or oid==self.anchor[1])}
        from guidance20 import snap_axis
        return snap_axis(app.scene,self.point(event),axes,9/max(.001,app.zoom))

    def layout(self,point):
        if self.extent is None:return []
        app=self.app
        axis=model20.axis(app.scene,self.anchor[1])['points']
        path=g.PathIndex(axis)
        start,end=self.anchor[2],self.extent[2]
        center,tangent=path.at((start+end)/2)
        normal=(-tangent[1],tangent[0])
        direction=sum((point[k]-center[k])*normal[k] for k in (0,1))
        length=min(500.,abs(direction))
        sign=1 if direction>=0 else -1
        count=self.options[0]
        rows=[]
        for i in range(count):
            station=(start+end)/2 if count==1 else start+(end-start)*i/(count-1)
            q,u=path.at(station)
            rows.append((station,q,[q[0]-sign*u[1]*length,q[1]+sign*u[0]*length]))
        return rows

    def opposed_layout(self,point):
        from geometry11 import LineString,Point
        from shapely.ops import nearest_points
        from stand15 import remote_exit_hit
        app=self.app
        hit=remote_exit_hit(app.scene,point,9/max(.001,app.zoom))
        if not hit or hit[1]==self.anchor[1]:return None,[],[]
        target=LineString(model20.axis(app.scene,hit[1])['points'])
        near,far=[],[]
        separation=self.options[4]+self.opposed_gap
        for station,start,guide in self.layout(hit[3]):
            if g.distance(start,guide)<.01:return hit,[],[]
            heading=g.unit(start,guide)
            ray=LineString([start,[start[k]+heading[k]*1000 for k in (0,1)]])
            contact=ray.intersection(target)
            if contact.is_empty:return hit,[],[]
            opposite=nearest_points(Point(start),contact)[1]
            approach=(opposite.distance(Point(start))-separation)/2
            if approach<max(15.,self.options[4]/2):return hit,[],[]
            opposite_point=list(opposite.coords[0])
            near.append((station,start,[start[k]+heading[k]*approach for k in (0,1)]))
            far.append((target.project(opposite),opposite_point,
                        [opposite_point[k]-heading[k]*approach for k in (0,1)]))
        return hit,near,far

    def exit_bindings(self,hit):
        from geometry11 import LineString,Point
        from stand15 import remote_stand_props
        scene=self.app.scene
        routes={oid:LineString(axis['points']) for oid,axis in model20.axes(scene).items()
                if axis['kind'] in model20.TAXIS and oid!=self.anchor[1]}
        if not routes:return []
        target=routes.get(hit[1]) if hit else None
        bindings=[]
        for _,start,end in self.exit_rows:
            heading=g.unit(start,end)
            # Intersect each stand's forward ray rather than projecting the
            # whole row onto the centreline under the mouse.
            reach=max(100.,2*g.distance(end,hit[3])) if hit else 100.
            ray=LineString([[end[k]+heading[k]*distance for k in (0,1)] for distance in (.5,reach)])
            candidates=[]
            for oid,path in routes.items():
                contact=ray.intersection(path)
                if contact.is_empty:continue
                from shapely.ops import nearest_points
                point=nearest_points(Point(end),contact)[1]
                candidates.append((point.distance(Point(end)),oid,path.project(point),list(point.coords[0])))
            if not candidates and target is not None:
                station=target.project(Point(end))
                point=list(target.interpolate(station).coords[0])
                if sum((point[k]-end[k])*heading[k] for k in (0,1))>.5:
                    candidates.append((g.distance(end,point),hit[1],station,point))
            bindings.append(remote_stand_props(min(candidates)) if candidates else None)
        return bindings

    def click(self,event):
        app=self.app
        if self.extent is None:
            hit=self.hit(event)
            if hit:
                if self.anchor is None:
                    self.anchor=hit
                    app.status.set('批量绘制机位：在同一条滑行道上选择终点。')
                elif abs(hit[2]-self.anchor[2])>=1:
                    self.extent=hit
                    if self.head_to_head:
                        app.status.set('请选择对侧滑行道中线，单击生成头对头双排机位。')
                        return 'break'
                    app.status.set('移动鼠标确定侧向和引入线长度，左键绘制，Esc 取消。')
            return 'break'
        from stand15 import remote_exit_hit
        bindings=None
        if self.exit_rows is not None:
            hit=remote_exit_hit(app.scene,self.point(event),9/max(.001,app.zoom))
            if not hit:
                app.status.set('请点击出口滑行道中线。')
                return 'break'
            bindings=self.exit_bindings(hit)
            if not bindings or any(binding is None for binding in bindings):
                app.status.set('部分机位前方没有可连接的滑行道中线。')
                return 'break'
        opposite_hit=None
        if self.head_to_head:
            opposite_hit,near,far=self.opposed_layout(self.point(event))
            if not near:
                app.status.set('请在对侧选择一条覆盖整排且间距足够的滑行道中线。')
                return 'break'
            rows=near+far
        else:
            rows=self.exit_rows if bindings is not None else self.layout(self.point(event))
        if not rows or g.distance(rows[0][1],rows[0][2])<15:
            app.status.set('引入线长度至少为 15 m。')
            return 'break'
        if self.remote and bindings is None:
            self.exit_rows=rows
            app.status.set('已确定各机位停止点。请点击出口滑行道中线。')
            return 'break'
        aid=self.anchor[1]
        _,first,stops,span,size,lead=self.options
        opposite_id=opposite_hit[1] if opposite_hit else None
        try:
            with app.processing('正在批量绘制机位'):
                with app.scene.transaction('批量绘制机位'):
                    for index,(station,q,end) in enumerate(rows,first):
                        name=str(index)
                        props={'has_bridge':True}
                        if bindings is not None:
                            props=bindings[index-first]
                        if self.ga is not None:
                            from stand13 import ga_stand_props
                            props.update(ga_stand_props())
                            props.update(self.ga)
                        if getattr(self,'helicopter',False):
                            from stand13 import helicopter_stand_props
                            props.update(helicopter_stand_props())
                            name='H'+name
                        entry_id=opposite_id if opposite_id and index-first>=len(rows)//2 else aid
                        parent=app.scene.assets.get(entry_id,{}).get('container_id')
                        sid=app.scene.create_asset('STAND',name,[q,end],width=span,maxspan=span,
                            aircraft_span=span,aircraft_length=size,stops=[dict(stop) for stop in stops],lead_type=lead,
                            stand_number=name,outward=True,entry_asset=entry_id,entry_station=station,entry_attached=True,**props,**self.work_zones)
                        if parent:app.scene.reparent(sid,parent)
                self.stop()
                app.refresh()
                app.status.set(f'已绘制 {len(rows)} 个绑定机位。')
        except ValueError as exc:
            app.status.set(str(exc))
        return 'break'

    def preview(self,event):
        app=self.app
        canvas=app.canvas
        canvas.delete('stand_row_preview')
        if self.extent:
            from stand15 import draw_exit_snap, remote_exit_hit, remote_exit_lines
            point=self.point(event)
            hit=remote_exit_hit(app.scene,point,9/max(.001,app.zoom)) if self.exit_rows else None
            if self.head_to_head:
                hit,near,far=self.opposed_layout(point)
                rows=near+far
            else:
                rows=self.exit_rows if self.exit_rows is not None else self.layout(point)
            bindings=self.exit_bindings(hit) if self.exit_rows is not None else []
            for index,(_,q,end) in enumerate(rows):
                if index<len(bindings) and bindings[index]:
                    sample=dict(points=[q,end],props=bindings[index])
                    for path in remote_exit_lines(sample,app.scene):
                        canvas.create_line(*[pixel for p in path for pixel in app.screen(p)],
                                           fill='#11a8bd',width=2,tags='stand_row_preview')
                canvas.create_line(*app.screen(q),*app.screen(end),fill='#11a8bd',width=2,tags='stand_row_preview')
                if self.ga is not None:
                    from stand13 import safety
                    corners=safety(app.scene,dict(points=[q,end],props=dict(
                        ga_stand=True,aircraft_span=self.options[3],aircraft_length=self.options[4])))
                    canvas.create_line(*[pixel for p in corners+[corners[0]] for pixel in app.screen(p)],
                                       fill='#ff0000',width=2,tags='stand_row_preview')
                if getattr(self,'helicopter',False):
                    x,y=app.screen(end)
                    radius=self.options[3]*app.zoom/2
                    canvas.create_oval(x-radius,y-radius,x+radius,y+radius,outline='#e7c640',
                                       width=2,tags='stand_row_preview')
                    continue
                ux,uy=g.unit(q,end)
                for stop in self.options[2]:
                    x=end[0]+ux*stop['offset'];y=end[1]+uy*stop['offset']
                    canvas.create_line(*app.screen((x-uy,y+ux)),*app.screen((x+uy,y-ux)),
                                       fill='#11a8bd',width=2,tags='stand_row_preview')
            if hit:draw_exit_snap(app,hit,'stand_row_preview')
            return
        for hit in (self.anchor,self.hit(event)):
            if hit is None:continue
            x,y=app.screen(hit[3])
            canvas.create_oval(x-4,y-4,x+4,y+4,fill='#11a8bd',outline='',tags='stand_row_preview')

    def stop(self):
        self.app._stand_row=None
        self.app.canvas.delete('stand_row_preview')
