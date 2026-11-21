"""Responsive scene editor: retained vectors, debounced forms, dependency jobs."""
import copy
from contextlib import contextmanager
import math
import time
from concurrent.futures import ThreadPoolExecutor
import qt_compat as tk
from qt_compat import ttk
from editor_gui import EditorApp
from airport_scene import AirportScene,PATH_KINDS,AREA_KINDS
from legacy_gui import NAMES,ROLE_NAMES
from automatic_markings import generated_markings,update_generated,detach_generated
from scene_hierarchy import all_objects,parent_of,descendants,CONTAINERS
from pavement_geometry import crossings,route_objects
from route_geometry import configure_rapid,rapid_layout
from scene_render import display_list
from scene_rules import validate_scene
from qt_renderer21 import CanvasRenderer
from marking_catalog import CATALOG,primitives
import scene_geometry as g


def live_demo():
    scene=AirportScene.demo();scene.data['meta']['name']='实时编辑示例 · 快速出口 / 机位 / 自动标记'
    mid=next(k for k,m in scene.movements.items() if m['role']=='EXIT_ONLY')
    configure_rapid(scene,mid,exit_angle=30.,exit_radius=550.,join_radius=25.,name='A2 快速出口：圆弧＋直线')
    entry=next(m for m in scene.movements.values() if m['role']=='ENTRY')
    entry['from']['station']=1600.;entry['to']['station']=1800.;scene.revision+=1
    root=scene.create_group('机场道面');rg=scene.create_group('跑道系统',root);tg=scene.create_group('滑行系统',root);ag=scene.create_group('机坪系统',root)
    for aid,a in scene.assets.items():
        if a['kind']=='RUNWAY':scene.reparent(aid,rg)
        elif a['kind']=='TAXIWAY':scene.reparent(aid,tg)
        elif a['kind']=='APRON':scene.reparent(aid,ag)
    for mid,m in scene.movements.items():
        owner=m['to']['asset'] if scene.assets[m['from']['asset']]['kind']=='RUNWAY' else m['from']['asset'];scene.reparent(mid,owner)
    from apron_markings import create_apron_kit
    apron=next(k for k,a in scene.assets.items() if a['kind']=='APRON');create_apron_kit(scene,apron)
    for aid,a in list(scene.assets.items()):
        if a['kind']=='STAND':scene.update_asset(aid,props={'show_safety':True,'width':45})
    scene.past.clear();return scene


def build_frame(data,options):
    scene=AirportScene(data)
    start=time.perf_counter()
    generated=generated_markings(scene)
    items=display_list(scene,*options,generated=generated)
    return items,generated,crossings(scene),(time.perf_counter()-start)*1000

def build_audit(data):return validate_scene(AirportScene(data))


class LiveEditor(EditorApp):
    def update_title(self):
        super().update_title();self.title(self.title().replace('Airport Canvas —','Airport Canvas 4.0 —'))
    def __init__(self,scene=None):
        self._property_after=None;self._render_after=None;self._audit_after=None;self._poll_after=None
        self._zoom_after=None
        self._dirty_fields=set();self._inspector_token=0;self._renderer=None;self.auto_assets={};self._junctions=[]
        self._syncing_tree=False;self._selected_form=None;self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='airport-geometry')
        self._future=None;self._pending_frame=False;self._frame_key=None;self._drag_data=None
        self._audit_executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='airport-audit');self._audit_future=None;self._audit_poll_after=None
        self.last_build_ms=0;self._closed=False
        self._last_edit=None;self._last_edit_time=0;self._field_controls={}
        super().__init__(scene or live_demo())
        self.bind('<Destroy>',self._destroy_event,add='+')

    def _destroy_event(self,e):
        if e.widget!=self:return
        self._closed=True
        for key in ('_property_after','_render_after','_audit_after','_poll_after','_zoom_after','_audit_poll_after'):
            handle=getattr(self,key,None)
            if handle:
                try:self.after_cancel(handle)
                except tk.TclError:pass
        self._executor.shutdown(wait=False,cancel_futures=True)
        self._audit_executor.shutdown(wait=False,cancel_futures=True)

    def _build(self):
        super()._build()
        self.tree.configure(selectmode='browse')
        toolbar=ttk.Frame(self.tree.master);toolbar.pack(fill='x',before=self.tree)
        ttk.Button(toolbar,text='新建道面组',command=self.add_group).pack(side='left')
        ttk.Button(toolbar,text='移至根层',command=lambda:self.move_into(None)).pack(side='left')
        self.tree.bind('<<TreeviewSelect>>',self.tree_select)
        self.tree.bind('<ButtonPress-1>',self.tree_drag_start,add='+');self.tree.bind('<B1-Motion>',self.tree_drag_motion,add='+');self.tree.bind('<ButtonRelease-1>',self.tree_drag_end,add='+')
        self.status.set('实时矢量绘图 · 属性自动更新 · 对象树可拖入道面组')

    def add_group(self):
        parent=self.selection if self.can_contain(self.selection) else None
        gid=self.scene.create_group('道面组 '+str(len(self.scene.data['groups'])+1),parent);self.selection=gid;self.refresh()

    def can_contain(self,oid):return oid in self.scene.data['groups'] or oid in self.scene.assets and self.scene.assets[oid]['kind'] in CONTAINERS

    def add_apron_kit(self,aid=None):
        from apron_markings import create_apron_kit
        aid=aid or self.selection
        try:
            group,created,skipped=create_apron_kit(self.scene,aid);self.selection=group;self.refresh()
            self.status.set(f'已添加 {len(created)} 项机坪配套候选标记；{len(skipped)} 项因空间不足跳过。可逐项调整位置。')
        except (KeyError,ValueError) as exc:self.property_error.configure(text='请先选择机坪。'+str(exc))

    def tree_drag_start(self,e):self._tree_drag=(self.tree.identify_row(e.y),e.x,e.y,False)
    def tree_drag_motion(self,e):
        if not getattr(self,'_tree_drag',None):return
        oid,x,y,_=self._tree_drag;self._tree_drag=(oid,x,y,abs(e.x-x)+abs(e.y-y)>8)
        target=self.tree.identify_row(e.y)
        if self.can_contain(target):self.status.set('松开：移入 '+all_objects(self.scene)[target]['name'])
    def tree_drag_end(self,e):
        if not getattr(self,'_tree_drag',None):return
        oid,x,y,moved=self._tree_drag;self._tree_drag=None
        if not moved:return
        target=self.tree.identify_row(e.y)
        if target.startswith('CAT:'):target=None
        if target is None or self.can_contain(target):self.selection=oid;self.move_into(target)

    def move_into(self,parent):
        oid=self.selection
        try:
            if oid in self.auto_assets:oid=detach_generated(self.scene,oid);self.selection=oid
            if oid not in all_objects(self.scene):return
            self.scene.reparent(oid,parent)
            if oid in self.scene.assets and parent in self.scene.assets and self.scene.assets[parent]['kind']=='APRON' and self.scene.assets[oid]['kind'] in ('STAND','APRON_TAXIWAY','STAND_TAXILANE'):
                self.scene.update_asset(oid,props={'parent_id':parent})
            self.refresh()
        except ValueError as exc:self.property_error.configure(text=str(exc))

    def sync_tree(self):
        self._syncing_tree=True
        try:
            roots={'GROUP':'道面组','RUNWAY':'跑道','TAXIWAY':'滑行路线','APRON':'机坪','STAND':'机位','MARKING':'独立标记','OTHER':'其他区域','MOVEMENT':'连接与快速出口','JUNCTION':'岔路口'}
            entries={'CAT:'+key:('',name,'分类') for key,name in roots.items()}
            from bitmap_layers46 import layers
            bitmaps=layers(self.scene)
            if bitmaps:
                entries['CAT:BITMAP']=('', '位图底图', '集合')
                for oid,row in bitmaps.items():
                    entries[oid]=('CAT:BITMAP',row['name'],'已锁定' if row['locked'] else '位图')
            for gid,obj in self.scene.data['groups'].items():entries[gid]=(parent_of(self.scene,gid) or 'CAT:GROUP',obj['name'],'道面组')
            for aid,a in self.scene.assets.items():
                kind=a['kind'];cat=kind if kind in roots else 'TAXIWAY' if kind in ('APRON_TAXIWAY','STAND_TAXILANE') else 'OTHER'
                entries[aid]=(parent_of(self.scene,aid) or 'CAT:'+cat,a['name'],NAMES[kind])
            for mid,m in self.scene.movements.items():entries[mid]=(parent_of(self.scene,mid) or 'CAT:MOVEMENT',m['name'],ROLE_NAMES[m['role']])
            for aid,a in self.auto_assets.items():entries[aid]=(a['owner'],a['name'],'自动标记')
            routes=route_objects(self.scene)
            for j in self._junctions:entries[j['id']]=('CAT:JUNCTION',' × '.join(routes[k]['name'] for k in j['assets']),'岔路口')
            done=set()
            def ensure(oid):
                if oid in done:return
                parent,name,kind=entries[oid]
                if parent and parent in entries:ensure(parent)
                elif parent:parent=''
                if self.tree.exists(oid):
                    if self.tree.parent(oid)!=parent:self.tree.move(oid,parent,'end')
                    self.tree.item(oid,text=name,values=(kind,))
                else:self.tree.insert(parent,'end',iid=oid,text=name,values=(kind,),open=not oid.startswith('AUTO:'))
                done.add(oid)
            for oid in entries:ensure(oid)
            def remove_stale(parent=''):
                for oid in self.tree.get_children(parent):
                    if oid not in entries:self.tree.delete(oid)
                    else:remove_stale(oid)
            remove_stale()
            if self.selection and self.tree.exists(self.selection) and self.tree.selection()!=(self.selection,):self.tree.selection_set(self.selection)
        finally:self._syncing_tree=False

    def tree_select(self,e=None):
        if self._syncing_tree or not self.tree.selection():return
        oid=self.tree.selection()[0]
        if oid.startswith('CAT:') or oid==self.selection:return
        self.select(oid)

    def select(self,oid):
        if oid!=self.selection:self.apply_properties()
        self.selection=oid
        if oid and self.tree.exists(oid):
            if self.tree.selection()!=(oid,):self.tree.selection_set(oid)
            self.tree.see(oid)
        if oid!=self._selected_form:self.update_inspector()
        self.redraw()

    @contextmanager
    def processing(self,label):
        tasks=self.__dict__.setdefault('_processing_tasks',{})
        token=object()
        self.show_processing(token,label,repaint=not tasks)
        try:yield
        finally:self.show_processing(token,None)

    def show_processing(self,token,label,repaint=False):
        tasks=self.__dict__.setdefault('_processing_tasks',{})
        if label:tasks[token]=label
        else:tasks.pop(token,None)
        status=self.__dict__.get('review_count')
        if not status:return
        if '_processing_bar' not in self.__dict__:
            self._processing_bar=ttk.Progressbar(status.master,length=110,maximum=100)
            self._processing_label=ttk.Label(status.master,text='')
            self._processing_bar.q.setFixedWidth(110)
        bar,text=self._processing_bar,self._processing_label
        if tasks:
            text.configure(text=next(reversed(tasks.values())))
            if not bar.winfo_manager():
                bar.pack(side='right',padx=3)
                text.pack(side='right',padx=4)
                bar.start()
            if repaint:
                status.master.q.layout().activate()
                text.q.repaint()
                bar.q.repaint()
        else:
            bar.stop()
            bar.pack_forget()
            text.pack_forget()

    def refresh(self):
        if getattr(self,'_rendered_scene50',None) is self.scene and self._large_scene50():
            self.highlight_tool()
            self.update_inspector()
            self.update_title()
            self.schedule_frame()
            self.schedule_audit()
            return
        with self.processing('正在重建道面与标注'):
            return self.rebuild_scene()

    def _large_scene50(self):
        return len(self.scene.assets)+len(self.scene.movements)>=100

    def rebuild_scene(self):
        self._frame_key=None;self.highlight_tool()
        self.auto_assets=generated_markings(self.scene)
        self.render_items=display_list(self.scene,*self.options(),generated=self.auto_assets)
        self._junctions=crossings(self.scene)
        self._rendered_scene50=self.scene
        self.sync_tree();self.update_inspector();self.redraw();self.update_title();self.schedule_audit()

    def options(self):return self.labels.get(),self.facilities.get(),self.protection.get()
    def current_frame_key(self):return id(self.scene),self.scene.revision,self.options()
    def schedule_frame(self):
        self._pending_frame=True
        if self._render_after:self.after_cancel(self._render_after)
        self._render_after=self.after(16,self.start_frame)
    def start_frame(self):
        self._render_after=None
        if self._future is not None:return
        key=self.current_frame_key();self._pending_frame=False;self._frame_key=key
        self.show_processing('frame','正在计算编辑预览')
        self._future=self._executor.submit(build_frame,copy.deepcopy(self.scene.data),self.options())
        self._poll_after=self.after(10,self.poll_frame)
    def poll_frame(self):
        self._poll_after=None
        if self._closed or self._future is None:return
        if not self._future.done():self._poll_after=self.after(10,self.poll_frame);return
        future=self._future;self._future=None
        self.show_processing('frame',None)
        try:
            frame=future.result()
            if self._frame_key==self.current_frame_key():
                self.render_items,self.auto_assets,self._junctions,self.last_build_ms=frame
                self.sync_tree();self.redraw()
        except (ValueError,TypeError) as exc:self.property_error.configure(text='几何预览：'+str(exc))
        if self._pending_frame or self._frame_key!=self.current_frame_key():self.start_frame()

    def schedule_audit(self):
        if self._audit_after:self.after_cancel(self._audit_after)
        self._audit_after=self.after(700,self.run_audit)
    def run_audit(self):
        self._audit_after=None
        if self.drag or self._audit_future is not None or self._future is not None or self._pending_frame:
            self.schedule_audit();return
        self._audit_key=(id(self.scene),self.scene.revision)
        self.show_processing('audit','正在审查机场工程')
        self._audit_future=self._audit_executor.submit(build_audit,copy.deepcopy(self.scene.data));self._audit_poll_after=self.after(25,self.poll_audit)
    def poll_audit(self):
        self._audit_poll_after=None
        if self._closed or self._audit_future is None:return
        if not self._audit_future.done():self._audit_poll_after=self.after(25,self.poll_audit);return
        future=self._audit_future;self._audit_future=None
        self.show_processing('audit',None)
        try:
            report=future.result()
            if self._audit_key==(id(self.scene),self.scene.revision):
                self.report=report;s=report['summary'];self.review_count.configure(text=f'审阅 · {s["FAIL"]} 项问题 / {s["UNKNOWN"]+s["UNVERIFIED"]} 项待核')
        except (ValueError,TypeError) as exc:self.status.set('审阅暂未更新：'+str(exc))

    def property_field(self,parent,key,label,value,kind='float',choices=None):
        control=super().property_field(parent,key,label,value,kind,choices)
        self._field_controls[key]=control
        var=self.editor_vars[key][0]
        var.trace_add('write',lambda *args,k=key:self.property_changed(k))
        if kind not in ('bool','radio') and not choices:control.bind('<Return>',lambda e:(self.apply_properties(),'break')[1])
        return control

    def property_changed(self,key):
        if self._inspector_busy:return
        self._dirty_fields.add(key)
        if self._property_after:self.after_cancel(self._property_after)
        token=self._inspector_token
        self._property_after=self.after(80,lambda:self.apply_properties() if token==self._inspector_token else None)

    def update_inspector(self):
        if self._property_after:self.after_cancel(self._property_after);self._property_after=None
        self._inspector_token+=1;self._dirty_fields.clear();self._selected_form=self.selection;self._field_controls={};self._runway_dimension_labels={}
        super().update_inspector()
        self._inspector_busy=True
        try:
            oid=self.selection
            if oid in self.scene.data['groups']:
                for child in self.property_body.winfo_children():child.destroy()
                self.editor_vars={};self._editor_oid=oid;self.property_title.configure(text=self.scene.data['groups'][oid]['name'])
                section=self.section('道面组');self.property_field(section,'name','组名称',self.scene.data['groups'][oid]['name'],'text')
                pts=[p for key in descendants(self.scene,oid) if key in self.scene.assets for p in self.scene.assets[key]['points']]
                self._editor_center=[(min(p[k] for p in pts)+max(p[k] for p in pts))/2 for k in (0,1)] if pts else [0,0]
                if pts:
                    for k,label,i in [('x','包络中心 X',0),('y','包络中心 Y',1)]:self.property_field(section,k,label,round(self._editor_center[i],3))
            if oid in all_objects(self.scene):
                section=self.section('层级归属（可拖动对象树）')
                excluded={oid}|set(descendants(self.scene,oid));self._container_choices={'（根层）':None}
                for key,obj in all_objects(self.scene).items():
                    if key not in excluded and self.can_contain(key):self._container_choices[obj['name']+' ['+key+']']=key
                parent=parent_of(self.scene,oid);value=next((s for s,k in self._container_choices.items() if k==parent),'（根层）')
                self.property_field(section,'_container','放入组/道面',value,'text',list(self._container_choices))
            if oid in self.auto_assets:
                ttk.Label(self.property_body,text='自动部件：随上级道面更新；本处修改保留为覆盖参数。',wraplength=250,padding=8).pack(fill='x')
                ttk.Button(self.property_body,text='分离为独立物体',command=self.detach_selected).pack(fill='x',padx=8,pady=6)
            if oid in self.scene.movements:
                m=self.scene.movements[oid];section=self.section('连接几何')
                choices=['AUTO','BEZIER','STRAIGHT']
                if self.scene.assets[m['from']['asset']]['kind']=='RUNWAY':choices.append('RAPID')
                self.property_field(section,'geometry','类型',m.get('geometry','AUTO'),'text',choices)
                ttk.Label(section,text='RAPID：转出圆弧＋直线＋接入圆弧；STRAIGHT：直线。',wraplength=245).grid(row=1,column=0,columnspan=2,sticky='w')
                for k,label,default in [('exit_angle','快速出口角 °',30),('exit_radius','转出半径 m',550),('join_radius','接入半径 m',25)]:self.property_field(section,k,label,m.get(k,default))
                self.property_field(section,'auto_signs','自动指令标识',m.get('auto_signs',True),'bool')
                self.property_field(section,'code_letter','指标Ⅱ',m.get('code_letter','C'),'text',list('ABCDEF'))
                for key,label,default in [('rapid_auto_fit','自动匹配角度/方向',True),('rapid_auto_radius','按代码选转出半径',False),('join_reverse_visible','显示反向接入引导线',True),('reverse_join_pavement','反向接入道面',True)]:self.property_field(section,key,label,m.get(key,default),'bool')
                self.property_field(section,'rapid_min_straight','要求直线长度 m',m.get('rapid_min_straight',1))
                self._rapid_length_label=ttk.Label(self.property_body,text='',wraplength=250,padding=8);self._rapid_length_label.pack(fill='x')
                if m.get('geometry')=='RAPID':
                    if 'handle' in self._field_controls:self._field_controls['handle'].configure(state='disabled')
                    p=rapid_layout(self.scene,m);self._rapid_length_label.configure(text=f'转出后直线长度：{p["straight"]:.1f} m（停止距离须另行核验）')
            a=self.scene.assets.get(oid)
            if a and a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                section=self.section('自动配套标记')
                self.property_field(section,'designation','路线编号',a['props'].get('designation') or a['name'].split()[0],'text')
                self.property_field(section,'auto_signs','位置/指令标识',a['props'].get('auto_signs',True),'bool')
                self.property_field(section,'show_holding','候选等待标志',a['props'].get('show_holding',True),'bool')
                self.property_field(section,'holding_distance','候选等待距 m',a['props'].get('holding_distance') or 90)
                self.property_field(section,'code_letter','指标Ⅱ',a['props'].get('code_letter','C'),'text',list('ABCDEF'))
            if a and a['kind']=='STAND':
                section=self.section('机位标志（6.2.16）')
                for k,label,value,kind in [('stand_number','机位号码',a['props'].get('stand_number') or a['name'],'text'),('number_height','号码字高 m',a['props'].get('number_height',4),'float'),('stop_length','停止线长度 m',a['props'].get('stop_length',2),'float'),('stop_width','停止线宽 m',a['props'].get('stop_width',.15),'float'),('aircraft_codes','适用机型',a['props'].get('aircraft_codes','A320'),'text'),('aircraft_text_height','机型字高 m',a['props'].get('aircraft_text_height',.2),'float'),('show_safety','机位安全线',a['props'].get('show_safety',False),'bool')]:self.property_field(section,k,label,value,kind)
            if a and a['kind']=='RUNWAY':
                from runway import aim_dimensions,threshold_geometry
                section=self.section('标记横向尺寸 · 表6.2.4/6.2.5');p=a['props'];n,sw=threshold_geometry(p['width'])
                label=ttk.Label(section,text=f'入口条纹：{n}条，宽{sw:.2f} m，距道面边{p["width"]/2-n*sw:.2f} m。',wraplength=245);label.grid(row=0,column=0,columnspan=2,sticky='w');self._runway_dimension_labels['threshold']=label
                for end in ('a','b'):
                    lda=p.get('lda_'+end) or g.length(a['points'])-p.get('displaced_'+end,0);_,length,width,gap=aim_dimensions(lda,p.get('aim_width_'+end),p.get('aim_gap_'+end),p.get('aim_length_'+end))
                    for key,label,value in [('aim_width_','瞄准点条宽 m',width),('aim_gap_','瞄准点内间距 m',gap),('aim_length_','瞄准点条长 m',length)]:self.property_field(section,key+end,end.upper()+'端 '+label,value)
                    row=__import__('property_rows').next_row(section)
                    label=ttk.Label(section,text=f'{end.upper()}端瞄准点距道面边：{p["width"]/2-gap/2-width:.2f} m',wraplength=245);label.grid(row=row,column=0,columnspan=2,sticky='w');self._runway_dimension_labels[end]=label
            if a and a['kind']=='APRON':ttk.Button(self.property_body,text='添加机坪配套标记组（14类）',command=lambda:self.add_apron_kit(oid)).pack(fill='x',padx=8,pady=8)
            if (a or self.auto_assets.get(oid)) and (a or self.auto_assets[oid])['kind']=='MARKING':
                mark=a or self.auto_assets[oid]
                spec=CATALOG[mark['props']['mark_type']]
                if spec.get('extra_fields'):
                    section=self.section('标记细节与预设尺寸')
                    for key,label,kind,default in spec['extra_fields']:self.property_field(section,key,label,mark['props'].get(key,default),kind)
                if mark['props']['mark_type']=='AIMING_POINT':
                    from runway import aim_dimensions
                    _,length,width,gap=aim_dimensions(mark['props'].get('lda',2400),mark['props'].get('aim_width'),mark['props'].get('aim_gap'),mark['props'].get('aim_length'))
                    section=self.section('瞄准点允许范围')
                    for key,label,value in [('aim_width','条宽 m',width),('aim_gap','内间距 m',gap),('aim_length','条长 m',length)]:self.property_field(section,key,label,value)
            self.update_geometry_controls()
        finally:self._inspector_busy=False

    def update_geometry_controls(self):
        self.update_runway_dimensions()
        if self.selection not in self.scene.movements:return
        mode=self.scene.movements[self.selection].get('geometry','AUTO')
        for key in ('exit_angle','exit_radius','join_radius','rapid_auto_fit','rapid_auto_radius','rapid_min_straight','join_reverse_visible','reverse_join_pavement'):
            if key in self._field_controls:self._field_controls[key].configure(state='normal' if mode=='RAPID' or key in ('join_reverse_visible','reverse_join_pavement') else 'disabled')
        if mode=='RAPID' and self.scene.movements[self.selection].get('rapid_auto_radius',False):self._field_controls['exit_radius'].configure(state='disabled')
        if 'handle' in self._field_controls:self._field_controls['handle'].configure(state='normal' if mode in ('AUTO','BEZIER') else 'disabled')
        label=getattr(self,'_rapid_length_label',None)
        if label is not None and label.winfo_exists():
            if mode=='RAPID':
                movement=self.scene.movements[self.selection];plan=rapid_layout(self.scene,movement)
                from route_geometry import reverse_join
                reverse_ok=reverse_join(self.scene,movement) is not None
                for key in ('join_reverse_visible','reverse_join_pavement'):
                    if key in self._field_controls:self._field_controls[key].configure(state='normal' if reverse_ok else 'disabled')
                label.configure(text=f'实际角 {plan["exit_angle"]:.1f}° / 半径 {plan["r"]:.1f} m / 直线 {plan["straight"]:.1f} m；停止距离须专项核验。'+('' if reverse_ok else '\n反向分支受道路流向或空间限制，当前不绘制。'))
            else:label.configure(text='')

    def update_runway_dimensions(self):
        a=self.scene.assets.get(self.selection);labels=getattr(self,'_runway_dimension_labels',{})
        if not a or a['kind']!='RUNWAY' or not labels:return
        from runway import aim_dimensions,threshold_geometry
        p=a['props'];count,stripe=threshold_geometry(p['width']);labels['threshold'].configure(text=f'入口条纹：{count}条，宽{stripe:.2f} m，距道面边{p["width"]/2-count*stripe:.2f} m。')
        old_busy=self._inspector_busy;self._inspector_busy=True
        try:
            for end in ('a','b'):
                lda=p.get('lda_'+end) or g.length(a['points'])-p.get('displaced_'+end,0);_,length,width,gap=aim_dimensions(lda,p.get('aim_width_'+end),p.get('aim_gap_'+end),p.get('aim_length_'+end))
                labels[end].configure(text=f'{end.upper()}端瞄准点距道面边：{p["width"]/2-gap/2-width:.2f} m')
                for prefix,value in [('aim_width_',width),('aim_gap_',gap),('aim_length_',length)]:
                    key=prefix+end
                    if key in self.editor_vars and key not in self._dirty_fields and p.get(key) is None:self.editor_vars[key][0].set(str(value))
        finally:self._inspector_busy=old_busy

    def apply_properties(self):
        if self._inspector_busy or self.selection!=getattr(self,'_editor_oid',None):return
        if self._property_after:self.after_cancel(self._property_after);self._property_after=None
        dirty=set(self._dirty_fields)
        if not dirty:return
        oid=self.selection
        if oid and oid.startswith('J:'):
            return self.apply_junction()
        try:
            values={}
            for key in dirty:
                var,kind=self.editor_vars[key];value=var.get()
                if kind in ('float','int'):
                    if str(value).strip()=='' and key in ('lda_a','lda_b'):value=None
                    else:
                        if str(value).strip() in ('','-','+','.','-.'):raise ValueError('输入尚未完成')
                        value=int(value) if kind=='int' else float(value)
                        if not math.isfinite(value):raise ValueError('数值必须有限')
                values[key]=value
            parent=values.pop('_container',None)
            with self.scene.transaction('实时修改属性'):
                if parent is not None:self.scene.reparent(oid,self._container_choices[parent])
                if oid in self.scene.data['groups']:
                    group=self.scene.data['groups'][oid]
                    if 'name' in values:group['name']=values.pop('name')
                    x=values.pop('x',self._editor_center[0]);y=values.pop('y',self._editor_center[1])
                    self.scene.translate(oid,x-self._editor_center[0],y-self._editor_center[1]);self._editor_center=[x,y]
                elif oid in self.scene.movements:
                    m=self.scene.movements[oid]
                    if '_exit_only_markings' in values:values['show_holding']=not values.pop('_exit_only_markings')
                    if values.get('geometry',m.get('geometry'))=='RAPID':configure_rapid(self.scene,oid,**values)
                    else:self.scene.update_movement(oid,**values)
                else:
                    a=self.scene.assets.get(oid) or generated_markings(self.scene).get(oid)
                    if not a:return
                    if 'text_height' in values and (a['props'].get('information_profile20_18')=='PAVEMENT' or
                            a['props'].get('mark_type')=='NO_ENTRY'):
                        if values['text_height']<=0:raise ValueError('字高须大于零')
                        values['sign_text_height']=values['text_height']
                    if 'text' in values and a['props'].get('information_profile20_18'):
                        label=values['text']
                        p=a['props']
                        if p.get('sign_panels24') or p.get('sign_role23')=='CAT_HOLD':
                            raise ValueError('请使用「信息引导 → 编辑选中的标识或标记牌文字」')
                        values.update(direction_name20_18=label,sign_custom_text=label)
                        if p.get('sign_role23')=='VACATED':values['location_name20_18']=label
                    points=copy.deepcopy(a['points']);name=values.pop('name',a['name']);center=self._editor_center
                    x=values.pop('x',center[0]);y=values.pop('y',center[1]);heading=values.pop('heading',None);length=values.pop('length',None)
                    if heading is not None or length is not None:
                        u=g.unit(points[0],points[-1]);heading=heading if heading is not None else math.degrees(math.atan2(u[0],u[1]))
                        span=length if length is not None else g.length(points)
                        if span<=0:raise ValueError('长度必须为正')
                        if self._point_marker:
                            angle=math.radians(heading);points=[[x,y],[x+span*math.sin(angle),y+span*math.cos(angle)]]
                        else:points=g.line([x,y],span,heading)
                    else:points=[[q[0]+x-center[0],q[1]+y-center[1]] for q in points]
                    if oid in self.auto_assets:
                        props=dict(a['props']);props.update(values);update_generated(self.scene,oid,name,points,props)
                    else:
                        # Explicit editor resize preserves proportional connection anchors.
                        old=g.length(a['points']);new=g.length(points)
                        if old>0 and abs(old-new)>.00001:
                            for m in self.scene.movements.values():
                                for side in ('from','to'):
                                    if m[side]['asset']==oid:m[side]['station']*=new/old
                        self.scene.update_asset(oid,name,points if dirty & {'x','y','heading','length'} else None,values)
                        if a['kind']=='STAND' and 'guidance' in values:a['props']['stop_reference']='NOSEWHEEL' if values['guidance']=='GUIDED' else 'LEFT_SEAT'
                    new_center=[x,y]
            if 'new_center' in locals():self._editor_center=new_center
            signature=(oid,tuple(sorted(dirty)));now=time.perf_counter()
            if self._last_edit==signature and now-self._last_edit_time<.8 and len(self.scene.past)>1 and self.scene.past[-1][0]=='实时修改属性':self.scene.past.pop()
            self._last_edit=signature;self._last_edit_time=now
            self._dirty_fields.difference_update(dirty);self.property_error.configure(text='')
            if oid in self.auto_assets:self.auto_assets=generated_markings(self.scene)
            current=all_objects(self.scene).get(oid) or self.auto_assets.get(oid)
            if current:self.property_title.configure(text=current['name'])
            self.update_geometry_controls()
            self.route_preview=None;self.sync_tree();self.schedule_frame();self.schedule_audit();self.update_title()
        except (ValueError,TypeError,KeyError) as exc:self.property_error.configure(text='未应用：'+str(exc))

    def detach_selected(self):
        if self.selection not in self.auto_assets:return
        self.selection=detach_generated(self.scene,self.selection);self.refresh()

    def apply_junction(self):
        try:
            radius=float(self.editor_vars['radius'][0].get());data={'radius':radius,'guides':{}}
            for key,(var,kind) in self.editor_vars.items():
                if key.startswith('guide_'):data['guides'][key[6:]]=bool(var.get())
                elif key.startswith('straight_'):data[key]=bool(var.get())
            self.scene.configure_junction(self.selection,**data);self._dirty_fields.clear();self.property_error.configure(text='')
            self.schedule_frame();self.schedule_audit();self.update_title()
        except (ValueError,TypeError) as exc:self.property_error.configure(text='未应用：'+str(exc))

    def pick(self,p,paths_only=False):
        if not paths_only:
            for aid,a in reversed(list(self.auto_assets.items())):
                for item in primitives(a):
                    if item['type']=='polygon' and item.get('fill') and g.inside(p,item['points']):return 0,aid,0,p
            from route_geometry import reverse_join
            for mid,m in self.scene.movements.items():
                if m.get('geometry')=='RAPID' and m.get('reverse_join_pavement',True):
                    branch=reverse_join(self.scene,m)
                    if branch:
                        d,station,q=g.project(branch['points'],p)
                        if d<max(6/self.zoom,m['width']/2):return d,mid,station,q
        return super().pick(p,paths_only)

    def click(self,e):
        self.apply_properties();super().click(e)
        self._drag_data=copy.deepcopy(self.scene.data) if self.drag and self.selection in self.scene.assets else None

    def motion(self,e):
        if self.drag and self._drag_data and self.selection in self.scene.assets:
            oid=self.selection
            point=self.world(e.x,e.y)
            self.drag['pending_point39']=point
            self.canvas.delete('asset_preview39')
            start=self.drag.get('start',point)
            delta=[point[k]-start[k] for k in (0,1)]
            for aid in [oid,*descendants(self.scene,oid)]:
                a=self.scene.assets.get(aid)
                if not a:continue
                points=[[q[k]+delta[k] for k in (0,1)] for q in a['points']]
                if 'vertex' in self.drag:
                    if aid!=oid:continue
                    points=list(map(list,a['points']))
                    points[self.drag['vertex']]=point
                if a['kind'] in AREA_KINDS:points.append(points[0])
                self.canvas.create_line(*[v for q in points for v in self.screen(q)],
                                        fill='#00a1c3',width=2,tags='asset_preview39')
            return
        super().motion(e)

    def release(self,e):
        if self.drag and self._drag_data:
            drag=self.drag
            self._drag_data=None
            self.drag=None
            self.canvas.delete('asset_preview39')
            point=drag.get('pending_point39')
            if point is None:return
            try:
                with self.scene.transaction('拖动对象或控制点'):
                    oid=self.selection
                    a=self.scene.assets[oid]
                    if 'vertex' in drag:
                        old=g.length(a['points'])
                        a['points'][drag['vertex']]=point
                        new=g.length(a['points'])
                        if old>0:
                            for m in self.scene.movements.values():
                                for port in (m['from'],m['to']):
                                    if port['asset']==oid:port['station']*=new/old
                    else:
                        dx,dy=(point[k]-drag['start'][k] for k in (0,1))
                        self.scene.translate(oid,dx,dy)
                    for m in self.scene.movements.values():
                        if m.get('geometry')=='RAPID':
                            plan=rapid_layout(self.scene,m)
                            m['to'].update(station=plan['station'],direction=plan['direction'])
                self.schedule_frame();self.update_inspector();self.schedule_audit();self.update_title()
            except ValueError as exc:self.property_error.configure(text='未移动：'+str(exc));self.schedule_frame()
            return
        super().release(e)

    def finish_draw(self):
        container=self.selection if self.can_contain(self.selection) else None;before=set(self.scene.assets)
        super().finish_draw()
        added=set(self.scene.assets)-before
        if container and added:
            for aid in added:self.scene.reparent(aid,container)
            self.refresh()

    def redraw(self):
        if not hasattr(self,'canvas'):return
        c=self.canvas
        if self._renderer is None:self._renderer=CanvasRenderer(c)
        items=self.render_items
        if self.scene.data['meta'].get('enlarge_boards23'):
            cached=getattr(self,'_board_display24',None)
            if not cached or cached[0] is not items:
                self._board_display24=(items,[e for e in items if not e.get('sign_board21_2')])
            items=self._board_display24[1]
        self._renderer.render(items,self.origin,self.zoom);c.delete('overlay');c.delete('grid')
        w,h=c.winfo_width(),c.winfo_height()
        if not hasattr(self,'draw_grid7') and self.grid_visible.get() and self.zoom*100>24:
            dark=getattr(self,'_dark_mode24',False)
            minor='#243441' if dark else '#dce3e8'
            major='#324655' if dark else '#ccd8e2'
            corners=[self.world(x,y) for x,y in ((0,0),(w,0),(w,h),(0,h))]
            xs,ys=zip(*corners)
            x0,x1=math.floor(min(xs)/100),math.ceil(max(xs)/100)
            y0,y1=math.floor(min(ys)/100),math.ceil(max(ys)/100)
            for x in range(x0,x1+1):
                c.create_line(*self.screen((100*x,100*y0)),*self.screen((100*x,100*y1)),fill=major if x%5==0 else minor,tags='grid')
            for y in range(y0,y1+1):
                c.create_line(*self.screen((100*x0,100*y)),*self.screen((100*x1,100*y)),fill=major if y%5==0 else minor,tags='grid')
            c.tag_lower('grid')
        oid=self.selection;a=self.scene.assets.get(oid) or self.auto_assets.get(oid)
        if a:
            pts=[self.screen(p) for p in a['points']]
            if a['kind'] in AREA_KINDS or a['kind']=='MARKING' and CATALOG[a['props']['mark_type']]['mode']=='AREA':pts=pts+[pts[0]]
            if len(pts)>1:c.create_line(*[v for p in pts for v in p],fill='#0f9ebb',width=2,dash=(5,3),tags='overlay')
            handles=pts
            if a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                from curve_model import editable_vertices
                handles=[self.screen(p) for p in editable_vertices(a)]
            for x,y in handles:c.create_rectangle(x-4,y-4,x+4,y+4,fill='white',outline='#0c90ad',width=2,tags='overlay')
        elif oid in self.scene.movements:
            pts=[self.screen(p) for p in self.scene.movement_path(oid)];c.create_line(*[v for p in pts for v in p],fill='#0f9ebb',width=2,dash=(5,3),tags='overlay')
        if self.mode=='JUNCTION' or oid and oid.startswith('J:'):
            for j in self._junctions:
                x,y=self.screen(j['point']);c.create_oval(x-7,y-7,x+7,y+7,fill='#d8f2f7',outline='#098ba8',width=2,tags='overlay')
        if self.points:
            pts=[self.screen(p) for p in self.points]
            if len(pts)>1:c.create_line(*[v for p in pts for v in p],fill='#0f9ebb',width=2,dash=(5,3),tags='overlay')
            for x,y in pts:c.create_oval(x-4,y-4,x+4,y+4,fill='#0f9ebb',tags='overlay')
        for port in self.connect_ports:
            q,_=g.at(self.scene.assets[port['asset']]['points'],port['station']);x,y=self.screen(q);c.create_oval(x-6,y-6,x+6,y+6,fill='#0f9ebb',tags='overlay')
        if self.route_preview:
            pts=[self.screen(p) for p in self.route_preview['points']]
            if len(pts)>1:c.create_line(*[v for p in pts for v in p],fill='#2182c5',width=3,dash=(8,4),tags='overlay')
        if not hasattr(self,'draw_compass23'):
            angle=getattr(c,'rotation21_2',0.)+math.radians(-self.scene.data['meta'].get('grid_north_true_heading',0));dx,dy=math.sin(angle),-math.cos(angle)
            c.create_line(w-35,45,w-35+dx*26,45+dy*26,arrow='last',fill='#526c7c',width=2,tags='overlay');c.create_text(w-35+dx*36,45+dy*36,text='N',tags='overlay',fill='#526c7c')

    def wheel(self,e):
        p=self.world(e.x,e.y);self.zoom=max(.01,min(250,self.zoom*(1.15 if e.delta>0 else 1/1.15)))
        x,y=self.screen(p)
        self.origin=[self.origin[0]+e.x-x,self.origin[1]+e.y-y]
        if self._zoom_after:self.after_cancel(self._zoom_after)
        self._zoom_after=self.after(16,self.finish_zoom)
    def finish_zoom(self):self._zoom_after=None;self.redraw()

    def delete_selected(self):
        if self.selection in self.auto_assets:
            with self.scene.transaction('隐藏自动部件'):self.scene.data['generated_overrides'].setdefault(self.selection,{})['hidden']=True
            self.selection=None;self.refresh();return
        super().delete_selected()

    def export(self,kind):self.apply_properties();super().export(kind)
    def save(self,*args):self.apply_properties();return super().save(*args)


def main():
    import sys
    scene=AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None
    LiveEditor(scene).mainloop()
