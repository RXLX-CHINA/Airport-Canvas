"""Predictable world-space previews and semantic entry anchors for Airport Canvas."""
from interface_language import tr
import copy,math,sys,time,hashlib
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from qt_compat import ttk
from PIL import Image, ImageDraw, ImageFont
from qt_canvas21 import ImageTk
from editor19_gui import Editor19
from airport_scene import AirportScene
import scene_geometry as g
import model20 as model
import guidance20
import icons20

PREVIEW_TAGS=('preview19','preview14','label_preview19','bridge_snap19','cross_preview14','cut_preview11','stand_preview11','angle_hint11','draft','preview','preview20','entry_preview20','entry20','corner_preview12','cursor_preview','deice_preview12','drag_preview','ghost11','lead_preview13','line_preview12','push_preview','route_preview17','shear_preview15','terminal_preview16')
PREVIEW_TAGS+=('connection_edit20_4',)
PREVIEW_TAGS+=('bridge_handle_preview20_6',)
PREVIEW_TAGS+=('polygon_preview20_7',)

class Editor20(Editor19):
    def __init__(self,scene=None):
        self._polygon_drag20_7=None;self._polygon_handles20_7=[]
        self._bridge_drag20_6=None;self._bridge_handle20_6=None
        self._entry_drag20=None;self._entry_handle20=None;self._world_preview20=[];self._last_pointer20=None;self._last_event20=None;self._preview_clock20=0
        if scene is None:scene=AirportScene.load(Path(__file__).with_name('example_editor20.ACP'))
        super().__init__(scene)
        menu=self.nametowidget(self.cget('menu'));tools=tk.Menu(menu,tearoff=False);menu.add_cascade(label='机场修正',menu=tools);tools.add_command(label='统一 NO ENTRY 尺寸／检查最窄处',command=self.no_entry_dialog20)
        tools.add_command(label='统一跑道编号强制指令标识',command=self.standardize_mandatory20)
        tools.add_command(label='去除强制性指令标识和增强型中线',command=self.remove_runway_instruction_markings20)
    def update_title(self):super().update_title();self.title(self.title().replace('19.0','20.18'))
    def tree_select(self,e=None):
        if len(self.__dict__.get('selected_ids',set()))>1 and set(self.tree.selection())==self.selected_ids:return
        return super().tree_select(e)
    def select(self,oid):
        self._boolean_order=[oid] if oid else []
        if oid in self.scene.movements:
            # Connections are editable objects, including legacy attachments.
            # Bypass whole-kit ownership promotion in Editor11.select.
            if oid!=self.selection:self._branch='MAIN'
            self._draft11=None;self._child13=False
            from editor7_gui import Editor7
            Editor7.select(self,oid)
            if self.mode=='SELECT':self.selected_ids=__import__('branch_selection20_15').chain(self.scene,oid)
            self.redraw()
            self.reveal_inspector11()
            if 'property_body' in self.__dict__:__import__('segment_property20_16').refresh_form(self)
            __import__('workspace20_18').sync_tree(self)
            return
        result=super().select(oid)
        if 'property_body' in self.__dict__:__import__('segment_property20_16').refresh_form(self)
        if self.mode=='SELECT' and oid in __import__('segments18').routes(self.scene):self.selected_ids=__import__('branch_selection20_15').chain(self.scene,oid);self.redraw()
        __import__('workspace20_18').sync_tree(self)
        return result
    def demo10(self):Editor20(AirportScene.load(Path(__file__).with_name('example_editor20.ACP')))
    def open(self, filename=None):
        self.clear_previews20();return super().open(filename)
    def action_icon11(self,key):
        photo=super().action_icon11(key);return ImageTk.PhotoImage(icons20.transparent(ImageTk.getimage(photo)),master=self)
    def _build(self):
        super()._build()
        __import__('workspace20_18').build(self)
        for key in icons20.KEYS:
            if key not in self.tool_buttons:continue
            image=icons20.tool(key).resize((34,20),Image.Resampling.LANCZOS);photo=ImageTk.PhotoImage(image,master=self);self._photos['new20:'+key]=photo;b=self.tool_buttons[key];b.configure(image=photo,compound='left',text=str(b.cget('text')).lstrip('＋+ '))
        toolbar=self.tool_buttons['SELECT'].master
        icon=Image.new('RGBA',(64,48))
        draw=ImageDraw.Draw(icon)
        draw.ellipse((13,5,50,42),fill='#b92832',outline='#822129',width=2)
        draw.rounded_rectangle((21,20,42,27),radius=2,fill='white')
        photo=ImageTk.PhotoImage(icon.resize((29,23),Image.Resampling.LANCZOS),master=self)
        self._photos['noentry20']=photo
        self.no_entry_button=ttk.Button(toolbar,image=photo,command=self.no_entry_dialog20,padding=4)
        self.no_entry_button.pack(side='left',padx=2)
        self.no_entry_button.q.setAccessibleName('统一 NO ENTRY 尺寸')
        self.tip11(self.no_entry_button,'统一全场 NO ENTRY 尺寸，检查最窄处可用空间')
        image=Image.new('RGBA',(64,48))
        pen=ImageDraw.Draw(image)
        pen.rounded_rectangle((3,4,60,43),radius=6,fill='#b92832',outline='#822129',width=2)
        pen.text((32,23),'09–27',font=ImageFont.load_default(size=17),anchor='mm',fill='white')
        photo=ImageTk.PhotoImage(image.resize((29,23),Image.Resampling.LANCZOS),master=self)
        self._photos['mandatory20']=photo
        mandatory=ttk.Button(self.tool_buttons['SELECT'].master,image=photo,command=self.standardize_mandatory20)
        mandatory.q.setAccessibleName('统一跑道号强制性标识')
        mandatory.pack(side='left',padx=2)
        self.tip11(mandatory,'统一跑道编号强制指令标识的尺寸和位置')
    def clear_previews20(self):
        self._world_preview20=[];self._last_pointer20=None;self._last_event20=None
        if 'canvas' in self.__dict__:
            for tag in PREVIEW_TAGS:self.canvas.delete(tag)
    def set_mode(self,mode):
        self.__dict__['_apron_anchor20_18']=None
        self._polygon_drag20_7=None
        self._bridge_drag20_6=None;self._bridge_handle20_6=None
        self.clear_previews20();self._entry_drag20=None;self._entry_handle20=None
        result=super().set_mode(mode)
        if mode in ('TRUNCATE20_18','APRON_RECT20_18','APRON_TRAP20_18','APRON_CARGO23','APRON_RUNUP23','APRON_DEICE_POLY'):
            self._draft11=None
            self.update_inspector()
            if mode=='TRUNCATE20_18':
                end='右端' if self.__dict__.get('_truncate_right21_2') else '左端'
                self.status.set(f'末端截断：左键确认删除{end}，右键／Esc取消')
            elif mode in __import__('workspace20_18').SPECIAL_APRONS:
                self.status.set('逐点绘制机坪边界，按 Enter 完成。')
            else:
                self.status.set('机坪绘制：选择两个对角点，右键取消')
        return result
    def cancel_action(self,e=None):
        if self.__dict__.pop('_remote_exit_drag',None):
            self.canvas.delete('remote_exit_preview')
            return 'break'
        if hasattr(self,'canvas'):self.canvas.delete('runway_end_preview32')
        if self.mode=='TRUNCATE20_18':
            self.canvas.delete('workspace20_18')
            self.set_mode('SELECT')
            self.status.set('已取消末端截断')
            return 'break'
        self.__dict__['_apron_anchor20_18']=None
        self.canvas.delete('workspace20_18')
        self._polygon_drag20_7=None;self.canvas.delete('polygon_preview20_7')
        self._bridge_drag20_6=None;self.canvas.delete('bridge_handle_preview20_6')
        self.clear_previews20()
        if self._entry_drag20:self._entry_drag20=None;self.redraw();return 'break'
        return super().cancel_action(e)
    def draw_world_preview20(self):
        c=self.canvas;c.delete('preview20')
        if self._color17 or not self.preview_enabled.get():return
        for item in self._world_preview20:
            coords=[v for q in item['points'] for v in self.screen(q)]
            if item['type']=='polygon':c.create_polygon(*coords,fill='',outline=item.get('color','#008da8'),width=2,tags='preview20')
            elif len(item['points'])>1:c.create_line(*coords,fill=item.get('color','#008da8'),width=3,dash=(5,3),tags='preview20')
    def preview19(self,q):
        self._last_pointer20=list(q)
        if not self.preview_enabled.get():self.canvas.delete('preview19');self._world_preview20=[];self.draw_world_preview20();return
        if self._custom19=='PIER19' and self._anchor19:
            aid,index,station=self._anchor19;a=self.scene.assets[aid];p,z,u,n=__import__('terminal19').frame(a,index)
            if sum((q[k]-p[k])*n[k] for k in (0,1))<=0:
                self.canvas.delete('preview19');self.canvas.create_line(*self.screen(g.at([p,z],station)[0]),*self.screen(q),fill='#c93952',width=3,dash=(4,3),tags='preview19');self.status.set('指廊必须向主体外侧挤出');return
        if self._custom19 in ('TERMINAL19','OTHER_BUILDING19') and self.values19['shape']!='CUSTOM':
            try:
                if not all(math.isfinite(float(self.values19[k])) and float(self.values19[k])>0 for k in ('width','depth')):raise ValueError()
            except ValueError:self.canvas.delete('preview19');self.status.set('主体尺寸必须是大于0的有限数');return
        if self._custom19!='ENHANCED19':return super().preview19(q)
        now=time.monotonic()
        if now-self._preview_clock20<.03:return
        self._preview_clock20=now;hit=guidance20.snap(self.scene,q,12/max(.001,self.zoom));self._world_preview20=[];self.canvas.delete('preview19')
        if hit:
            _,source,s,p=hit;a=guidance20.routes(self.scene)[source]
            try:
                length=float(self.values19['enhanced_length']);lo,hi=guidance20.span(a,s,length,self.values19['enhanced_direction'])
                if not math.isfinite(length) or length<=0:raise ValueError('长度必须大于0')
                mark=dict(id='PREVIEW20',kind='MARKING',points=g.subpath(a['points'],lo,hi),props=dict(mark_type='TWY_ENHANCED',enhanced_anchor19=True,enhanced_source20=source,enhanced_origin20=p,enhanced_station19=s,label_asset=a['props'].get('guidance_owner20',source),enhanced_length19=length,enhanced_direction19=self.values19['enhanced_direction']))
                guidance20.sync_mark(self.scene,mark)
                result=__import__('enhanced19')._refine(self.scene,{'PREVIEW20':mark});self._world_preview20=[dict(type='line',points=m['points']) for m in result.values() if m['props'].get('mark_type')=='TWY_ENHANCED']
                x,y=self.screen(p);self.canvas.create_oval(x-7,y-7,x+7,y+7,outline='#d52c7a',width=2,tags='preview19')
            except (ValueError,KeyError):pass
        self.draw_world_preview20()
    def preview_bridges19(self):
        try:
            preview=AirportScene(copy.deepcopy(self.scene.data));ids=__import__('terminal19').bridges(preview,self.selection,int(self.values19['bridge_count']),float(self.values19['bridge_width']),float(self.values19['bridge_length']));self._world_preview20=[dict(type='polygon',points=preview.assets[aid]['points']) for aid in ids];self.draw_world_preview20();warnings=model.bridge_clearances(preview);self.status.set(f'预览 {len(ids)} 座廊桥，机位间距告警 {len(warnings)} 项；确认后生成。'+(' 可减少数量或调整尺寸。' if warnings else ''))
        except (ValueError,KeyError) as exc:self.status.set(str(exc));self._world_preview20=[];self.draw_world_preview20()
    def update_inspector(self):
        super().update_inspector()
        __import__('sidebar20_17').fit(self)
        a=self.scene.assets.get(self.selection)
        if not self.__dict__.get('_draft11') and a and a['kind'] in model.TAXIS:
            self._inspector_busy=True
            try:
                section=self.section('自动方向信息')
                self.property_field(section,'auto_direction20_18','生成最近相接滑行道的方向信息',a['props'].get('auto_direction20_18',True),'bool')
            finally:self._inspector_busy=False
        if self.mode=='SPLIT7':return
        if self._custom19:return
        a=self.scene.assets.get(self.selection);m=self.scene.movements.get(self.selection)
        if not a and self.selection in self.scene.data.get('groups',{}):
            ids=__import__('bridge_snap20_5').stands(self.scene,{self.selection})
            if len(ids)==1:a=self.scene.assets[ids[0]]
        self._inspector_busy=True
        try:
            if a and a['kind'] in model.TAXIS or m and model.axis(self.scene,self.selection):
                p=a['props'] if a else m;self.property_field(self.section('机坪道面外观'),'inherit_apron_color20','机坪内沿用机坪背景色',p.get('inherit_apron_color20',True),'bool')
                if m:
                    from project10 import SUBTYPES
                    route_type=m.get('route_type',{'RAPID_EXIT':'快速脱离道','APRON_ACCESS':'机坪入口滑行道'}.get(m.get('role'),'联络道'))
                    self.property_field(self.section('滑行路线预制'),'_connected_route_type39',
                                        '类型',route_type,'text',list(SUBTYPES))
                if m:self.property_field(self.section('连接道独立编号'),'designation','独立编号',m.get('designation',m['name']),'text')
                self.property_field(self.section('强制性指令标志'),'paired_mandatory20_2','窄道面也在两侧成对绘制（需审阅）',p.get('paired_mandatory20_2',True),'bool')
                if m:
                    sec=self.section('连接线形状')
                    for geometry,label in [('STRAIGHT','改为直线'),('BEZIER','恢复曲线')]:ttk.Button(sec,text=label,command=lambda geometry=geometry:self.set_connection_shape20_2(geometry)).grid(row=__import__('property_rows').next_row(sec),column=0,columnspan=2,sticky='ew',pady=3)
            from rapid_editor39 import source,open_dialog
            if (m and m.get('role')=='RAPID_EXIT') or (a and a['props'].get('rapid_exit')):
                props=m if m else a['props']
                self.property_field(self.section('快速脱离道标记'),'hide_entry_markings43',
                                    '关闭进入道面标记',props.get('hide_entry_markings43',False),'bool')
            if source(self.scene,self.selection):
                page=self.section('快速脱离道几何')
                ttk.Button(page,text='两端半径与直线段…',command=lambda:open_dialog(self)).grid(
                    row=0,column=0,columnspan=2,sticky='ew',pady=4)
            if a and a['kind']=='APRON':
                import signs21_2
                self.property_field(self.section('机坪用途'),'destination_code23','目的地牌面',signs21_2.apron_name(a),'text',signs21_2.DESTINATIONS)
            if a and a['kind']=='RUNWAY':self.property_field(self.section('交叉跑道标志'),'intersection_relocate20','瞄准点／接地带整组避让（需审阅）',a['props'].get('intersection_relocate20',True),'bool')
            if a and a['props'].get('building_role19')=='PIER':
                self.property_field(self.section('指廊尺寸'),'_pier_length20_7','指廊长度 m',__import__('polygon_edit20_7').pier_length(a),'float')
            if a and a['props'].get('building_role19')=='BRIDGE':
                sec=self.section('相邻机位间距预检查')
                for key,label,default in [('gate_span20','设计翼展 m',self.scene.scenario.get('aircraft_wingspan',36)),('gate_length20','机长 m',self.scene.scenario.get('aircraft_length',40)),('gate_clearance20','相邻净距 m',4.5)]:self.property_field(sec,key,label,a['props'].get(key,default),'float')
            if a and a['kind']=='STAND':
                from stand13 import WORK_ZONES59
                props=a['props'];page=self.section('机位作业区')
                zones=(('work_zone_left','左侧'),('work_zone_right','右侧')) if props.get('remote_stand') else (('work_zone','作业区类型'),)
                from stand13 import NO_WORK_ZONE
                if not props.get('remote_stand') and not props.get('has_bridge'):
                    zones+=(('work_zone_bridge_side','原廊桥侧作业区'),)
                for key,label in zones:
                    optional=key=='work_zone_bridge_side'
                    choices=(*WORK_ZONES59,NO_WORK_ZONE) if optional else WORK_ZONES59
                    self.property_field(page,key,label,props.get(key,NO_WORK_ZONE if optional else WORK_ZONES59[0]),'text',list(choices))
            if a and a['kind']=='STAND':
                ttk.Button(self.section('廊桥吸附'),text='整套机位对准最近廊桥',command=self.align_bridge20_5).grid(row=__import__('property_rows').next_row(self.section('廊桥吸附')),column=0,columnspan=2,sticky='ew',pady=3)
                sec=self.section('入口中线连接点');ttk.Label(sec,text='橙色圆点沿绑定中线滑动，停止端保持原位；蓝色点继续编辑分支形状。',wraplength=260).grid(row=__import__('property_rows').next_row(sec),column=0,columnspan=2,sticky='w')
                if a['props'].get('hangar19'):
                    self.hide_field11('lead_type');self.property_field(self.section('机库引入线'),'lead_type','引入线构型',a['props'].get('lead_type','A'),'radio',list('ABCD'))
        finally:self._inspector_busy=False
        self.bind_route_type40()
        current=__import__('segment_property20_16').target(self)
        self._segment_form20_16=None
        if current:
            aid,part=current;self._segment_form20_16=(aid,part['id']);self._inspector_busy=True
            try:
                self.hide_field11('name');self.hide_field11('designation')
                axis=__import__('segments18').route(self.scene,aid);pieces=__import__('segments18').pieces(axis)
                self._segment_choices20_16={str(i+1)+' · '+p['name']:p['id'] for i,p in enumerate(pieces)}
                selected=next(label for label,pid in self._segment_choices20_16.items() if pid==part['id'])
                self.property_field(self.section('路线编号'),'_segment_pick20_16','选择子段',selected,'text',list(self._segment_choices20_16))
                self.property_field(self.section('路线编号'),'_segment_name20_16','路线编号',part['name'],'text')
            finally:self._inspector_busy=False
        self.ensure_book15().actions(self.property_body);self._book15.tidy()
    def align_bridge20_5(self):
        import terminal19 as terminal
        a=self.scene.assets.get(self.selection)
        if not a:
            ids=__import__('bridge_snap20_5').stands(self.scene,{self.selection})
            if len(ids)==1:a=self.scene.assets[ids[0]]
        if not a or a['kind']!='STAND':return
        bridges=[b for b in terminal.buildings(self.scene) if b['props']['building_role19']=='BRIDGE']
        if not bridges:self.status.set('请先创建廊桥。');return
        home=terminal.stand_home(self.scene,a);b=min(bridges,key=lambda b:g.distance(home,terminal.bridge_tip(b)))
        with self.scene.transaction('整套机位对准廊桥头部'):
            a['props'].update(entry_attached=False,bridge_bound19=False)
            a['props']['entry_bindings15']={key:False for key in a['props'].get('entry_bindings15',{})}
            root=self.selection
            if root not in self.scene.data['groups']:
                parent=a.get('container_id')
                if parent in self.scene.data['groups'] and self.scene.data['groups'][parent].get('stand_root13'):root=parent
            delta=[terminal.bridge_tip(b)[k]-home[k] for k in (0,1)]
            __import__('transform11').apply(self.scene,{root},delta=delta)
            terminal.align_stand(self.scene,a,terminal.bridge_tip(b));a['props'].update(gate_bridge19=b['id'],bridge_bound19=True,has_bridge=True)
        self.refresh();self.status.set('整套机位已移动，回位圆已对准廊桥头部。')
    def redraw(self):
        if self.__dict__.get('_redrawing20_2',False):return
        self._redrawing20_2=True
        try:self._redraw20_2()
        finally:self._redrawing20_2=False
    def _redraw20_2(self):
        super().redraw()
        __import__('view_overlay20_9').status(self)
        if 'canvas' not in self.__dict__:return
        self.draw_remote_exit_handles()
        self.canvas.delete('entry20');self._entry_handle20=None
        if not self._color17 and self.mode in ('SELECT','NODES'):
            a=self.root14()
            if a and a['props'].get('entry_attached',True) and model.entry_point(self.scene,a):
                q=model.entry_point(self.scene,a);x,y=self.screen(q);self.canvas.create_oval(x-7,y-7,x+7,y+7,fill='#ffb63d',outline='#8a4e12',width=2,tags='entry20');self.canvas.create_text(x+11,y+11,text=tr('入口·沿中线滑动'),anchor='nw',fill='#885216',tags='entry20');self._entry_handle20=(x,y,a['id'])
        if self._color17:
            self.canvas.delete('movement_names20')
            import segments18
            from segments16 import color_name
            from scene_render import rapid_f6_guides
            cache=self.__dict__.get('_rapid_f6_paths')
            if not cache or cache[0] is not self.render_items:
                cache=self._rapid_f6_paths=(self.render_items,rapid_f6_guides(self.render_items))
            rapid_paths=cache[1]
            for oid,paths in rapid_paths.items():
                owner=model.axis(self.scene,oid)
                movement=self.scene.movements.get(oid,{})
                for path in paths:
                    length=g.length(path)
                    cuts=[0.,length]
                    if owner:
                        axis_length=g.length(owner['points'])
                        for part in segments18.pieces(owner)[:-1]:
                            point,_=g.at(owner['points'],axis_length*part['hi'])
                            distance,station,_=g.project(path,point)
                            if distance<.2 and .001<station<length-.001:cuts.append(station)
                    cuts=sorted(set(cuts))
                    for lo,hi in zip(cuts,cuts[1:]):
                        if owner:
                            midpoint=g.at(path,(lo+hi)/2)[0]
                            station=g.project(owner['points'],midpoint)[1]
                            name=segments18.piece_at(owner,station)['name']
                        else:
                            name=movement.get('designation') or movement.get('name') or oid
                        self.canvas.create_line(*[v for q in g.subpath(path,lo,hi) for v in self.screen(q)],
                                                fill=color_name(name),width=3,
                                                tags=('movement_names20','f6_owner20_2:'+oid))
            for key,route in guidance20.routes(self.scene).items():
                if not key.startswith('G20-') and 'guidance_owner20' not in route['props']:continue
                owner_id=route['props'].get('guidance_owner20')
                owner=self.scene.assets.get(owner_id) or model.axis(self.scene,owner_id)
                if not owner:continue
                station=g.project(owner['points'],route['points'][0])[1];name=segments18.piece_at(owner,station)['name'];color=color_name(name);self.canvas.create_line(*[v for q in route['points'] for v in self.screen(q)],fill=color,width=3,tags='movement_names20')
            for mid,m in self.scene.movements.items():
                a=model.axis(self.scene,mid)
                if not a:
                    if mid in rapid_paths or m.get('legacy_attachment') or not m.get('guide_visible',True):continue
                    path=self.scene.movement_path(mid)
                    if len(path)>=2 and g.length(path)>.01:
                        tags=('movement_names20','f6_owner20_2:'+mid)
                        self.canvas.create_line(*[v for point in path for v in self.screen(point)],
                                                fill='#a14f88',width=3,tags=tags)
                    continue
                for part in segments18.pieces(a):
                    name=part['name'];color=color_name(name);tags=('movement_names20','f6_owner20_2:'+mid);L=g.length(a['points']);path=g.subpath(a['points'],part['lo']*L,part['hi']*L)
                    if mid not in rapid_paths:
                        self.canvas.create_line(*[v for p in path for v in self.screen(p)],fill=color,width=3,tags=tags)
                    q,_=g.at(path,g.length(path)/2);x,y=self.screen(q);self.canvas.create_text(x,y-12,text=name,fill=color,font=('Segoe UI',11,'bold'),tags=tags)
        else:self.canvas.delete('movement_names20')
        self.draw_world_preview20()
        if self._custom19 in ('TERMINAL19','OTHER_BUILDING19','PIER19','BRIDGE19') and self._last_pointer20 is not None:self.preview19(self._last_pointer20)
        self.reproject_previews20()
        self.draw_connection_overlay20_4()
        self.draw_bridge_handle20_6()
        self.draw_polygon_handles20_7()
        __import__('view_overlay20_9').deice(self)
        self.draw_segment_cuts20_14()
        __import__('workspace20_18').overlay(self)
        self.canvas.tag_raise('view_mode18')
    def draw_segment_cuts20_14(self):
        self.canvas.delete('segment_cuts20_14')
        if not self._color17 and self.mode!='SPLIT7':return
        logical=__import__('segments18')
        for aid,a in logical.routes(self.scene).items():
            pieces=logical.pieces(a)
            if len(pieces)<2:continue
            L=g.length(a['points']);half=max(3/max(.001,self.__dict__.get('zoom',1)),a['props'].get('width',12)/2)
            for part in pieces[:-1]:
                q,u=g.at(a['points'],part['hi']*L);v=[-u[1],u[0]];points=[[q[k]+sign*half*v[k] for k in (0,1)] for sign in (-1,1)]
                self.canvas.create_line(*[value for p in points for value in self.screen(p)],fill='#7b507f',width=1,dash=(3,3),tags='segment_cuts20_14')
    def finish_draw(self):
        from workspace20_18 import SPECIAL_APRONS,finish_special_apron
        if self.mode in SPECIAL_APRONS:return finish_special_apron(self)
        if self.mode=='SPLIT7':
            if self.route17.pending:self.commit_route17()
            return
        return super().finish_draw()
    def draw_polygon_handles20_7(self):
        self.canvas.delete('polygon_handles20_7');self._polygon_handles20_7=[]
        if self.mode!='NODES':return
        a=self.scene.assets.get(self.selection)
        if not __import__('polygon_edit20_7').eligible(a):return
        for index,q in enumerate(a['points']):
            x,y=self.screen(q);self._polygon_handles20_7.append((x,y,a['id'],index));self.canvas.create_rectangle(x-5,y-5,x+5,y+5,fill='#e4faff',outline='#008da8',width=2,tags='polygon_handles20_7')
    def bind_route_type40(self):
        oid=self.selection
        key=('_connected_route_type39' if oid in self.scene.movements else 'route_type')
        control=self._field_controls.get(key)
        if control is None:return
        control.bind('<<ComboboxSelected>>',lambda event:self.commit_route_type40(oid,key,control.get()))

    def commit_route_type40(self,oid,key,value):
        if self._inspector_busy or self.selection!=oid:return
        try:
            if key=='_connected_route_type39':
                from rapid_editor39 import set_connected_type
                set_connected_type(self.scene,oid,value)
            else:
                self.scene.update_asset(oid,props={'route_type':value})
        except ValueError as error:
            self.status.set(str(error))
            self.property_error.configure(text=str(error))
            return
        self._dirty_fields.discard(key)
        if self._dirty_fields:
            self.apply_properties()
        if self._dirty_fields:
            self.schedule_frame()
            self.schedule_audit()
        else:
            self.refresh()
        self.update_title()
        self.status.set(f'已应用滑行道类型：{value}')

    def apply_properties(self):
        if self._inspector_busy:return
        bridge_changed='has_bridge' in self._dirty_fields
        changed=False
        if '_connected_route_type39' in self._dirty_fields:
            from rapid_editor39 import set_connected_type
            try:
                set_connected_type(self.scene,self.selection,self.editor_vars['_connected_route_type39'][0].get())
            except ValueError as error:
                self.property_error.configure(text=str(error));self.status.set(str(error));return False
            self._dirty_fields.discard('_connected_route_type39')
            changed=True
        if '_segment_name20_16' in self._dirty_fields:
            try:
                aid,pid=self._segment_form20_16
                if aid!=self.selection:raise ValueError('请重新选择需要改号的子段。')
                __import__('segment_property20_16').rename(self.scene,aid,pid,self.editor_vars['_segment_name20_16'][0].get());self._dirty_fields.discard('_segment_name20_16');changed=True
            except (ValueError,KeyError,TypeError) as exc:self.property_error.configure(text=str(exc));return
        if '_segment_pick20_16' in self._dirty_fields:
            try:
                pid=self._segment_choices20_16[self.editor_vars['_segment_pick20_16'][0].get()];axis=__import__('segments18').route(self.scene,self.selection);part=next(p for p in __import__('segments18').pieces(axis) if p['id']==pid)
                self._active_piece18=(self.selection,pid);self._logical_station18=g.length(axis['points'])*(part['lo']+part['hi'])/2;self._dirty_fields.discard('_segment_pick20_16');changed=True
            except (KeyError,ValueError,StopIteration) as exc:self.property_error.configure(text=str(exc));return
        if '_pier_length20_7' in self._dirty_fields:
            try:
                length=float(self.editor_vars['_pier_length20_7'][0].get());__import__('polygon_edit20_7').resize_pier(self.scene,self.selection,length);self._dirty_fields.discard('_pier_length20_7');changed=True
            except (ValueError,KeyError) as exc:self.property_error.configure(text=str(exc));return
        super().apply_properties()
        if (changed or bridge_changed) and not self._dirty_fields:self.refresh()
    def draw_bridge_handle20_6(self):
        self.canvas.delete('bridge_handle20_6');self._bridge_handle20_6=None
        if self.mode not in ('SELECT','NODES'):return
        a=self.root14()
        if not a or a['kind']!='STAND' or not a['props'].get('has_bridge'):return
        q=__import__('terminal19').stand_home(self.scene,a);x,y=self.screen(q);self._bridge_handle20_6=(x,y,a['id'])
        self.canvas.create_oval(x-8,y-8,x+8,y+8,fill='#b7f0d5',outline='#16724c',width=2,tags='bridge_handle20_6')
        self.canvas.create_text(x+12,y+14,text=tr('廊桥回位点 · 固定入口旋转'),anchor='nw',fill='#16724c',tags='bridge_handle20_6')
    def draw_connection_overlay20_4(self):
        c=self.canvas;c.delete('connection_edit20_4')
        if self.mode=='CONNECT' and self.preview_enabled.get():
            preview=self.__dict__.get('_connect_preview');hit=self.__dict__.get('_snap_hit')
            if preview and hit:
                c.create_line(*[v for q in preview[1] for v in self.screen(q)],fill='#d52c7a',width=3,tags='connection_edit20_4')
            if hit:
                x,y=self.screen(hit[3]);c.create_oval(x-8,y-8,x+8,y+8,outline='#d52c7a',width=2,tags='connection_edit20_4');c.create_text(x+12,y-12,text='终点吸附中线' if self.connect_ports else '起点吸附中线',anchor='w',fill='#a02465',tags='connection_edit20_4')
        if self._color17 and self.mode in ('SELECT','NODES') and self.selection in self.scene.movements:
            geometry=self.control_geometry()
            if not geometry:return
            for q in geometry[:2]:
                x,y=self.screen(q);c.create_oval(x-6,y-6,x+6,y+6,fill='#e4faff',outline='#008da8',width=2,tags='connection_edit20_4')
            for end,q in zip(geometry[:2],geometry[2]):
                x,y=self.screen(q);c.create_line(*self.screen(end),x,y,fill='#ba4688',dash=(4,3),tags='connection_edit20_4');c.create_rectangle(x-5,y-5,x+5,y+5,fill='#ffdbef',outline='#a83b79',width=2,tags='connection_edit20_4')
        c.tag_raise('connection_edit20_4')
    def pointer(self,e):
        if self.mode in ('TRUNCATE20_18','APRON_RECT20_18','APRON_TRAP20_18','APRON_CARGO23','APRON_RUNUP23','APRON_DEICE_POLY'):return __import__('workspace20_18').preview(self,e)
        __import__('view_overlay20_9').status(self,e)
        if not self._pan11:self._last_event20=(self.world(e.x,e.y),getattr(e,'state',0))
        result=super().pointer(e)
        __import__('view_overlay20_9').status(self)
        if self.mode in ('SELECT','NODES'):__import__('node_interaction20_8').hover(self,e)
        if self.mode=='CONNECT':
            if not self.__dict__.get('_snap_hit'):self._connect_preview=None
            self.draw_connection_overlay20_4()
        if not self.preview_enabled.get():
            for tag in PREVIEW_TAGS:
                if tag!='entry20':self.canvas.delete(tag)
        return result
    def reproject_previews20(self):
        c=self.canvas
        if self._color17 or not self.preview_enabled.get():
            for tag in PREVIEW_TAGS:
                if tag!='entry20':c.delete(tag)
            return
        # All stored drag candidates live in metres; redraw them at the new zoom/origin.
        d=self._entry_drag20
        if d and d.get('candidate'):
            self.paint_stand_preview20(d['candidate'],'entry_preview20','#e99c28');return
        d=getattr(self,'_stand_drag14',None)
        if d and d.get('candidate'):
            a=copy.deepcopy(d['original']);a['props']=copy.deepcopy(d['candidate']);self.paint_stand_preview20(a,'preview14','#00a7c2');return
        d=getattr(self,'_transform14',None)
        if d:
            c.delete('preview14');box=d.get('target',d['box']) if d['kind'] not in ('MOVE','ROTATE') else d['box'];x0,y0,x1,y1=box;pts=[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]
            if d['kind'] in ('MOVE','ROTATE'):pts=[__import__('transform11').point(q,d['center'],d['angle'],d['delta']) for q in pts]
            c.create_line(*[v for q in pts for v in self.screen(q)],fill='#00a7c2',width=2,tags='preview14');return
        d=getattr(self,'_edit12',None)
        if d and d.get('candidate'):
            vertices,radii=d['candidate'];module=__import__('curve_model');nodes,_=module.rounded_nodes(vertices,d['radius'],radii);pts=module.evaluate(nodes);c.delete('corner_preview12');c.create_line(*[v for q in pts for v in self.screen(q)],fill='#00a1c3',width=3,tags='corner_preview12');return
        d=getattr(self,'_shear15',None)
        if d and 'angle' in d:
            candidate=copy.deepcopy(d['original']);candidate['props']['crossing_skew13']=d['angle'];c.delete('shear_preview15')
            for item in __import__('marking_catalog').primitives(candidate):c.create_polygon(*[v for q in item['points'] for v in self.screen(q)],outline='#008fab',fill='#ffffff',tags='shear_preview15')
            return
        d=getattr(self,'_label_drag19',None)
        if d and d.get('candidate') is not None:
            c.delete('label_preview19');x,y=self.screen(d['candidate']);c.create_oval(x-6,y-6,x+6,y+6,outline='#d52c7a',width=2,tags='label_preview19');return
        if self._last_event20 and self.mode not in ('SELECT','NODES','SPLIT7','STAND') and not self._custom19:
            q,state=self._last_event20
            if state&1 and self.points:
                tangent=g.unit(self.points[-2],self.points[-1]) if len(self.points)>1 else self.__dict__.get('_start_tangent10');q=__import__('project10').constrain(self.points[-1],q,tangent)
            hit=self.__dict__.get('_snap_hit')
            if hit and g.distance(q,hit[3])<=max(.05,12/max(.001,self.zoom)):q=hit[3]
            try:
                items=__import__('connection20_2').creation_preview(self.scene,self.mode,self.points,q,self._draft_values11,self._stand_start11,self._deice_hit12)
                for item in items:
                    c.delete(item['tag'])
                    if len(item['points'])>1:c.create_line(*[v for p in item['points'] for v in self.screen(p)],fill='#00a1c3',width=2,tags=item['tag'])
            except (ValueError,KeyError):pass
    def paint_stand_preview20(self,a,tag,color):
        c=self.canvas;c.delete(tag);view=SimpleNamespace(assets=dict(self.scene.assets,**{a['id']:a}),movements=self.scene.movements,movement_path=self.scene.movement_path,scenario=self.scene.scenario,data=self.scene.data)
        for part in __import__('stand15').design(a,view)['paths']:c.create_line(*[v for q in part['points'] for v in self.screen(q)],fill=color,width=2,tags=tag)
        for n in __import__('stand15').design(a,view)['numbers']:
            x,y=self.screen(n['point']);c.create_rectangle(x-7,y-7,x+7,y+7,outline=color,width=2,tags=tag)
    def draw_view_badge18(self):
        c=self.canvas
        c.delete('view_mode18')
        if getattr(getattr(self,'view_tools21_2',None),'active',False):
            text='目的地与方向标识与标记牌编辑模式·F5'
        else:
            text='显示模式：彩色分段 · F6' if self._color17 else '显示模式：普通机场图'
        item=c.create_text(max(24,c.winfo_width()-16),20,text=tr(text),anchor='ne',fill='#d6e7f3' if getattr(self,'_dark_mode24',False) else '#173446',
                           font=('Microsoft YaHei',10,'bold'),tags='view_mode18')
        box=c.bbox(item)
        if box:
            bg=c.create_rectangle(box[0]-8,box[1]-6,box[2]+8,box[3]+6,fill='#202e3d' if getattr(self,'_dark_mode24',False) else '#f7fafc',outline='#42566a' if getattr(self,'_dark_mode24',False) else '#b6c5cf',tags='view_mode18');c.tag_lower(bg,item)
        c.tag_raise('view_mode18')
    def pick(self,p,paths_only=False):
        if not paths_only and self.mode in ('SELECT','NODES') and not getattr(self,'_color17',False):
            items=getattr(self,'render_items',[])
            cache=self.__dict__.get('_runway_guide_pick32')
            if not cache or cache[0] is not items:
                cache=self._runway_guide_pick32=(items,[item for item in items if item.get('runway_junction_guide32')
                                                       and not item.get('black_underlay')])
            hits=[(distance,item['oid'],station,q) for item in cache[1]
                  for distance,station,q in [g.project(item['points'],p)] if distance<=5/max(.001,self.zoom)]
            if hits:return min(hits,key=lambda hit:hit[0])
        picked=super().pick(p,paths_only)
        if paths_only or self.mode!='NODES':return picked
        obj=(self.scene.assets.get(picked[1]) or self.auto_assets.get(picked[1])) if picked else None
        if obj and (obj['kind']=='STAND' or self.scene.assets.get(obj.get('owner'),{}).get('kind')=='STAND'):
            hit=model.snap(self.scene,p,2/max(.001,self.zoom))
            if hit:return hit
        return picked
    def draw_remote_exit_handles(self):
        from stand15 import remote_exit_handles
        self.canvas.delete('remote_exit_nodes')
        self._remote_exit_handles=[]
        if self.mode!='NODES' or self._color17:return
        mark=self.auto_assets.get(self.selection,{})
        aid=mark.get('owner') if mark.get('props',{}).get('mark_type')=='LEAD_OUT' else self.selection
        stand=self.scene.assets.get(aid,{})
        if stand.get('kind')!='STAND' or not stand['props'].get('remote_stand'):return
        for index,point in remote_exit_handles(stand,self.scene):
            x,y=self.screen(point)
            self.canvas.create_rectangle(x-4,y-4,x+4,y+4,fill='#fff',outline='#008da5',width=2,tags='remote_exit_nodes')
            self._remote_exit_handles.append((x,y,aid,index))

    def remote_exit_node_candidate(self,e,aid,index):
        from stand15 import drawn_remote_exit_props,remote_exit_fork_props,remote_exit_hit,remote_exit_vertices
        stand=self.scene.assets[aid]
        point=self.world(e.x,e.y)
        if index=='FORK':
            return dict(stand,props=remote_exit_fork_props(stand,point))
        vertices=remote_exit_vertices(stand,self.scene)
        hit=None
        if index==len(vertices)-1:
            hit=remote_exit_hit(self.scene,point,10/max(.001,self.zoom))
            if hit:point=hit[3]
        else:
            props=stand['props']
            if props.get('exit_asset'):
                hit=(None,props['exit_asset'],props.get('exit_station',0))
        vertices[index]=point
        props=dict(stand['props'])
        for key in ('exit_asset','exit_station'):props.pop(key,None)
        props.update(drawn_remote_exit_props(stand,vertices,hit))
        return dict(stand,props=props)

    def click(self,e):
        if self.mode=='TRUNCATE20_18':return __import__('workspace20_18').cut(self,e,self.__dict__.get('_truncate_right21_2',False))
        if self.mode in ('APRON_RECT20_18','APRON_TRAP20_18','APRON_CARGO23','APRON_RUNUP23','APRON_DEICE_POLY'):return __import__('workspace20_18').apron_click(self,e)
        if self._space11:return super().click(e)
        if self.mode=='NODES' and not self._color17:
            for x,y,aid,index in reversed(getattr(self,'_remote_exit_handles',())):
                if math.hypot(e.x-x,e.y-y)<=9:
                    self._remote_exit_drag=(aid,index)
                    return
            hit=self.pick(self.world(e.x,e.y))
            mark=self.auto_assets.get(hit[1],{}) if hit else {}
            if mark.get('props',{}).get('mark_type')=='LEAD_OUT':
                stand=self.scene.assets.get(mark.get('owner'),{})
                from stand15 import remote_exit_handles
                if stand.get('props',{}).get('remote_stand') and remote_exit_handles(stand,self.scene):
                    self.select(stand['id'])
                    self.redraw()
                    return
        if '_segment_name20_16' in self.__dict__.get('_dirty_fields',set()):self.apply_properties()
        if self.mode=='SELECT' and getattr(e,'state',0)&4 and not self.__dict__.get('_custom19'):
            p=self.world(e.x,e.y);hit=self.pick(p);oid=hit[1] if hit else None
            if self._color17:oid=self.pick_f6_connection20_2(e) or oid
            if oid:
                oid=__import__('transform11').owner(self.scene,oid,self.auto_assets)
                unit=__import__('branch_selection20_15').chain(self.scene,oid)
                current=set(self.selected_ids) if self.selected_ids else ({self.selection} if self.selection else set())
                chosen=current-unit if unit<=current else current|unit
                order=[aid for aid in getattr(self,"_boolean_order",[self.selection]) if aid in chosen]
                if oid in chosen:order.append(oid)
                self.select(oid if oid in chosen else next(iter(sorted(chosen)),None));self.selected_ids=chosen;self._boolean_order=order;self._marquee12=None;self._ctrl_click20_15=True;self.update_inspector();self.redraw();self.status.set('已多选 '+str(len(chosen))+' 个对象；Ctrl点击可取消选择。');return
        if self.mode=='NODES':
            for x,y,aid,index in self.__dict__.get('_polygon_handles20_7',[]):
                if math.hypot(e.x-x,e.y-y)<=10:self._polygon_drag20_7=dict(aid=aid,index=index,points=copy.deepcopy(self.scene.assets[aid]['points']),candidate=None);return
            hit=self.pick(self.world(e.x,e.y));a=self.scene.assets.get(hit[1]) if hit else None
            if __import__('polygon_edit20_7').eligible(a):self.select(a['id']);self.redraw();return
        h=self.__dict__.get('_bridge_handle20_6')
        if h and self.mode in ('SELECT','NODES') and math.hypot(e.x-h[0],e.y-h[1])<=11:
            self._bridge_drag20_6=dict(aid=h[2],target=None,bid=None);self._marquee12=None;return
        if self.__dict__.get('_entry_handle20') and self.mode in ('SELECT','NODES'):
            x,y,aid=self._entry_handle20
            if math.hypot(e.x-x,e.y-y)<=11:self._entry_drag20=dict(aid=aid,original=copy.deepcopy(self.scene.assets[aid]),candidate=None);self._marquee12=None;return
        if not self._custom19 and self.mode in ('SELECT','NODES'):
            p=self.world(e.x,e.y)
            if self.__dict__.get('selection') in self.scene.movements:
                geometry=self.control_geometry()
                if geometry:
                    for index,q in enumerate(geometry[:2]):
                        if g.distance(p,q)<=9/max(.001,self.zoom):
                            self._marquee12=None;self._drag10=dict(data=copy.deepcopy(self.scene.data),index=index,kind='endpoint',selection=self.selection,branch=self._branch);return
                    for index,q in enumerate(geometry[2]):
                        if g.distance(p,q)<=10/max(.001,self.zoom):
                            self._marquee12=None;self._drag10=dict(data=copy.deepcopy(self.scene.data),index=index,kind='control',selection=self.selection,branch=self._branch);return
            oid=__import__('connection20_2').pick_axis(self.scene,p,max(.05,8/max(.001,self.zoom)))
            if oid in self.scene.movements and not getattr(e,'state',0)&4:
                self._logical_station18=g.project(self.scene.movement_path(oid),p)[1]
                self._active_piece18=(oid,__import__('segments18').piece_at(__import__('segments18').route(self.scene,oid),self._logical_station18)['id'])
                self._marquee12=None;self.select(oid);self.redraw();self.status.set('已选中独立连接道：拖动端点调整交汇位置，拖动控制柄调整曲线；右侧修改编号或切换直线。');return
        if self.__dict__.get('_color17',False) and self.mode in ('SELECT','SPLIT7'):
            oid=self.pick_f6_connection20_2(e)
            if oid in self.scene.movements:
                if self.mode=='SPLIT7':return super().click(e)
                if self.mode!='SELECT':self.set_mode('SELECT')
                self.select(oid);self.redraw();self.status.set('已选择连接道，可在右侧修改独立编号或名称');return
        if self._custom19=='ENHANCED19':
            hit=guidance20.snap(self.scene,self.world(e.x,e.y),12/max(.001,self.zoom))
            if not hit:self.status.set('请点击可见的直线或转弯引导中线');return
            try:self.selection=guidance20.select(self.scene,hit,float(self.values19['enhanced_length']),self.values19['enhanced_direction']);self.set_mode('SELECT');self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        if self._entry_handle20 and self.mode in ('SELECT','NODES'):
            x,y,aid=self._entry_handle20
            if math.hypot(e.x-x,e.y-y)<=11:self._entry_drag20=dict(aid=aid,original=copy.deepcopy(self.scene.assets[aid]),candidate=None);self._marquee12=None;return
        if self.mode=='STAND' and not self.points:
            hit=model.snap(self.scene,self.world(e.x,e.y),12/max(.001,self.zoom))
            if hit and hit[1] in self.scene.movements:self._stand_start11=hit;self.points=[hit[3]];self.redraw();return
        return super().click(e)
    def pick_f6_connection20_2(self,e):
        c=self.canvas
        if hasattr(c,'find_overlapping'):
            for item in reversed(c.find_overlapping(e.x-5,e.y-5,e.x+5,e.y+5)):
                for tag in c.gettags(item):
                    if tag.startswith('f6_owner20_2:'):
                        oid=tag.split(':',1)[1]
                        if oid in self.scene.movements:return oid
        return __import__('connection20_2').pick_axis(self.scene,self.world(e.x,e.y),max(.05,10/max(.001,self.zoom)))
    def set_connection_shape20_2(self,geometry):
        if self.selection not in self.scene.movements:return
        try:self.scene.update_movement(self.selection,geometry=geometry);self.refresh();self.status.set('连接线已改为'+('直线' if geometry=='STRAIGHT' else '曲线'))
        except ValueError as exc:self.status.set(str(exc))
    def motion(self,e):
        drag=self.__dict__.get('_remote_exit_drag')
        if drag:
            from stand15 import remote_exit_lines
            candidate=self.remote_exit_node_candidate(e,*drag)
            self.canvas.delete('remote_exit_preview')
            for path in remote_exit_lines(candidate,self.scene):
                self.canvas.create_line(*[v for q in path for v in self.screen(q)],fill='#00a0c0',width=2,tags='remote_exit_preview')
            return
        result=Editor20.motion_with_preview32(self,e)
        c=self.canvas
        c.delete('runway_end_preview32')
        drag=self.__dict__.get('_transform14') or self.__dict__.get('_object_drag11')
        if drag and (drag.get('kind')=='MOVE' or 'rotation' in drag and not drag['rotation']):
            from pavement10 import preview_runway_ends
            preview_runway_ends(self,drag.get('roots',()))
        return result

    def motion_with_preview32(self,e):
        __import__('view_overlay20_9').status(self,e)
        polygon_drag=self.__dict__.get('_polygon_drag20_7')
        if polygon_drag:
            d=polygon_drag;q=self.world(e.x,e.y)
            q,hit=__import__('node_interaction20_8').resolve(self.scene,q,d['points'][d['index']],bool(getattr(e,'state',0)&1),max(.25,12/max(.001,self.__dict__.get('zoom',4))),d['aid'])
            points=copy.deepcopy(d['points']);points[d['index']]=q
            try:__import__('polygon_edit20_7').checked(points);d['candidate']=q;color='#008da8'
            except ValueError:d['candidate']=None;color='#d52c3a'
            self.canvas.delete('polygon_preview20_7');self.canvas.create_line(*[v for p in points+[points[0]] for v in self.screen(p)],fill=color,width=3,tags='polygon_preview20_7');return
        d=self.__dict__.get('_bridge_drag20_6')
        if d:
            module=__import__('bridge_handle20_6');a=self.scene.assets[d['aid']]
            try:
                q,bid=module.target(self.scene,a,self.world(e.x,e.y),max(2,18/max(.001,self.zoom)),bool(getattr(e,'state',0)&1));candidate=module.preview(self.scene,d['aid'],q)
                d.update(target=q,bid=bid);self.paint_stand_preview20(candidate,'bridge_handle_preview20_6','#19a86b' if bid else '#008da8')
                home=__import__('terminal19').stand_home(self.scene,candidate);x,y=self.screen(home);self.canvas.create_oval(x-9,y-9,x+9,y+9,outline='#19a86b' if bid else '#008da8',width=3,tags='bridge_handle_preview20_6')
                self.status.set('已吸附廊桥头部；入口固定在原滑行道中线上。' if bid else '入口固定，拖动调整机位方向与长度；Shift约束方向。')
            except ValueError as exc:d['target']=None;self.status.set(str(exc))
            return
        if self._entry_drag20:
            d=self._entry_drag20;a=copy.deepcopy(d['original']);parent=model.axis(self.scene,a['props'].get('entry_asset'));q=self.world(e.x,e.y)
            if not parent:return
            hit=model.snap(self.scene,q,max(.25,12/max(.001,self.__dict__.get('zoom',4))))
            if hit:parent=model.axis(self.scene,hit[1])
            if getattr(e,'state',0)&1:
                if hit:q=g.project(parent['points'],a['points'][-1])[2]
                else:q=__import__('project10').constrain(a['points'][0],q)
            _,s,q=g.project(parent['points'],q);a['points'][0]=q;a['props'].update(entry_asset=parent['id'],entry_station=s,entry_attached=True,entry_bindings15={key:True for key in ('ENTRY:0','ENTRY:1','ENTRY:-1')})
            if g.distance(a['points'][0],a['points'][-1])<15:return
            d['candidate']=a;view=SimpleNamespace(assets=dict(self.scene.assets,**{a['id']:a}),movements=self.scene.movements,movement_path=self.scene.movement_path,scenario=self.scene.scenario,data=self.scene.data)
            self.status.set('吸附中线：'+parent['name']+'；松手更新入口绑定。')
            self.canvas.delete('entry_preview20')
            for part in __import__('stand15').design(a,view)['paths']:self.canvas.create_line(*[v for p in part['points'] for v in self.screen(p)],fill='#e99c28',width=2,tags='entry_preview20')
            x,y=self.screen(q);self.canvas.create_oval(x-8,y-8,x+8,y+8,fill='#ffb63d',outline='#8a4e12',tags='entry_preview20');return
        return super().motion(e)
    def release(self,e):
        drag=self.__dict__.pop('_remote_exit_drag',None)
        if drag:
            self.canvas.delete('remote_exit_preview')
            candidate=self.remote_exit_node_candidate(e,*drag)
            with self.scene.transaction('编辑远机位引出线顶点'):
                self.scene.assets[drag[0]]['props'].update(candidate['props'])
                for key in ('exit_asset','exit_station'):
                    if key not in candidate['props']:self.scene.assets[drag[0]]['props'].pop(key,None)
            self.refresh()
            return
        if hasattr(self,'canvas'):self.canvas.delete('runway_end_preview32')
        if self.__dict__.pop('_ctrl_click20_15',False):return
        polygon_drag=self.__dict__.get('_polygon_drag20_7')
        if polygon_drag:
            self._polygon_drag20_7=None;self.canvas.delete('polygon_preview20_7')
            if polygon_drag['candidate'] is not None:
                try:__import__('polygon_edit20_7').set_vertex(self.scene,polygon_drag['aid'],polygon_drag['index'],polygon_drag['candidate']);self.refresh()
                except ValueError as exc:self.status.set(str(exc))
            return
        d=self.__dict__.get('_bridge_drag20_6')
        if d:
            self._bridge_drag20_6=None;self.canvas.delete('bridge_handle_preview20_6')
            if d['target'] is not None:
                try:
                    with self.scene.transaction('固定入口调整廊桥机位'):__import__('bridge_handle20_6').apply(self.scene,d['aid'],d['target'],d['bid'])
                    self.refresh()
                except ValueError as exc:self.status.set(str(exc))
            return
        if self._entry_drag20:
            d=self._entry_drag20;self._entry_drag20=None;self.canvas.delete('entry_preview20')
            if d['candidate']:
                try:model.slide_entry(self.scene,d['aid'],d['candidate']['points'][0],d['candidate']['props']['entry_asset']);self.refresh()
                except ValueError as exc:self.status.set(str(exc))
            return
        result=super().release(e)
        if self._custom19 is None:
            self._world_preview20=[];self.draw_world_preview20()
        return result
    def wheel(self,e):
        __import__('view_overlay20_9').status(self,e)
        result=super().wheel(e);__import__('view_overlay20_9').status(self);return result
    def pan_move(self,e):
        __import__('view_overlay20_9').status(self,e)
        result=super().pan_move(e);__import__('view_overlay20_9').status(self);return result
    def remove_runway_instruction_markings20(self):
        from automatic_markings import remove_runway_instruction_markings
        from qt_core21 import W
        title=tr('去除强制性指令标识和增强型中线')
        buttons=W.QMessageBox.StandardButton
        if W.QMessageBox.question(self.q,title,tr('去除手绘标识并停止自动生成？可用撤销恢复。'),
                                  buttons.Yes|buttons.No,buttons.No)!=buttons.Yes:
            return
        remove_runway_instruction_markings(self.scene)
        self.refresh()
        self.status.set(tr('已去除强制性指令标识和增强型中线。'))

    def standardize_mandatory20(self):
        from automatic_markings import standardize_runway_mandatory
        with self.processing('正在按道面净宽统一跑道编号标识'):
            count = standardize_runway_mandatory(self.scene)
            self.refresh()
        self.status.set(f'已按道面净宽重新计算 {count} 个跑道编号强制指令标识')

    def no_entry_dialog20(self):
        import styles19
        try:rows=model.no_entry_limits(self.scene)
        except ValueError as exc:self.status.set(str(exc));return
        standard=styles19.standard_no_entry_height(self.scene);maximum=min(x['maximum'] for x in rows) if rows else standard;limiting=[x for x in rows if abs(x['maximum']-maximum)<.001];window=tk.Toplevel(self);window.title('全机场 NO ENTRY 尺寸');window.geometry('470x350');body=ttk.Frame(window,padding=16);body.pack(fill='both',expand=True)
        ttk.Label(body,text=f'标志 {len(rows)} 个；指标字高 {standard:g}m；最窄位置可容纳字高上限 {maximum:.2f}m。\n限制位置：'+('、'.join(sorted({x['name'] for x in limiting})) or '无额外限制'),wraplength=420).pack(fill='x',pady=8)
        mode=tk.StringVar(value=self.scene.data['meta'].get('no_entry_mode20','STANDARD'))
        for value,label in [('STANDARD','按指标统一；容纳不下的标志列入审阅'),('FIT','按最窄处统一；低于标准时列入审阅')]:ttk.Radiobutton(body,text=label,variable=mode,value=value).pack(anchor='w',pady=6)
        ttk.Label(body,text='新增或修改滑行道后，可再次使用本工具重新计算。按最窄处缩小不代表符合规范。',wraplength=420).pack(fill='x',pady=12)
        def apply():
            try:report=model.uniform_no_entry(self.scene,mode.get());self.refresh();self.status.set(f'已统一 {report["count"]} 个 NO ENTRY，字高 {report["height"]:.2f}m');window.destroy()
            except ValueError as exc:self.status.set(str(exc))
        ttk.Button(body,text='检查并应用全机场',command=apply).pack(fill='x')

def main():Editor20(AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None).mainloop()
