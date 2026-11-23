"""Airport Canvas 19: searchable tools, explicit anchors and terminal workflow."""
import copy,math,sys
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from qt_compat import ttk
from editor18_gui import Editor18
from airport_scene import AirportScene
import scene_geometry as g
import terminal19 as terminal
CUSTOM={'OTHER_BUILDING19','TERMINAL19','PIER19','BRIDGE19','BRIDGES19','NUMBER_BRIDGES19','ENHANCED19'}

class Editor19(Editor18):
    def __init__(self,scene=None):
        self._custom19=None;self._anchor19=None;self._polygon19=[];self._label_drag19=None;self._prefab19=None;self._search_job19=None
        self.values19=dict(shape='RECTANGLE',width='140',depth='90',pier_width='28',bridge_count='6',bridge_width='3.5',bridge_length='26',clockwise='顺时针',start='1',digits='2',enhanced_length='47',enhanced_direction='END')
        super().__init__(scene if scene is not None else AirportScene.load(Path(__file__).with_name('example_editor19.ACP')))
    def update_title(self):super().update_title();self.title(self.title().replace('18.0','19.0'))
    def _build(self):
        super()._build()
        frame=ttk.Frame(self.tool_body);frame.pack(fill='x',before=self.tool_body.winfo_children()[0],padx=4,pady=5)
        ttk.Label(frame,text='搜索绘制工具').pack(anchor='w');self.tool_search19=tk.StringVar();entry=ttk.Entry(frame,textvariable=self.tool_search19);entry.pack(fill='x');self.tool_search19.trace_add('write',lambda *a:self.filter_tools19())
        content=self._palette_groups11[0][2]
        for mode,label in [('REMOTE_STAND','远机位'),('GA_STAND','通航机场机位'),('HELI_STAND','直升机坪（带引入线）'),('AUX_STAND19','辅助机位引导线＋编号'),('HANGAR19','机库／带屋顶机位'),('TERMINAL19','航站楼主体'),('OTHER_BUILDING19','其他建筑'),('PIER19','从主体边缘挤出指廊'),('BRIDGE19','从指廊边缘挤出廊桥'),('BRIDGES19','指廊等距生成廊桥'),('NUMBER_BRIDGES19','廊桥顺序编号'),('ENHANCED19','指定长度增强中线')]:
            b=ttk.Button(content,text=label,style='Item11.TButton',command=lambda m=mode:self.set_mode(m));b.pack(fill='x',pady=1);self.tool_buttons[mode]=b;self.tip11(b,label)
        from qt_core21 import C,G
        icon=G.QPixmap(24,24)
        icon.fill(C.Qt.GlobalColor.transparent)
        painter=G.QPainter(icon)
        painter.setRenderHint(G.QPainter.RenderHint.Antialiasing)
        painter.fillRect(3,4,7,16,G.QColor('#598caa'))
        painter.setPen(G.QPen(G.QColor('#eab554'),3))
        painter.drawPolyline(G.QPolygonF([C.QPointF(10,10),C.QPointF(16,10),C.QPointF(21,15)]))
        painter.end()
        self.tool_buttons['BRIDGE19'].q.setIcon(G.QIcon(icon))
        parent = self.tree.master
        self.tree_search19 = tk.StringVar()
        self.tree_search_row19 = ttk.Frame(parent)
        self.tree_search_row19.pack(fill='x', before=self.tree)
        entry = ttk.Entry(self.tree_search_row19, textvariable=self.tree_search19)
        entry.q.setPlaceholderText('搜索场景对象')
        entry.q.setAccessibleName('搜索场景对象')
        entry.pack(fill='x')
        parent.q.layout().setContentsMargins(6, 6, 6, 6)
        parent.q.layout().setSpacing(6)
        self.tree_search19.trace_add('write', lambda *args: self.queue_tree_search19())
    def filter_tools19(self):
        query=self.tool_search19.get().strip().casefold()
        for title,heading,content in self._palette_groups11:
            visible=0
            for child in content.winfo_children():
                mode=next((key for key,value in self.tool_buttons.items() if value is child),'')
                match=not query or query in title.casefold() or query in str(child.cget('text')).casefold() or query in mode.casefold()
                if match:child.pack(fill='x',pady=1);visible+=1
                else:child.pack_forget()
            if visible:
                heading.master.pack(fill='x',padx=3,pady=3)
                heading.show_palette_children(bool(query) or heading.palette_open)
            else:heading.master.pack_forget()
    def queue_tree_search19(self):
        if self._search_job19:self.after_cancel(self._search_job19)
        self._search_job19=self.after(120,self.search_tree19)
    def search_tree19(self):
        self._search_job19=None;self.sync_tree()
    def sync_tree(self):
        super().sync_tree()
        for a in terminal.buildings(self.scene):
            if self.tree.exists(a['id']):self.tree.item(a['id'],values=({'TERMINAL':'航站楼主体','OTHER':'其他建筑','PIER':'指廊','BRIDGE':'廊桥'}[a['props']['building_role19']],))
        query=self.tree_search19.get().strip().casefold() if hasattr(self,'tree_search19') else ''
        all_ids=[]
        def walk(parent=''):
            for oid in self.tree.get_children(parent):all_ids.append(oid);walk(oid)
        walk();keep=set()
        for oid in all_ids:
            label=str(self.tree.item(oid,'text'))+' '+str(self.tree.item(oid,'values'))
            if not query or query in label.casefold():
                keep.add(oid);parent=self.tree.parent(oid)
                while query and parent:keep.add(parent);self.tree.item(parent,open=True);parent=self.tree.parent(parent)
        for oid in all_ids:self.tree.set_hidden(oid,oid not in keep)
    def draft_defaults11(self,mode):
        p=super().draft_defaults11(mode)
        if mode=='STAND':p.update(auxiliary=False,show_safety=True,stand_support=True,hangar19=False)
        if mode=='STAND' and self._prefab19=='AUX_STAND19':p.update(auxiliary=True,show_safety=False,stand_support=False,has_bridge=False)
        if mode=='STAND':
            from stand13 import WORK_ZONES59,NO_WORK_ZONE
            if self._prefab19=='REMOTE_STAND':
                p['has_bridge']=False
                for field in ('work_zone_left','work_zone_right'):p.setdefault(field,WORK_ZONES59[0])
            elif self._prefab19=='GA_STAND':
                from stand13 import ga_stand_props
                p.update(ga_stand_props())
            elif self._prefab19=='HELI_STAND':
                from stand13 import helicopter_stand_props
                p.update(helicopter_stand_props())
                p.update(aircraft_span=12.,aircraft_length=12.)
            elif not self._prefab19:
                p.setdefault('work_zone',WORK_ZONES59[0])
                p.setdefault('work_zone_bridge_side',NO_WORK_ZONE)
        if mode=='STAND' and self._prefab19=='HANGAR19':p.update(hangar19=True,has_bridge=False)
        return p
    def highlight_tool(self,mode=None):
        active=mode or self.mode
        if active=='STAND':
            active=self._prefab19 or active
        return super().highlight_tool(active)

    def set_mode(self,mode):
        self._custom19=None;self._anchor19=None;self._polygon19=[];self._label_drag19=None;self._prefab19=mode if mode in ('AUX_STAND19','HANGAR19','REMOTE_STAND','GA_STAND','HELI_STAND') else None
        if mode in CUSTOM:
            super().set_mode('SELECT');self.mode=mode;self._custom19=mode;self._draft11=None;self.update_inspector();self.redraw();return
        return super().set_mode('STAND' if self._prefab19 else mode)
    def custom_inspector19(self):
        if self.__dict__.get('_property_after'):self.after_cancel(self._property_after);self._property_after=None
        if self.__dict__.get('_inspector_job11'):self.after_cancel(self._inspector_job11);self._inspector_job11=None
        self._editor_oid=None;self._selected_form=None;self._inspector_token=self.__dict__.get('_inspector_token',0)+1
        if 'property_canvas' in self.__dict__:self.property_canvas.yview_moveto(0)
        self._inspector_busy=True
        try:
            for child in self.property_body.winfo_children():child.destroy()
            self._book15=None;self.editor_vars={};self._field_controls={};self._dirty_fields.clear()
            self.property_title.configure(text='航站楼与引导工具')
            panel=ttk.Frame(self.property_body,padding=10);panel.pack(fill='x');mode=self._custom19
            def field(key,label,choices=None):
                ttk.Label(panel,text=label).pack(anchor='w',pady=(7,1));module=__import__('terminal_style20_3');display=module.shape_label(self.values19[key]) if key=='shape' else self.values19[key];options=[module.shape_label(v) for v in choices] if key=='shape' and choices else choices;var=tk.StringVar(value=display);widget=ttk.Combobox(panel,textvariable=var,values=options,state='readonly') if choices else ttk.Entry(panel,textvariable=var);widget.pack(fill='x');var.trace_add('write',lambda *args:self.values19.__setitem__(key,module.shape_value(var.get()) if key=='shape' else var.get()))
            if mode in ('TERMINAL19','OTHER_BUILDING19'):
                field('shape','主体形状',['RECTANGLE','CIRCLE','HEXAGON','OCTAGON','CUSTOM']);field('width','主体宽度 m');field('depth','主体深度 m');text='点击放置主体。自定义多边形：逐点点击，Enter 完成。'
            elif mode=='PIER19':field('pier_width','指廊宽度 m');text='先选择航站楼，再点主体边缘；向外移动并再次点击确定指廊长度。'
            elif mode=='BRIDGE19':
                field('bridge_width','廊桥宽度 m');text='选择指廊，点击边缘设置起点，移动鼠标预览后再次点击确认。按住 Shift 垂直挤出。'
            elif mode=='BRIDGES19':
                field('bridge_count','廊桥数量');field('bridge_width','廊桥宽度 m');field('bridge_length','廊桥长度 m');text='选择指廊后点击“预览”，确认无重叠后生成。连接主体的一侧自动排除。';ttk.Button(panel,text='预览等距廊桥',command=self.preview_bridges19).pack(fill='x',pady=6);ttk.Button(panel,text='确认生成廊桥',command=self.commit_bridges19).pack(fill='x')
            elif mode=='NUMBER_BRIDGES19':field('clockwise','编号方向',['顺时针','逆时针']);field('start','起始编号');field('digits','统一位数');text='先选航站楼主体，再点击作为起点的廊桥。'
            else:field('enhanced_length','增强中线距离 m');field('enhanced_direction','从点击位置向哪端延伸',['START','END']);text='点击滑行道中线；指定距离内的相连分支一并处理。START 朝起点，END 朝终点。'
            ttk.Label(panel,text=text,wraplength=270).pack(fill='x',pady=12);ttk.Button(panel,text='退出工具',command=lambda:self.set_mode('SELECT')).pack(fill='x')
        finally:self._inspector_busy=False
    def update_inspector(self):
        if self._custom19:return self.custom_inspector19()
        super().update_inspector();a=self.scene.assets.get(self.selection) or getattr(self,'auto_assets',{}).get(self.selection)
        if self._draft11=='STAND':
            self._inspector_busy=True
            try:
                for key in ('auxiliary','show_safety','stand_support','hangar19'):self.hide_field11('_draft_'+key)
                sec=self.section('预制组成')
                if self._prefab19=='GA_STAND':
                    self.property_field(sec,'_draft_show_safety','显示机位线框',self._draft_values11.get('show_safety',True),'bool')
                elif self._prefab19!='HELI_STAND':
                    for key,label in [('auxiliary','辅助机位虚线'),('show_safety','机位安全线'),('stand_support','作业区与轮挡区'),('hangar19','机库屋顶')]:self.property_field(sec,'_draft_'+key,label,self._draft_values11.get(key,False),'bool')
            finally:self._inspector_busy=False
            self.ensure_book15().actions(self.property_body);self._book15.tidy()
        if not a:return
        self._inspector_busy=True
        try:
            p=a['props'];role=p.get('building_role19')
            if role:
                sec=self.section('建筑与编号')
                if role=='TERMINAL':
                    self.property_field(sec,'terminal_number19','主体编号',p.get('terminal_number19',a['name']),'text')
                    for mode,label in [('PIER19','挤出指廊'),('NUMBER_BRIDGES19','选起点顺序编号')]:ttk.Button(sec,text=label,command=lambda m=mode:self.set_mode(m)).grid(row=__import__('property_rows').next_row(sec),column=0,columnspan=2,sticky='ew')
                if role=='OTHER':
                    self.property_field(sec,'terminal_number19','建筑编号',p.get('terminal_number19',a['name']),'text')
                if role=='PIER':ttk.Button(sec,text='等距布置廊桥',command=lambda:self.set_mode('BRIDGES19')).grid(column=0,columnspan=2,sticky='ew')
                if role=='BRIDGE':self.property_field(sec,'bridge_number19','廊桥编号',p.get('bridge_number19','01'),'text')
            if a['kind']=='STAND':
                sec=self.section('建筑与廊桥');self.property_field(sec,'hangar19','显示机库屋顶',p.get('hangar19',False),'bool');self.property_field(sec,'bridge_snap19','移动时吸附廊桥',p.get('bridge_snap19',True),'bool');self.property_field(sec,'bridge_bound19','绑定已吸附的廊桥',p.get('bridge_bound19',False),'bool');self.property_field(sec,'home_white19','廊桥回位点白色填充',p.get('home_white19',False),'bool')
            key=p.get('mark_type')
            if key=='MAX_SPAN':
                self.hide_field11('background');self.property_field(self.section('标志底色'),'background','黑色底色（取消为透明）',p.get('background',True),'bool')
            if key in ('BRIDGE_COMPOSITE','BRIDGE_AREA'):self.property_field(self.section('回位点'),'home_white19','白色填充',p.get('home_white19',False),'bool')
            if p.get('enhanced_anchor19'):
                sec=self.section('增强中线范围');self.property_field(sec,'enhanced_length19','增强长度 m',p['enhanced_length19'],'float');self.property_field(sec,'enhanced_direction19','延伸方向',p['enhanced_direction19'],'text',['START','END'])
        finally:self._inspector_busy=False
        self.ensure_book15().actions(self.property_body);self._book15.tidy()
    def pointer(self,e):
        if self._pan11:return
        if self._custom19:
            self._extrusion_shift19=bool(getattr(e,'state',0)&1)
            self.preview19(self.world(e.x,e.y));return
        # No snapping before object selection. Existing drag and drawing paths retain it.
        if self.mode in ('SELECT','NODES') and not self.gesture11() and not getattr(self,'_transform14',None):
            for tag in ('snap_cursor','snap_cursor11','snap_hint','angle_hint11'):self.canvas.delete(tag)
            if self.mode=='SELECT' and self._frame_box11:
                *_,box=self._frame_box11;self.canvas.configure(cursor='fleur' if self.border_hit11(e.x,e.y,box) else '')
            return
        return super().pointer(e)
    def bridge_edge_hit19(self,q):
        width=float(self.values19['bridge_width'])
        if not math.isfinite(width) or width<=0:raise ValueError('廊桥宽度必须大于 0。')
        tolerance=18/max(.001,self.zoom)
        candidates=[]
        margin=width/2+.5
        for pier in terminal.buildings(self.scene):
            if pier['props']['building_role19']!='PIER':continue
            for index,length in terminal.eligible_edges(self.scene,pier):
                if length<width+2:continue
                start,end,_,_=terminal.frame(pier,index)
                distance,station,_=g.project([start,end],q)
                if distance<=tolerance:
                    station=max(margin,min(length-margin,station))
                    point=g.at([start,end],station)[0]
                    candidates.append((g.distance(point,q),pier['id'],index,station,point))
        return min(candidates,default=None)

    def preview19(self,q):
        c=self.canvas;c.delete('preview19');mode=self._custom19
        try:
            pts=None
            if mode in ('TERMINAL19','OTHER_BUILDING19'):
                if self.values19['shape']=='CUSTOM':pts=self._polygon19+[q]
                else:
                    w=float(self.values19['width']);h=float(self.values19['depth']);n={'CIRCLE':64,'HEXAGON':6,'OCTAGON':8}.get(self.values19['shape'])
                    pts=[[q[0]+w/2*math.cos(2*math.pi*i/n),q[1]+h/2*math.sin(2*math.pi*i/n)] for i in range(n)] if n else [[q[0]-w/2,q[1]-h/2],[q[0]+w/2,q[1]-h/2],[q[0]+w/2,q[1]+h/2],[q[0]-w/2,q[1]+h/2]]
            elif mode=='BRIDGE19' and not self._anchor19:
                hit=self.bridge_edge_hit19(q)
                if hit:
                    _,aid,index,station,point=hit
                    a=self.scene.assets[aid]
                    start,end,_,_=terminal.frame(a,index)
                    c.create_line(*self.screen(start),*self.screen(end),fill='#008da8',width=3,tags='preview19')
                    x,y=self.screen(point)
                    c.create_oval(x-5,y-5,x+5,y+5,fill='#ffc24a',outline='#008da8',tags='preview19')
            elif mode in ('PIER19','BRIDGE19') and self._anchor19:
                aid,index,station=self._anchor19
                a=self.scene.assets[aid]
                length,shear=terminal.extrusion(a,index,station,q,getattr(self,'_extrusion_shift19',False))
                width=float(self.values19['pier_width' if mode=='PIER19' else 'bridge_width'])
                pts=terminal.quad(a,index,station,width,length,shear)
            elif mode=='ENHANCED19':
                hit=self.fast_hit18(q)
                if hit:
                    _,aid,s,q=hit;a=self.scene.assets[aid];n=float(self.values19['enhanced_length']);lo,hi=__import__('enhanced19').interval(self.scene,aid,s,n,self.values19['enhanced_direction']);pts=g.subpath(a['points'],lo,hi);x,y=self.screen(q);c.create_oval(x-7,y-7,x+7,y+7,outline='#d52c7a',width=2,tags='preview19')
            if pts and len(pts)>1:c.create_line(*[v for p in pts+([pts[0]] if mode in ('TERMINAL19','OTHER_BUILDING19','PIER19','BRIDGE19') else []) for v in self.screen(p)],fill='#008da8',width=3,dash=(5,3),tags='preview19')
        except (ValueError,KeyError):pass
    def click(self,e):
        if self._space11 and self.scene.data['meta'].get('space_pan',True):return super().click(e)
        q=self.world(e.x,e.y)
        if self._custom19:
            try:
                mode=self._custom19
                if mode in ('TERMINAL19','OTHER_BUILDING19'):
                    if self.values19['shape']=='CUSTOM':self._polygon19.append(q);self.preview19(q);return
                    self.selection=terminal.body(self.scene,q,float(self.values19['width']),float(self.values19['depth']),self.values19['shape'],role='OTHER' if mode=='OTHER_BUILDING19' else 'TERMINAL');self.set_mode('SELECT');self.refresh()
                elif mode in ('PIER19','BRIDGE19'):
                    role='TERMINAL' if mode=='PIER19' else 'PIER'
                    self._extrusion_shift19=bool(getattr(e,'state',0)&1)
                    if not self._anchor19 and mode=='BRIDGE19':
                        hit=self.bridge_edge_hit19(q)
                        if not hit:raise ValueError('请把光标移到指廊外边缘附近，点击高亮边缘。')
                        _,aid,index,station,point=hit
                        self._anchor19=(aid,index,station)
                        self.preview19(point)
                        self.status.set('已锁定廊桥起点。移动鼠标预览，再点击确认；Shift 垂直挤出。')
                    elif not self._anchor19:
                        a=self.scene.assets.get(self.selection)
                        if not a or a['props'].get('building_role19')!=role:
                            a=self.building_at19(q,role)
                        if not a:raise ValueError('请先选择需要挤出的建筑。')
                        distance,index,station,target=terminal.edge(a,q)
                        if distance>max(3,15/self.zoom):raise ValueError('请选择建筑边缘。')
                        self._anchor19=(a['id'],index,station)
                        self.preview19(q)
                    else:
                        aid,index,station=self._anchor19
                        length,shear=terminal.extrusion(self.scene.assets[aid],index,station,q,self._extrusion_shift19)
                        width=float(self.values19['pier_width' if mode=='PIER19' else 'bridge_width'])
                        extrude=terminal.extrude_pier if mode=='PIER19' else terminal.extrude_bridge
                        self.selection=extrude(self.scene,aid,index,station,width,length,shear)
                        self.set_mode('SELECT');self.refresh()
                elif mode=='BRIDGES19':
                    a=self.building_at19(q,'PIER')
                    if a:self.selection=a['id'];self.preview_bridges19()
                elif mode=='NUMBER_BRIDGES19':
                    b=self.building_at19(q,'BRIDGE');root=self.scene.assets.get(self.selection)
                    if not b or not root or root['props'].get('building_role19')!='TERMINAL':raise ValueError('需先选主体，再点击起始廊桥')
                    terminal.renumber(self.scene,root['id'],b['id'],self.values19['clockwise']=='顺时针',int(self.values19['start']),int(self.values19['digits']));self.set_mode('SELECT');self.refresh()
                else:
                    hit=self.fast_hit18(q)
                    if not hit:raise ValueError('请点击滑行道中线')
                    self.selection=__import__('enhanced19').select(self.scene,hit[1],hit[2],float(self.values19['enhanced_length']),self.values19['enhanced_direction']);self.set_mode('SELECT');self.refresh()
            except (ValueError,KeyError) as exc:self.status.set(str(exc))
            return
        if self.mode=='SELECT' and not self._space11 and not self._color17 and not getattr(e,'state',0)&(1|4):
            hit=self.pick(q);mark=(self.scene.assets.get(hit[1]) or self.auto_assets.get(hit[1])) if hit else None
            if mark and mark['kind']=='MARKING' and __import__('marking_catalog').CATALOG[mark['props']['mark_type']]['mode']=='POINT' and mark['props']['mark_type']!='STAND_NUMBER':
                self.selection=mark['id'];self.selected_ids={mark['id']};self.update_inspector();self.redraw();self._label_drag19=dict(aid=mark['id'],start=(e.x,e.y),point=mark['points'][0],candidate=None);return
        return super().click(e)
    def building_at19(self,q,role):
        from geometry11 import Point,polygon
        return next((a for a in reversed(terminal.buildings(self.scene)) if a['props']['building_role19']==role and polygon(a['points']).covers(Point(q))),None)
    def preview_bridges19(self):
        try:
            snapshot=AirportScene(copy.deepcopy(self.scene.data));ids=terminal.bridges(snapshot,self.selection,int(self.values19['bridge_count']),float(self.values19['bridge_width']),float(self.values19['bridge_length']));self.canvas.delete('preview19')
            for aid in ids:self.canvas.create_polygon(*[v for p in snapshot.assets[aid]['points'] for v in self.screen(p)],fill='',outline='#008da8',width=2,tags='preview19')
            self.status.set(f'{len(ids)} 座廊桥通过重叠检查；点击确认生成')
        except (ValueError,KeyError) as exc:self.status.set(str(exc))
    def commit_bridges19(self):
        try:terminal.bridges(self.scene,self.selection,int(self.values19['bridge_count']),float(self.values19['bridge_width']),float(self.values19['bridge_length']));self.set_mode('SELECT');self.refresh()
        except (ValueError,KeyError) as exc:self.status.set(str(exc))
    def finish_polygon19(self,e=None):
        if self._custom19 not in ('TERMINAL19','OTHER_BUILDING19') or self.values19['shape']!='CUSTOM':return
        try:
            if len(self._polygon19)<3:raise ValueError('至少绘制三个顶点')
            self.selection=terminal.body(self.scene,[0,0],shape='CUSTOM',points=self._polygon19,role='OTHER' if self._custom19=='OTHER_BUILDING19' else 'TERMINAL');self.set_mode('SELECT');self.refresh()
        except ValueError as exc:self.status.set(str(exc))
        return 'break'
    def finish_draw(self):
        if self._custom19:
            self.finish_polygon19();return 'break'
        return super().finish_draw()
    def motion(self,e):
        if self._label_drag19:
            d=self._label_drag19
            if math.hypot(e.x-d['start'][0],e.y-d['start'][1])<4 and d['candidate'] is None:return
            p=self.world(e.x,e.y)
            if getattr(e,'state',0)&1:p=__import__('project10').constrain(d['point'],p)
            from editor7_model import snap_path
            hit=snap_path(self.scene,p,max(.25,12/self.zoom))
            if hit:p=hit[3]
            d['candidate']=p;self.canvas.delete('label_preview19');x,y=self.screen(p);self.canvas.create_oval(x-6,y-6,x+6,y+6,outline='#d52c7a',width=2,tags='label_preview19')
            mark=self.scene.assets.get(d['aid']) or self.auto_assets.get(d['aid']);self.canvas.create_text(x+10,y-12,text=mark['props'].get('text',''),anchor='sw',fill='#a02465',tags='label_preview19');return
        result=super().motion(e)
        self.canvas.delete('bridge_snap19');d=getattr(self,'_transform14',None)
        if d and d['kind']=='MOVE':
            for aid in __import__('bridge_snap20_5').stands(self.scene,d['roots']):
                a=self.scene.assets.get(aid)
                if not a or a['kind']!='STAND' or not a['props'].get('bridge_snap19',True):continue
                q=[terminal.stand_home(self.scene,a)[k]+d['delta'][k] for k in (0,1)]
                for bridge in terminal.buildings(self.scene):
                    if bridge['props']['building_role19']!='BRIDGE':continue
                    target=terminal.bridge_tip(bridge)
                    if g.distance(q,target)<=max(2,18/self.zoom):
                        x,y=self.screen(target);self.canvas.create_oval(x-9,y-9,x+9,y+9,outline='#d52c7a',width=2,tags='bridge_snap19');self.canvas.create_text(x+12,y,text='吸附廊桥 '+bridge['props']['bridge_number19'],anchor='w',fill='#a02465',tags='bridge_snap19')
        return result
    def release(self,e):
        self.canvas.delete('bridge_snap19')
        if self._label_drag19:
            d=self._label_drag19;self._label_drag19=None;self.canvas.delete('label_preview19')
            if d['candidate'] is not None:
                try:__import__('styles19').move_label(self.scene,d['aid'],d['candidate']);self.refresh()
                except (ValueError,KeyError) as exc:self.status.set(str(exc))
            return
        transform=getattr(self,'_transform14',None) or getattr(self,'_object_drag11',None)
        moved=__import__('bridge_snap20_5').stands(self.scene,transform.get('roots',[])) if transform and transform.get('kind','MOVE')=='MOVE' else []
        if moved:
            with self.scene.transaction('移动机位并吸附廊桥'):
                for aid in moved:self.scene.assets[aid]['props']['bridge_bound19']=False
                if transform.get('bridge_snap20_5'):
                    for aid in moved:
                        p=self.scene.assets[aid]['props'];p['entry_attached']=False
                        p['entry_bindings15']={key:False for key in p.get('entry_bindings15',{})}
                super().release(e)
                for aid in moved:
                    if self.scene.assets[aid]['props'].get('bridge_snap19',True):terminal.snap_stand(self.scene,aid,max(2,18/self.zoom))
            self.refresh();return
        return super().release(e)
    def cancel_action(self,e=None):
        self._label_drag19=None;self.canvas.delete('label_preview19');self.canvas.delete('preview19');self.canvas.delete('bridge_snap19')
        if self._custom19:self.set_mode('SELECT');return 'break'
        return super().cancel_action(e)
    def redraw(self):
        super().redraw()
        if self._color17:
            self.canvas.delete('runway_labels19')
            for a in self.scene.assets.values():
                if a['kind']=='RUNWAY':
                    for i,end in [(0,'a'),(-1,'b')]:
                        x,y=self.screen(a['points'][i]);self.canvas.create_text(x,y-16,text='RWY '+a['props'].get('label_'+end,''),fill='#173446',font=('Segoe UI',11,'bold'),tags='runway_labels19')
            self.canvas.tag_raise('view_mode18')
        else:self.canvas.delete('runway_labels19')

def main():Editor19(AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None).mainloop()
