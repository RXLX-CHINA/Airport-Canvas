"""Qt lighting workspace; the project stores overrides and authored fixtures only."""
from interface_language import tr
import math
import time
from uuid import uuid4
from qt_core21 import C, G, W, Qt
import scene_geometry as geometry
import lighting_model as model


class LightingView(C.QObject):
    def __init__(self, app):
        super().__init__(app.q)
        self.app = app
        self.active = False
        self.tool = None
        self.anchor = None
        self.selected = None
        self.cache_key = None
        self.approach_edit=self.approach_drag=self.approach_selected=None
        self.custom_drag=None
        self.animated_items = {}
        self.animation_timer = C.QTimer(app.q)
        self.animation_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.animation_timer.setInterval(10)
        self.animation_epoch = time.monotonic()
        self.animation_timer.timeout.connect(self.animate)
        self.paused_at = None
        self.resume_timer = C.QTimer(self)
        self.resume_timer.setSingleShot(True)
        self.resume_timer.setInterval(400)
        self.resume_timer.timeout.connect(self.resume_animation)
        right = app.property_title.q.parentWidget()
        self.inspector = W.QScrollArea(right)
        self.inspector.setWidgetResizable(True)
        right.layout().addWidget(self.inspector,1)
        self.inspector.hide()
        self.tabs = app.tool_canvas.q.parentWidget()
        while not isinstance(self.tabs, W.QTabWidget):
            self.tabs = self.tabs.parentWidget()
        self.original_tabs = [self.tabs.widget(i) for i in range(self.tabs.count())]
        self.palette = W.QWidget()
        layout = W.QVBoxLayout(self.palette)
        for key, label in [(None, '选择灯光'), *[(key, item[0]) for key, item in model.CUSTOM.items()]]:
            button = W.QPushButton(label)
            button.clicked.connect(lambda checked=False, key=key: self.choose(key))
            layout.addWidget(button)
        self.animation_switch = W.QCheckBox('灯光动画')
        self.animation_switch.toggled.connect(self.set_animation)
        layout.addWidget(self.animation_switch)
        self.animation_action = app.display_menu14.q.addAction('助航灯光动画')
        self.animation_action.setCheckable(True)
        self.animation_action.setChecked(app.scene.data['meta'].get('lighting_f7',{}).get('animate',True))
        self.animation_action.toggled.connect(self.set_animation)
        self.traffic_action = app.display_menu14.q.addAction('灯光方案 · 高交通密度')
        self.traffic_action.setCheckable(True)
        self.traffic_action.toggled.connect(self.set_high_traffic)
        layout.addStretch()
        self.tree = W.QTreeWidget()
        self.tree.setHeaderLabels(['灯光对象'])
        self.tree.setAlternatingRowColors(True)
        self.tree.currentItemChanged.connect(self.tree_selection)
        self.palette_index = self.tabs.addTab(self.palette, '灯光工具')
        self.tree_index = self.tabs.addTab(self.tree, '灯光对象')
        self.tabs.setTabVisible(self.palette_index, False)
        self.tabs.setTabVisible(self.tree_index, False)
        self.action = app.display_menu14.q.addAction('助航灯光 · F7', self.toggle)
        self.action.setCheckable(True)
        app.bind('<F7>', lambda event: self.toggle())

    def toggle(self):
        if self.active:
            self.leave()
        else:
            self.app.prepare_display_mode()
            self.active = True
            W.QApplication.instance().installEventFilter(self)
            parent = self.inspector.parentWidget()
            self.hidden_inspector_widgets = [widget for widget in parent.findChildren(
                W.QWidget,options=Qt.FindChildOption.FindDirectChildrenOnly)
                if widget is not self.inspector and not widget.isHidden()]
            for widget in self.hidden_inspector_widgets:
                widget.hide()
            self.inspector.show()
            self.action.setChecked(True)
            self.tabs.setTabVisible(self.palette_index, True)
            self.tabs.setTabVisible(self.tree_index, True)
            self.normal_tab = self.tabs.currentWidget()
            self.tabs.setCurrentWidget(self.palette)
            self.sync()
            self.show_properties()
            self.app.status.set('点选灯光后在右侧编辑属性，按 F7 返回')
            self.app.canvas.focus_set()
            self.app.redraw()
        return 'break'

    def leave(self, redraw=True):
        if not self.active:
            return
        self.active = False
        W.QApplication.instance().removeEventFilter(self)
        self.inspector.hide()
        for widget in self.hidden_inspector_widgets:
            widget.show()
        self.resume_timer.stop()
        self.paused_at = None
        self.animation_timer.stop()
        self.animated_items.clear()
        self.action.setChecked(False)
        self.tool = self.anchor = None
        self.stop_approach()
        for tab in self.original_tabs:
            self.tabs.setTabVisible(self.tabs.indexOf(tab), True)
        if self.normal_tab in self.original_tabs:
            self.tabs.setCurrentWidget(self.normal_tab)
        self.tabs.setTabVisible(self.palette_index, False)
        self.tabs.setTabVisible(self.tree_index, False)
        canvas = self.app.canvas
        canvas.delete('lighting_f7')
        canvas.itemconfigure('map', state='normal')
        canvas.q.setBackgroundBrush(G.QColor('#131d27' if self.app.dark_mode_enabled() else '#e9eef2'))
        if redraw:
            self.app.redraw()

    def choose(self, key):
        self.app.set_mode('SELECT')
        self.tool, self.anchor = key, None
        self.pause_animation()
        self.app.canvas.focus_set()
        self.app.status.set('单击画布放置灯具' if key == 'point' else '单击两点布置灯列；滑行道中线灯可沿同一条滑行道绘制' if key else '点选灯组后在右侧编辑属性')
        self.app.redraw()

    def sync(self):
        scene = self.app.scene
        key = (id(scene), id(scene.data), scene.revision)
        if self.cache_key == key:
            return
        if self.approach_edit and self.cache_key and self.cache_key[0]!=id(scene):self.stop_approach()
        self.cache_key = key
        from lighting_closures import lighting_closures
        self.closures = lighting_closures(scene)
        self.rows = {row[0]: row for row in model.rows(scene,self.app.auto_assets,self.closures)}
        with C.QSignalBlocker(self.traffic_action):
            self.traffic_action.setChecked(scene.data['meta'].get('lighting_f7',{}).get('high_traffic',False))
        enabled = scene.data['meta'].get('lighting_f7',{}).get('animate',True)
        for control in (self.animation_switch,self.animation_action):
            with C.QSignalBlocker(control):
                control.setChecked(enabled)
        styles=scene.data['meta'].get('object_display',{})
        def visible(row):
            owner=row[2]['id'] if row[2] is not None else row[0]
            style=styles.get(owner,{})
            return row[-1].get('enabled',True) and not style.get('hidden') and style.get('opacity')!=0
        self.lamps = {key: list(model.fixtures(row)) for key, row in self.rows.items() if visible(row)}
        self.visible_owners={self.rows[key][2]['id'] for key,lamps in self.lamps.items()
                             if lamps and self.rows[key][2] is not None}
        self.cache_base_geometry()
        self.tree_items = {}
        if self.selected not in self.rows:
            self.selected = None
        with C.QSignalBlocker(self.tree):
            self.tree.clear()
            for key, row in self.rows.items():
                enabled = row[-1].get('enabled', True)
                suffix = '（关闭）' if row[-1].get('closed') else '' if enabled else '（停用）'
                item = W.QTreeWidgetItem(self.tree,[row[1]+suffix])
                item.setData(0, Qt.ItemDataRole.UserRole, key)
                self.tree_items[key] = item
            self.tree.setCurrentItem(self.tree_items.get(self.selected))

    def tree_selection(self, item, previous):
        self.select(item.data(0,Qt.ItemDataRole.UserRole) if item else None)

    def select(self, key):
        if key != self.selected:
            self.stop_approach()
            self.selected = key
            if self.app.mode=='NODES':self.approach_edit=key
            with C.QSignalBlocker(self.tree):
                self.tree.setCurrentItem(self.tree_items.get(key))
            self.show_properties()
        self.pause_animation()
        self.app.redraw()

    def show_properties(self):
        key = self.selected
        if self.paused_at is not None:
            self.resume_timer.start()
        panel = W.QWidget()
        form = W.QFormLayout(panel)
        form.setFieldGrowthPolicy(W.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(W.QFormLayout.RowWrapPolicy.WrapLongRows)
        self.inspector.setWidget(panel)
        title = W.QLabel('灯光属性')
        title.setStyleSheet('font-weight:700;font-size:15px')
        form.addRow(title)
        if key not in self.rows:
            form.addRow(W.QLabel('在画布或灯光对象列表中选择灯组。'))
            return
        _, label, runway, kind, _, options = self.rows[key]
        name = W.QLabel(label)
        name.setWordWrap(True)
        form.addRow(name)
        if options.get('closed'):
            form.addRow(W.QLabel('关闭状态生效，灯光已熄灭。'))
        fields = {}
        if runway is None:
            fields['name'] = W.QLineEdit(options.get('name', label))
            form.addRow('名称', fields['name'])
        else:
            form.addRow('预设', W.QLabel('保留手动设置'))
            combo = fields['enabled'] = W.QComboBox()
            for label, value in [('随跑道等级', None), ('启用', True), ('停用', False)]:
                combo.addItem(tr(label),value)
            combo.setCurrentIndex(combo.findData(options.get('enabled_override')))
            form.addRow('绘制状态', combo)
        if kind in model.CONFIGURATIONS:
            combo = fields['configuration'] = W.QComboBox()
            choices = model.CONFIGURATIONS[kind]
            for value in options.get('configuration_choices',choices):
                combo.addItem(tr(choices[value]),value)
            combo.setCurrentIndex(combo.findData(options['configuration']))
            form.addRow('灯光构型',combo)
        if kind=='runway_guard':
            stop = W.QCheckBox()
            stop.setChecked(options['stopbar_enabled'])
            stop.setEnabled(options['configuration']=='GUARD_A')
            stop.toggled.connect(lambda enabled:self.set_guard_stopbar(key,enabled))
            form.addRow('同时设置停止排灯',stop)
        if 'facing' in options:
            combo = fields['facing'] = W.QComboBox()
            combo.addItem(tr('按标线方向'),'AUTO')
            combo.addItem(tr('反转'),'REVERSE')
            combo.setCurrentIndex(combo.findData(options['facing']))
            form.addRow('发光朝向',combo)
        if kind in model.FLASHING:
            fields['animate'] = W.QCheckBox()
            fields['animate'].setChecked(options.get('animate',True))
            form.addRow('播放该灯组动画', fields['animate'])
        if 'system' in options:
            combo = fields['system'] = W.QComboBox()
            for value, name in [('SIMPLE_A','简易 A 型'),('SIMPLE_B','简易 B 型'),('CAT1_A','Ⅰ类 A 型'),('CAT1_B','Ⅰ类 B 型'),('CAT23','Ⅱ／Ⅲ类')]:
                combo.addItem(tr(name),value)
            combo.setCurrentIndex(combo.findData(options['system']))
            form.addRow('进近灯光类型', combo)
            form.addRow('长度范围', W.QLabel('简易通常 420 m；精密通常 900 m，受限时至少 720 m'))
        for field, name, minimum, maximum in [('length','总长（m）',1,3000),('spacing','灯间距（m）',.5,150),('curve_spacing','弯道最大灯间距（m）',.5,60),('count','灯具数量（0 为按间距）',0,100)]:
            if field not in options:
                continue
            widget = fields[field] = W.QDoubleSpinBox() if field != 'count' else W.QSpinBox()
            widget.setRange(minimum,maximum)
            widget.setValue(options[field])
            form.addRow(name,widget)
        if runway is None:
            combo = fields['color'] = W.QComboBox()
            for color, label in [(model.WHITE,'白色'),(model.RED,'红色'),(model.GREEN,'绿色'),(model.YELLOW,'黄色'),(model.BLUE,'蓝色')]:
                combo.addItem(tr(label),color)
            combo.setCurrentIndex(combo.findData(options['color']))
            form.addRow('颜色',combo)
        reset = W.QPushButton('恢复自动' if runway else '删除灯组')
        reset.clicked.connect(lambda: self.change_properties(key,{},reset=True))
        form.addRow(reset)
        for field,widget in fields.items():
            if field!='enabled' and key not in self.lamps:widget.setEnabled(False)
            def changed(*_, field=field, widget=widget):
                if isinstance(widget,W.QComboBox):
                    value = widget.currentData()
                elif isinstance(widget,W.QCheckBox):
                    value = widget.isChecked()
                elif isinstance(widget,W.QLineEdit):
                    value = widget.text().strip()
                else:
                    value = widget.value()
                self.change_properties(key,{field:value})

            if isinstance(widget,W.QComboBox):
                widget.currentIndexChanged.connect(changed)
            elif isinstance(widget,W.QCheckBox):
                widget.toggled.connect(changed)
            elif isinstance(widget,W.QLineEdit):
                widget.textEdited.connect(changed)
            else:
                widget.valueChanged.connect(changed)

    def change_properties(self, key, updates, reset=False):
        if not self.active or self.selected != key or key not in self.rows:
            return
        _,_,asset,_,_,options = self.rows[key]
        updates = {field:value for field,value in updates.items()
                   if value != (options.get('enabled_override') if field=='enabled'
                                else options.get(field,True if field=='animate' else None))}
        if not reset and not updates:
            return
        self.pause_animation()
        with self.app.scene.transaction('编辑助航灯光'):
            data = self.app.scene.data['meta'].setdefault('lighting_f7', {})
            group = data.setdefault('runways' if asset else 'custom', {})
            if reset:
                group.pop(key,None)
            else:
                override = group.setdefault(key,{})
                override.update(updates)
                if override.get('enabled') is None:
                    override.pop('enabled',None)
        # Keep the editor in place while typing or holding a spin-box button.
        self.sync()
        if reset or 'configuration' in updates:
            C.QTimer.singleShot(0,self.show_properties)
        self.app.redraw()

    def set_guard_stopbar(self,key,enabled):
        if not self.active or key!=self.selected or key not in self.rows:
            return
        options = self.rows[key][-1]
        with self.app.scene.transaction('设置警戒灯配套停止排灯'):
            settings = self.app.scene.data['meta'].setdefault('lighting_f7',{}).setdefault('runways',{})
            stop = settings.setdefault(options['stopbar_id'],{})
            stop['enabled'] = bool(enabled)
            if enabled and not stop.get('configuration','STOP').startswith('STOP'):
                stop['configuration'] = 'STOP'
        self.pause_animation()
        self.sync()
        C.QTimer.singleShot(0,self.show_properties)
        self.app.redraw()

    def approach_record(self):
        row=self.rows.get(self.approach_edit) if self.approach_edit in self.lamps else None
        if row and row[3]=='approach':return row

    def save_approach(self,record,**changes):
        if all(record[-1].get(key,0.)==value for key,value in changes.items()):return
        with self.app.scene.transaction('编辑进近灯光中轴'):
            rows=self.app.scene.data['meta'].setdefault('lighting_f7',{}).setdefault('runways',{})
            rows.setdefault(record[0],{}).update(changes)
        self.app.update_title()
        self.app.redraw()

    def approach_geometry(self,record,override=None,radii=None):
        from lighting_model import approach_axis,approach_frame
        options=record[-1]
        if override is not None:options=dict(options,axis_nodes=override)
        if radii is not None:options=dict(options,axis_radii=radii)
        controls,path=approach_axis(options)
        origin,outward,normal=approach_frame(record[2],record[4])
        def world(local):
            x,y=local
            return [p+x*u+y*v for p,u,v in zip(origin,outward,normal)]
        return [world(p) for p in controls],[world(p) for p in path]

    def draw_approach(self,nodes=None,radii=None):
        canvas=self.app.canvas
        tag='lighting_approach'
        canvas.delete(tag)
        record=self.approach_record()
        if record is None:
            self.draw_custom_nodes()
            return
        if record[-1]['length']<=0:return
        controls,path=self.approach_geometry(record,nodes,radii)
        canvas.create_line(*[v for q in path for v in self.app.screen(q)],
                           fill='#07869a',dash=(5,4),width=2,tags=tag)
        for index,q in enumerate(controls[1:]):
            x,y=self.app.screen(q)
            color='#f69b29' if index==self.approach_selected else '#ffffff'
            canvas.create_oval(x-5,y-5,x+5,y+5,fill=color,outline='#07869a',width=2,tags=tag)

        for index,anchor,handle,_ in self.approach_handles(record,controls,radii):
            x,y=handle
            canvas.create_line(*anchor,x,y,fill='#efa945',width=1,tags=tag)
            canvas.create_oval(x-4,y-4,x+4,y+4,fill='#efa945',outline='#583915',tags=tag)

    def approach_handles(self,record,controls,radii=None):
        options=record[-1]
        if radii is None:radii=options.get('axis_radii',{})
        for index,point in enumerate(controls[1:-1],1):
            anchor=self.app.screen(point)
            incoming=geometry.unit(anchor,self.app.screen(controls[index-1]))
            radius=radii.get(str(index),options.get('axis_radius') or 60.)
            reach=16+min(34,radius*self.app.zoom*.35)
            handle=[x+d*reach for x,d in zip(anchor,incoming)]
            yield index,anchor,handle,incoming

    def approach_local(self,record,point):
        from lighting_model import approach_frame
        origin,outward,normal=approach_frame(record[2],record[4])
        delta=[p-q for p,q in zip(point,origin)]
        return sum(a*b for a,b in zip(delta,outward))/record[-1]['length'],sum(a*b for a,b in zip(delta,normal))

    def approach_insert_target(self,x,y):
        record=self.approach_record()
        if record is None or record[-1]['length']<=0:return None
        _,path=self.approach_geometry(record)
        _,_,snap=geometry.project(path,self.app.world(x,y))
        if snap is None or math.dist(self.app.screen(snap),(x,y))>10:return None
        fraction,_=self.approach_local(record,snap)
        gap=min(.1,.2/record[-1]['length'])
        if gap<fraction<1-gap and all(abs(fraction-q[0])>gap for q in record[-1].get('axis_nodes',())):
            return snap
        return None

    def click_approach(self,event,record):
        options=record[-1]
        if options['length']<=0:return 'break'
        controls,_=self.approach_geometry(record)
        nodes=[list(p) for p in options.get('axis_nodes',())]
        if getattr(event,'state',0)&8:
            snap=self.approach_insert_target(event.x,event.y)
            if snap is not None:
                fraction,offset=self.approach_local(record,snap)
                nodes.append([fraction,offset])
                nodes.sort()
                self.approach_selected=nodes.index([fraction,offset])
                at=self.approach_selected+1
                radii={str(i+(i>=at)):r for key,r in options.get('axis_radii',{}).items() for i in [int(key)]}
                radii[str(at)]=options.get('axis_radius') or 60.
                self.save_approach(record,axis_nodes=nodes,axis_radii=radii)
        else:
            mouse=(event.x,event.y)
            radii=options.get('axis_radii',{}).copy()
            for index,_,handle,direction in self.approach_handles(record,controls,radii):
                if math.dist(handle,mouse)<=8:
                    self.approach_selected=index-1
                    radii.setdefault(str(index),options.get('axis_radius') or 60.)
                    self.approach_drag=(record,index,nodes,mouse,direction,radii)
                    self.draw_approach()
                    return 'break'
            distance,index=min((math.dist(self.app.screen(q),(event.x,event.y)),i)
                               for i,q in enumerate(controls[1:]))
            self.approach_selected=index if distance<=9 else None
            if self.approach_selected is not None:
                if index==len(nodes):nodes.append([1.,0.])
                self.approach_drag=(record,index,nodes,(event.x,event.y),None,radii)
            self.draw_approach()
        return 'break'

    def approach_candidate(self,event):
        record,index,original,start,direction,radii=self.approach_drag
        if direction is not None:
            delta=sum(u*(b-a) for u,a,b in zip(direction,start,(event.x,event.y)))
            result=radii.copy()
            result[str(index)]=max(.1,min(10000.,radii[str(index)]+delta/max(.001,self.app.zoom*.35)))
            return original,result
        nodes=[p.copy() for p in original]
        fraction,offset=self.approach_local(record,self.app.world(event.x,event.y))
        gap=min(.1,.2/record[-1]['length'])
        low=(nodes[index-1][0] if index else 0.)+gap
        high=(nodes[index+1][0] if index+1<len(nodes) else 1.)-gap
        nodes[index]=[1. if original[index][0]==1. else max(low,min(fraction,high)),offset]
        try:model.approach_axis(dict(record[-1],axis_nodes=nodes,axis_radii=radii),strict=True)
        except ValueError:return original,radii
        return nodes,radii

    def custom_points(self):
        row=self.rows.get(self.approach_edit)
        if row and self.approach_edit in self.lamps and row[2] is None:return row[-1].get('points')
        return None

    def draw_custom_nodes(self,points=None):
        points=self.custom_points() if points is None else points
        if not points:return
        canvas=self.app.canvas
        tag='lighting_approach'
        canvas.delete(tag)
        coords=[self.app.screen(q) for q in points]
        if len(coords)>1:
            canvas.create_line(*[v for p in coords for v in p],fill='#07869a',dash=(5,4),tags=tag)
        for index,(x,y) in enumerate(coords):
            color='#f69b29' if index==self.approach_selected else '#ffffff'
            canvas.create_oval(x-5,y-5,x+5,y+5,fill=color,outline='#07869a',width=2,tags=tag)

    def custom_candidate(self,event):
        index,original,_=self.custom_drag
        points=list(original)
        points[index]=self.app.world(event.x,event.y)
        if any(geometry.distance(a,b)<.05 for a,b in zip(points,points[1:])):return original
        return points

    def stop_approach(self):
        self.approach_edit=self.approach_drag=self.approach_selected=self.custom_drag=None
        self.app.canvas.delete('lighting_approach')

    def motion(self,event):
        if self.approach_drag:self.draw_approach(*self.approach_candidate(event))
        elif self.custom_drag:self.draw_custom_nodes(self.custom_candidate(event))
        return 'break'

    def release(self,event):
        if self.custom_drag:
            points=self.custom_candidate(event)
            original=self.custom_drag[1]
            self.custom_drag=None
            if points!=original:self.change_properties(self.selected,{'points':points})
            self.draw_approach()
        if self.approach_drag:
            record,_,_,press,_,_=self.approach_drag
            nodes,radii=self.approach_candidate(event)
            self.approach_drag=None
            if math.dist(press,(event.x,event.y))>=3:self.save_approach(record,axis_nodes=nodes,axis_radii=radii)
            else:self.draw_approach()
        return 'break'

    def delete_node(self):
        if self.app.mode=='SELECT':
            row=self.rows.get(self.selected)
            if self.selected in self.lamps and row:
                if row[2] is None:
                    self.change_properties(self.selected,{},reset=True)
                    self.select(None)
                else:self.change_properties(self.selected,{'enabled':False})
            return 'break'
        points=self.custom_points()
        index=self.approach_selected
        if points and len(points)>2 and index is not None and index<len(points):
            self.approach_selected=None
            self.change_properties(self.selected,{'points':points[:index]+points[index+1:]})
            return 'break'
        record=self.approach_record()
        if record is not None and self.approach_selected is not None:
            nodes=list(record[-1].get('axis_nodes',()))
            if self.approach_selected<len(nodes):
                at=self.approach_selected+1
                nodes.pop(self.approach_selected)
                radii={str(i-(i>at)):r for key,r in record[-1].get('axis_radii',{}).items()
                       for i in [int(key)] if i!=at}
                self.approach_selected=None
                self.save_approach(record,axis_nodes=nodes,axis_radii=radii)
        return 'break'

    def click(self, event):
        record=self.approach_record()
        if record is not None:return self.click_approach(event,record)
        q = self.app.world(event.x,event.y)
        points=self.custom_points()
        if points:
            if getattr(event,'state',0)&8:
                from node_interaction20_8 import edge_insertion
                hit=edge_insertion(points,q,10/max(.001,self.app.zoom))
                if hit:
                    index,point=hit
                    self.approach_selected=index
                    self.change_properties(self.selected,{'points':points[:index]+[point]+points[index:]})
                    return 'break'
            distance,index=min((math.dist(self.app.screen(p),(event.x,event.y)),i) for i,p in enumerate(points))
            if distance<=9:
                self.approach_selected=index
                self.custom_drag=(index,points,(event.x,event.y))
                self.draw_custom_nodes()
                return 'break'
        if self.tool is None:
            radius = 8/max(.001,self.app.zoom)
            hits = [(distance,key) for key, lights in self.lamps.items() for point, _, _, _ in lights
                    if (distance := geometry.distance(q,point)) <= radius]
            self.select(min(hits)[1] if hits else None)
            return 'break'
        scene = self.app.scene
        if self.tool != 'point' and self.anchor is None:
            self.anchor = q
            self.app.status.set('单击终点完成灯列，Esc 取消')
            self.app.redraw()
            return 'break'
        path = [q] if self.tool == 'point' else [self.anchor, q]
        if len(path) == 2 and geometry.distance(*path) < .05:
            return 'break'
        name, color, spacing = model.CUSTOM[self.tool]
        if self.tool == 'taxi_center':
            from guidance20 import routes
            limit = 14/max(.001,self.app.zoom)
            matches = []
            for route in routes(scene).values():
                if not all(self.app.can_edit_object(oid) for oid in route['props'].get('guidance_parents',(route['id'],))):continue
                a, b = [geometry.project(route['points'], pt) for pt in path]
                if max(a[0], b[0]) <= limit and abs(a[1]-b[1]) > .05:
                    matches.append((a[0]+b[0], route['id'], a[1], b[1], route['points']))
            if matches:
                _, owner, start, stop, axis = min(matches)
                path = geometry.subpath(axis,min(start,stop),max(start,stop))
        if geometry.length(path) > 5000:
            self.app.status.set('单个灯列长度不能超过 5000 m')
            return 'break'
        key = 'LIGHT-'+uuid4().hex
        with scene.transaction('绘制助航灯光'):
            scene.data['meta'].setdefault('lighting_f7', {}).setdefault('custom', {})[key] = {
                'name': name, 'kind': self.tool, 'color': color,'spacing': spacing,'points': path,
            }
        self.sync()
        self.select(key)
        self.choose(None)
        return 'break'

    def cache_base_geometry(self):
        from export_modes21 import lighting_wireframe
        self.base_paths,self.base_labels = lighting_wireframe(self.app.scene,self.rows.values(),self.closures[0])

    def redraw(self,editing=False):
        previous = self.cache_key
        self.sync()
        if previous != self.cache_key:
            self.show_properties()
        app, canvas = self.app, self.app.canvas
        canvas.camera21(app.origin,app.zoom)
        canvas.q.setBackgroundBrush(G.QColor('#101922'))
        canvas.delete('lighting_f7')
        canvas.itemconfigure('map',state='hidden')
        for item,_ in app.__dict__.get('_bitmap_items',{}).values():
            item.hide()
        for tag in (() if editing else ('overlay','frame11','view_mode18','north23','bitmap46','color17',
                    'movement_names20','snap_cursor','semantic14','corner_handles12','cut_preview11')):
            canvas.delete(tag)
        dark = app._dark_mode24
        app._dark_mode24 = True
        try:
            app.draw_grid7()
            app.draw_scale14()
            app.draw_compass23()
        finally:
            app._dark_mode24 = dark
        tag = 'lighting_f7'
        w,h = canvas.winfo_width(),canvas.winfo_height()

        def line(points, color, width=1):
            if len(points)>1:
                canvas.create_line(*[v for p in points for v in app.screen(p)],fill=color,width=width,tags=tag)

        for points,color in self.base_paths:
            line(points,color)
        for point,label in self.base_labels:
            x,y = app.screen(point)
            if 15<x<w-15 and 20<y<h-20:
                canvas.create_text(x,y-9,text=label,fill='#becbd7',tags=tag)
        self.animated_items.clear()
        self.animation_phases = {}
        radius = max(2.0,min(12.0,.45*app.zoom))
        animate = self.animation_switch.isChecked()
        for key, lamps in self.lamps.items():
            _, _, _, kind, _, options = self.rows[key]
            selected = key == self.selected
            r = min(12.0,radius + (1 if selected else 0) + (2 if kind == 'flash' else 0))
            for point,color,direction,phase in lamps:
                x,y = app.screen(point)
                if not -r<=x<=w+r or not -r<=y<=h+r:
                    continue
                outline = '#fff' if selected else '#91e4ff' if kind == 'flash' else ''
                if direction is None:
                    item = canvas.create_oval(x-r,y-r,x+r,y+r,fill=color,outline=outline,tags=tag)
                else:
                    dx,dy = app.screen((point[0]+direction[0],point[1]+direction[1]))
                    heading = math.atan2(dy-y,dx-x)
                    angles = [heading+math.pi*(i/12-.5) for i in range(13)]
                    coords = [coordinate for angle in angles for coordinate in
                              (x+r*math.cos(angle),y+r*math.sin(angle))]
                    item = canvas.create_polygon(*coords,fill=color,outline=outline,tags=tag)
                if phase is not None and animate and options.get('animate',True):
                    self.animated_items.setdefault(key,[]).append((item,phase))
                if kind == 'flash':
                    canvas.tag_raise(item)
        if self.animated_items:
            if self.paused_at is None:
                if not self.animation_timer.isActive():
                    self.animation_timer.start()
            elif not self.resume_timer.isActive() and self.anchor is None:
                self.resume_timer.start()
            self.animate()
        else:
            self.animation_timer.stop()
        if self.anchor is not None:
            x,y = app.screen(self.anchor)
            canvas.create_oval(x-5,y-5,x+5,y+5,outline='#8fe9ff',tags=tag)
        canvas.create_text(w-16,20,text=tr('助航灯光 · F7'),anchor='ne',fill='#e0edf7',
                           font=('Microsoft YaHei',10,'bold'),tags=tag)
        _,closed_runways,airport_inactive = self.closures
        if closed_runways:
            text = '机场已停用 · 全部灯光关闭' if airport_inactive else '跑道关闭 · 相关灯光已关闭'
            item = canvas.create_text(w/2,58,text=tr(text),fill='#fff',
                                      font=('Microsoft YaHei',12,'bold'),tags=tag)
            box = canvas.bbox(item)
            if box:
                x0,y0,x1,y1 = box
                background = canvas.create_rectangle(x0-16,y0-8,x1+16,y1+8,
                                                     fill='#a12739',outline='#ff8490',tags=tag)
                canvas.tag_lower(background,item)
        canvas.tag_raise('north23')
        self.draw_approach()

    def set_high_traffic(self, enabled):
        with self.app.scene.transaction('设置灯光方案交通密度'):
            self.app.scene.data['meta'].setdefault('lighting_f7',{})['high_traffic'] = bool(enabled)
        self.app.redraw()

    def set_animation(self, enabled):
        scene = self.app.scene
        with scene.transaction('设置灯光动画'):
            scene.data['meta'].setdefault('lighting_f7', {})['animate'] = bool(enabled)
        self.sync()
        if self.active:
            self.app.redraw()

    def animate(self):
        now = (time.monotonic() if self.paused_at is None else self.paused_at)-self.animation_epoch
        for key, items in self.animated_items.items():
            kind = self.rows[key][3]
            if kind in ('guard','runway_hold','runway_guard'):
                rate = 31 if self.rows[key][-1].get('configuration')=='GUARD_B' else 48
                active = int(now*rate/30) % 2
            else:
                count = len(self.lamps[key])
                active = min(count-1,int((now % .5)/.5*count))
            if self.animation_phases.get(key) == active:
                continue
            self.animation_phases[key] = active
            for item,phase in items:
                record = self.app.canvas._items.get(item)
                if record:
                    record['q'].setOpacity(1.0 if phase == active else (0.0 if kind == 'flash' else .25))

    def eventFilter(self, watched, event):
        if self.active and isinstance(watched,W.QWidget):
            owner = watched
            while owner and owner is not self.app.q:
                owner = owner.parentWidget()
            if owner and event.type() in (
                    C.QEvent.Type.MouseButtonPress,C.QEvent.Type.MouseButtonRelease,
                    C.QEvent.Type.MouseButtonDblClick,
                    C.QEvent.Type.Wheel,C.QEvent.Type.KeyPress,C.QEvent.Type.KeyRelease,
                    C.QEvent.Type.TouchBegin,C.QEvent.Type.TouchUpdate,C.QEvent.Type.TouchEnd):
                self.pause_animation()
            elif owner and event.type() == C.QEvent.Type.MouseMove:
                if self.anchor is not None or event.buttons() != Qt.MouseButton.NoButton:
                    self.pause_animation()
        return False

    def pause_animation(self):
        if not self.active:
            return
        if self.paused_at is None:
            self.paused_at = time.monotonic()
        self.animation_timer.stop()
        self.resume_timer.start()

    def resume_animation(self):
        if not self.active or self.paused_at is None:
            return
        if self.anchor is not None:
            return
        if (W.QApplication.mouseButtons() != Qt.MouseButton.NoButton
                or W.QApplication.activePopupWidget() or W.QApplication.activeModalWidget()):
            self.resume_timer.start()
            return
        self.animation_epoch += time.monotonic()-self.paused_at
        self.paused_at = None
        if self.animated_items:
            self.animation_timer.start()
