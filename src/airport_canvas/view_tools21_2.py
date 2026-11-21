"""Qt display controls, sign editing and viewport rotation gestures."""
from interface_language import tr
import math
import os
import time

from qt_core21 import C, G, W, Qt
from qt_compat import ttk
from geometry11 import Point, polygon
import scene_geometry as g
import signs21_2 as signs

OPTIONS = (
    ('hide_boards21_2','隐藏标记牌'),
    ('enlarge_boards23','标记牌不按比例显示'),
    ('enlarge_boards26','标记牌放大显示（固定倍数）'),
    ('dark_mode24','深色模式'),
)


def rotate(x,y,angle):
    c,s = math.cos(angle),math.sin(angle)
    return c*x-s*y,s*x+c*y


def memory_mib():
    if os.name == 'nt':
        import ctypes as ct
        from ctypes import wintypes as wt

        class Counters(ct.Structure):
            _fields_ = [('cb',wt.DWORD),('faults',wt.DWORD)] + [
                (key,ct.c_size_t) for key in ('peak','working','pool_peak','pool',
                                               'nonpaged_peak','nonpaged','page','page_peak')]
        counter = Counters()
        counter.cb = ct.sizeof(counter)
        process = ct.windll.kernel32.GetCurrentProcess
        process.restype = wt.HANDLE
        query = ct.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [wt.HANDLE,ct.POINTER(Counters),wt.DWORD]
        if query(process(),ct.byref(counter),counter.cb):
            return counter.working/2**20
    else:
        try:
            with open('/proc/self/statm',encoding='ascii') as stat:
                return int(stat.read().split()[1])*os.sysconf('SC_PAGE_SIZE')/2**20
        except (OSError,ValueError,IndexError):
            pass
    return None


class ViewTools(C.QObject):
    def __init__(self, app):
        super().__init__(app.q)
        self.app = app
        self.anchor = None
        self.physical_anchor=None
        self.editing = None
        self.active = False
        self.drag = None
        self.paint_count = 0
        self.frame_count = 0
        self.viewport = app.canvas.q.viewport()
        app.canvas.viewport_input21_2 = self.viewport_input
        display = app.display_menu14
        for label,variable,command in app.display_options23:
            display.add_checkbutton(label=label,variable=variable,command=command)
        display.add_checkbutton(label="彩色分段 · F6",variable=app._color_var17,command=app.toggle_color17)
        menu = display.q
        main=app.q.menuBar()
        signs_menu=next((action.menu() for action in main.actions() if action.text() in ('信息引导',tr('信息引导'))),None)
        if signs_menu is None:signs_menu=main.addMenu('信息引导')
        signs_menu.addSeparator()
        edit_menu=next((action.menu() for action in main.actions() if action.text() in ('编辑',tr('编辑'))),None)
        if edit_menu is None:edit_menu=main.addMenu('编辑')
        outlines=edit_menu.addMenu('统一描边')
        self.outlines_menu=outlines
        self.outline_actions={}
        for key,label in (
            ('hide_runway_outline21_2','统一启用跑道黑色描边'),
            ('hide_taxi_outline21_2','统一启用滑行道黑色描边'),
            ('hide_stand_outline21_2','统一启用机位引入线／停止线／机位编号黑色描边'),
            ('hide_safety_outline21_2','统一启用安全线／廊桥／栓井白色描边'),
        ):
            action=outlines.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(lambda enabled,k=key:self.set_outline(k,enabled))
            self.outline_actions[key]=action
        outlines.aboutToShow.connect(self.sync_menu)
        menu.addSeparator()
        self.actions = {}
        for key,label in OPTIONS:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(lambda enabled,k=key:self.set_option(k,enabled))
            self.actions[key] = action
        menu.aboutToShow.connect(self.sync_menu)
        menu.addSeparator()
        action = menu.addAction('显示 FPS 与内存')
        action.setCheckable(True)
        action.toggled.connect(self.performance)
        self.badge = W.QLabel(self.viewport)
        self.badge.setStyleSheet('background:transparent;color:#25465b;font-size:11px;')
        self.badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.badge.hide()
        self.timer = C.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.sample)

        self.bar = ttk.Frame(app)
        layout = self.bar._ensure_layout(side='left')
        layout.setContentsMargins(8,2,8,2)
        layout.setSpacing(6)
        layout.addWidget(W.QLabel('标识编辑  F5',self.bar.q))
        self.caption=layout.itemAt(0).widget()
        self.drawing=False
        self.cursor_point=None
        self.append_id=None
        self.kind = W.QComboBox(self.bar.q)
        for label,value in (('目的地与方向标识','PAVEMENT'),
                            ('方向标记牌','DIRECTION_BOARD'),('目的地标记牌','DESTINATION_BOARD'),
                            ('交叉点起飞标记牌','TAKEOFF'),('跑道等待位置标记牌','HOLD_BOARD'),
                            ('HP 等待点标记牌','FREQUENCY'),('HP 等待点道面标识','FREQUENCY_PAVEMENT')):
            self.kind.addItem(tr(label),value)
        from boards24 import TEMPLATES
        for kind,label,_ in TEMPLATES:self.kind.addItem(tr(label),kind)
        self.kind.currentIndexChanged.connect(self.reset_anchor)
        layout.addWidget(self.kind)
        self.side = W.QComboBox(self.bar.q)
        for label,value in (('右侧','RIGHT'),('左侧','LEFT'),('两侧','BOTH')):
            self.side.addItem(tr(label),value)
        layout.addWidget(self.side)
        retarget = W.QPushButton('重选目的地',self.bar.q)
        retarget.clicked.connect(self.retarget)
        layout.addWidget(retarget)
        for label,action in (('编辑文字',self.edit_text),('追加分支',self.append_branch)):
            button=W.QPushButton(label,self.bar.q)
            button.clicked.connect(action)
            layout.addWidget(button)
        self.append_action=signs_menu.addAction('为选中的目的地与方向标识追加分支')
        self.append_action.triggered.connect(self.append_branch)
        signs_menu.addAction('编辑选中的标识或标记牌文字',self.edit_text)
        rebind=W.QPushButton('重绑来源',self.bar.q)
        rebind.clicked.connect(self.rebind)
        layout.addWidget(rebind)
        button = W.QPushButton('生成标记牌',self.bar.q)
        button.clicked.connect(self.generate)
        layout.addWidget(button)
        layout.addStretch(1)
        app.bind('<F5>',lambda e:self.toggle())
        edit = menu.addAction('标识编辑  F5')
        edit.triggered.connect(self.toggle)
        generate = signs_menu.addAction('生成标记牌')
        generate.triggered.connect(self.generate)
        north = menu.addAction('真北朝上')
        north.setShortcut(G.QKeySequence('Alt+N'))
        north.triggered.connect(self.north)
        self.north_action=north
        grid = menu.addAction('工程网格朝上')
        grid.setShortcuts([G.QKeySequence('Alt+Return'), G.QKeySequence('Alt+Enter')])
        grid.triggered.connect(lambda:self.angle(0))
        self.grid_action=grid
        performance_action=next(item for item in menu.actions() if 'FPS' in item.text())
        performance_action.setChecked(True)

    def sync_menu(self):
        meta = self.app.scene.data['meta']
        for key,action in self.outline_actions.items():
            group=key.split('_')[1]
            default=group=='safety' or bool(meta.get('guidance_black_outline',False))
            action.setChecked(not meta[key] if key in meta else default)
        for key,action in self.actions.items():
            action.setChecked(self.app.dark_mode_enabled() if key=='dark_mode24' else bool(meta.get(key)))

    def set_outline(self,key,enabled):
        from paint10 import set_outline_group
        with self.app.processing('正在统一更新描边'):
            set_outline_group(self.app.scene,key,enabled)
            self.app.refresh()

    def set_option(self,key,enabled):
        if key=='dark_mode24':
            self.app.set_dark_mode(enabled)
            return
        with self.app.scene.transaction('显示选项'):
            meta=self.app.scene.data['meta']
            meta[key]=bool(enabled)
            if enabled and key in ('enlarge_boards23','enlarge_boards26'):
                other='enlarge_boards26' if key=='enlarge_boards23' else 'enlarge_boards23'
                meta[other]=False
        self.app.refresh()

    def generate(self):
        with self.app.processing('正在生成目的地与方向标识和标记牌'):
            return self.generate_signs()

    def generate_signs(self):
        app = self.app
        with app.scene.transaction('生成标记牌'):
            meta = app.scene.data['meta']
            meta.update(auto_boards20_18=True,hide_boards21_2=False)
            overrides = app.scene.data['generated_overrides']
            for mark in __import__('directions20_18').generated(app.scene).values():
                if mark['props']['information_profile20_18']=='BOARD' and mark['id'] in overrides:
                    overrides[mark['id']].pop('hidden',None)
        app._options20_18['auto_boards20_18'].set(True)
        app.refresh()
        count = sum(mark['props'].get('information_profile20_18')=='BOARD'
                    for mark in app.auto_assets.values())
        app.status.set(f'已生成 {count} 处自动标记牌')

    def toggle(self):
        with self.app.processing('正在切换标识与标记牌编辑视图'):
            return self.toggle_editor()

    def toggle_editor(self):
        if self.active:
            self.exit()
        else:
            if self.app._color17:
                self.app.toggle_color17(False)
            self.app.set_mode('SELECT')
            self.active = True
            self.caption.setText(tr('标识编辑  F5'))
            self.bar.pack(fill='x',before=self.app._body11)
            self.reset_anchor()
            self.app.canvas.focus_set()
            self.app.redraw()
        return 'break'

    def exit(self):
        self.active = False
        self.drawing=False
        self.anchor = None
        self.physical_anchor=None
        self.editing = None
        self.bar.pack_forget()
        self.app.canvas.delete('sign_anchor21_2')
        self.app.canvas.delete('sign_cursor')
        self.app.status.set('已退出目的地与方向标识与标记牌工具')
        self.app.redraw()

    def start(self,kind):
        self.drawing=True
        self.caption.setText('目的地与方向标识与标记牌' if not self.active else '标识编辑  F5')
        self.bar.pack(fill='x',before=self.app._body11)
        self.kind.setCurrentIndex(self.kind.findData(kind))
        self.reset_anchor()
        self.app.canvas.focus_set()
        self.app.redraw()

    def edit_text(self):
        app=self.app
        mark=app.scene.assets.get(app.selection) or app.auto_assets.get(app.selection)
        if not mark or not mark['props'].get('information_profile20_18'):
            app.status.set('请先选中目的地与方向标识或标记牌')
            return
        p=mark['props']
        if p.get('sign_role23')=='NO_ENTRY_BOARD':
            app.status.set('禁止进入标记牌使用图形符号')
            return
        panels=p.get('sign_panels24',[])
        ground=p.get('sign_ground_rows',[])
        rows=panels or ground
        value=' | '.join(row['label'] for row in rows) if rows else p.get('direction_name20_18','')
        from boards24 import runway_connections,cat_labels
        runways=runway_connections(app.scene,p.get('sign_axis21_2') or mark.get('owner')) if p.get('sign_role23')=='CAT_HOLD' else {}
        if runways:
            choices=sorted({item for runway in runways.values() for item in cat_labels(runway)})
            if not choices:
                app.status.set('相连跑道没有设置精密进近等级')
                return
            label,ok=W.QInputDialog.getItem(app.q,'编辑文字','相连跑道与盲降等级',
                                            choices,choices.index(value) if value in choices else 0,False)
        else:
            label,ok=W.QInputDialog.getText(app.q,'编辑文字','多块牌面请用 | 分隔',text=value)
        if not ok:return
        if not label.strip():
            app.status.set('请输入牌面文字')
            return
        values=dict(text=label,direction_name20_18=label,sign_custom_text=label)
        if p.get('sign_role23')=='VACATED':
            values['location_name20_18']=label
        if rows:
            parts=[part.strip() for part in label.split('|')]
            if len(parts)!=len(rows) or not all(parts):
                app.status.set('请为每块牌面输入对应的文字')
                return
            if panels:
                values['sign_panels24']=[dict(panel,label=name) for panel,name in zip(panels,parts)]
            else:
                values.update(text=parts[0],direction_name20_18=parts[0],sign_custom_text=parts[0],
                              sign_extra_targets=[dict(ref,sign_custom_text=name)
                                                  for ref,name in zip(p['sign_extra_targets'],parts[1:])])
        with app.scene.transaction('编辑标识文字'):
            if mark['id'] in app.scene.assets:
                mark['props'].update(values)
                mark['name']=label
            else:
                override=app.scene.data['generated_overrides'].setdefault(mark['id'],{})
                override.setdefault('props',{}).update(values)
        app.refresh()

    def append_branch(self):
        app=self.app
        mark=app.scene.assets.get(app.selection)
        p=mark['props'] if mark else {}
        axis=signs.routes(app.scene).get(p.get('sign_axis21_2'))
        if not axis or p.get('information_profile20_18')!='PAVEMENT' or not p.get('sign_target21_2'):
            app.status.set('请选中已有的手动目的地与方向标识')
            return
        self.start('PAVEMENT')
        station=signs.station_at(p,axis)
        self.anchor=axis['id'],station,g.at(axis['points'],station)[0]
        self.append_id=mark['id']
        self.render_anchor()
        app.status.set('点击要追加的分支')

    def retarget(self):
        app=self.app
        mark=app.scene.assets.get(app.selection,{})
        p=mark.get('props',{})
        source=p.get('sign_axis21_2')
        axis=signs.routes(app.scene).get(source)
        if not axis or p.get('sign_static_face26'):
            app.status.set('请先选中一个手动放置的标识')
            return
        profile=p['information_profile20_18']
        self.start('PAVEMENT' if profile=='PAVEMENT' else
                   'DIRECTION_BOARD' if p.get('sign_location21_2') else 'DESTINATION_BOARD')
        self.side.setCurrentIndex(self.side.findData(p['direction_side21_2']))
        station=signs.station_at(p,axis)
        self.anchor=source,station,g.at(axis['points'],station)[0]
        self.editing=mark['id']
        self.render_anchor()
        app.canvas.focus_set()
        app.status.set('请点击新的目的地')

    def rebind(self):
        mark=self.app.scene.assets.get(self.app.selection,{})
        props=mark.get('props',{})
        if not props.get('information_profile20_18'):
            self.app.status.set('请先从画布或树列表选中手动标记牌')
            return
        self.start(props.get('sign_role23') or 'PAVEMENT')
        self.rebind_id26=mark['id']
        self.app.status.set('请点击标记牌的新来源中心线')
        self.app.canvas.focus_set()

    def reset_anchor(self,*_):
        self.rebind_id26=None
        self.append_id=None
        self.cursor_point=None
        self.anchor = None
        self.physical_anchor=None
        self.editing = None
        self.app.canvas.delete('sign_anchor21_2')
        self.app.canvas.delete('sign_cursor')
        if self.active or self.drawing:
            self.app.status.set('标识编辑：选择类型和侧别，再点击滑行道中线')

    def axes(self,kind):
        if kind in ('ROAD_STOP_BOARD','RUNWAY_EXIT'):
            asset_kind='ROAD' if kind=='ROAD_STOP_BOARD' else 'RUNWAY'
            return {a['id']:a for a in self.app.scene.assets.values() if a['kind']==asset_kind}
        return signs.routes(self.app.scene)

    def pointer(self,event):
        world=self.app.world(event.x,event.y)
        from guidance20 import snap_axis
        hit=snap_axis(self.app.scene,world,self.axes(self.kind.currentData()),13/self.app.zoom)
        self.cursor_point=hit[3] if hit and hit[0]<=13/self.app.zoom else None
        self.render_cursor()

    def render_cursor(self):
        canvas=self.app.canvas
        canvas.delete('sign_cursor')
        if self.cursor_point is not None:
            x,y=self.app.screen(self.cursor_point)
            canvas.create_oval(x-5,y-5,x+5,y+5,fill='#5de4ef',outline='#193942',
                               width=2,tags='sign_cursor')

    def render_anchor(self):
        canvas = self.app.canvas
        canvas.delete('sign_anchor21_2')
        from segments18 import pieces
        from scene_render import rapid_f6_guides
        items = self.app.render_items
        cache = self.app.__dict__.get('_rapid_f6_paths')
        if not cache or cache[0] is not items:
            cache = self.app._rapid_f6_paths = (items, rapid_f6_guides(items))
        rapid_paths = cache[1]
        for aid, axis in self.axes(self.kind.currentData()).items():
            if len(axis['points'])<2:continue
            if self.anchor:
                length=g.length(axis['points'])
                for part in pieces(axis):
                    x,y=self.app.screen(g.at(axis['points'],length*(part['lo']+part['hi'])/2)[0])
                    canvas.create_text(x,y-10,text=part['name'],fill='#088ca6',
                                       font=('Segoe UI',11,'bold'),tags='sign_anchor21_2')
            elif aid not in rapid_paths or not self.active:
                # F5 already paints the same colored rapid guides as F6.
                for path in rapid_paths.get(aid, (axis['points'],)):
                    canvas.create_line(*[c for p in path for c in self.app.screen(p)],
                                       fill='#25bbd0',width=2,tags='sign_anchor21_2')
        if self.anchor:
            x,y = self.app.screen(self.anchor[2])
            canvas.create_oval(x-6,y-6,x+6,y+6,fill='#fdf055',outline='#223749',
                               width=2,tags='sign_anchor21_2')
        self.render_cursor()

    def click(self,e):
        app = self.app
        q = app.world(e.x,e.y)
        network = signs.routes(app.scene)
        rebind=getattr(self,'rebind_id26',None)
        selected=app.scene.assets.get(rebind,{})
        kind=selected.get('props',{}).get('sign_role23') if rebind else self.kind.currentData()
        if kind=='ROAD_STOP_BOARD':
            network={a['id']:a for a in app.scene.assets.values() if a['kind']=='ROAD'}
        elif kind=='RUNWAY_EXIT':
            network={a['id']:a for a in app.scene.assets.values() if a['kind']=='RUNWAY'}
        tolerance = 13/app.zoom
        hits = sorted((g.project(axis['points'],q)[0],aid) for aid,axis in network.items())
        if self.anchor is None:
            from guidance20 import snap_axis
            axis_hit=snap_axis(app.scene,q,network,tolerance)
            if self.drawing and kind=='PAVEMENT' and not rebind:
                pointer=set(app.canvas.find_overlapping(e.x-3,e.y-3,e.x+3,e.y+3))
                for mark in app.scene.assets.values():
                    props=mark['props']
                    if props.get('information_profile20_18')=='PAVEMENT' and props.get('sign_target21_2'):
                        if pointer.intersection(app.canvas.find_withtag('owner:'+mark['id'])):
                            app.select(mark['id'])
                            self.append_branch()
                            return 'break'
            if not axis_hit:
                hits_at_pointer = set(app.canvas.find_overlapping(e.x-4,e.y-4,e.x+4,e.y+4))
                marks = [mark for mark in (*app.scene.assets.values(),*app.auto_assets.values())
                         if mark['props'].get('information_profile20_18')
                         and hits_at_pointer.intersection(app.canvas.find_withtag('owner:'+mark['id']))]
                if marks:
                    app.select(marks[0]['id'])
                    app.status.set('已选中标识，可在右侧编辑属性或按 Delete 删除')
                    return 'break'
                target={'ROAD_STOP_BOARD':'服务车道','RUNWAY_EXIT':'跑道'}.get(self.kind.currentData(),'滑行道或机坪滑行道')
                app.status.set('请点击'+target+'中线')
                return 'break'
            _,source,station,point=axis_hit
            physical=getattr(axis_hit,'source',None)
            self.physical_anchor=physical if physical and physical[0].startswith('G20-') else None
            if rebind:
                signs.bind_existing(app.scene,rebind,network[source],station,self.physical_anchor)
                self.reset_anchor()
                app.refresh()
                app.status.set('已重新绑定标记牌来源')
                return 'break'
            self.anchor = source,station,point
            self.render_anchor()
            kind=self.kind.currentData()
            from boards24 import TEMPLATES, parse_panels
            templates={key:(title,default) for key,title,default in TEMPLATES}
            if kind in templates:
                title,default=templates[kind]
                face={}
                label=default
                direction=None
                if kind not in ('NO_ENTRY_BOARD','ROAD_STOP_BOARD'):
                    caption='牌面编号或组合内容'
                    if kind in ('VACATED','LOCATION_BOARD'):default=__import__('segments18').piece_at(network[source],station)['name']
                    from boards24 import runway_connections, cat_labels
                    connected=runway_connections(app.scene,source) if kind=='CAT_HOLD' else {}
                    if connected:
                        options=sorted({label for runway in connected.values() for label in cat_labels(runway)})
                        if not options:
                            self.reset_anchor()
                            app.status.set('相连跑道没有设置精密进近等级')
                            return 'break'
                        label,ok=W.QInputDialog.getItem(app.q,title,'相连跑道与盲降等级',options,0,False)
                    else:
                        label,ok=W.QInputDialog.getText(app.q,title,caption,text=default)
                        if kind=='CAT_HOLD' and ok and not __import__('re').fullmatch(
                            r'(0[1-9]|[12][0-9]|3[0-6])[LCR]? CAT (I|II|III|II/III)',label.strip().upper()
                        ):
                            self.reset_anchor()
                            app.status.set('请输入跑道号码和 ILS 等级，例如 25 CAT II')
                            return 'break'
                    if not ok or not label.strip():
                        self.reset_anchor()
                        return 'break'
                try:
                    if kind in ('DIRECTION_GROUP','DESTINATION_GROUP'):
                        face['sign_panels24']=parse_panels(label,kind)
                    if kind=='RUNWAY_NUMBER':
                        own,ok=W.QInputDialog.getText(app.q,title,'位置编号',text=network[source]['name'])
                        if not ok:
                            self.reset_anchor()
                            return 'break'
                        face['location_name20_18']=own.strip().upper()
                    if kind=='RUNWAY_EXIT':
                        direction,ok=W.QInputDialog.getItem(app.q,title,'出口方向',list(signs.ARROWS),2,False)
                        if not ok:
                            self.reset_anchor()
                            return 'break'
                    if kind in ('NO_ENTRY_BOARD','RUNWAY_NUMBER','CAT_HOLD'):
                        choice=W.QMessageBox.question(app.q,title,'白色内容添加黑边？',
                            W.QMessageBox.StandardButton.Yes|W.QMessageBox.StandardButton.No)
                        face['sign_black_ink24']=choice==W.QMessageBox.StandardButton.Yes
                    self.special(kind,label.strip().upper(),direction,**face)
                except ValueError as exc:
                    self.reset_anchor()
                    app.status.set(str(exc))
                return 'break'
            if kind in ('HOLD_BOARD','FREQUENCY','FREQUENCY_PAVEMENT'):
                prefix=__import__('segments18').piece_at(network[source],station)['name']
                label,ok=W.QInputDialog.getText(app.q,'标记牌牌面','编号',text='HP 1' if kind.startswith('FREQUENCY') else prefix)
                if ok and label.strip():
                    if kind.startswith('FREQUENCY') and not __import__('re').fullmatch(r'HP ?[1-9][0-9]*',label.strip().upper()):
                        app.status.set('转换频率标记牌使用 HP 加正整数，例如 HP 1')
                        self.reset_anchor()
                        return 'break'
                    self.special(kind,label.strip().upper())
                else:self.reset_anchor()
                return 'break'
            app.status.set('点击目的滑行道、跑道头或机坪。右键取消')
            return 'break'

        source,station,_ = self.anchor
        targets = [(d,aid) for d,aid in hits if d<=tolerance]
        for aid,asset in app.scene.assets.items():
            if asset['kind']=='RUNWAY':
                distance = min(g.distance(q,asset['points'][0]),g.distance(q,asset['points'][-1]))
                if distance<=max(tolerance,asset['props']['width']/2):
                    targets.append((distance,aid))
            elif asset['kind']=='APRON' and polygon(asset['points']).covers(Point(q)):
                targets.append((tolerance+1,aid))
        if not targets:
            app.status.set('请点击目的滑行道、跑道头或机坪')
            return 'break'
        if getattr(e,'state',0)&1:
            apron_targets=[x for x in targets if app.scene.assets.get(x[1],{}).get('kind')=='APRON']
            if apron_targets:targets=apron_targets
        target = min(targets)[1]
        side = self.side.currentData()
        profile = self.kind.currentData()
        try:
            if profile=='TAKEOFF':
                asset=app.scene.assets.get(target,{})
                if asset.get('kind')!='RUNWAY':
                    app.status.set('交叉点起飞标记牌请选择跑道头')
                    return 'break'
                axis=network[source]
                point=self.anchor[2]
                _,pos,near=g.project(asset['points'],point)
                joins=[j for j in __import__('pavement_geometry').crossings(app.scene)
                       if {source,target}==set(j['assets'])]
                if joins:
                    join=min(joins,key=lambda j:g.distance(point,j['point']))
                    pos=join['stations'][join['assets'].index(target)]
                length=g.length(asset['points'])
                toward_a=g.distance(q,asset['points'][0])<=g.distance(q,asset['points'][-1])
                # The runway number at a threshold denotes the direction toward its opposite end.
                estimate=length-pos if toward_a else pos
                distance,ok=W.QInputDialog.getInt(app.q,'交叉点起飞标记牌','经核实的剩余 TORA（米）',round(estimate),1,20000)
                if ok:
                    _,u=g.at(axis['points'],station)
                    _,runway_axis=g.at(asset['points'],pos)
                    if sum(u[k]*(near[k]-point[k]) for k in (0,1))<0:u=[-x for x in u]
                    self.special(profile,f'{distance}m',signs.arrow(u,runway_axis if toward_a else [-x for x in runway_axis]),near,
                                 sign_target21_2=target,sign_end21_2=0 if toward_a else -1)
                return 'break'
            sides=('LEFT','RIGHT') if side=='BOTH' else (side,)
            if self.editing and side=='BOTH':
                app.status.set('重选目的地时请选择一侧；两侧请分别编辑')
                return 'break'
            if self.append_id:
                signs.append_target(app.scene,self.append_id,target,q)
            else:
                signs.create(app.scene,source,station,target,q,profile,sides,self.editing,physical=getattr(self,'physical_anchor',None))
        except (ValueError,KeyError) as exc:
            app.status.set(str(exc))
            return 'break'
        self.reset_anchor()
        self.finish_draw()
        app.refresh()
        app.status.set('已添加标识，可继续选择下一条中线')
        return 'break'

    def special(self,kind,label,arrow=None,toward=None,**face):
        app=self.app
        source,station,point=self.anchor
        side=self.side.currentData()
        sides=('LEFT','RIGHT') if side=='BOTH' else (side,)
        if physical:=getattr(self,'physical_anchor',None):
            face['physical_axis_source']=list(physical)
        signs.special(app.scene,source,station,kind,label,arrow,sides,toward,**face)
        self.reset_anchor()
        self.finish_draw()
        app.refresh()

    def finish_draw(self):
        if self.drawing and not self.active and not self.app.repeat.get():
            self.exit()

    @staticmethod
    def face_center(items):
        points=[p for item in items for p in item['points']]
        return tuple(sum(p[i] for p in points)/len(points) for i in (0,1))

    def draw_face(self,oid,items,project,scale,turn,tag,parent=None):
        c=self.app.canvas
        tags=('sign_display23','owner:'+oid,tag)
        for e in items:
            pixels=list(map(project,e['points']))
            width=max(.1,e.get('width',.1)*scale)
            if e['type']=='text':
                size=max(1,round(e['size']*scale*.75))
                dimensions={}
                if e.get('text_width'):
                    dimensions=dict(text_width_px=e['text_width']*scale,text_height_px=e['size']*scale)
                identifier=c.create_text(*pixels[0],text=e['text'],fill=e['fill'],
                    font=('Segoe UI',size,'bold'),angle=e.get('rotation',0)-turn,tags=tags,
                    outline='#101010' if e.get('black_outline') else '',
                    outline_width=e['size']*scale*.055,**dimensions)
            elif e['type']=='polygon':
                identifier=c.create_polygon(*[v for p in pixels for v in p],fill=e.get('fill') or '',
                                          outline=e.get('stroke') or '',width=width,tags=tags)
            elif e['type']=='line':
                identifier=c.create_line(*[v for p in pixels for v in p],fill=e['stroke'],width=width,tags=tags)
            else:continue
            if parent is not None:c._items[identifier]['q'].setParentItem(parent)

    def clear_fixed(self):
        c=self.app.canvas
        c.delete('fixed_board25')
        for node in getattr(self,'board_nodes25',{}).values():
            if node.scene() is not None:node.scene().removeItem(node)
        self.board_nodes25={}
        self.board_source25=None
        self.board_positions25=None

    def draw_fixed(self,turn):
        from boards24 import group_faces, layout_faces, pavement, scaled_face
        app=self.app
        c=app.canvas
        if getattr(self,'board_source25',None) is not app.render_items:
            self.clear_fixed()
            c.enable_world21()
            self.board_source25=app.render_items
            self.board_groups25=group_faces(app.render_items)
            self.board_centers25={}
            for oid,items in self.board_groups25.items():
                x,y=self.face_center(items)
                self.board_centers25[oid]=(x,y)
                node=W.QGraphicsItemGroup(c._overlay_root21)
                node.setZValue(400)
                self.board_nodes25[oid]=node
                self.draw_face(oid,scaled_face(items,1.),lambda p:(p[0]-x,y-p[1]),
                               1.,0.,'fixed_board25',node)
        positions=self.board_positions25
        if positions is None or positions[0]!=app.zoom:
            scaled={oid:scaled_face(items,app.zoom) for oid,items in self.board_groups25.items()}
            self.board_positions25=positions=(app.zoom,layout_faces(scaled,pavement(app.scene),
                                                                      gap=1/max(.0001,app.zoom)))
        for oid,node in self.board_nodes25.items():
            x,y=self.board_centers25[oid]
            delta=positions[1].get(oid)
            node.setVisible(delta is not None)
            if delta is None:continue
            dx,dy=delta
            node.setPos(*app.screen((x+dx,y+dy)))
            node.setRotation(turn)

    def draw_signs(self):
        app=self.app
        c=app.canvas
        dark=app._dark_mode24
        if dark!=getattr(self,'badge_theme25',None):
            self.badge_theme25=dark
            self.badge.setStyleSheet('background:transparent;font-size:11px;color:'
                                     +('#bbdcee' if dark else '#25465b'))
        c.delete('sign_preview25')
        enlarge=app.scene.data['meta'].get('enlarge_boards23')
        turn=math.degrees(getattr(c,'rotation21_2',0))
        if enlarge:self.draw_fixed(turn)
        elif getattr(self,'board_source25',None) is not None:self.clear_fixed()
        if not self.active:return
        groups={}
        for item in app.render_items:
            board=item.get('sign_board21_2')
            if board is False or board is True and not enlarge:
                groups.setdefault(item['oid'],[]).append(item)
        for oid,items in groups.items():
            self.draw_face(oid,items,app.screen,app.zoom,turn,'sign_preview25')

    def viewport_input(self,event):
        kind = event.type()
        if kind==C.QEvent.Type.Paint:
            if self.timer.isActive():
                self.paint_count += 1
                self.frame_count += 1
        elif kind==C.QEvent.Type.Resize:
            self.place_badge()
        elif kind==C.QEvent.Type.MouseButtonPress and (
            event.button()==Qt.MouseButton.RightButton and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self.app.canvas.focus_set()
            self.drag = event.position().x(),self.app.canvas.__dict__.get('rotation21_2',0.)
            return True
        elif kind==C.QEvent.Type.MouseMove and self.drag is not None:
            start,angle = self.drag
            self.angle(angle+(event.position().x()-start)*.009)
            return True
        elif kind==C.QEvent.Type.MouseButtonRelease and self.drag is not None:
            if event.button()==Qt.MouseButton.RightButton:
                self.drag = None
                return True
        return False

    def angle(self,value):
        app = self.app
        center = self.viewport.rect().center()
        x,y = center.x(),center.y()
        point = app.world(x,y)
        app.canvas.rotation21_2 = math.remainder(value,math.tau)
        sx,sy = app.screen(point)
        app.origin[0] += x-sx
        app.origin[1] += y-sy
        app.redraw()

    def north(self):
        self.angle(math.radians(self.app.scene.data['meta'].get('grid_north_true_heading',0)))
        return 'break'

    def performance(self,enabled):
        if enabled:
            self.paint_count = 0
            self.last_sample = time.monotonic()
            self.badge.setText(tr('FPS —   内存 —'))
            self.place_badge()
            self.badge.show()
            self.timer.start()
        else:
            self.timer.stop()
            self.badge.hide()

    def place_badge(self):
        self.badge.adjustSize()
        self.badge.move(max(0,self.viewport.width()-self.badge.width()-8),
                        max(0,self.viewport.height()-self.badge.height()-3))
        self.badge.raise_()

    def sample(self):
        now = time.monotonic()
        fps = self.paint_count/max(.001,now-self.last_sample)
        self.last_sample,self.paint_count = now,0
        mem = memory_mib()
        usage = f'{mem:.0f} MiB' if mem is not None else '—'
        self.badge.setText(f'FPS {fps:.0f}   {tr("帧")} {self.frame_count}   {tr("内存")} {usage}')
        self.place_badge()
