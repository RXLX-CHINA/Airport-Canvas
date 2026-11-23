"""Airport Canvas 21: Qt shell with unchanged airport editing controllers."""
import sys
from contextlib import contextmanager
from interface_language import APPROACH_LEVELS, tr
from pathlib import Path
from qt_core21 import application
from qt_theme21 import apply
from airport_scene import AirportScene
from editor20_gui import Editor20
from view_tools21_2 import ViewTools, rotate

class AirportApp(Editor20):
    def __init__(self,scene=None):
        from user_settings34 import path,read,migrate
        import interface_language
        self._preferences34=path()
        migrate(self._preferences34)
        config=read(self._preferences34)
        interface_language.language=config.get('interface','language',fallback='zh_CN')
        interface_language.install_catalog(application())
        try:self._theme_preference=config.getboolean('display','dark_mode24',fallback=None)
        except ValueError:self._theme_preference=None
        apply();super().__init__(scene if scene is not None else AirportScene.load(Path(__file__).with_name('ZSQD.ACP')))
        try:self.gpu_requested=config.getboolean('display','gpu_viewport',fallback=False)
        except ValueError:self.gpu_requested=False
        self.gpu_active=self.canvas.enable_gpu49() if self.gpu_requested else False
        self.view_tools21_2 = ViewTools(self)
        from lighting_view import LightingView
        self.lighting_view = LightingView(self)
        from chart_view_f8 import ChartView
        self.chart_view = ChartView(self)
        from holding_point_boards import install as install_hp_boards
        install_hp_boards(self)
        from bitmap_layers46 import import_image,manage,install_drop_filter
        self._file_drop_filter=install_drop_filter(self)
        from PySide6.QtCore import Qt
        tree=self.tree.q
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.scene_display_menu)
        settings_menu=next((act.menu() for act in self.q.menuBar().actions()
                            if act.text().replace('&','') in ('设置',tr('设置'))),None)
        edit_menu=next((act.menu() for act in self.q.menuBar().actions()
                        if act.text().replace('&','') in ('编辑',tr('编辑'))),None)
        if edit_menu:
            from stand_row47 import StandRow
            edit_menu.addAction('批量绘制机位…',lambda:StandRow(self).start())
            from stand_names65 import show_stand_names
            edit_menu.addAction('机位命名…',lambda:show_stand_names(self))
        from palette_icons21 import install as install_palette_icons
        install_palette_icons(self)
        if settings_menu:
            from qt_core21 import G,W
            from user_settings34 import save_language
            menu=settings_menu.addMenu('语言 / Language')
            group=G.QActionGroup(menu)
            def choose_language(code):
                try:save_language(self._preferences34,code)
                except OSError as exc:
                    W.QMessageBox.warning(self.q,'Airport Canvas',str(exc))
                    return
                W.QMessageBox.information(self.q,'Airport Canvas',
                    interface_language.tr('设置保存后将于下次启动生效。'))
            for code,caption in (('zh_CN','简体中文'),('en','English')):
                action=menu.addAction(caption)
                group.addAction(action)
                action.setCheckable(True)
                action.setChecked(interface_language.language==code)
                action.triggered.connect(lambda checked,code=code:choose_language(code) if checked else None)
            settings_menu.addAction('统一道面与道肩颜色…',self.surface_colors)
            settings_menu.addAction('绘制工具预设…',self.edit_drawing_preset)
            gpu=settings_menu.addAction('OpenGL 画布（重启生效）')
            gpu.setCheckable(True);gpu.setChecked(self.gpu_requested)
            gpu.toggled.connect(self.set_gpu49)
        from PySide6.QtCore import QTimer
        from user_settings34 import path, read
        config=read(path())
        import json
        try:
            presets=json.loads(config.get('editing','drawing_presets',fallback='{}'))
            self.drawing_presets=presets if isinstance(presets,dict) else {}
        except ValueError:
            self.drawing_presets={}
        self.autosave_enabled=True
        self.autosave_minutes=5
        try:
            self.autosave_enabled=config.getboolean('editing','autosave',fallback=True)
            self.autosave_minutes=max(1,min(120,config.getint('editing','autosave_minutes',fallback=5)))
        except ValueError:
            pass
        self.autosave_timer=QTimer(self.q)
        self.autosave_timer.timeout.connect(self.autosave_project)
        self.configure_autosave()
        file_menu=self.q.menuBar().actions()[0].menu()
        self.recent_projects_menu=file_menu.addMenu('最近使用')
        self.recent_projects_menu.aboutToShow.connect(self.populate_recent_projects)
        file_menu.addSeparator()
        file_menu.addAction('导入位图…',lambda:import_image(self))
        file_menu.addAction('管理位图底图…',lambda:manage(self))
        from qt_core21 import G
        for name in ('AirportCanvas.ico','AirportCanvas.png'):
            icon=Path(__file__).with_name(name)
            if icon.is_file():
                self.q.setWindowIcon(G.QIcon(str(icon)))
                break
        area=self.q.screen().availableGeometry();self.q.setMinimumSize(min(1000,area.width()),min(640,area.height()));self.q.resize(min(self.q.width(),area.width()),min(self.q.height(),area.height()))
        from qt_compat import ttk
        toolbar = self.tool_buttons['SELECT'].master
        from PySide6.QtWidgets import QToolButton
        from stand_names65 import stand_overlap_icon
        overlap_button=ttk.Button(toolbar,command=self.start_stand_overlap)
        overlap_button.q.setIcon(stand_overlap_icon())
        overlap_button.q.setToolTip('编辑机位相交区域')
        overlap_button.q.setAccessibleName('编辑机位相交区域')
        overlap_button.q.setFixedSize(40,34)
        overlap_button.pack(side='left',before=self.no_entry_button,padx=4)
        outline=QToolButton(toolbar.q)
        outline.setText('描边')
        outline.setMenu(self.view_tools21_2.outlines_menu)
        outline.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.q.layout().addWidget(outline)
        ttk.Checkbutton(toolbar,text='连续绘制',variable=self.repeat).pack(side='left',padx=8)
        for button in toolbar.pack_slaves():
            if button.cget('image'):
                button.q.setFixedSize(40, 34)
        self.tool_body.q.setProperty('acRole','palette');self.property_title.q.setProperty('acRole','inspectorTitle')
        for child in self.winfo_children():
            if child._options.get('bg')=='#1b3048':
                child.q.setProperty('acRole','banner')
                child.q.setStyleSheet('')
                child.q.setContentsMargins(16,0,12,0)
                for label in child.winfo_children():
                    if 'AIRPORT CANVAS' in str(label.cget('text')):label.q.setStyleSheet('color:white;background:transparent;font-size:20px;font-weight:700;')
        from shortcuts21 import Shortcuts
        self.shortcuts21=Shortcuts(self)
        if settings_menu:settings_menu.addAction(tr('自定义快捷键…'),self.shortcuts21.dialog)
        if interface_language.language=='en':interface_language.install(self)
        self.shortcuts21.sync_captions()
        help_menu=next((action.menu() for action in self.q.menuBar().actions()
                        if action.text().replace('&','') in ('帮助',tr('帮助'))),None)
        if help_menu:
            help_menu.addAction(tr('软件许可证'),lambda:self.release_document('LICENSE.md',tr('软件许可证')))
            help_menu.addAction(tr('软件功能介绍'),self.feature_overview)
            help_menu.addAction(tr('快速入门'),self.quick_start)
            help_menu.addAction(tr('更新日志'),lambda:self.release_document('CHANGELOG.md',tr('更新日志')))
            help_menu.addAction(tr('关于 Airport Canvas'),self.show_release_about)

    def release_document(self,filename,title):
        from qt_manual21 import show
        return show(self,Path(__file__).with_name(filename),title)

    def quick_start(self):
        import interface_language
        return self.release_document('QUICK_START_EN.md' if interface_language.language=='en' else 'QUICK_START.md',
                                     tr('快速入门'))

    def feature_overview(self):
        import interface_language
        filename='FEATURES_EN.md' if interface_language.language=='en' else 'FEATURES.md'
        return self.release_document(filename,tr('软件功能介绍'))

    def show_release_about(self):
        import json
        from qt_core21 import W
        info=json.loads(Path(__file__).with_name('VERSION.json').read_text(encoding='utf8'))
        links=' | '.join(f'<a href="{url}">{name}</a>' for name,url in info['author_links'].items())
        W.QMessageBox.about(self.q,tr('关于 Airport Canvas'),f"<h3>Airport Canvas v{info['version']}</h3><p>{tr('作者')}  {info['author']}</p><p>{info['license']}</p><p>{links}</p>")

    def layer_menu_actions(self,menu,oid):
        from bitmap_layers46 import layers
        from scene_render import layer_ids
        bitmap_ids=layers(self.scene)
        owner=self.auto_assets.get(oid,{}).get('owner') or oid.split(':')[0]
        order=self.scene.data['meta'].get('draw_order',{})
        if oid in bitmap_ids:
            band='bitmap'
            owner=oid
            ids=[key for key in dict.fromkeys([*order.get(band,()),*bitmap_ids]) if key in bitmap_ids]
        else:
            band='surface'
            ids=layer_ids(self.render_items,self.auto_assets,band)
            if owner not in ids:
                band='object'
                ids=layer_ids(self.render_items,self.auto_assets,band)
        if owner not in ids:return {}
        current=ids.index(owner)
        actions={}
        for title,target in (('上移一层',current+1),('下移一层',current-1),
                             ('置于顶层',len(ids)-1),('置于底层',0)):
            action=menu.addAction(title)
            action.setEnabled(0<=target<len(ids) and target!=current)
            actions[action]=(band,ids,owner,target)
        return actions

    def apply_layer_order(self,band,ids,owner,target):
        reordered=list(ids)
        reordered.remove(owner)
        reordered.insert(target,owner)
        with self.scene.transaction('调整绘制图层'):
            self.scene.data['meta'].setdefault('draw_order',{})[band]=reordered
        self.refresh()

    def scene_display_menu(self,point):
        from PySide6.QtWidgets import QInputDialog,QMenu
        from bitmap_layers46 import layers
        native=self.tree.q
        item=native.itemAt(point)
        if item is None:return
        from PySide6.QtCore import Qt
        oid=item.data(0,Qt.ItemDataRole.UserRole)
        bitmaps=layers(self.scene)
        objects={**self.scene.assets,**self.scene.movements,**getattr(self,'auto_assets',{}),**bitmaps}
        if oid not in objects:return
        selected=set(self.tree.selection())
        canvas_selection=set(getattr(self,'selected_ids',()))
        if oid in canvas_selection:selected.update(canvas_selection)
        if oid not in selected:selected={oid}
        def kind(key):
            obj=objects[key]
            return (obj.get('kind') or obj.get('role') or 'BITMAP',obj.get('props',{}).get('mark_type'))
        ids=[key for key in selected if key in objects and kind(key)==kind(oid)
             and not bitmaps.get(key,{}).get('locked')]
        styles=self.scene.data['meta'].get('object_display',{})
        hidden=bool(styles.get(oid,{}).get('hidden'))
        menu=QMenu(native)
        toggle=menu.addAction('显示对象' if hidden else '隐藏对象')
        opacity=menu.addAction('设置透明度…')
        opacity.setEnabled(bool(ids))
        group=[key for key in ids if key in self.scene.assets or key in self.scene.movements]
        batch=menu.addAction('批量修改同类参数…')
        batch.setEnabled(len(group)>1)
        menu.addSeparator()
        ordering=self.layer_menu_actions(menu,oid)
        choice=menu.exec(native.viewport().mapToGlobal(point))
        if choice in ordering:
            self.apply_layer_order(*ordering[choice])
            return
        if choice==batch:
            self.batch_parameters(group,oid)
            return
        if choice not in (toggle,opacity):return
        if choice==opacity:
            initial=bitmaps.get(oid,{}).get('opacity',styles.get(oid,{}).get('opacity',1.))
            value,ok=QInputDialog.getInt(self.q,'对象透明度','透明度（%）',round(100*(1-initial)),0,100)
            if not ok:return
        with self.scene.transaction('更新对象显示'):
            styles=self.scene.data['meta'].setdefault('object_display',{})
            for key in (selected & objects.keys() if choice==toggle else ids):
                if choice==toggle:styles.setdefault(key,{})['hidden']=not hidden
                elif key in bitmaps:bitmaps[key]['opacity']=1-value/100
                else:styles.setdefault(key,{})['opacity']=1-value/100
        if choice==toggle and not hidden:self.select(None)
        self.refresh()

    def selected_batch_ids(self):
        def signature(oid):
            asset=self.scene.assets.get(oid)
            if asset:
                return ('asset',asset['kind'],asset['props'].get('mark_type'))
            movement=self.scene.movements.get(oid)
            if movement:
                return ('movement',movement.get('role'),movement.get('geometry'))
            return None
        selected=set(self.selected_ids)|set(self.tree.selection())
        kind=signature(self.selection)
        return sorted(oid for oid in selected if kind is not None and signature(oid)==kind)

    def batch_parameters(self,ids,primary):
        from PySide6.QtWidgets import QInputDialog
        values={aid:(self.scene.assets[aid]['props'] if aid in self.scene.assets else self.scene.movements[aid]) for aid in ids}
        fields={'道面宽度':'width','道肩宽度':'shoulder','转弯半径':'turn_radius',
                '转角半径':'corner_radius','线宽':'line_width','字高':'text_height',
                '翼展':'aircraft_span','飞机长度':'aircraft_length','安全间距':'safety_clearance',
                '引入线类型':'lead_type','引入线半径':'lead_radius','配备廊桥':'has_bridge',
                '显示安全线':'show_safety','显示边线':'edges_visible','显示中线':'center_visible'}
        from stand13 import WORK_ZONES59,NO_WORK_ZONE
        for label,key in (('作业区类型','work_zone'),('左侧作业区','work_zone_left'),
                          ('右侧作业区','work_zone_right'),('原廊桥侧作业区','work_zone_bridge_side')):
            fields[label]=key
        options={'lead_type':list('ABCD'),
                 **{k:list(WORK_ZONES59) for k in ('work_zone','work_zone_left','work_zone_right')},
                 'work_zone_bridge_side':[*WORK_ZONES59,NO_WORK_ZONE]}
        first=values.get(primary,next(iter(values.values())))
        labels=[]
        for label,key in fields.items():
            kind=type(first.get(key))
            allowed_types=(int,float) if kind in (int,float) else (kind,)
            if (kind in (float,int,bool) or key in options and kind is str) and all(
                    type(props.get(key)) in allowed_types for props in values.values()):
                labels.append(label)
        if not labels:
            self.status.set('所选对象没有可批量修改的共同参数。')
            return
        label,ok=QInputDialog.getItem(self.q,'批量修改同类参数','参数',labels,editable=False)
        if not ok:return
        key=fields[label]
        initial=first[key]
        if type(initial) is bool:
            choice,ok=QInputDialog.getItem(self.q,'批量修改同类参数',label,['关闭','开启'],int(initial),False)
            value=choice=='开启'
        elif key in options:
            allowed=options[key]
            value,ok=QInputDialog.getItem(self.q,'批量修改同类参数',label,allowed,
                                          allowed.index(initial) if initial in allowed else 0,False)
        else:
            value,ok=QInputDialog.getDouble(self.q,'批量修改同类参数',label+'（m）',initial,0,10000,3)
        if not ok:return
        try:
            with self.processing('正在批量更新参数'):
                with self.scene.transaction('批量修改同类参数'):
                    for aid in ids:
                        if aid in self.scene.assets:self.scene.update_asset(aid,props={key:value})
                        else:self.scene.update_movement(aid,**{key:value})
                self.refresh()
            self.status.set(f'已更新 {len(ids)} 个对象的{label}。')
        except ValueError as exc:self.status.set(str(exc))

    def set_gpu49(self,enabled):
        from user_settings34 import path,save
        self.gpu_requested=bool(enabled)
        try:
            save(self,path())
            self.status.set('OpenGL 画布设置已保存，重启生效。')
        except OSError as error:self.status.set(str(error))

    def preset_defaults(self,mode,current):
        from marking_catalog import CATALOG,EDITABLE_FIELDS
        defaults={}
        if mode.startswith('MARK:') and mode[5:] in CATALOG:
            spec=CATALOG[mode[5:]]
            defaults={key:value for key,value in spec['defaults'].items()
                      if key in EDITABLE_FIELDS.get(spec['shape'],()) and type(value) in (int,float,bool,str)}
        elif mode=='RUNWAY':defaults=dict(width=45.,shoulder=7.5)
        elif mode.startswith('APRON'):defaults=dict(width=1.)
        defaults.update(current)
        return defaults

    def draft_defaults11(self,mode):
        current=super().draft_defaults11(mode)
        variants=getattr(self,'drawing_presets',{})
        key=getattr(self,'_prefab19',None) or mode
        preset=variants.get(key)
        if isinstance(preset,dict) and preset:
            current=self.preset_defaults(mode,current)
            current.update(preset)
        return current

    def edit_drawing_preset(self):
        from PySide6.QtWidgets import QInputDialog,QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QCheckBox,QComboBox
        modes={str(button.cget('text'))+' · '+key:key for key,button in self.tool_buttons.items()
               if key not in ('SELECT','NODES','SPLIT7','TRUNCATE20_18','CONNECT','JUNCTION','BOX_SELECT','BREAK')}
        label,ok=QInputDialog.getItem(self.q,'绘制工具预设','工具',sorted(modes),editable=False)
        if not ok:return
        key=modes[label]
        mode='STAND' if key in ('AUX_STAND19','HANGAR19','REMOTE_STAND') else key
        values=self.preset_defaults(mode,super().draft_defaults11(mode))
        from stand13 import WORK_ZONES59,NO_WORK_ZONE
        from project10 import SUBTYPES
        if key=='REMOTE_STAND':
            values.pop('work_zone',None)
            values.update(has_bridge=False,work_zone_left=WORK_ZONES59[0],work_zone_right=WORK_ZONES59[0])
        elif key=='STAND':
            values.setdefault('work_zone_bridge_side',NO_WORK_ZONE)
        choices={'lead_type':list('ABCD'),'route_type':list(SUBTYPES),
                 'axis_side':['A','B','BOTH'] if key.startswith('MARK:') and key[5:] in __import__('roads10').ROAD_MARKS else ['CENTER','A','B','BOTH'],
                 'deice_crossfall_mode':['SINGLE','SYMMETRIC'],
                 'flow':['BOTH','FORWARD','REVERSE'],'closure_kind':['TEMPORARY','PERMANENT'],
                 'code_letter':list('ABCDEF'),'code_number':['1','2','3','4'],
                 'level_a':APPROACH_LEVELS,'level_b':APPROACH_LEVELS,
                 'enhanced_direction':['START','END'],'guidance':['GUIDED','UNGUIDED']}
        for field in ('work_zone','work_zone_left','work_zone_right','work_zone_bridge_side'):
            choices[field]=list(WORK_ZONES59)+( [NO_WORK_ZONE] if field=='work_zone_bridge_side' else [])
        values.update(self.drawing_presets.get(key,{}))
        if not values:
            self.status.set('此工具没有可预设的绘制参数。')
            return
        dialog=QDialog(self.q)
        dialog.setWindowTitle(label)
        form=QFormLayout(dialog)
        controls={}
        for field,value in values.items():
            if isinstance(value,bool):
                control=QCheckBox()
                control.setChecked(value)
            elif field in choices:
                control=QComboBox()
                options=choices[field]
                if isinstance(options,dict):
                    for code,caption in options.items():control.addItem(tr(caption),code)
                    control.setCurrentIndex(max(0,control.findData(str(value))))
                else:
                    control.addItems(options)
                    control.setCurrentText(str(value))
            else:
                control=QLineEdit(str(value))
            form.addRow(field,control)
            controls[field]=control
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if not dialog.exec():return
        parsed={}
        try:
            for field,control in controls.items():
                if isinstance(control,QCheckBox):
                    parsed[field]=control.isChecked()
                elif isinstance(control,QComboBox):
                    parsed[field]=control.currentData() or control.currentText()
                else:
                    parsed[field]=type(values[field])(control.text().strip())
            self.drawing_presets[key]=parsed
            from user_settings34 import path,save
            save(self,path())
            self.status.set('已保存绘制工具预设。')
        except (ValueError,OSError) as error:self.status.set('无法保存预设 '+str(error))

    def surface_colors(self):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog,QDialog,QDialogButtonBox,QFormLayout,QPushButton
        from scene_render import COLORS
        dialog=QDialog(self.q)
        dialog.setWindowTitle('统一道面与道肩颜色')
        form=QFormLayout(dialog)
        original=self.scene.data['meta'].get('surface_colors',{})
        colors=dict(original)
        for key,title in (('runway','跑道'),('taxiway','滑行道'),('apron','机坪')):
            for part,label,default in (('surface','道面',COLORS[key]),('shoulder','道肩',COLORS['shoulder'])):
                field=key+'_'+part
                button=QPushButton(colors.get(field,default),dialog)
                def choose(checked=False,field=field,button=button):
                    color=QColorDialog.getColor(QColor(button.text()),dialog)
                    if color.isValid():
                        colors[field]=color.name()
                        button.setText(colors[field])
                button.clicked.connect(choose)
                form.addRow(title+label,button)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Reset)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(lambda:(colors.clear(),dialog.accept()))
        form.addRow(buttons)
        if dialog.exec() and colors!=original:
            with self.scene.transaction('调整统一道面颜色'):
                self.scene.data['meta']['surface_colors']=colors
            self.refresh()

    def configure_autosave(self):
        self.autosave_timer.stop()
        if self.autosave_enabled:self.autosave_timer.start(self.autosave_minutes*60_000)

    def populate_recent_projects(self):
        from user_settings34 import recent_projects
        menu=self.recent_projects_menu
        menu.clear()
        history=recent_projects(self._preferences34)
        if not history:
            menu.addAction('暂无最近项目').setEnabled(False)
        for filename in history:
            project=Path(filename)
            action=menu.addAction(filename.replace('&','&&'))
            action.setEnabled(project.is_file())
            action.triggered.connect(lambda checked=False,p=project:self.open(p))

    def remember_current_project(self):
        from user_settings34 import remember_project
        if self.filepath is None:return
        try:remember_project(self._preferences34,self.filepath)
        except OSError as exc:self.status.set('无法更新最近使用记录：'+str(exc))

    @contextmanager
    def opening_project(self, filename):
        from qt_core21 import C,W,Qt
        text = tr(f'正在导入“{Path(filename).name}”……')
        viewport = self.canvas.q.viewport()
        badge = W.QLabel(text,viewport)
        badge.setTextFormat(Qt.TextFormat.PlainText)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setAccessibleName(text)
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        badge.setStyleSheet('QLabel { background:#1b3048; color:#f4f8fc; border:1px solid #69879c;'
                            'border-radius:9px; padding:16px; font-weight:600; }')
        width = max(1,min(viewport.width()-32,badge.sizeHint().width()))
        badge.setText(badge.fontMetrics().elidedText(text,Qt.TextElideMode.ElideMiddle,max(1,width-34)))
        badge.setFixedWidth(width)
        badge.adjustSize()
        badge.move((viewport.width()-badge.width())//2,(viewport.height()-badge.height())//2)
        with self.processing(text):
            badge.show()
            badge.raise_()
            badge.repaint()
            W.QApplication.processEvents(C.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            try:
                yield
            finally:
                badge.hide()
                badge.deleteLater()

    def open(self,filename=None):
        previous=self.scene
        result=super().open(filename)
        if self.scene is not previous:
            self.remember_current_project()
            from user_settings34 import remember_directory
            try:remember_directory(self._preferences34,'open',self.filepath)
            except OSError as exc:self.status.set(tr('无法保存习惯设置：'+str(exc)))
        return result

    def save(self,save_as=False):
        result=super().save(save_as)
        if result:self.remember_current_project()
        return result

    def autosave_project(self):
        import json
        from user_settings34 import path
        if not self.autosave_enabled or getattr(self,'drag',None) or getattr(self,'_processing_tasks',None):
            return
        if json.dumps(self.scene.data,sort_keys=True)==self.saved:
            return
        original=self.filepath
        target=(original.with_name(original.stem+'.autosave.ACP') if original and not original.stem.endswith('.autosave')
                else path().parent/'Untitled.autosave.ACP')
        try:
            target.parent.mkdir(parents=True,exist_ok=True)
            self.scene.save(target)
            self.status.set('自动保存副本 '+str(target))
        except (OSError,ValueError) as exc:
            self.status.set('自动保存失败 '+str(exc))

    def confirm_leave(self):
        data=self.scene.data
        if self.filepath is None and not any(data.get(key) for key in ('assets','movements','groups','bitmap_layers')):
            return True
        return super().confirm_leave()

    def close(self):
        if not self.confirm_leave():return
        filename=self.__dict__.get('_preferences34')
        if filename:
            from user_settings34 import save
            try:save(self,filename)
            except OSError as exc:
                import warnings
                warnings.warn(f'无法保存习惯设置：{exc}',RuntimeWarning)
        self.destroy()
        if self.__dict__.get('_owns_mainloop'):application().quit()

    def destroy(self):
        if self._destroyed:return
        lighting=self.__dict__.get('lighting_view')
        if lighting and lighting.active:lighting.leave(redraw=False)
        localizer=self.__dict__.pop('_interface_localizer',None)
        if localizer:application().removeEventFilter(localizer)
        timer=self.__dict__.get('autosave_timer')
        if timer:timer.stop()
        export=self.__dict__.get('_export_cancel')
        if export:export.set()
        super().destroy()

    def undo(self):
        with self.processing('正在撤销并重建机场图'):
            return super().undo()

    def redo(self):
        with self.processing('正在重做并重建机场图'):
            return super().redo()

    def no_entry_dialog20(self):
        from dialogs31 import no_entry_settings
        return no_entry_settings(self)

    def open_review(self):
        from dialogs31 import review
        return review(self)

    def world(self,x,y):
        angle = getattr(getattr(self,'canvas',None),'rotation21_2',0.)
        if not angle:return super().world(x,y)
        dx,dy = rotate(x-self.origin[0],y-self.origin[1],-angle)
        return [dx/self.zoom,-dy/self.zoom]

    def screen(self,p):
        angle = getattr(getattr(self,'canvas',None),'rotation21_2',0.)
        if not angle:return super().screen(p)
        dx,dy = rotate(p[0]*self.zoom,-p[1]*self.zoom,angle)
        return [self.origin[0]+dx,self.origin[1]+dy]

    def fit(self):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active:
            chart.ensure()
            items=chart.items
        else:
            items=self.__dict__.get('render_items',())
        import chart_f8
        from bitmap_layers46 import layers, corners
        rows=list(items)
        if not (chart and chart.active):
            hidden=self.scene.data['meta'].get('object_display',{})
            rows.extend({'points':corners(layer)} for oid,layer in layers(self.scene).items()
                        if not hidden.get(oid,{}).get('hidden'))
        angle=getattr(self.canvas,'rotation21_2',0.)
        points=[rotate(x,-y,angle) for row in rows for x,y in row['points']]
        x0,y0,x1,y1=chart_f8.chart_extent([{'points':points}])
        w,h=max(50,self.canvas.winfo_width()),max(50,self.canvas.winfo_height())
        self.zoom=min((w-32)/max(1,x1-x0),(h-32)/max(1,y1-y0))
        self.origin=[w/2-(x0+x1)/2*self.zoom,h/2-(y0+y1)/2*self.zoom]
        self.redraw()

    def finish_draw(self):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active:return chart.finish()
        return super().finish_draw()

    def tree_select(self,event=None):
        if not self._syncing_tree and self.tree.selection():
            from bitmap_layers46 import layers
            oid=self.tree.selection()[0]
            if oid in layers(self.scene):
                if oid!=self.__dict__.get('_bitmap_selection46'):
                    self.select_bitmap46(oid)
                return
        return super().tree_select(event)

    def select_bitmap46(self,oid):
        from bitmap_layers46 import layers
        row=layers(self.scene).get(oid)
        self.select(None)
        self._bitmap_selection46=oid if row else None
        self.sync_tree()
        if row and self.tree.exists(oid):
            self._syncing_tree=True
            try:
                self.tree.selection_set(oid)
                self.tree.see(oid)
            finally:
                self._syncing_tree=False
        self.update_inspector()
        self.redraw()

    def select(self,oid):
        if self.__dict__.pop('_bitmap_selection46',None):
            self._selected_form=object()
        return super().select(oid)

    def start_stand_overlap(self):
        self.set_mode('SELECT')
        if self._color17:self.toggle_color17()
        self.selected_ids=set()
        self.select(None)
        self._stand_overlap_scene=self.scene
        self._stand_overlap_pairs=set()
        self.redraw()
        self.update_inspector()
        self.status.set('点击高亮的机位相交区，在右侧选择处理方式。按 Esc 退出。')

    def stand_overlap_active(self):
        return self.__dict__.get('_stand_overlap_scene') is self.scene

    def stand_overlap_regions(self):
        from stand_overlap9 import overlap_regions
        key=(self.scene,self.scene.revision,id(self.auto_assets))
        cache=self.__dict__.get('_stand_overlap_cache')
        if not cache or cache[0]!=key:
            cache=self._stand_overlap_cache=(key,overlap_regions(self.scene,self.auto_assets))
        return cache[1]

    def draw_stand_overlap_regions(self):
        from geometry11 import polygons
        self.canvas.delete('stand_overlap_regions')
        if not self.stand_overlap_active():return
        for key,shape in self.stand_overlap_regions().items():
            selected=key in self._stand_overlap_pairs
            color='#f4a832' if selected else '#28bddb'
            for area in polygons(shape):
                coords=[v for q in area.exterior.coords for v in self.screen(q)]
                self.canvas.create_polygon(*coords,fill=color,fill_alpha=.32 if selected else .20,
                                           outline=color,width=2,tags='stand_overlap_regions')
        self.canvas.tag_raise('stand_overlap_regions')

    def set_stand_overlap_style(self,selected,merged):
        if not self.stand_overlap_active():return
        selected=selected.intersection(self.stand_overlap_regions())
        if not selected:return
        with self.scene.transaction('编辑机位相交区域'):
            pairs=self.scene.data['meta'].setdefault('merged_stand_overlaps',{})
            for pair in selected:
                if merged:pairs[pair]=True
                else:pairs.pop(pair,None)
        self.refresh()

    def stand_overlap_inspector(self):
        from qt_compat import ttk
        from property_rows import next_row
        panel=self.section('机位相交区域')
        regions=self.stand_overlap_regions()
        selected=self._stand_overlap_pairs.intersection(regions)
        if not selected:
            message='点击区域选中，按住 Ctrl 可多选。' if regions else '当前没有相交的机位安全线区域。'
            ttk.Label(panel,text=tr(message),wraplength=235).grid(row=next_row(panel),column=0,columnspan=2,sticky='w')
            return
        if len(selected)==1:
            caption=' / '.join(self.scene.assets[aid]['name'] for aid in next(iter(selected)).split('|'))
        else:
            caption=tr('已选区域数')+'  '+str(len(selected))
        ttk.Label(panel,text=caption).grid(row=next_row(panel),column=0,columnspan=2,sticky='w')
        for merged,label in ((False,'应用斜线阴影'),(True,'应用机位合并')):
            ttk.Button(panel,text=tr(label),
                       command=lambda mode=merged:self.set_stand_overlap_style(selected,mode)).grid(
                           row=next_row(panel),column=0,columnspan=2,sticky='ew')

    def update_inspector(self):
        super().update_inspector()
        if self.stand_overlap_active():return self.stand_overlap_inspector()
        ids=self.selected_batch_ids()
        if len(ids)>1:
            from qt_compat import ttk
            panel=self.section('多选')
            from property_rows import next_row
            ttk.Button(panel,text=f'批量修改参数（{len(ids)} 个）',
                       command=lambda:self.batch_parameters(ids,self.selection)).grid(
                           row=next_row(panel),column=0,columnspan=2,sticky='ew')
            self.ensure_book15().tidy()
        if len(ids)==1 and self.scene.assets.get(self.selection,{}).get('kind')=='RUNWAY':
            props=self.scene.assets[self.selection]['props']
            elevation=self.section('跑道端海拔')
            for end in ('a','b'):
                self.property_field(elevation,'elevation_'+end,
                                    tr('跑道端海拔 (m，可空)')+' '+end.upper(),
                                    props.get('elevation_'+end),'float')
            self.property_field(elevation,'elevation_unit',tr('海拔标注单位'),
                                props.get('elevation_unit','m'),'text',['m','ft'])
            from qt_compat import ttk
            panel=self.section('PAPI')
            ttk.Button(panel,text=tr('PAPI 灯设置…'),command=self.configure_papi).grid(
                row=0,column=0,columnspan=2,sticky='ew')
        oid=self.__dict__.get('_bitmap_selection46')
        if not oid:return
        from bitmap_layers46 import inspector,layers
        row=layers(self.scene).get(oid)
        if not row or self.selection:
            self._bitmap_selection46=None
            return
        inspector(self,oid)

    def pick(self,point,paths_only=False):
        hit=super().pick(point,paths_only)
        if not hit or paths_only or self.mode not in ('SELECT','NODES'):return hit
        oid=hit[1]
        owner=self.auto_assets.get(oid,{}).get('owner') or oid.split(':')[0]
        styles=self.scene.data['meta'].get('object_display',{})
        if any(styles.get(key,{}).get('hidden') or styles.get(key,{}).get('opacity')==0 for key in (oid,owner)):
            return None
        return hit

    def click(self,event):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active and not self._space11:return chart.click(event)
        lighting = self.__dict__.get('lighting_view')
        if lighting and lighting.active and not self._space11:
            return lighting.click(event)
        if self.stand_overlap_active() and not self._space11:
            from geometry11 import Point
            point=Point(self.world(event.x,event.y))
            hits=[(shape.area,key) for key,shape in self.stand_overlap_regions().items() if shape.covers(point)]
            pair=min(hits)[1] if hits else None
            if getattr(event,'state',0)&0x0004:
                if pair:self._stand_overlap_pairs.symmetric_difference_update({pair})
            else:
                self._stand_overlap_pairs={pair} if pair else set()
            self.update_inspector()
            self.draw_stand_overlap_regions()
            return 'break'
        row=self.__dict__.get('_stand_row')
        if row and not self._space11:return row.click(event)
        if self.mode=='SELECT' and not self._space11 and getattr(event,'state',0)&4:
            oid=self.selection
            movement=self.scene.movements.get(oid)
            if movement and not movement.get('legacy_attachment'):
                import copy
                point=self.world(event.x,event.y)
                import scene_geometry as g
                if g.project(self.scene.movement_path(oid),point)[0]<=8/max(.001,self.zoom):
                    self._connector_drag48=(oid,point,copy.deepcopy(movement))
                    return 'break'
            asset=self.scene.assets.get(oid,{})
            props=asset.get('props',{})
            if asset.get('kind')=='STAND' and props.get('entry_attached',True) and props.get('entry_asset'):
                from model20 import axis
                import scene_geometry as g
                point=self.world(event.x,event.y)
                parent=axis(self.scene,props['entry_asset'])
                if parent and g.project(asset['points'],point)[0]<=10/max(.001,self.zoom):
                    self._connector_drag48=(oid,point,None)
                    return 'break'
        tools = self.__dict__.get('view_tools21_2')
        if tools and (tools.active or tools.drawing) and not self._space11:
            return tools.click(event)
        if (self.mode=='SELECT' and not self._space11 and not getattr(event,'state',0)&5
                and not self.selection and not getattr(self,'selected_ids',None)
                and 'canvas' in self.__dict__):
            from bitmap_layers46 import layers,contains
            records=layers(self.scene)
            if records:
                point=self.world(event.x,event.y)
                oid=next((key for key,row in reversed(list(records.items()))
                          if not row['locked'] and row['opacity']>0 and contains(row,point)
                          and not self.scene.data['meta'].get('object_display',{}).get(key,{}).get('hidden')),None)
                if oid and not self.pick(point):
                    self.select_bitmap46(oid)
                    self._bitmap_drag55=(self.scene,oid,point,(records[oid]["x"],records[oid]["y"]))
                    return 'break'
        if self.mode=='NODES' and not self._space11:
            import math
            runway=self.scene.assets.get(self.selection)
            if runway and runway['kind']=='RUNWAY':
                index=min(range(2),key=lambda i:math.dist(self.screen(runway['points'][i]),(event.x,event.y)))
                if math.dist(self.screen(runway['points'][index]),(event.x,event.y))<=10:
                    self.runway_drag=(runway['id'],index)
                    return 'break'
            hit=self.pick(self.world(event.x,event.y))
            if hit and self.scene.assets.get(hit[1],{}).get('kind')=='RUNWAY':
                self.select(hit[1])
                self.redraw()
                return 'break'
        return super().click(event)

    def bound_stand_target49(self,oid,start,pointer):
        from model20 import axis
        import scene_geometry as g
        stand=self.scene.assets[oid]
        parent=axis(self.scene,stand['props']['entry_asset'])
        root=stand['points'][0]
        target=g.project(parent['points'],[root[i]+pointer[i]-start[i] for i in (0,1)])[2]
        return [[q[i]+target[i]-root[i] for i in (0,1)] for q in stand['points']]

    def bitmap_drag_position(self,event,drag):
        _,_,start,center=drag
        point=self.world(event.x,event.y)
        return tuple(c+p-q for c,p,q in zip(center,point,start))

    def cancel_bitmap_drag(self):
        drag=self.__dict__.pop('_bitmap_drag55',None)
        if drag:
            from bitmap_layers46 import draw
            draw(self)
        return bool(drag)

    def motion(self,event):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active and not (self._pan11 or self._space11):
            return chart.drag_symbol(event)
        lighting = self.__dict__.get('lighting_view')
        if lighting and lighting.active and not self._pan11:
            return 'break'
        drag=self.__dict__.get('_bitmap_drag55')
        if drag:
            item=self._bitmap_items.get(drag[1])
            if item and self.scene is drag[0]:
                item[0].setPos(*self.bitmap_drag_position(event,drag))
            return 'break'
        bound=self.__dict__.get('_connector_drag48')
        if bound:
            from connector_drag48 import connector_ports
            oid,start,original=bound
            if original is None:
                pts=self.bound_stand_target49(oid,start,self.world(event.x,event.y))
            else:
                _,_,delta,end=connector_ports(self.scene,oid,self.world(event.x,event.y),start,original)
                pts=self.scene.movement_path(oid)
                pts=[[p[i]+delta[i] for i in (0,1)] for p in pts]
                pts[-1]=end
            self.canvas.delete('bound_preview48')
            self.canvas.create_line(*[n for p in pts for n in self.screen(p)],fill='#25bbd0',width=3,tags='bound_preview48')
            return 'break'
        drag=self.__dict__.get('runway_drag')
        if not drag:return super().motion(event)
        oid,index=drag
        points=list(self.scene.assets[oid]['points'])
        points[index]=self.world(event.x,event.y)
        self.canvas.delete('runway_drag')
        self.canvas.create_line(*[v for p in points for v in self.screen(p)],
                                fill='#25bbd0',width=3,tags='runway_drag')

    def release(self,event):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active and not (self._pan11 or self._space11):
            return chart.release_symbol(event)
        lighting = self.__dict__.get('lighting_view')
        if lighting and lighting.active and not self._pan11:
            return 'break'
        bound=self.__dict__.pop('_connector_drag48',None)
        if bound:
            from connector_drag48 import connector_ports,slide_connector
            oid,start,original=bound
            self.canvas.delete('bound_preview48')
            point=self.world(event.x,event.y)
            if max(abs(p-q) for p,q in zip(point,start))*self.zoom<=3:
                return super().click(event)
            try:
                with self.processing('正在重算连接道'):
                    if original is None:
                        self.scene.update_asset(oid,points=self.bound_stand_target49(oid,start,point))
                    else:
                        a,b,delta,_=connector_ports(self.scene,oid,point,start,original)
                        slide_connector(self.scene,oid,(a,b),delta)
                    self.refresh()
            except ValueError as error:self.status.set(str(error))
            return 'break'
        bitmap=self.__dict__.pop('_bitmap_drag55',None)
        if bitmap:
            from bitmap_layers46 import layers,update
            scene,oid,start,center=bitmap
            if self.scene is scene and oid in layers(scene):
                x,y=self.bitmap_drag_position(event,bitmap)
                if max(abs(x-center[0]),abs(y-center[1]))*self.zoom>=2:
                    update(scene,oid,x=x,y=y)
                    self.update_inspector()
                    self.update_title()
            self.redraw()
            return 'break' 
        drag=self.__dict__.pop('runway_drag',None)
        if not drag:return super().release(event)
        self.canvas.delete('runway_drag')
        oid,index=drag
        points=list(self.scene.assets[oid]['points'])
        points[index]=self.world(event.x,event.y)
        try:
            self.scene.update_asset(oid,points=points)
            self.refresh()
        except ValueError as exc:
            self.status.set(str(exc))

    def pointer(self,event):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active and not (self._pan11 or self._space11):
            return chart.pointer(event)
        row=self.__dict__.get('_stand_row')
        if row and not self._space11:
            row.preview(event)
            return
        if self.mode=='STOPWAY':
            from pavement10 import snap_stopway
            self.canvas.delete('stopway_snap34')
            hit=snap_stopway(self.scene,self.world(event.x,event.y),self.zoom)
            if hit:
                _,aid,end,q=hit
                runway=self.scene.assets[aid]
                import scene_geometry as g
                u=g.unit(*runway['points'])
                sign=-1 if end=='a' else 1
                length=runway['props'].get('stopway_'+end,0) or 90.
                tip=[q[k]+sign*u[k]*length for k in (0,1)]
                points=g.rectangle([q,tip],runway['props']['width'])
                self.canvas.create_polygon(*[v for p in points for v in self.screen(p)],
                                           outline='#35bbd3',fill='',width=2,dash=(5,4),tags='stopway_snap34')
                x,y=self.screen(q)
                self.canvas.create_text(x,y-14,text=f'已吸附跑道端头 · {length:g} m',
                                        fill='#35bbd3',tags='stopway_snap34')
            return 'break'
        tools=self.__dict__.get('view_tools21_2')
        if tools and (tools.active or tools.drawing):
            tools.pointer(event)
        return super().pointer(event)

    def cancel_action(self,event=None):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active:
            chart.cancel_symbol_drag()
            if chart.tool:chart.choose(None)
            else:
                chart.selected=None
                chart.properties()
                chart.selection_frame()
            return 'break'
        lighting = self.__dict__.get('lighting_view')
        if lighting and lighting.active:
            lighting.choose(None)
            return 'break'
        if self.stand_overlap_active():
            self.set_mode('SELECT')
            return 'break'
        if self.cancel_bitmap_drag():return 'break'
        if self.__dict__.pop('_connector_drag48',None):
            self.canvas.delete('bound_preview48')
            return 'break'
        row=self.__dict__.get('_stand_row')
        if row:
            row.stop()
            return 'break'
        if self.__dict__.pop('runway_drag',None):
            self.canvas.delete('runway_drag')
            return 'break'
        tools = self.__dict__.get('view_tools21_2')
        if tools and (tools.active or tools.drawing):
            if tools.anchor:tools.reset_anchor()
            else:tools.exit()
            return 'break'
        if getattr(event,'num',0)==3 and self.mode=='SELECT' and not self.gesture11():
            hit=self.pick(self.world(event.x,event.y))
            if hit:
                from PySide6.QtCore import QPoint
                from PySide6.QtWidgets import QMenu
                menu=QMenu(self.q)
                ordering=self.layer_menu_actions(menu,hit[1])
                if ordering:
                    choice=menu.exec(QPoint(event.x_root,event.y_root))
                    if choice in ordering:self.apply_layer_order(*ordering[choice])
                    return 'break'
        return super().cancel_action(event)

    def set_mode(self,mode):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active:chart.leave(redraw=False)
        lighting = self.__dict__.get('lighting_view')
        if lighting and lighting.active:
            lighting.leave()
        self.__dict__.pop('_stand_overlap_scene',None)
        if hasattr(self,'canvas'):self.canvas.delete('stand_overlap_regions')
        self.cancel_bitmap_drag()
        row=self.__dict__.get('_stand_row')
        if row:row.stop()
        if hasattr(self,'canvas'):self.canvas.delete('stopway_snap34')
        tools = self.__dict__.get('view_tools21_2')
        if tools and mode.startswith('SIGN23:'):
            super().set_mode('SELECT')
            tools.start(mode.partition(':')[2])
            return 'break'
        if tools and (tools.active or tools.drawing):tools.exit()
        return super().set_mode(mode)

    def toggle_color17(self,*args):
        chart=self.__dict__.get('chart_view')
        if chart and chart.active:chart.leave(redraw=False)
        lighting = self.__dict__.get('lighting_view')
        if lighting and lighting.active:
            lighting.leave(redraw=False)
        if self.stand_overlap_active():self.set_mode('SELECT')
        tools = self.__dict__.get('view_tools21_2')
        if tools and (tools.active or tools.drawing):tools.exit()
        with self.processing('正在切换机场图显示模式'):
            return super().toggle_color17(*args)

    def dark_mode_enabled(self):
        preference=getattr(self,'_theme_preference',None)
        if preference is not None:return preference
        return bool(self.scene.data['meta'].get('dark_mode24',False))

    def set_dark_mode(self,enabled):
        from user_settings34 import save_theme
        self._theme_preference=bool(enabled)
        try:save_theme(self._preferences34,self._theme_preference)
        except OSError as error:self.status.set(f'无法保存深色模式设置：{error}')
        self.redraw()

    def redraw(self):
        tools = self.__dict__.get('view_tools21_2')
        f5=bool(tools and tools.active)
        if 'canvas' in self.__dict__:
            from qt_theme21 import window_theme
            window_theme(self,self.dark_mode_enabled())
        lighting = self.__dict__.get('lighting_view')
        if lighting and lighting.active:
            lighting.redraw()
            self.update_minimap()
            return
        chart=self.__dict__.get('chart_view')
        if chart and chart.active:
            chart.redraw()
            self.update_minimap()
            return
        if (f5 or self._color17) and 'canvas' in self.__dict__:
            self.canvas.camera21(self.origin,self.zoom)
        if f5:
            color=self._color17
            self._color17=True
            try:super().redraw()
            finally:self._color17=color
        else:super().redraw()
        if f5 or self._color17:self.update_minimap()
        if tools:
            tools.draw_signs()
            if f5 or tools.drawing:tools.render_anchor()
            mark=self.scene.assets.get(self.selection) or self.auto_assets.get(self.selection)
            if self.mode=='SELECT' and mark and mark['props'].get('information_profile20_18')=='BOARD':
                if len(getattr(self,'selected_ids',()))<=1:
                    screen_box=self.canvas.bbox('owner:'+self.selection,visible_only=True)
                    if screen_box:
                        self.draw_frame11(screen_box=screen_box)
                        self.canvas.tag_raise('frame11')
                    else:
                        self.canvas.delete('frame11')
                        self._frame_box11=None
        if 'canvas' in self.__dict__:
            self.canvas.delete('runway_nodes')
            runway=self.scene.assets.get(self.selection)
            if self.mode=='NODES' and runway and runway['kind']=='RUNWAY':
                for point in runway['points']:
                    x,y=self.screen(point)
                    self.canvas.create_oval(x-5,y-5,x+5,y+5,fill='#5de4ef',outline='#193942',
                                            width=2,tags='runway_nodes')
            from bitmap_layers46 import draw
            draw(self)
            self.draw_stand_overlap_regions()
            self.draw_compass23()
            self.canvas.tag_raise('view_mode18')

    def draw_compass23(self):
        import math
        c=self.canvas
        c.delete('north23')
        meta=self.scene.data['meta']
        from qt_core21 import C
        transform=c.q.viewportTransform()
        origin=transform.map(C.QPointF())
        bearing=math.radians(-meta.get('grid_north_true_heading',0))
        north=transform.map(C.QPointF(math.sin(bearing),math.cos(bearing)))-origin
        true=math.atan2(north.x(),-north.y())
        decl=meta.get('magnetic_declination') or 0
        marks=[
            ('真北',true,'#a9def0' if self._dark_mode24 else '#224e68'),
            ('磁北',true+math.radians(decl),'#e8af77' if self._dark_mode24 else '#9c5920'),
        ]
        for i,(label,angle,color) in enumerate(marks):
            x,y=c.winfo_width()-128+78*i,80
            c.create_line(x,y,x+math.sin(angle)*17,y-math.cos(angle)*17,arrow='last',fill=color,width=2,tags='north23')
            caption=C.QCoreApplication.translate('CanvasCompass',label)
            c.create_text(x,y+26,text=caption,fill=color,font=('Microsoft YaHei',8),tags='north23')

    def update_title(self):
        super().update_title();self.q.setWindowTitle(self.q.windowTitle().replace('20.18','v1.0.1'))
    def demo10(self):
        previous=self.scene
        super().open(Path(__file__).with_name('ZSQD.ACP'))
        if self.scene is not previous:
            self.filepath=None
            self.update_title()

    def configure_papi(self):
        from qt_core21 import W
        runway=self.scene.assets.get(self.selection,{})
        if runway.get('kind')!='RUNWAY':
            W.QMessageBox.information(self.q, tr('PAPI 灯设置…'), tr('请先选择跑道'))
            return
        dialog=W.QDialog(self.q)
        dialog.setWindowTitle('PAPI')
        form=W.QFormLayout(dialog)
        controls={}
        for end in ('a','b'):
            stored=runway['props'].get('papi',{}).get(end,{})
            role=W.QComboBox()
            for code,label in [('off','关闭'),('left','左侧'),('right','右侧'),('both','两侧')]:
                role.addItem(tr(label),code)
            role.setCurrentIndex(max(0,role.findData(stored.get('side','off'))))
            offset=W.QDoubleSpinBox()
            offset.setRange(1,500)
            offset.setSuffix(' m')
            offset.setValue(stored.get('offset',15))
            station=W.QDoubleSpinBox()
            station.setRange(0,__import__('scene_geometry').length(runway['points']))
            station.setSuffix(' m')
            station.setValue(stored.get('station',300))
            form.addRow(runway['props'].get('label_'+end,end.upper()),role)
            form.addRow(tr('距跑道边缘'),offset)
            form.addRow(tr('距跑道端'),station)
            controls[end]=(role,offset,station)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Ok|W.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec():
            with self.scene.transaction('PAPI'):
                runway['props']['papi']={end:dict(side=role.currentData(),offset=offset.value(),station=station.value())
                                          for end,(role,offset,station) in controls.items()}
            self.refresh()

    def frame11(self):
        roots=self.selected_roots11()
        if not roots:return roots,[],None
        tools = self.__dict__.get('view_tools21_2')
        positions = getattr(tools,'board_positions25',None)
        if positions and len(roots)==1:
            oid = next(iter(roots))
            group = getattr(tools,'board_groups25',{}).get(oid)
            if group and oid in positions[1] and oid.startswith('AUTO:'):
                from boards24 import scaled_face,shift_face
                from transform11 import bounds
                items = shift_face(scaled_face(group,self.zoom),positions[1][oid])
                return roots,items,bounds(items)
        key=(id(self.scene.data),self.scene.revision,frozenset(roots),id(self.render_items),id(self.auto_assets),self.__dict__.get('_child13',False))
        cached=self.__dict__.get('_frame_cache21')
        if not cached or cached[0]!=key:cached=(key,super().frame11());self._frame_cache21=cached
        return cached[1]

def main():
    application()
    args=sys.argv[1:]
    from user_settings34 import path,read,apply_scene,apply_window,migrate
    filename=path()
    migrate(filename)
    config=read(filename)
    scene=AirportScene()
    apply_scene(scene,config)
    app=AirportApp(scene)
    app._preferences34=filename
    apply_window(app,config)
    if args and args!=['--blank']:
        from qt_core21 import C
        C.QTimer.singleShot(0,lambda:app.open(Path(args[0]).resolve()))
    return app.mainloop()
if __name__=='__main__':main()
