"""Prefab-first workspace and a single, deterministic connection drag controller."""
import copy
import math
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from qt_compat import ttk
from PIL import Image,ImageDraw
from qt_canvas21 import ImageTk
from editor9_gui import Editor9
from airport_scene import AirportScene
from marking_catalog import CATALOG
import scene_geometry as g
from project10 import TAXIS,SUBTYPES,constrain,parallel_number,rapid_option,move_endpoint

class Editor10(Editor9):
    def __init__(self,scene=None):
        self._drag10=None;self._stand_hit10=None;self._start_tangent10=None;self._divider10=None
        if scene is None:
            path=Path(__file__).with_name('example_editor10.airport.json')
            if path.exists():scene=AirportScene.load(path)
        super().__init__(scene)
        self.grid_visible.set(self.scene.data['meta'].get('grid_visible',True))
    def update_title(self):
        super().update_title();self.title(self.title().replace('9.0','10.0'))
    def _build(self):
        super()._build()
        for widget in self.tree.master.winfo_children():
            if widget!=self.tree:widget.destroy()
        self.tree.column('#0',width=115);self.tree.column('kind',width=65)
        self.tool_canvas.configure(width=180)
        for child in self.tool_body.winfo_children():child.destroy()
        self.tool_buttons={}
        def group(title,items,opened=False):
            outer=ttk.Frame(self.tool_body);outer.pack(fill='x',padx=3,pady=2);inner=ttk.Frame(outer);state=[opened]
            def toggle():
                state[0]=not state[0];button.configure(text=('▾ ' if state[0] else '▸ ')+title)
                if state[0]:inner.pack(fill='x')
                else:inner.pack_forget()
            button=ttk.Button(outer,text=('▾ ' if opened else '▸ ')+title,command=toggle);button.pack(fill='x')
            if opened:inner.pack(fill='x')
            for mode,label in items:
                photo=self.tool_icon(mode);small=ImageTk.PhotoImage(ImageTk.getimage(photo).resize((30,18),Image.Resampling.LANCZOS),master=self);self._photos['draw'+mode]=small
                b=ttk.Button(inner,text=label,image=small,compound='left',command=lambda mode=mode:self.set_mode(mode));b.pack(fill='x',pady=1);self.tool_buttons[mode]=b
        group('预制绘画',[('RUNWAY','跑道'),('TAXIWAY','滑行路线'),('STAND','成套机位'),('ROAD','双向服务车道'),('APRON','机坪'),('DEICE10','除冰坪'),('TURN_PAD','跑道掉头坪'),('STOPWAY','停止道')],True)
        options=ttk.LabelFrame(self.tool_body,text='滑行路线类型');options.pack(fill='x',padx=4,pady=4)
        self.taxi_type10=tk.StringVar(value='滑行道');ttk.Combobox(options,textvariable=self.taxi_type10,values=list(SUBTYPES),state='readonly',width=16).pack(fill='x')
        stand=ttk.LabelFrame(self.tool_body,text='机位预制');stand.pack(fill='x',padx=4,pady=4)
        self.lead10=tk.StringVar(value='A');self.bridge10=tk.BooleanVar(value=False)
        row=ttk.Frame(stand);row.pack(fill='x')
        for value in 'ABCD':ttk.Radiobutton(row,text=value,value=value,variable=self.lead10).pack(side='left')
        ttk.Checkbutton(stand,text='廊桥',variable=self.bridge10).pack(anchor='w')
        lane=ttk.LabelFrame(self.tool_body,text='服务车道标记位置');lane.pack(fill='x',padx=4,pady=4)
        self.lane10=tk.StringVar(value='BOTH');ttk.Combobox(lane,textvariable=self.lane10,values=['A','B','BOTH'],state='readonly',width=16).pack(fill='x')
        ttk.Label(lane,text='A：沿绘制方向右侧\nB：沿绘制方向左侧',font=('Microsoft YaHei UI',8)).pack(anchor='w')
        group('常用绘制',[('MARK:INTERMEDIATE_POINT','中间等待点'),('MARK:HOLD_B','B型等待'),('MARK:MAX_SPAN','翼展限制'),('PUSHBACK9','推出路径')],True)
        for name in dict.fromkeys(x['group'] for x in CATALOG.values()):group(name,[('MARK:'+key,x['name']) for key,x in CATALOG.items() if x['group']==name and key not in ('INTERMEDIATE_POINT','HOLD_B','MAX_SPAN')])
        group('其他区域',[('PROTECTION','保护区'),('EQUIPMENT','设备区域'),('CLOSED_AREA','关闭区域')])
        body=self.canvas.master;toolbar=ttk.Frame(self);toolbar.pack(fill='x',before=body,padx=10,pady=2)
        entries=[('SELECT','选择'),('NODES','节点编辑'),('BREAK','打断编号'),('SPLIT7','分段'),('BOX_SELECT','框选'),('CONNECT','连接并预览'),('EDIT_GUIDE','编辑连接线'),('JUNCTION','岔路口设置')]
        for i,(mode,label) in enumerate(entries):
            photo=self.operation_icon10(i);self._photos['op'+mode]=photo
            b=ttk.Button(toolbar,image=photo,command=lambda mode=mode:self.set_mode(mode));b.pack(side='left',padx=2)
            b.bind('<Enter>',lambda e,label=label:self.status.set(label));self.tool_buttons[mode]=b
        ttk.Separator(toolbar,orient='vertical').pack(side='left',fill='y',padx=8)
        ttk.Button(toolbar,text='所有车道尾流提示',command=self.all_jet10).pack(side='left',padx=3)
        ttk.Button(toolbar,text='平行跑道编号',command=self.parallel10).pack(side='left',padx=3)
        ttk.Checkbutton(toolbar,text='连接预览',variable=self.preview_enabled).pack(side='left',padx=8)
        menu=self.nametowidget(self.cget('menu'));settings=tk.Menu(menu,tearoff=False);menu.add_cascade(label='设置',menu=settings)
        settings.add_command(label='项目首选项…',command=self.preferences10)
        settings.add_command(label='新建道面组',command=self.add_group);settings.add_command(label='移至根层',command=lambda:self.move_into(None));settings.add_command(label='示例工程：ZSQD',command=self.demo10)
        self.after_idle(lambda:body.sashpos(0,200))
    def operation_icon10(self,i):
        im=Image.new('RGB',(28,25),'#edf2f6');d=ImageDraw.Draw(im);c='#25596f'
        if i==0:d.polygon([(4,2),(6,20),(11,14),(17,21),(20,18),(13,12),(21,9)],fill=c)
        elif i==1:
            d.line([(3,21),(10,6),(24,12)],fill=c,width=2)
            for x,y in [(3,21),(10,6),(24,12)]:d.rectangle((x-2,y-2,x+2,y+2),fill='#31a0bb')
        elif i==2:d.line((2,7,25,7),fill=c,width=3);d.line((14,1,14,23),fill='#d85b54',width=2);d.text((2,12),'A B',fill=c)
        elif i==3:d.line((2,12,25,12),fill=c,width=4);d.ellipse((10,7,20,17),outline='#d85b54',width=2)
        elif i==4:d.rectangle((3,3,24,22),outline=c,width=2);d.rectangle((9,9,18,17),fill='#7bd1df')
        elif i==5:d.arc((3,2,26,24),180,350,fill=c,width=2);d.line((2,14,7,14),fill=c,width=2);d.ellipse((20,6,25,11),fill='#32a879')
        elif i==6:d.arc((2,1,25,23),190,340,fill=c,width=2);d.line((5,18,10,4,23,13),fill='#b94e89');d.rectangle((8,2,12,6),fill='#b94e89')
        else:d.line((2,12,26,12),fill=c,width=4);d.line((14,2,14,23),fill=c,width=4);d.ellipse((9,7,19,17),fill='#f4c75a')
        return ImageTk.PhotoImage(im,master=self)
    def tool_icon(self,key):
        if key not in {'ROAD','DEICE10','STAND','APRON','TURN_PAD','STOPWAY','PUSHBACK9'}:return super().tool_icon(key)
        im=Image.new('RGB',(72,40),'#e5ebf0');d=ImageDraw.Draw(im)
        if key=='ROAD':
            d.rectangle((3,6,69,34),fill='#737b83');d.line((3,8,69,8),fill='white');d.line((3,32,69,32),fill='white')
            for x in range(3,69,13):d.line((x,20,x+7,20),fill='white')
        elif key=='DEICE10':
            d.rectangle((9,3,63,37),fill='#889ca6',outline='#247999')
            for a,b in [((36,8),(36,32)),((25,12),(47,28)),((25,28),(47,12))]:d.line((a,b),fill='white',width=2)
        elif key=='STAND':d.polygon([(22,31),(22,16),(10,11),(10,5),(62,5),(62,11),(50,16),(50,31)],outline='#d74b51');d.line((36,38,36,9),fill='#ffe081',width=2);d.line((31,12,41,12),fill='#ffe081',width=2)
        elif key=='APRON':d.polygon([(8,8),(58,3),(67,31),(15,37)],fill='#929ca4',outline='#496678');d.line((19,31,56,11),fill='#ffe081',width=2)
        elif key=='TURN_PAD':d.polygon([(5,31),(64,31),(64,5),(32,5)],fill='#737b83',outline='#9fa7ae');d.arc((32,8,61,31),-90,180,fill='#ffe081',width=2)
        elif key=='STOPWAY':
            d.rectangle((4,3,68,37),fill='#c7cbd0')
            for x in (20,41,62):d.line((x-14,5,x,20,x-14,35),fill='#e7b624',width=3)
        else:d.arc((12,0,63,37),0,150,fill='#ffffff',width=2);d.line((5,25,24,25),fill='#737b83',width=3);d.polygon([(55,4),(65,12),(55,15)],fill='#52697e')
        return ImageTk.PhotoImage(im,master=self)
    def set_mode(self,mode):
        if self._drag10:self._drag10=None;self.canvas.delete('geometry_drag39')
        self._stand_hit10=None;self._start_tangent10=None
        self._divider10=None
        super().set_mode(mode)
        if mode=='STAND':self.status.set('点击滑行道/机坪滑行道中线作为入口，再点击机位停止位置；A/B/C/D与廊桥在左侧选择')
        if mode in ('ROAD','TAXIWAY'):self.status.set('依次点击折线顶点，Enter生成圆角；Shift锁定方向；右键取消')
    def event10(self,e):
        if not (getattr(e,'state',0)&1) or not self.points:return e
        p=constrain(self.points[-1],self.world(e.x,e.y),self._start_tangent10 if len(self.points)==1 else None);x,y=self.screen(p)
        return SimpleNamespace(x=x,y=y,state=e.state,widget=getattr(e,'widget',self.canvas))
    def pointer(self,e):
        e=self.event10(e)
        h=None;label='吸附中线';key=self.mode[5:] if self.mode.startswith('MARK:') else None
        from roads10 import ROAD_MARKS,hit
        if self.mode=='ROAD' or key in ROAD_MARKS|{'ROAD_DIVIDER'}:h=hit(self.scene,self.world(e.x,e.y),max(.02,12/self.zoom))
        elif self.mode in TAXIS or self.mode=='STAND' and not self.points:
            from curve_model import snap
            h=snap(self.scene,self.world(e.x,e.y),max(.02,12/self.zoom))
        elif key and CATALOG[key]['shape']=='shoulder_bars':
            from editor7_model import snap_path
            h=snap_path(self.scene,self.world(e.x,e.y),max(.02,12/self.zoom));label='吸附边线'
            if h:
                d,aid,s,q=h;a=self.scene.assets[aid];q,u=g.at(a['points'],s);v=[-u[1],u[0]];point=self.world(e.x,e.y);side=1 if sum((point[k]-q[k])*v[k] for k in (0,1))>=0 else -1
                h=(d,aid,s,[q[k]+v[k]*side*a['props']['width']/2 for k in (0,1)])
        if h:
            x,y=self.screen(h[3]);e=SimpleNamespace(x=x,y=y,state=getattr(e,'state',0),widget=getattr(e,'widget',self.canvas))
        super().pointer(e)
        self.canvas.delete('snap10')
        if h:
            self._snap_hit=h;x,y=self.screen(h[3]);self.canvas.create_oval(x-7,y-7,x+7,y+7,outline='#df408a',width=2,tags='snap10');self.canvas.create_text(x+10,y-12,text=label,anchor='w',fill='#a52b54',tags='snap10')
    def click(self,e):
        e=self.event10(e);p=self.world(e.x,e.y)
        if self.mode in ('SELECT','NODES') and self.selection in self.scene.movements:
            geometry=self.control_geometry()
            if geometry:
                options=[(g.distance(p,q),kind,i) for kind,points in [('endpoint',geometry[:2]),('control',geometry[2])] for i,q in enumerate(points)]
                distance,kind,i=min(options)
                if distance<10/self.zoom:
                    self.apply_properties();self._anchor_drag=self._guide_drag=self._control_drag=self._vertex_drag=None;self.drag=None
                    self._drag10=dict(data=copy.deepcopy(self.scene.data),index=i,kind=kind,selection=self.selection,branch=self._branch);return
        if self.mode=='DEICE10':
            self.points.append(p)
            if len(self.points)==2:
                x0,x1=sorted(q[0] for q in self.points);y0,y1=sorted(q[1] for q in self.points)
                if min(x1-x0,y1-y0)<10:self.status.set('除冰坪两边至少10m');self.points=[];return
                self.selection=self.scene.create_asset('APRON','除冰坪',[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],role='DEICING',pavement_color='#889ca6');self.set_mode('SELECT');self.refresh()
            else:self.redraw()
            return
        if self.mode=='STOPWAY':
            from pavement10 import snap_stopway
            hit=snap_stopway(self.scene,p,self.zoom)
            if not hit:
                self.status.set('请靠近跑道端头，等待吸附提示')
                return 'break'
            _,aid,end,_=hit
            runway=self.scene.assets[aid]
            length=runway['props'].get('stopway_'+end,0) or 90.
            self.scene.update_asset(aid,props={'stopway_'+end:length})
            self.selection=aid
            self.set_mode('SELECT')
            self.refresh()
            return 'break'
        if self.mode=='STAND':
            from curve_model import snap
            if not self.points:
                h=snap(self.scene,p,max(.02,12/self.zoom))
                if not h or self.scene.assets[h[1]]['kind'] not in TAXIS:self.status.set('机位入口须点选滑行道中线');return
                self._stand_hit10=h;self.points=[h[3]];self.redraw();return
            from stand10 import attached_stand
            try:
                self.selection=attached_stand(self.scene,self._stand_hit10,p,str(100+sum(a['kind']=='STAND' for a in self.scene.assets.values())+1),self.lead10.get(),self.bridge10.get());self.set_mode('SELECT');self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        if self.mode=='ROAD':
            from roads10 import hit
            h=hit(self.scene,p,max(.02,12/self.zoom));self.points.append(h[3] if h else p)
            if len(self.points)==1 and h:self._start_tangent10=g.at(self.scene.assets[h[1]]['points'],h[2])[1]
            self.redraw();return
        if self.mode in TAXIS and not self.points:
            from curve_model import snap
            h=snap(self.scene,p,max(.02,12/self.zoom))
            if h:self._start_tangent10=g.at(self.scene.assets[h[1]]['points'],h[2])[1]
        if self.mode=='NODES' and self.selection not in self.scene.assets:
            from roads10 import hit
            h=hit(self.scene,p,max(.02,12/self.zoom))
            if h:self.select(h[1]);return
        if self.mode.startswith('MARK:'):
            key=self.mode[5:]
            from roads10 import ROAD_MARKS,hit,place
            if key=='ROAD_DIVIDER':
                h=hit(self.scene,p,max(.02,12/self.zoom))
                if not h:self.status.set('请点选服务车道中线');return
                if not self._divider10:self._divider10=h;self.points=[h[3]];self.redraw();return
                if h[1]!=self._divider10[1]:self.status.set('请在同一服务车道上选择终点');return
                lo,hi=sorted((h[2],self._divider10[2]))
                if hi-lo<1:return
                self.selection=self.scene.create_marking(key,g.subpath(self.scene.assets[h[1]]['points'],lo,hi),divider_road=h[1],divider_start=lo,divider_end=hi);self.set_mode('SELECT');self.refresh();return
            if key in ROAD_MARKS:
                h=hit(self.scene,p,max(.02,12/self.zoom))
                if h:
                    self.selection=place(self.scene,key,h,self.lane10.get())[0];self.set_mode('SELECT');self.refresh();return
            if key in ('SHOULDER_BARS','TWY_SHOULDER') or CATALOG[key]['shape']=='shoulder_bars':
                from editor7_model import snap_path
                h=snap_path(self.scene,p,max(.02,12/self.zoom))
                if not h:self.status.set('请点选道面边线附近');return
                _,aid,s,q=h;a=self.scene.assets[aid];q,u=g.at(a['points'],s);v=[-u[1],u[0]];side=1 if sum((p[k]-q[k])*v[k] for k in (0,1))>=0 else -1
                pts=g.subpath(a['points'],max(0,s-15),min(g.length(a['points']),s+15));from pavement_geometry import offset
                pts=offset(pts,side*a['props']['width']/2)
                if side<0:pts.reverse()
                self.selection=self.scene.create_marking(key,pts,width=a['props'].get('shoulder') or 7.5,label_asset=aid,edge_side=side);self.set_mode('SELECT');self.refresh();return
        super().click(e)
    def finish_draw(self):
        if self.mode=='ROAD':
            if len(self.points)<2:return
            from curve_model import rounded_nodes,evaluate
            try:
                nodes,radii=rounded_nodes(self.points,12)
                with self.scene.transaction('绘制双向服务车道'):
                    aid=self.scene.create_asset('ROAD','R'+str(len([a for a in self.scene.assets.values() if a['kind']=='ROAD'])+1),evaluate(nodes),corner_radius=12,auto_jet_blast=True)
                    self.scene.assets[aid].update(design_vertices=copy.deepcopy(self.points),curve_nodes=nodes)
                self.selection=aid;self.set_mode('SELECT');self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        mode=self.mode
        if mode=='TAXIWAY':self.mode=SUBTYPES[self.taxi_type10.get()]
        super().finish_draw()
        if mode=='TAXIWAY' and self.selection in self.scene.assets:
            a=self.scene.assets[self.selection];a['props']['route_type']=self.taxi_type10.get()
            if self.taxi_type10.get()=='快速脱离道':
                try:rapid_option(self.scene,self.selection,True);self.refresh()
                except ValueError as exc:self.status.set(str(exc))
    def motion(self,e):
        if not self._drag10:return super().motion(e)
        d=self._drag10
        geometry=self.control_geometry()
        if not geometry:return
        anchor=geometry[d['index']] if d['kind']!='endpoint' else geometry[1-d['index']]
        q,_=__import__('node_interaction20_8').resolve(
            self.scene,self.world(e.x,e.y),anchor,bool(getattr(e,'state',0)&1),
            max(.25,12/self.zoom),d['selection'])
        d['point']=q
        start,end,controls=geometry
        controls=list(controls)
        if d['kind']=='control':controls[d['index']]=q
        elif d['index']==0:
            controls[0]=[controls[0][k]+q[k]-start[k] for k in (0,1)]
            start=q
        else:
            controls[1]=[controls[1][k]+q[k]-end[k] for k in (0,1)]
            end=q
        from connection9 import path_with_controls
        points=path_with_controls(start,end,controls)
        self.canvas.delete('geometry_drag39')
        self.canvas.create_line(*[v for p in points for v in self.screen(p)],
                                fill='#d34f94',width=2,dash=(6,4),tags='geometry_drag39')

    def release(self,e):
        if not self._drag10:return super().release(e)
        d=self._drag10
        self._drag10=None
        self.canvas.delete('geometry_drag39')
        if 'point' not in d:return
        q=d['point']
        try:
            with self.scene.transaction('编辑连接端点或控制柄'):
                if d['kind']=='endpoint':
                    move_endpoint(self.scene,d['selection'],d['branch'],d['index'],q)
                else:
                    from editor7_model import main_controls
                    m=self.scene.movements[d['selection']]
                    if m.get('legacy_attachment'):
                        from project10 import legacy_controls
                        controls=copy.deepcopy(self.control_geometry()[2])
                        controls[d['index']]=q
                        legacy_controls(self.scene,m['id'],controls)
                    elif d['branch']=='MAIN':
                        controls=main_controls(self.scene,m)
                        controls[d['index']]=q
                        m.update(bezier_controls=controls,geometry='BEZIER',follow_existing=False)
                    else:
                        from junction_routes import branches
                        branch=next(b for b in branches(self.scene,m) if b['side']==d['branch'])
                        controls=copy.deepcopy(branch['controls'])
                        controls[d['index']]=q
                        m.setdefault('branch_controls',{})[d['branch']]=controls
            self.refresh()
        except (ValueError,StopIteration) as exc:self.status.set(str(exc))

    def control_geometry(self):
        m=self.scene.movements.get(self.selection)
        if m and m.get('legacy_attachment'):
            from project10 import route_nodes
            nodes=route_nodes(self.scene.assets[m['to']['asset']]);return nodes[0]['p'],nodes[-1]['p'],[nodes[0]['outgoing'],nodes[-1]['incoming']]
        return super().control_geometry()
    def anchor_paths(self):
        m=self.scene.movements.get(self.selection)
        if not m or not m.get('legacy_attachment'):return super().anchor_paths()
        child=self.scene.assets[m['to']['asset']];total=g.length(child['points']);paths=[]
        for end in (0,total):
            link=next((link for link in self.scene.movements.values() if link.get('legacy_attachment') and link['to']['asset']==child['id'] and abs(link['to']['station']-end)<.1),None)
            paths.append(self.scene.assets[link['from']['asset']]['points'] if link else child['points'])
        return paths
    def cancel_action(self,e=None):
        if self._drag10:self._drag10=None;self.canvas.delete('geometry_drag39')
        return super().cancel_action(e)
    def update_inspector(self):
        super().update_inspector();a=self.scene.assets.get(self.selection)
        if not a:return
        self._inspector_busy=True
        try:
            p=a['props']
            if a['kind'] in ('RUNWAY','APRON','ROAD')+TAXIS:
                sec=self.section('运行状态');self.property_field(sec,'closed','关闭道面',p.get('closed',False),'bool');self.property_field(sec,'closure_kind','关闭类别',p.get('closure_kind','TEMPORARY' if p.get('closed') else 'PERMANENT'),'radio',['TEMPORARY','PERMANENT'])
            if a['kind'] in TAXIS:
                sec=self.section('滑行路线预制');self.property_field(sec,'route_type','类型',p.get('route_type','滑行道'),'text',list(SUBTYPES))
                if p.get('rapid_fit_note'):ttk.Label(sec,text=p['rapid_fit_note'],wraplength=240).grid(row=3,column=0,columnspan=2,sticky='w')
                link=next((m for m in self.scene.movements.values() if m.get('legacy_attachment') and m['to']['asset']==a['id']),None)
                if link:ttk.Button(self.property_body,text='编辑两端交汇点和控制柄',command=lambda mid=link['id']:self.select(mid)).pack(fill='x',padx=8,pady=5)
            if a['kind']=='RUNWAY':
                sec=self.section('编号联动与停止道');self.property_field(sec,'sync_number','两端编号联动',p.get('sync_number',True),'bool');self.property_field(sec,'sync_suffix','两端L/R/C联动',p.get('sync_suffix',True),'bool')
                for end in ('a','b'):self.property_field(sec,'stopway_'+end,end.upper()+'端外延停止道 m',p.get('stopway_'+end,0))
            if a['kind']=='STAND':
                sec=self.section('成套机位');self.property_field(sec,'has_bridge','廊桥',p.get('has_bridge',False),'bool');self.property_field(sec,'outward','机位大头朝外',p.get('outward',True),'bool')
            if p.get('turn_pad'):
                sec=self.section('掉头坪位置');self.property_field(sec,'_padside10','朝跑道端口看', 'LEFT' if p.get('pad_side',1)==1 else 'RIGHT','radio',['LEFT','RIGHT'])
            if a['kind']=='ROAD':
                sec=self.section('双向服务车道');self.property_field(sec,'auto_jet_blast','交汇处自动尾流警示',p.get('auto_jet_blast',False),'bool')
                ttk.Label(sec,text='两车道，A在绘制方向右侧，B在左侧。\n节点工具可修改圆角和折线。').grid(row=1,column=0,columnspan=2)
        finally:self._inspector_busy=False
    def apply_properties(self):
        if self._inspector_busy:return
        m=self.scene.movements.get(self.selection)
        if m and m.get('legacy_attachment'):
            custom={key for key in getattr(self,'_dirty_fields',set()) if key.startswith('_c') and len(key)==4}
            if custom:
                try:
                    from project10 import legacy_controls
                    controls=[[float(self.editor_vars[f'_c{i}{key}'][0].get()) for key in ('x','y')] for i in (0,1)];legacy_controls(self.scene,m['id'],controls);self._dirty_fields.difference_update(custom);self.schedule_frame();self.redraw()
                except ValueError as exc:self.property_error.configure(text=str(exc));return
        if '_padside10' in getattr(self,'_dirty_fields',set()):
            from turn_pad import update_turn_pad
            try:
                update_turn_pad(self.scene,self.selection,dict(pad_side=1 if self.editor_vars['_padside10'][0].get()=='LEFT' else -1));self._dirty_fields.remove('_padside10');self.schedule_frame();self.redraw()
            except ValueError as exc:self.property_error.configure(text=str(exc));return
        if '_rapid10' in getattr(self,'_dirty_fields',set()):
            try:
                rapid_option(self.scene,self.selection,self.editor_vars['_rapid10'][0].get());self._dirty_fields.remove('_rapid10');self.schedule_frame();self.schedule_audit();self.redraw()
            except ValueError as exc:self.property_error.configure(text=str(exc));return
        return super().apply_properties()
    def all_jet10(self):
        with self.scene.transaction('所有服务车道添加尾流提示'):
            for a in self.scene.assets.values():
                if a['kind']=='ROAD':a['props']['auto_jet_blast']=True
        self.refresh()
    def parallel10(self):
        try:n=parallel_number(self.scene);self.refresh();self.status.set(f'已为{n}条跑道按平行组编号；请核对项目磁偏角')
        except ValueError as exc:self.status.set(str(exc))
    def preferences10(self):
        win=tk.Toplevel(self);win.title('设置 · 项目首选项');frame=ttk.Frame(win,padding=15);frame.pack(fill='both',expand=True)
        traffic=tk.StringVar(value=self.scene.data['meta'].get('traffic_side','RIGHT'));grid=tk.BooleanVar(value=self.grid_visible.get());outline=tk.BooleanVar(value=self.scene.data['meta'].get('guidance_black_outline',False));distance=tk.StringVar(value=str(self.scene.data['meta'].get('jet_warning_distance',12)))
        ttk.Label(frame,text='服务车道行驶侧').pack(anchor='w')
        for value,label in [('RIGHT','靠右行驶'),('LEFT','靠左行驶')]:ttk.Radiobutton(frame,text=label,value=value,variable=traffic).pack(anchor='w')
        ttk.Checkbutton(frame,text='背景网格',variable=grid).pack(anchor='w');ttk.Checkbutton(frame,text='全部标记黑色底纹/黑边',variable=outline).pack(anchor='w');ttk.Label(frame,text='尾流警示距交叉道面边缘 m').pack(anchor='w');ttk.Entry(frame,textvariable=distance).pack(fill='x')
        def save():
            try:
                number=float(distance.get())
                if not math.isfinite(number) or number<3:raise ValueError('距离至少3m')
                with self.scene.transaction('项目首选项'):
                    self.scene.data['meta'].update(traffic_side=traffic.get(),grid_visible=grid.get(),guidance_black_outline=outline.get(),jet_warning_distance=number)
                    from roads10 import refresh_attachments,roads
                    for a in roads(self.scene):refresh_attachments(self.scene,a['id'])
                self.grid_visible.set(grid.get());win.destroy();self.refresh()
            except ValueError as exc:self.status.set(str(exc))
        ttk.Button(frame,text='保存到项目',command=save).pack(fill='x',pady=10)
    def demo10(self):
        # Open through a separate window so an unsaved project remains available.
        Editor10(AirportScene.load(Path(__file__).with_name('example_editor10.airport.json')))

def main():Editor10().mainloop()
if __name__=='__main__':main()
