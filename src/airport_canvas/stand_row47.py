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
        model.addItems(['A319','A320','A321','A330','A350','A380','B737','B738','B747','B777','B787','C919'])
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
        self.work_zones={}
        self.exit_rows=None

    def start(self):
        from PySide6.QtWidgets import QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,QFormLayout,QPushButton,QSpinBox
        app=self.app
        dialog=QDialog(app.q)
        dialog.setWindowTitle('批量绘制机位')
        form=QFormLayout(dialog)
        count=QSpinBox();count.setRange(1,150);count.setValue(6)
        first=QSpinBox();first.setRange(1,99999);first.setValue(101)
        from editor6_geometry import stop_rows
        self.stop_rows=stop_rows({'props':{'guidance':'GUIDED'}})
        aircraft=QPushButton('编辑停止线…（1 条）')
        def edit_stops():
            updated=edit_stop_rows(dialog,self.stop_rows)
            if updated is not None:
                self.stop_rows=updated
                aircraft.setText(f'编辑停止线…（{len(updated)} 条）')
        aircraft.clicked.connect(edit_stops)
        span=QDoubleSpinBox();span.setRange(5,110);span.setValue(36);span.setSuffix(' m')
        size=QDoubleSpinBox();size.setRange(8,120);size.setValue(40);size.setSuffix(' m')
        stand_kind=QComboBox();stand_kind.addItems(['廊桥机位','远机位'])
        form.addRow('机位类型',stand_kind)
        from stand13 import WORK_ZONES59
        zones={}
        for key,label in [('work_zone','作业区类型'),('work_zone_left','左侧作业区类型'),('work_zone_right','右侧作业区类型')]:
            field=QComboBox();field.addItems(list(WORK_ZONES59));form.addRow(label,field)
            zones[key]=(field,form.labelForField(field))
        def show_zones(index):
            for key,(field,label) in zones.items():
                visible=(key=='work_zone')==(index==0)
                field.setVisible(visible);label.setVisible(visible)
        stand_kind.currentIndexChanged.connect(show_zones)
        show_zones(0)
        lead=QComboBox();lead.addItems(list('ABCD'))
        for label,control in (('数量',count),('起始机位号',first),('停止线机型',aircraft),
                              ('翼展',span),('机身长度',size),('引入线类型',lead)):
            form.addRow(label,control)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if not dialog.exec():return
        app.set_mode('SELECT')
        self.remote=stand_kind.currentIndex()==1
        self.work_zones={key:field.currentText() for key,(field,_) in zones.items()
                         if (key!='work_zone')==self.remote}
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
                    app.status.set('移动鼠标确定侧向和引入线长度，左键绘制，Esc 取消。')
            return 'break'
        from stand15 import remote_exit_hit,remote_stand_props
        exit_axis=None
        if self.exit_rows is not None:
            hit=remote_exit_hit(app.scene,self.point(event),9/max(.001,app.zoom))
            if not hit:
                app.status.set('请点击出口滑行道中线。')
                return 'break'
            exit_axis=model20.axis(app.scene,hit[1])
        rows=self.exit_rows if exit_axis else self.layout(self.point(event))
        if not rows or g.distance(rows[0][1],rows[0][2])<15:
            app.status.set('引入线长度至少为 15 m。')
            return 'break'
        if self.remote and exit_axis is None:
            self.exit_rows=rows
            app.status.set('已确定各机位停止点。请点击出口滑行道中线。')
            return 'break'
        aid=self.anchor[1]
        _,first,stops,span,size,lead=self.options
        parent=app.scene.assets.get(aid,{}).get('container_id')
        try:
            with app.processing('正在批量绘制机位'):
                with app.scene.transaction('批量绘制机位'):
                    for index,(station,q,end) in enumerate(rows,first):
                        name=str(index)
                        props={'has_bridge':True}
                        if exit_axis:
                            distance,out_station,out_point=g.project(exit_axis['points'],end)
                            heading=g.unit(q,end)
                            if sum((out_point[k]-end[k])*heading[k] for k in (0,1))<=.5:
                                raise ValueError('出口中线应位于所有远机位停止点的前方。')
                            props=remote_stand_props((distance,exit_axis['id'],out_station,out_point))
                        sid=app.scene.create_asset('STAND',name,[q,end],width=span,maxspan=span,
                            aircraft_span=span,aircraft_length=size,stops=[dict(stop) for stop in stops],lead_type=lead,
                            stand_number=name,outward=True,entry_asset=aid,entry_station=station,entry_attached=True,**props,**self.work_zones)
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
            from stand15 import remote_exit_hit, remote_exit_lines, remote_stand_props
            point=self.point(event)
            hit=remote_exit_hit(app.scene,point,9/max(.001,app.zoom)) if self.exit_rows else None
            target=model20.axis(app.scene,hit[1]) if hit else None
            for _,q,end in self.exit_rows if self.exit_rows is not None else self.layout(point):
                if target:
                    distance,station,out=g.project(target['points'],end)
                    sample=dict(points=[q,end],props=remote_stand_props((distance,hit[1],station,out)))
                    for path in remote_exit_lines(sample,app.scene):
                        canvas.create_line(*[pixel for p in path for pixel in app.screen(p)],
                                           fill='#11a8bd',width=2,tags='stand_row_preview')
                canvas.create_line(*app.screen(q),*app.screen(end),fill='#11a8bd',width=2,tags='stand_row_preview')
                ux,uy=g.unit(q,end)
                for stop in self.options[2]:
                    x=end[0]+ux*stop['offset'];y=end[1]+uy*stop['offset']
                    canvas.create_line(*app.screen((x-uy,y+ux)),*app.screen((x+uy,y-ux)),
                                       fill='#11a8bd',width=2,tags='stand_row_preview')
            return
        for hit in (self.anchor,self.hit(event)):
            if hit is None:continue
            x,y=app.screen(hit[3])
            canvas.create_oval(x-4,y-4,x+4,y+4,fill='#11a8bd',outline='',tags='stand_row_preview')

    def stop(self):
        self.app._stand_row=None
        self.app.canvas.delete('stand_row_preview')
