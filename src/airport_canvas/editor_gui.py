"""WYSIWYG-focused editor shell; legacy commands remain reusable adapters."""
import copy
import json
import math
from pathlib import Path
from interface_language import APPROACH_LEVELS
import qt_compat as tk
from qt_compat import ttk,filedialog,messagebox
from PIL import Image,ImageDraw
from qt_canvas21 import ImageTk
from legacy_gui import AirportApp as BaseApp,FormDialog,field,NAMES,ROLE_NAMES,STATES
from airport_scene import AirportScene,PATH_KINDS,AREA_KINDS
from marking_catalog import CATALOG,primitives,EDITABLE_FIELDS
from pavement_geometry import crossings,turn_guides,route_objects
from scene_render import display_list,bounds,export_png,export_svg
from scene_rules import validate_scene
from map_painter import draw_items
import scene_geometry as g

NAMES['MARKING']='道面标记'

class EditorApp(BaseApp):
    def __init__(self,scene=None):
        if scene is None:
            scene=AirportScene.demo()
            scene.create_asset('TAXIWAY','B',[[700,-150],[700,600]],width=23,shoulder=7.5)
            scene.past.clear()
        super().__init__(scene)

    def _bindings(self):
        super()._bindings()
        self.bind_all('<MouseWheel>',self.scroll_sidebar,add='+')

    def scroll_sidebar(self,e):
        widget=e.widget
        while widget is not None:
            if widget==self.property_body:
                self.property_canvas.yview_scroll(-3 if e.delta>0 else 3,'units');return
            if widget==getattr(self,'tool_body',None):
                self.tool_canvas.yview_scroll(-3 if e.delta>0 else 3,'units');return 'break'
            widget=getattr(widget,'master',None)

    def _build(self):
        self.title('Airport Canvas · 所见即所得机场编辑器');self.geometry('1520x980')
        self.configure(bg='#edf1f5');self.labels.set(False);self.protection.set(False)
        self.grid_visible=tk.BooleanVar(value=False);self.repeat=tk.BooleanVar(value=False)
        self._inspector_busy=False;self.editor_vars={};self._photos={};self.tool_buttons={};self._review=None
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10),background='#f0f3f6',foreground='#2c4257')
        style.configure('TButton',padding=(8,5));style.configure('Tool.TButton',padding=5,font=('Microsoft YaHei UI',9))
        style.configure('Selected.Tool.TButton',background='#b9e3ec',foreground='#075369')
        style.configure('Treeview',rowheight=26,background='white',fieldbackground='white');style.configure('Treeview.Heading',padding=5)
        menu=tk.Menu(self);self.config(menu=menu);fm=tk.Menu(menu,tearoff=False);menu.add_cascade(label='文件',menu=fm)
        for title,cmd in [('新建 Ctrl+N',self.new),('打开 Ctrl+O',self.open),('保存 Ctrl+S',self.save),('另存为',lambda:self.save(True)),('导入旧版 JSON',self.import_legacy),('导出 PNG',lambda:self.export('png')),('导出 SVG',lambda:self.export('svg')),('导出分层 PSD',lambda:self.export('psd')),('导出分层 PDF',lambda:self.export('pdf')),('导出分层 PPTX',lambda:self.export('pptx')),('导出灯光 GIF',lambda:self.export('gif')),('导出审阅报告',self.export_report),('退出',self.close)]:fm.add_command(label=title,command=cmd)
        edit=tk.Menu(menu,tearoff=False);menu.add_cascade(label='编辑',menu=edit)
        for title,cmd in [('撤销 Ctrl+Z',self.undo),('重做 Ctrl+Y',self.redo),('切分路线',self.split_selected),('删除',self.delete_selected),('操纵矩阵',self.movement_matrix),('运行情景',self.edit_scenario),('机场整体参数',self.project_settings)]:edit.add_command(label=title,command=cmd)
        review=tk.Menu(menu,tearoff=False);menu.add_cascade(label='审阅',menu=review);review.add_command(label='打开独立审阅窗口',command=self.open_review);review.add_command(label='规范来源与覆盖',command=self.coverage)
        helpmenu=tk.Menu(menu,tearoff=False);menu.add_cascade(label='帮助',menu=helpmenu);helpmenu.add_command(label='绘图操作说明',command=self.help)
        header=tk.Frame(self,bg='#1b3048',height=44);header.pack(fill='x');header.pack_propagate(False)
        tk.Label(header,text='  AIRPORT CANVAS',bg='#1b3048',fg='white',font=('Segoe UI',15,'bold')).pack(side='left',padx=12)
        tk.Label(header,text='所见即所得机场图编辑',bg='#1b3048',fg='#b3cadf',font=('Microsoft YaHei UI',10)).pack(side='left',padx=15)
        bar=ttk.Frame(self);bar.pack(fill='x',padx=10,pady=6)
        for title,cmd in [('↖ 选择',lambda:self.set_mode('SELECT')),('↶ 撤销',self.undo),('↷ 重做',self.redo),('打开',self.open),('保存',self.save),('导出 PNG',lambda:self.export('png')),('导出 SVG',lambda:self.export('svg')),('适合画布',self.fit)]:ttk.Button(bar,text=title,command=cmd).pack(side='left',padx=2)
        for title,var,cmd in [('网格',self.grid_visible,self.redraw),('辅助名称',self.labels,self.refresh),('自动等待线',self.facilities,self.refresh),('保护区',self.protection,self.refresh),('连续绘制',self.repeat,lambda:None)]:ttk.Checkbutton(bar,text=title,variable=var,command=cmd).pack(side='left',padx=6)
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=8)
        left=ttk.Frame(body,width=195);body.add(left,weight=0)
        tabs=ttk.Notebook(left);tabs.pack(fill='both',expand=True)
        tools=ttk.Frame(tabs);objects=ttk.Frame(tabs);tabs.add(tools,text='  绘制工具  ');tabs.add(objects,text='  场景对象  ')
        toolcanvas=tk.PropertyScrollArea(tools,width=180)
        toolcanvas.q.setVerticalScrollBarPolicy(tk.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        toolcanvas.pack(fill='both',expand=True)
        toolbody=ttk.Frame(toolcanvas)
        toolcanvas.set_body(toolbody)
        self.tool_body=toolbody
        self.tool_canvas=toolcanvas
        def group(title,items,opened=False):
            outer=ttk.Frame(toolbody);outer.pack(fill='x',padx=3,pady=2);inner=ttk.Frame(outer)
            state=tk.BooleanVar(value=opened)
            def toggle():
                state.set(not state.get())
                if state.get():inner.pack(fill='x',pady=4)
                else:inner.pack_forget()
                button.configure(text=('▾ ' if state.get() else '▸ ')+title)
            button=ttk.Button(outer,text=('▾ ' if opened else '▸ ')+title,command=toggle);button.pack(fill='x')
            if opened:inner.pack(fill='x',pady=4)
            for index,(key,label) in enumerate(items):
                photo=self.tool_icon(key);self._photos[key]=photo
                b=ttk.Button(inner,image=photo,text=label,compound='top',style='Tool.TButton',command=lambda k=key:self.set_mode(k))
                self.tool_buttons[key]=b
                b.grid(row=index//2,column=index%2,sticky='nsew',padx=2,pady=2)
                b.bind('<Enter>',lambda e,k=key:self.tool_hint(k));inner.columnconfigure(index%2,weight=1)
        group('基础道面',[('RUNWAY','跑道'),('TAXIWAY','滑行道'),('APRON','机坪'),('APRON_TAXIWAY','机坪滑行道'),('STAND_TAXILANE','机位通道'),('STAND','机位'),('ROAD','服务车道'),('PROTECTION','保护区'),('EQUIPMENT','设备区域'),('CLOSED_AREA','关闭区域')],True)
        group('岔路与连接',[('CONNECT','连接曲线'),('JUNCTION','编辑岔路口')],True)
        for name in dict.fromkeys(x['group'] for x in CATALOG.values()):group(name,[('MARK:'+k,x['name']) for k,x in CATALOG.items() if x['group']==name],name=='跑道标记')
        self.tree=ttk.Treeview(objects,columns=('kind',),show='tree headings',selectmode='browse');self.tree.heading('#0',text='对象');self.tree.heading('kind',text='类型');self.tree.column('#0',width=115);self.tree.column('kind',width=65)
        self.tree.pack(fill='both',expand=True);self.tree.bind('<<TreeviewSelect>>',self.tree_select)
        self.canvas=tk.Canvas(body,bg='#e9eef2',highlightthickness=0);body.add(self.canvas,weight=1)
        right=ttk.Frame(body,width=305);body.add(right,weight=0)
        self.property_title=ttk.Label(right,text='属性',font=('Microsoft YaHei UI',12,'bold'));self.property_title.pack(anchor='w',padx=12,pady=10)
        property_holder=ttk.Frame(right);property_holder.pack(fill='both',expand=True)
        self.property_canvas=tk.Canvas(property_holder,width=290,highlightthickness=0,bg='#f0f3f6');ps=ttk.Scrollbar(property_holder,command=self.property_canvas.yview);self.property_canvas.configure(yscrollcommand=ps.set)
        ps.pack(side='right',fill='y');self.property_canvas.pack(fill='both',expand=True)
        self.property_body=ttk.Frame(self.property_canvas);pw=self.property_canvas.create_window(0,0,window=self.property_body,anchor='nw')
        self.property_body.bind('<Configure>',lambda e:self.property_canvas.configure(scrollregion=self.property_canvas.bbox('all')));self.property_canvas.bind('<Configure>',lambda e:self.property_canvas.itemconfigure(pw,width=e.width))
        self.property_canvas.bind('<MouseWheel>',self.scroll_sidebar)
        self.apply_button=ttk.Button(right,text='应用属性  ↵',command=self.apply_properties);self.apply_button.pack(fill='x',padx=9,pady=7)
        ttk.Button(right,text='聚焦对象',command=self.focus_selected).pack(fill='x',padx=9,pady=(0,7))
        self.property_error=ttk.Label(right,text='',foreground='#a23b46',wraplength=280);self.property_error.pack(fill='x',padx=9,pady=4)
        # Review widgets are deliberately not packed into the drawing workspace.
        self.issues=ttk.Treeview(self,columns=('state','object','rule','message'),show='headings');self.summary=ttk.Label(self)
        bottom=ttk.Frame(self);bottom.pack(fill='x',padx=10,pady=5)
        ttk.Label(bottom,textvariable=self.status).pack(side='left',fill='x',expand=True)
        self.review_count=ttk.Button(bottom,text='审阅',command=self.open_review);self.review_count.pack(side='right',padx=8)
        ttk.Label(bottom,textvariable=self.view_status).pack(side='right')

    def tool_icon(self,key):
        if key.startswith('MARK:'):
            mark=key[5:];mode=CATALOG[mark]['mode'];pts=[[0,0],[45,0]] if mode!='AREA' else [[0,0],[25,0],[25,18],[0,18]]
            p=dict(CATALOG[mark]['defaults'],mark_type=mark)
            items=primitives(dict(id='icon',points=pts,props=p))
            allpts=[q for x in items for q in x['points']]
            x0=min(q[0] for q in allpts);x1=max(q[0] for q in allpts);y0=min(q[1] for q in allpts);y1=max(q[1] for q in allpts)
            for e in items:
                if e['type']=='text':
                    h=e['size'];w=max(h,len(e['text'])*h*.65);x,y=e['points'][0];x0=min(x0,x-w/2);x1=max(x1,x+w/2);y0=min(y0,y-h/2);y1=max(y1,y+h/2)
            scale=min(62/max(1,x1-x0),30/max(1,y1-y0));im=draw_items(items,(72,40),[36-(x0+x1)*scale/2,20+(y0+y1)*scale/2],scale,'#56616e')
        else:
            im=Image.new('RGB',(72,40),'#e3e9ee');d=ImageDraw.Draw(im)
            if key in ('APRON','STAND','PROTECTION'):d.rounded_rectangle((9,5,63,35),radius=3,fill='#9ba6b1',outline='#54718a');d.line((36,8,36,32),fill='#ffe48a',width=2)
            elif key=='JUNCTION':
                d.line((5,20,67,20),fill='#929aa4',width=18);d.line((36,0,36,40),fill='#929aa4',width=18);d.arc((22,6,50,34),180,270,fill='#ffe48a',width=2);d.line((5,20,67,20),fill='#ffe48a')
            elif key=='CONNECT':d.arc((8,-14,66,43),0,125,fill='#c2b9a6',width=15);d.arc((8,-14,66,43),0,125,fill='#6f7c87',width=10);d.arc((8,-14,66,43),0,125,fill='#ffe48a',width=1)
            else:
                d.line((5,20,67,20),fill='#bfb4a3',width=26);d.line((5,20,67,20),fill='#55616e',width=18)
                if key=='RUNWAY':
                    for x in range(9,63,15):d.line((x,20,x+8,20),fill='white')
                else:d.line((6,20,66,20),fill='#ffe48a')
        return ImageTk.PhotoImage(im,master=self)

    def tool_hint(self,key):
        if key.startswith('MARK:'):
            s=CATALOG[key[5:]];self.status.set(s['name']+' · '+s['clause']+' · '+('单击放置，右侧调整方向与尺寸' if s['mode']=='POINT' else '点击绘制；区域按Enter结束' if s['mode']=='AREA' else '点击起点和终点'))

    def set_mode(self,mode):
        self.highlight_tool(mode)
        self.mode=mode;self.points=[];self.connect_ports=[];self.drag=None
        title=CATALOG[mode[5:]]['name'] if mode.startswith('MARK:') else NAMES.get(mode,{'SELECT':'选择 / 移动','CONNECT':'连接向导','JUNCTION':'编辑岔路口'}.get(mode,mode))
        self.status.set(title+' · '+('点击对象后直接编辑右侧属性' if mode=='SELECT' else '点击路口中心选择各转弯引导线' if mode=='JUNCTION' else 'Esc取消；Enter完成区域绘制'))
        self.canvas.configure(cursor='arrow' if mode=='SELECT' else 'crosshair');self.redraw()

    def highlight_tool(self,mode=None):
        for key,button in self.tool_buttons.items():button.configure(style='Selected.Tool.TButton' if key==(mode or self.mode) else 'Tool.TButton')

    def pick(self,p,paths_only=False):
        if not paths_only:
            for aid,a in reversed(list(self.scene.assets.items())):
                if a['kind']!='MARKING':continue
                if CATALOG[a['props']['mark_type']]['mode']=='AREA' and g.inside(p,a['points']):return 0,aid,0,p
                for e in primitives(a):
                    if e['type']=='text' and g.distance(e['points'][0],p)<max(7/self.zoom,e['size']*1.5):return 0,aid,0,p
                    if e['type']=='polygon' and e.get('fill') and g.inside(p,e['points']):return 0,aid,0,p
                    if len(e['points'])>1 and g.project(e['points']+([e['points'][0]] if e['type']=='polygon' else []),p)[0]<max(6/self.zoom,e.get('width',.15)):return 0,aid,0,p
        return super().pick(p,paths_only)

    def click(self,e):
        self.canvas.focus_set()
        p=self.world(e.x,e.y)
        if self.mode=='JUNCTION':
            options=[j for j in crossings(self.scene) if g.distance(j['point'],p)<max(30,16/self.zoom)]
            if options:self.select(min(options,key=lambda j:g.distance(j['point'],p))['id'])
            else:self.status.set('此处没有可编辑的道面交汇点；可先让路线相交或使用连接曲线。')
            return
        if self.mode.startswith('MARK:'):
            key=self.mode[5:];spec=CATALOG[key];self.points.append(p)
            if spec['mode']=='POINT' or spec['mode']=='PATH' and len(self.points)==2:self.finish_draw()
            else:self.redraw()
            return
        if self.mode=='SELECT':
            if self.selection in self.scene.assets:
                a=self.scene.assets[self.selection]
                candidates=[(g.distance(p,q),i) for i,q in enumerate(a['points'])]
                distance,index=min(candidates)
                if distance<8/self.zoom:
                    self.drag=dict(vertex=index,start=p,old=copy.deepcopy(a['points']),delta=[0,0]);return
            return super().click(e)
        if self.mode in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
            # A click on a road/runway mouth anchors to its axis. Surface clipping
            # still stops at the runway edge, while guidance reaches the axis.
            candidates=[]
            for a in self.scene.assets.values():
                if a['kind'] in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                    d,station,q=g.project(a['points'],p)
                    if d<=a['props']['width']/2+min(5,8/self.zoom):candidates.append((d,q))
            if candidates:p=min(candidates,key=lambda x:x[0])[1]
            self.points.append(p)
            if len(self.points)==2:self.finish_draw()
            else:self.redraw()
            return
        return super().click(e)

    def motion(self,e):
        if self.drag and 'vertex' in self.drag:
            pts=copy.deepcopy(self.drag['old']);pts[self.drag['vertex']]=self.world(e.x,e.y)
            self.drag['points']=pts;self.canvas.delete('drag_preview')
            screen=[self.screen(p) for p in pts]
            self.canvas.create_line(*[v for p in screen for v in p],fill='#0f9ebb',width=3,dash=(6,3),tags='drag_preview')
        else:super().motion(e)

    def release(self,e):
        if self.drag and 'vertex' in self.drag:
            try:
                if 'points' in self.drag:self.scene.update_asset(self.selection,points=self.drag['points']);self.refresh()
            except ValueError as exc:self.property_error.configure(text='未移动：'+str(exc))
            self.drag=None;self.canvas.delete('drag_preview');return
        super().release(e)

    def pointer(self,e):
        super().pointer(e);self.canvas.delete('cursor_preview')
        if self.points and self.mode not in ('SELECT','CONNECT','JUNCTION'):
            p=self.screen(self.points[-1]);self.canvas.create_line(*p,e.x,e.y,fill='#0f9ebb',dash=(5,3),width=2,tags='cursor_preview')

    def finish_draw(self):
        mode=self.mode
        if mode in ('SELECT','CONNECT','JUNCTION') or not self.points:return
        is_mark=mode.startswith('MARK:');spec=CATALOG[mode[5:]] if is_mark else None
        area=(spec and spec['mode']=='AREA') or mode in AREA_KINDS
        if area and len(self.points)<3:self.status.set('区域至少需要三个顶点，Enter结束。');return
        if not area and not (spec and spec['mode']=='POINT') and len(self.points)<2:return
        try:
            pts=copy.deepcopy(self.points)
            if is_mark:
                if spec['mode']=='POINT':pts=[pts[0],[pts[0][0]+10,pts[0][1]]]
                self.selection=self.scene.create_marking(mode[5:],pts)
            else:self.selection=self.scene.create_asset(mode,NAMES[mode]+' '+str(len(self.scene.assets)+1),pts)
            self.points=[];self.route_preview=None
            if not self.repeat.get():self.mode='SELECT';self.canvas.configure(cursor='arrow')
            self.refresh()
        except (ValueError,TypeError) as exc:self.property_error.configure(text=str(exc))

    def select(self,oid):
        self.selection=oid
        if oid and self.tree.exists(oid):self.tree.selection_set(oid);self.tree.see(oid)
        self.update_inspector();self.redraw()

    def refresh(self):
        self.highlight_tool()
        self.render_items=display_list(self.scene,self.labels.get(),self.facilities.get(),self.protection.get())
        for item in self.tree.get_children():self.tree.delete(item)
        for aid,a in self.scene.assets.items():self.tree.insert('', 'end',iid=aid,text=a['name'],values=(NAMES[a['kind']],))
        for mid,m in self.scene.movements.items():self.tree.insert('', 'end',iid=mid,text=m['name'],values=(ROLE_NAMES[m['role']],))
        routes=route_objects(self.scene)
        for j in crossings(self.scene):self.tree.insert('', 'end',iid=j['id'],text=' × '.join(routes[x]['name'] for x in j['assets']),values=('岔路口',))
        if self.selection and self.tree.exists(self.selection):self.tree.selection_set(self.selection)
        self.validate(True);self.update_inspector();self.redraw();self.update_title()

    def section(self,title):
        frame=ttk.LabelFrame(self.property_body,text=title,padding=8);frame.pack(fill='x',padx=7,pady=5);frame.columnconfigure(1,weight=1);return frame

    def property_field(self,parent,key,label,value,kind='float',choices=None):
        row=__import__('property_rows').next_row(parent)
        ttk.Label(parent,text=label,wraplength=105).grid(row=row,column=0,sticky='w',padx=(0,6),pady=4)
        if kind=='bool':
            var=tk.BooleanVar(value=bool(value));control=ttk.Checkbutton(parent,variable=var,command=self.apply_properties)
        else:
            var=tk.StringVar(value='' if value is None else str(value))
            if kind=='radio':
                control=ttk.Frame(parent)
                for choice in choices:
                    ttk.Radiobutton(control,text={'GUIDED':'有引导','UNGUIDED':'无引导'}.get(choice,choice),value=choice,variable=var,command=self.apply_properties).pack(anchor='w')
            elif kind=='color':
                from qt_widgets21 import colorchooser
                def choose():
                    color=colorchooser.askcolor(var.get(),parent=parent)[1]
                    if color:
                        var.set(color)
                        control.configure(text=color)
                        self.apply_properties()
                control=ttk.Button(parent,text=var.get(),command=choose)
            elif choices:
                control=ttk.Combobox(parent,textvariable=var,values=choices,state='readonly',width=15);control.bind('<<ComboboxSelected>>',lambda e:self.apply_properties())
            else:control=ttk.Entry(parent,textvariable=var,width=17);control.bind('<Return>',lambda e:self.apply_properties());control.bind('<FocusOut>',lambda e:self.apply_properties())
        control.grid(row=row,column=1,sticky='ew',pady=4);self.editor_vars[key]=(var,'text' if kind=='color' else kind)
        return control

    def update_inspector(self):
        self._inspector_busy=True
        for child in self.property_body.winfo_children():child.destroy()
        self.editor_vars={};self.property_error.configure(text='');self._editor_oid=self.selection
        try:
            oid=self.selection
            if oid and oid.startswith('J:'):self.junction_inspector(oid);return
            a=self.scene.assets.get(oid) or getattr(self,'auto_assets',{}).get(oid);m=self.scene.movements.get(oid)
            if not a and not m:
                self.property_title.configure(text='绘图属性')
                ttk.Label(self.property_body,text='从左侧图标选择道面或标记。\n\n点选图中元素，即可在此编辑。\n\n左键绘制 / 选择\n右键拖动画布\n滚轮缩放\nEnter结束区域\nEsc取消工具',justify='left',padding=15).pack(fill='x')
                return
            self.property_title.configure(text=(a or m)['name'])
            general=self.section('基本信息');self.property_field(general,'name','名称',(a or m)['name'],'text')
            if m:
                shape=self.section('连接道面与引导')
                for key,label,default in [('width','道面宽度 m',12),('shoulder','每侧道肩 m',7.5),('handle','曲线控制 m',60)]:self.property_field(shape,key,label,m.get(key,default))
                for key,label in [('guide_visible','显示引导线'),('pavement_visible','显示连接道面'),('edges_visible','显示边线')]:self.property_field(shape,key,label,m.get(key,True),'bool')
                self.property_field(shape,'_exit_only_markings','仅允许滑出道面标记',
                                    not m.get('show_holding',True),'bool')
                ttk.Button(self.property_body,text='方向、用途及保护区…',command=lambda:BaseApp.edit_movement(self,oid)).pack(fill='x',padx=8,pady=8);return
            p=a['props'];pts=a['points'];position=self.section('位置与方向')
            self._point_marker=a['kind']=='MARKING' and CATALOG[p['mark_type']]['mode']=='POINT'
            center=list(pts[0]) if self._point_marker else [sum(x[k] for x in pts)/len(pts) for k in (0,1)]
            self._editor_center=center
            for key,label,value in [('x','中心 X / m',center[0]),('y','中心 Y / m',center[1])]:self.property_field(position,key,label,round(value,3))
            if len(pts)==2:
                u=g.unit(*pts);self.property_field(position,'heading','方位 / °',round(math.degrees(math.atan2(u[0],u[1]))%360,3))
                if not self._point_marker:self.property_field(position,'length','绘制长度 m',round(g.length(pts),3))
            style=self.section('尺寸与外观')
            if a['kind']=='MARKING':
                entry=CATALOG[p['mark_type']]
                ttk.Label(style,text=entry['name']+' · '+entry['clause'],wraplength=240).grid(row=0,column=0,columnspan=2,sticky='w',pady=4)
                for key,label,value,kind in [('width','横向尺寸 m',p['width'],'float'),('line_width','线宽 m',p.get('line_width',.15),'float'),('spacing','间距 m',p.get('spacing',2),'float'),('text','文字内容',p.get('text',''),'text'),('text_height','字高 m',p.get('text_height',4),'float'),('background','显示文字底色',p.get('background',True),'bool')]:
                    if key in EDITABLE_FIELDS.get(entry['shape'],set()):self.property_field(style,key,label,value,kind)
                if entry['shape']=='tdz':self.property_field(style,'bars','每组条数',p.get('bars',3),'int')
                if entry['shape']=='aim':self.property_field(style,'lda','可用着陆距 m',p.get('lda',2400))
            elif a['kind'] in PATH_KINDS:
                for key,label,default in [('width','道面宽度 m',18),('shoulder','每侧道肩 m',0),('fillet_radius','道面圆角 m',25),('turn_radius','路口转弯 m',25)]:self.property_field(style,key,label,p.get(key,default))
                for key,label,default in [('auto_markings','自动道面标记',True),('center_visible','显示中线',True),('edges_visible','显示边线',True),('shoulder_markings','道肩条带',False)]:self.property_field(style,key,label,p.get(key,default),'bool')
                if a['kind']=='RUNWAY':
                    for end,title in [('a','A端'),('b','B端')]:
                        ef=self.section(title+' 跑道标记');self.property_field(ef,'label_'+end,'号码',p.get('label_'+end,'09'),'text');self.property_field(ef,'level_'+end,'进近类别',p.get('level_'+end,'1'),'text',APPROACH_LEVELS);self.property_field(ef,'displaced_'+end,'入口内移 m',p.get('displaced_'+end,0));self.property_field(ef,'lda_'+end,'LDA m',p.get('lda_'+end))
                    for key,label in [('show_numbers','号码'),('show_thresholds','入口条纹'),('show_aimpoints','瞄准点'),('show_tdz','接地带')]:self.property_field(style,key,label,p.get(key,True),'bool')
                if a['kind']=='STAND':
                    self.property_field(style,'guidance','引导方式',p.get('guidance','GUIDED'),'radio',['GUIDED','UNGUIDED']);self.property_field(style,'stop_reference','停止点参考',p.get('stop_reference','NOSEWHEEL'),'text',['NOSEWHEEL','LEFT_SEAT'])
            if a['kind']!='MARKING':ttk.Button(self.property_body,text='更多工程参数…',command=lambda:BaseApp.edit_selected(self)).pack(fill='x',padx=8,pady=8)
        finally:self._inspector_busy=False

    def apply_properties(self):
        if self._inspector_busy or self.selection!=getattr(self,'_editor_oid',None) or not self.editor_vars:return
        oid=self.selection
        if oid and oid.startswith('J:'):return self.apply_junction()
        try:
            values={}
            for key,(var,kind) in self.editor_vars.items():
                value=var.get()
                if kind in ('float','int'):
                    value=None if str(value).strip()=='' else float(value) if kind=='float' else int(value)
                    if value is not None and not math.isfinite(value):raise ValueError('数值必须有限')
                values[key]=value
            name=values.pop('name')
            if oid in self.scene.movements:
                if '_exit_only_markings' in values:values['show_holding']=not values.pop('_exit_only_markings')
                self.scene.update_movement(oid,name=name,**values)
            elif oid in self.scene.assets:
                a=self.scene.assets[oid];center=self._editor_center;pts=a['points'];x=values.pop('x');y=values.pop('y')
                if x is None or y is None:raise ValueError('位置不可为空')
                if self._point_marker:
                    heading=values.pop('heading');angle=math.radians(heading)
                    points=[[x,y],[x+g.length(pts)*math.sin(angle),y+g.length(pts)*math.cos(angle)]]
                elif 'length' in values:
                    length=values.pop('length');heading=values.pop('heading')
                    if length is None or length<=0 or heading is None:raise ValueError('绘制长度必须为正，方位不可为空')
                    points=g.line([x,y],length,heading)
                else:points=[[p[0]+x-center[0],p[1]+y-center[1]] for p in pts]
                self.scene.update_asset(oid,name,points,values)
                self._editor_center=list(points[0]) if self._point_marker else [sum(p[k] for p in points)/len(points) for k in (0,1)]
            if self.tree.exists(oid):self.tree.item(oid,text=name)
            self.property_title.configure(text=name)
            self.route_preview=None;self.render_items=display_list(self.scene,self.labels.get(),self.facilities.get(),self.protection.get());self.validate(True);self.redraw();self.update_title();self.property_error.configure(text='')
        except (ValueError,TypeError) as exc:self.property_error.configure(text='未应用：'+str(exc))

    def edit_selected(self):self.update_inspector();self.property_canvas.yview_moveto(0)

    def update_title(self):
        self.title(('● ' if self.dirty() else '')+'Airport Canvas — '+(self.filepath.name if self.filepath else self.scene.data['meta']['name']))

    def focus_selected(self):
        if self.selection and self.selection.startswith('J:'):
            j=next((j for j in crossings(self.scene) if j['id']==self.selection),None)
            if j:
                x,y=j['point'];self.zoom=max(self.zoom,2)
                self.origin=[self.canvas.winfo_width()/2-x*self.zoom,self.canvas.winfo_height()/2+y*self.zoom];self.redraw()
        else:super().focus_selected()

    def delete_selected(self):
        if self.selection and self.selection.startswith('J:'):
            self.status.set('岔路口随道路几何生成；可在右侧关闭引导线，或编辑道路。');return
        super().delete_selected()

    def junction_inspector(self,jid):
        routes=route_objects(self.scene)
        j=next((x for x in crossings(self.scene) if x['id']==jid),None)
        if j is None:return
        self.property_title.configure(text='岔路口引导线')
        settings=self.scene.data.get('junctions',{}).get(jid,{})
        section=self.section('路口设置');ttk.Label(section,text=' × '.join(routes[k]['name'] for k in j['assets']),wraplength=240).grid(row=0,column=0,columnspan=2,sticky='w',pady=5)
        self.property_field(section,'radius','转弯半径 m',settings.get('radius',25))
        straights=self.section('直行引导线')
        for i,aid in enumerate(j['assets']):self.property_field(straights,'straight_'+str(i),routes[aid]['name'],settings.get('straight_'+str(i),True),'bool')
        turns=self.section('转弯引导线')
        for a in (-1,1):
            for b in (-1,1):
                key=f'{a}:{b}';label=f'{routes[j["assets"][0]]["name"]} {"起点" if a<0 else "终点"} ↔\n{routes[j["assets"][1]]["name"]} {"起点" if b<0 else "终点"}'
                self.property_field(turns,'guide_'+key,label,settings.get('guides',{}).get(key,True),'bool')
        ttk.Button(self.property_body,text='显示全部转弯',command=lambda:self.all_junction_guides(True)).pack(fill='x',padx=8,pady=4)
        ttk.Button(self.property_body,text='隐藏全部转弯',command=lambda:self.all_junction_guides(False)).pack(fill='x',padx=8,pady=4)
        ttk.Label(self.property_body,text='这些开关只改变图上的引导线；\n不会删除道面，也不自动改变通行许可。',wraplength=255,padding=10).pack(fill='x')
    def apply_junction(self):
        try:
            radius=float(self.editor_vars['radius'][0].get());data={'radius':radius,'guides':{}}
            for key,(var,kind) in self.editor_vars.items():
                if key.startswith('guide_'):data['guides'][key[6:]]=bool(var.get())
                elif key.startswith('straight_'):data[key]=bool(var.get())
            self.scene.configure_junction(self.selection,**data);self.render_items=display_list(self.scene,self.labels.get(),self.facilities.get(),self.protection.get());self.redraw();self.update_title();self.property_error.configure(text='')
        except (ValueError,TypeError) as exc:self.property_error.configure(text=str(exc))
    def all_junction_guides(self,value):
        for key,(var,kind) in self.editor_vars.items():
            if key.startswith('guide_'):var.set(value)
        self.apply_junction()

    def redraw(self):
        if not hasattr(self,'canvas'):return
        c=self.canvas;c.delete('all');w=max(1,c.winfo_width());h=max(1,c.winfo_height())
        if w*h>8_000_000:return
        image=draw_items(self.render_items,(w,h),self.origin,self.zoom,grid=self.grid_visible.get())
        self._canvas_image=ImageTk.PhotoImage(image,master=self);c.create_image(0,0,image=self._canvas_image,anchor='nw')
        oid=self.selection
        if oid in self.scene.assets:
            a=self.scene.assets[oid];pts=[self.screen(p) for p in a['points']]
            if a['kind'] in AREA_KINDS or a['kind']=='MARKING' and CATALOG[a['props']['mark_type']]['mode']=='AREA':c.create_polygon(*[v for p in pts for v in p],fill='',outline='#0f9ebb',width=2,dash=(5,3))
            elif len(pts)>1:c.create_line(*[v for p in pts for v in p],fill='#0f9ebb',width=2,dash=(5,3))
            for x,y in pts:c.create_rectangle(x-4,y-4,x+4,y+4,fill='white',outline='#0c90ad',width=2)
        elif oid in self.scene.movements:
            pts=[self.screen(p) for p in self.scene.movement_path(oid)];c.create_line(*[v for p in pts for v in p],fill='#0f9ebb',width=2,dash=(5,3))
        if self.mode=='JUNCTION' or oid and oid.startswith('J:'):
            for j in crossings(self.scene):
                x,y=self.screen(j['point']);c.create_oval(x-7,y-7,x+7,y+7,fill='#d8f2f7',outline='#098ba8',width=2)
        if self.points:
            pts=[self.screen(p) for p in self.points]
            for x,y in pts:c.create_oval(x-4,y-4,x+4,y+4,fill='#0f9ebb',outline='white')
            if len(pts)>1:c.create_line(*[v for p in pts for v in p],fill='#0f9ebb',width=2,dash=(5,3))
        for port in self.connect_ports:
            p,_=g.at(self.scene.assets[port['asset']]['points'],port['station']);x,y=self.screen(p);c.create_oval(x-6,y-6,x+6,y+6,fill='#0f9ebb',outline='white')
        if self.route_preview:
            pts=[self.screen(p) for p in self.route_preview['points']]
            if len(pts)>1:c.create_line(*[v for p in pts for v in p],fill='#2182c5',width=3,dash=(8,4))
        c.create_line(w-25,44,w-25,18,arrow='last',fill='#526c7c',width=2);c.create_text(w-25,9,text='N',fill='#526c7c')

    def validate(self,silent=False):
        self.report=validate_scene(self.scene);s=self.report['summary'];self.review_count.configure(text=f'审阅 · {s["FAIL"]} 项问题 / {s["UNKNOWN"]+s["UNVERIFIED"]} 项待核')
        if not silent:self.open_review()
    def open_review(self):
        if self._review and self._review.winfo_exists():self._review.destroy()
        self.report=validate_scene(self.scene);win=tk.Toplevel(self);self._review=win;win.title('独立审阅 · 不占用绘图画布');win.geometry('1080x590')
        ttk.Label(win,text='审阅仅覆盖已实现规则；未核验的图表、场地条件和专项数据不计为通过。',padding=12).pack(fill='x')
        tree=ttk.Treeview(win,columns=('state','object','rule','message'),show='headings')
        for key,label,width in [('state','状态',100),('object','对象',150),('rule','规则',150),('message','说明',620)]:tree.heading(key,text=label);tree.column(key,width=width)
        tree.pack(fill='both',expand=True,padx=12,pady=5)
        reviewed_issues=copy.deepcopy(self.report['issues'])
        for i,item in enumerate(reviewed_issues):
            obj=self.scene.assets.get(item['object_id']) or self.scene.movements.get(item['object_id']);tree.insert('', 'end',iid=str(i),values=(STATES[item['status']],obj['name'] if obj else '场景',item['rule'],item['message']))
        def locate(e=None):
            if tree.selection():
                item=reviewed_issues[int(tree.selection()[0])]
                if item['object_id']:self.select(item['object_id']);self.focus_selected()
        tree.bind('<<TreeviewSelect>>',locate)
        ttk.Button(win,text='刷新审阅',command=self.open_review).pack(side='left',padx=12,pady=10)
        ttk.Button(win,text='导出报告',command=self.export_report).pack(side='right',padx=12,pady=10);ttk.Button(win,text='规范来源与覆盖',command=self.coverage).pack(side='right',pady=10)
    def export(self,kind):
        p=filedialog.asksaveasfilename(title='导出当前图层的机场图',defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if not p:return
        try:
            (export_png if kind=='png' else export_svg)(self.scene,p,labels=self.labels.get(),facilities=self.facilities.get(),protection=self.protection.get());self.status.set('已导出：'+p)
        except (ValueError,OSError) as exc:messagebox.showerror('导出失败',str(exc),parent=self)
    def help(self):
        messagebox.showinfo('机场图绘制','左侧是分组图标工具：\n• 点状标记单击放置，右侧调整尺寸与方向。\n• 线状标记依次点击起点和终点。\n• 区域标记连续点选顶点，Enter结束。\n\n点选元素后，右侧可直接输入、勾选和选择。\n“编辑岔路口”点选交汇中心，可选择每条转弯引导线。\n\n画布和PNG使用同一渲染器；导出不附加审阅文字。\n审阅信息在底部按钮和独立窗口中。',parent=self)

def main():
    import sys
    scene=AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None
    app=EditorApp(scene);app.mainloop()
