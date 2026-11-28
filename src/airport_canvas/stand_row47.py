"""Place a row of attached stands with a lightweight mouse preview."""
import scene_geometry as g
import model20
from interface_language import tr

def edit_stop_rows(parent, initial):
    from PySide6.QtWidgets import (QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,
                                  QHBoxLayout,QHeaderView,QLabel,QPushButton,QTableWidget,QVBoxLayout)
    dialog=QDialog(parent)
    dialog.setWindowTitle('机型停止线编辑器')
    dialog.resize(460,310)
    layout=QVBoxLayout(dialog)
    table=QTableWidget(0,2)
    table.setHorizontalHeaderLabels([tr('机型'),tr('偏移（米）')])
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
                error.setText(tr('第 {row} 行须填写机型，且偏移不能与其他行重复。').format(row=index+1))
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
        self.preview_event=None
        self.extent=None
        self.remote=False
        self.head_to_head=False
        self.work_zones={}
        self.exit_rows=None
        self.preset_placements={}
        self.preset_instance_nodes={}
        self.preset_instance_zone_styles={}
        self.presets=[]
        self.overlap_style='hatch'

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
        aircraft=QPushButton()
        def edit_stops():
            updated=edit_stop_rows(dialog,self.stop_rows)
            if updated is not None:
                stops_by_kind[kinds[stand_kind.currentIndex()]]=updated
                self.stop_rows=updated
                aircraft.setText(tr('编辑停止线…（{count} 条）').format(count=len(updated)))
        aircraft.clicked.connect(edit_stops)
        span=QDoubleSpinBox();span.setRange(5,110);restore_number(span,'span',36.);span.setSuffix(' m')
        size=QDoubleSpinBox();size.setRange(8,120);restore_number(size,'length',40.);size.setSuffix(' m')
        stand_kind=QComboBox();stand_kind.addItems([tr(label) for label in ('廊桥机位','远机位','通航机场机位','直升机坪','头对头双排通航机位')])
        form.addRow('机位类型',stand_kind)
        from stand13 import WORK_ZONES59
        zones={}
        stored_zones=saved.get('work_zones')
        if not isinstance(stored_zones,dict):stored_zones={}
        for key,label in [('work_zone','作业区类型'),('work_zone_left','左侧作业区类型'),('work_zone_right','右侧作业区类型')]:
            field=QComboBox()
            for zone in WORK_ZONES59:field.addItem(tr(zone),zone)
            form.addRow(label,field)
            index=field.findData(stored_zones.get(key))
            if index>=0:field.setCurrentIndex(index)
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
            aircraft.setText(tr('编辑停止线…（{count} 条）').format(count=len(self.stop_rows)))
            for field in ga_controls.values():form.setRowVisible(field,index in (2,4))
            form.setRowVisible(gap,index==4)
            for key,(field,label) in zones.items():
                visible=index in (0,1) and (key=='work_zone')==(index==0)
                field.setVisible(visible);label.setVisible(visible)
        stand_kind.currentIndexChanged.connect(show_zones)
        kind=saved.get('kind')
        stand_kind.setCurrentIndex(kinds.index(kind) if kind in kinds else 0)
        show_zones(stand_kind.currentIndex())
        single_number=QComboBox();single_number.addItems([tr('默认机位编号'),tr('引入线中线单编号')])
        single_number.setCurrentIndex(int(bool(saved.get('single_lead_number',False))))
        form.addRow(tr('机位编号标识'),single_number)
        directions={}
        for key,label in (('lead_direction','引入线方向'),('exit_direction','引出线方向')):
            field=QComboBox()
            for code,caption in (('BOTH','两侧'),('LEFT','左侧'),('RIGHT','右侧')):
                field.addItem(tr(caption),code)
            field.setCurrentIndex(max(0,field.findData(saved.get(key,'BOTH'))))
            form.addRow(tr(label),field)
            directions[key]=field
        lead=QComboBox();lead.addItems(['A','B','C','D','ICAO'])
        restore_choice(lead,saved.get('lead'))
        for label,control in (('数量',count),('起始机位号',first),('停止线机型',aircraft),
                              ('翼展',span),('机身长度',size),('引入线类型',lead)):
            form.addRow(label,control)
        def update_dimension(index):
            form.labelForField(count).setText(tr("每排数量" if index==4 else "数量"))
            form.labelForField(span).setText(tr('机位直径' if index==3 else '翼展'))
        stand_kind.currentIndexChanged.connect(update_dimension)
        update_dimension(stand_kind.currentIndex())
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        from stand_presets import caption,read_arrangement,validate_multi
        from PySide6.QtWidgets import QFileDialog
        imported=None
        def import_plan():
            nonlocal imported
            filename,_=QFileDialog.getOpenFileName(dialog,caption('导入机位组合','Import stand arrangement'),
                                                   '', 'Stand arrangements (*.acprsq *.acpasq)')
            if not filename:return
            try:imported=read_arrangement(filename)
            except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
                QMessageBox.warning(dialog,dialog.windowTitle(),str(exc))
                return
            dialog.accept()
        buttons.addButton(caption('导入方案','Import arrangement'),QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(import_plan)
        arrangements=app.scene.data['meta'].get('stand_arrangements',{})
        saved_plan=QComboBox()
        saved_plan.addItem(caption('按参数绘制','Use drawing parameters'),None)
        for name in sorted(arrangements):saved_plan.addItem(name,name)
        form.addRow(caption('工程内批量绘制方案','Arrangement saved in project'),saved_plan)
        if not dialog.exec():return
        name=saved_plan.currentData()
        if imported is None and name is not None:
            try:imported=validate_multi(arrangements[name])
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                QMessageBox.warning(app.q,dialog.windowTitle(),str(exc))
                return
        if imported:
            self.start_preset([entry['stand'] for entry in imported['entries']],imported['count'],
                              imported['first'],imported['overlap'],imported['placements'],imported['instance_nodes'],imported['instance_zone_styles'])
            return
        values=dict(kind=kinds[stand_kind.currentIndex()],count=count.value(),first=first.value(),
                    span=span.value(),length=size.value(),lead=lead.currentText(),opposed_gap=gap.value(),
                    stops=stops_by_kind,single_lead_number=bool(single_number.currentIndex()),
                    work_zones={key:field.currentData() for key,(field,_) in zones.items()},
                    ga={key:field.text() for key,field in ga_controls.items()})
        values.update({key:field.currentData() for key,field in directions.items()})
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
        self.work_zones={key:field.currentData() for key,(field,_) in zones.items()
                         if not self.helicopter and self.ga is None and (key!='work_zone')==self.remote}
        self.work_zones['single_lead_number']=values['single_lead_number']
        self.work_zones.update({key:values[key] for key in directions})
        self.options=(count.value(),first.value(),self.stop_rows,span.value(),size.value(),lead.currentText())
        app._stand_row=self
        app.status.set('批量绘制机位：选择滑行道中线上的起点。')

    def start_preset(self,presets,count,first,overlap,placements=None,instance_nodes=None,instance_zone_styles=None):
        self.preset_instance_zone_styles=instance_zone_styles or {}
        self.preset_instance_nodes=instance_nodes or {}
        self.preset_placements=placements or {}
        self.presets=presets
        self.overlap_style=overlap
        self.ga=None
        self.helicopter=False
        self.work_zones={}
        self.options=(count,first,[],1.,1.,'A')
        self.app.set_mode('SELECT')
        self.app._stand_row=self
        self.app.status.set('Select the start of the stand row on a taxiway.')

    def point(self,event):
        return self.app.world(event.x,event.y)

    def hit(self,event):
        app=self.app
        axes={oid:axis for oid,axis in model20.axes(app.scene).items()
              if axis['kind'] in model20.TAXIS and app.can_edit_object(oid) and (self.anchor is None or oid==self.anchor[1])}
        from guidance20 import snap_axis
        return snap_axis(app.scene,self.point(event),axes,9/max(.001,app.zoom))

    def layout(self,point,perpendicular=False):
        if self.extent is None:return []
        app=self.app
        axis=model20.axis(app.scene,self.anchor[1])['points']
        path=g.PathIndex(axis)
        start,end=self.anchor[2],self.extent[2]
        center,tangent=path.at((start+end)/2)
        normal=(-tangent[1],tangent[0])
        delta=[point[k]-center[k] for k in (0,1)]
        across=sum(delta[k]*normal[k] for k in (0,1))
        sign=1 if across>=0 else -1
        length=min(500.,abs(across) if perpendicular else g.distance(center,point))
        heading=g.unit(center,point) if length else normal
        count=self.options[0]
        rows=[]
        for i in range(count):
            station=(start+end)/2 if count==1 else start+(end-start)*i/(count-1)
            along,depth,*lateral=self.preset_placements.get(str(i),(0,0))
            direction=1 if end>=start else -1
            station=max(0,min(g.length(axis),station+direction*along))
            q,u=path.at(station)
            pose=self.presets[i%len(self.presets)].get('preset_pose',[0,0]) if self.presets else (0,0)
            reach=max(15 if self.presets else 0,length+depth+pose[0])
            shift=direction*(sum(lateral)+pose[1])
            forward=(-sign*u[1],sign*u[0]) if perpendicular else heading
            lateral_axis=u if perpendicular else (sign*heading[1],-sign*heading[0])
            rows.append((station,q,[q[k]+forward[k]*reach+lateral_axis[k]*shift for k in (0,1)]))
        return rows

    def opposed_layout(self,point,perpendicular=False):
        from geometry11 import LineString,Point
        from shapely.ops import nearest_points
        from stand15 import remote_exit_hit
        app=self.app
        hit=remote_exit_hit(app.scene,point,9/max(.001,app.zoom),visible=app.can_edit_object)
        if not hit or hit[1]==self.anchor[1]:return None,[],[]
        target=LineString(model20.axis(app.scene,hit[1])['points'])
        near,far=[],[]
        separation=self.options[4]+self.opposed_gap
        for station,start,guide in self.layout(hit[3],perpendicular):
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
        from shapely.ops import nearest_points
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
                point=nearest_points(Point(end),contact)[1]
                candidates.append((point.distance(Point(end)),oid,path.project(point),list(point.coords[0])))
            if not candidates and target is not None:
                # A skewed approach can miss the finite exit centreline. Find
                # the nearest point on the reachable portion in front of the stand.
                coordinates=list(target.coords)
                def forward(point):
                    return sum((point[k]-end[k])*heading[k] for k in (0,1))-.5
                for left,right in zip(coordinates,coordinates[1:]):
                    a,b=forward(left),forward(right)
                    if max(a,b)<0:continue
                    if min(a,b)<0:
                        t=a/(a-b)
                        crossing=tuple(left[k]+t*(right[k]-left[k]) for k in (0,1))
                        if a<0:left=crossing
                        else:right=crossing
                    point=nearest_points(Point(end),LineString([left,right]))[1] if left!=right else Point(left)
                    candidates.append((point.distance(Point(end)),hit[1],target.project(point),list(point.coords[0])))
            bindings.append(remote_stand_props(min(candidates)) if candidates else None)
        return bindings

    def click(self,event):
        app=self.app
        if self.extent is None:
            hit=self.hit(event)
            if hit:
                if self.anchor is None:
                    self.anchor=hit
                    if self.options[0]==1 and not self.head_to_head:
                        self.extent=hit
                        app.status.set(tr('移动鼠标设定整排引入方向，按住 Shift 垂直绘制，单击确认。'))
                        return 'break'
                    app.status.set('批量绘制机位：在同一条滑行道上选择终点。')
                elif abs(hit[2]-self.anchor[2])>=1:
                    self.extent=hit
                    if self.head_to_head:
                        app.status.set('请选择对侧滑行道中线，单击生成头对头双排机位。')
                        return 'break'
                    app.status.set('移动鼠标设定整排引入方向，按住 Shift 垂直绘制，单击确认。')
            return 'break'
        from stand15 import remote_exit_hit
        bindings=None
        if self.exit_rows is not None:
            hit=remote_exit_hit(app.scene,self.point(event),9/max(.001,app.zoom),visible=app.can_edit_object)
            if not hit:
                app.status.set('请点击出口滑行道中线。')
                return 'break'
            bindings=self.exit_bindings(hit)
            if not bindings or any(binding is None for binding in bindings):
                app.status.set(tr('部分机位前方没有可连接的滑行道中线。请另选出口，或右键返回调整停止点。'))
                return 'break'
        opposite_hit=None
        if self.head_to_head:
            opposite_hit,near,far=self.opposed_layout(self.point(event),bool(event.state&1))
            if not near:
                app.status.set('请在对侧选择一条覆盖整排且间距足够的滑行道中线。')
                return 'break'
            rows=near+far
        else:
            rows=self.exit_rows if bindings is not None else self.layout(self.point(event),bool(event.state&1))
        if not rows or any(g.distance(q,end)<15 for _,q,end in rows):
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
                    created=[]
                    for index,(station,q,end) in enumerate(rows,first):
                        template=self.presets[(index-first)%len(self.presets)] if self.presets else {}
                        row_span=template.get('aircraft_span',span)
                        row_size=template.get('aircraft_length',size)
                        row_stops=template.get('stops',stops)
                        row_lead=template.get('lead_type',lead)
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
                        props.update(self.work_zones)
                        props.update({k:v for k,v in template.items()
                                      if k not in ('aircraft_span','aircraft_length','stops','lead_type')})
                        if str(index-first) in self.preset_instance_nodes:
                            props['preset_nodes']={**props.get('preset_nodes',{}),
                                                   **self.preset_instance_nodes[str(index-first)]}
                        if str(index-first) in self.preset_instance_zone_styles:
                            props['preset_zone_overrides']={**props.get('preset_zone_overrides',{}),
                                                            **self.preset_instance_zone_styles[str(index-first)]}
                        sid=app.scene.create_asset('STAND',name,[q,end],width=row_span,maxspan=row_span,
                            aircraft_span=row_span,aircraft_length=row_size,stops=[dict(stop) for stop in row_stops],lead_type=row_lead,
                            stand_number=name,outward=True,entry_asset=entry_id,entry_station=station,entry_attached=True,**props)
                        if parent:app.scene.reparent(sid,parent)
                        created.append(sid)
                    if self.overlap_style!='hatch':
                        from itertools import combinations
                        from stand_overlap9 import pair_key
                        meta=app.scene.data['meta']
                        record='dashed_stand_overlaps' if self.overlap_style=='dashed' else 'merged_stand_overlaps'
                        pairs=meta.setdefault(record,{})
                        for left,right in combinations(created,2):
                            pairs[pair_key(left,right)]=True
                self.stop()
                app.refresh()
                app.status.set(tr('已绘制 {count} 个绑定机位。').format(count=len(rows)))
        except ValueError as exc:
            app.status.set(str(exc))
        return 'break'

    def preview(self,event):
        self.preview_event=event
        app=self.app
        canvas=app.canvas
        canvas.delete('stand_row_preview')
        if self.extent:
            from stand15 import draw_exit_snap, remote_exit_hit, remote_exit_lines
            point=self.point(event)
            hit=remote_exit_hit(app.scene,point,9/max(.001,app.zoom),visible=app.can_edit_object) if self.exit_rows else None
            if self.head_to_head:
                hit,near,far=self.opposed_layout(point,bool(event.state&1))
                rows=near+far
            else:
                rows=self.exit_rows if self.exit_rows is not None else self.layout(point,bool(event.state&1))
            bindings=self.exit_bindings(hit) if self.exit_rows is not None else []
            for index,(_,q,end) in enumerate(rows):
                template=self.presets[index%len(self.presets)] if self.presets else {}
                preview_stops=template.get('stops',self.options[2])
                if index<len(bindings) and bindings[index]:
                    sample=dict(points=[q,end],props={**bindings[index],**self.work_zones,**template})
                    for path in remote_exit_lines(sample,app.scene):
                        canvas.create_line(*[pixel for p in path for pixel in app.screen(p)],
                                           fill='#11a8bd',width=2,tags='stand_row_preview')
                canvas.create_line(*app.screen(q),*app.screen(end),fill='#11a8bd',width=2,tags='stand_row_preview')
                if g.distance(q,end)>.01 and not getattr(self,'helicopter',False):
                    from stand13 import safety
                    props=dict(aircraft_span=self.options[3],aircraft_length=self.options[4],
                               ga_stand=self.ga is not None,remote_stand=self.remote,guidance='GUIDED')
                    props.update(template)
                    props['stops']=preview_stops
                    sample=dict(id=f'preview-stand-{index}',kind='STAND',points=[q,end],props=props)
                    corners=safety(app.scene,sample)
                    outline=corners if props.get('remote_stand') else corners+[corners[0]]
                    canvas.create_line(*[pixel for p in outline for pixel in app.screen(p)],
                                       fill='#ff5959',width=2,tags='stand_row_preview')
                if getattr(self,'helicopter',False):
                    x,y=app.screen(end)
                    radius=self.options[3]*app.zoom/2
                    canvas.create_oval(x-radius,y-radius,x+radius,y+radius,outline='#e7c640',
                                       width=2,tags='stand_row_preview')
                    continue
                ux,uy=g.unit(q,end)
                for stop in preview_stops:
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
