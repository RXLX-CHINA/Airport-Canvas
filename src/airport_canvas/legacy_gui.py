#!/usr/bin/env python3
"""Airport Scene Studio: local desktop scene editor, no web service required."""
import copy
import json
import math
from pathlib import Path
import sys
from interface_language import APPROACH_LEVELS
import qt_compat as tk
from qt_compat import ttk,filedialog,messagebox
import traceback
import webbrowser
from airport_scene import AirportScene,PATH_KINDS,AREA_KINDS
import scene_geometry as g
from scene_rules import validate_scene
from scene_render import display_list,bounds,export_png,export_svg,COLORS

BASE=Path(__file__).resolve().parent
NAMES={'RUNWAY':'跑道','TAXIWAY':'滑行道','APRON':'机坪','APRON_TAXIWAY':'机坪滑行道',
       'STAND_TAXILANE':'机位滑行通道','STAND':'机位','ROAD':'服务车道','PROTECTION':'保护区',
       'EQUIPMENT':'设备区','CLOSED_AREA':'临时关闭区'}
ROLE_NAMES={'ENTRY':'跑道入口','EXIT':'普通出口','EXIT_ONLY':'仅作出口','RAPID_EXIT':'快速出口',
            'CROSSING':'穿越连接','TAXIWAY_JOIN':'滑行道连接','APRON_ACCESS':'机坪连接',
            'STAND_ENTRY':'机位引入','PUSHBACK':'推出路线','ROAD_CROSSING':'道路连接'}
STATES={'PASS':'通过（局部）','FAIL':'不满足','UNKNOWN':'缺少数据','UNVERIFIED':'尚未核验',
        'NOT_APPLICABLE':'当前不适用','REVIEW_REQUIRED':'需设计复核'}
STATUS_COLOR={'FAIL':'#ad394a','UNKNOWN':'#aa6d18','UNVERIFIED':'#78599d','PASS':'#317861','REVIEW_REQUIRED':'#a55a21','NOT_APPLICABLE':'#667782'}

class FormDialog(tk.Toplevel):
    """Typed modal forms, scrollable at small display sizes."""
    def __init__(self,parent,title,fields,values):
        super().__init__(parent);self.title(title);self.result=None;self.fields=fields;self.variables={}
        self.transient(parent);self.geometry('570x650');self.minsize(450,400)
        holder=ttk.Frame(self);holder.pack(fill='both',expand=True,padx=16,pady=12)
        canvas=tk.Canvas(holder,highlightthickness=0);scroll=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        form=ttk.Frame(canvas);window=canvas.create_window(0,0,window=form,anchor='nw')
        form.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        form.columnconfigure(1,weight=1)
        for row,(key,label,kind,choices) in enumerate(fields):
            ttk.Label(form,text=label,wraplength=200).grid(row=row,column=0,sticky='w',padx=(0,14),pady=7)
            value=values.get(key,'')
            if kind=='multi':
                entry=tk.Listbox(form,selectmode='multiple',exportselection=False,height=min(5,max(2,len(choices))),font=('Microsoft YaHei UI',9))
                for idx,(identifier,text) in enumerate(choices):
                    entry.insert('end',text)
                    if identifier in (value or []):entry.selection_set(idx)
                v=entry
            elif kind=='bool':
                v=tk.BooleanVar(value=bool(value));entry=ttk.Checkbutton(form,variable=v)
            else:
                v=tk.StringVar(value='' if value is None else str(value))
                if choices:entry=ttk.Combobox(form,textvariable=v,values=choices,state='readonly')
                else:entry=ttk.Entry(form,textvariable=v)
            entry.grid(row=row,column=1,sticky='ew',pady=7);self.variables[key]=v
        ttk.Label(self,text='空白工程数值表示未知；不会自动判定满足规范。',foreground='#856424').pack(pady=4)
        buttons=ttk.Frame(self);buttons.pack(fill='x',padx=16,pady=12)
        ttk.Button(buttons,text='取消',command=self.destroy).pack(side='right',padx=5)
        ttk.Button(buttons,text='应用',command=self.submit).pack(side='right')
        self.bind('<Escape>',lambda e:self.destroy());self.protocol('WM_DELETE_WINDOW',self.destroy)
        self.grab_set();self.wait_visibility();self.focus_set();parent.wait_window(self)

    def submit(self):
        try:
            data={}
            for key,label,kind,choices in self.fields:
                if kind=='multi':
                    data[key]=[choices[i][0] for i in self.variables[key].curselection()]
                    continue
                value=self.variables[key].get()
                if kind in ('float','int'):
                    if not str(value).strip():value=None
                    else:value=float(value) if kind=='float' else int(value)
                    if value is not None and not math.isfinite(value):raise ValueError(label+'必须是有限数值')
                data[key]=value
            self.result=data;self.destroy()
        except ValueError as exc:messagebox.showerror('输入无效',str(exc),parent=self)

def field(key,label,kind='text',choices=None):return key,label,kind,choices

class AirportApp(tk.Tk):
    def __init__(self,scene=None):
        super().__init__();self.title('Airport Scene Studio · 机场场面编辑器')
        self.geometry('1480x940');self.minsize(1080,720)
        self.scene=scene or AirportScene.demo();self.filepath=None;self.saved=json.dumps(self.scene.data,sort_keys=True)
        self.selection=None;self.mode='SELECT';self.points=[];self.connect_ports=[];self.drag=None;self.route_preview=None
        self.zoom=0.4;self.origin=[500.,500.];self.render_items=[];self.report={};self.simulation=False
        self.labels=tk.BooleanVar(value=True);self.facilities=tk.BooleanVar(value=True);self.protection=tk.BooleanVar(value=True)
        self.status=tk.StringVar(value='就绪');self.view_status=tk.StringVar(value='本地设计坐标 · 单位 m')
        self._build();self._bindings();self.refresh();self._fit_after=self.after(200,self.fit);self.bind('<Destroy>',self._cancel_initial_fit,add='+')
        self.protocol('WM_DELETE_WINDOW',self.close)

    def _cancel_initial_fit(self,event):
        if event.widget==self and getattr(self,'_fit_after',None):
            try:self.after_cancel(self._fit_after)
            except tk.TclError:pass

    def report_callback_exception(self,exc,val,tb):
        details=''.join(traceback.format_exception(exc,val,tb))
        try:(BASE/'gui_error.log').write_text(details,encoding='utf-8')
        except OSError:pass
        messagebox.showerror('操作失败',str(val)+'\n详细信息见 gui_error.log',parent=self)

    def _build(self):
        self.configure(bg='#e6edf3');style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10),background='#edf2f6',foreground='#263f53')
        style.configure('TButton',padding=(9,6));style.configure('Treeview',rowheight=27,background='#ffffff',fieldbackground='#ffffff')
        style.configure('Treeview.Heading',font=('Microsoft YaHei UI',10,'bold'),padding=5)
        style.configure('Title.TLabel',font=('Microsoft YaHei UI',16,'bold'),foreground='#f2f8ff',background='#172d43')
        menu=tk.Menu(self);self.config(menu=menu)
        fm=tk.Menu(menu,tearoff=False);menu.add_cascade(label='文件',menu=fm)
        for label,cmd in [('新建场景  Ctrl+N',self.new),('打开场景  Ctrl+O',self.open),('保存场景  Ctrl+S',self.save),('另存为',lambda:self.save(True)),('导入旧版跑道/滑行道 JSON',self.import_legacy),('导出 PNG',lambda:self.export('png')),('导出 SVG',lambda:self.export('svg')),('导出核验报告',self.export_report),('退出',self.close)]:fm.add_command(label=label,command=cmd)
        em=tk.Menu(menu,tearoff=False);menu.add_cascade(label='编辑',menu=em)
        for label,cmd in [('撤销 Ctrl+Z',self.undo),('重做 Ctrl+Y',self.redo),('编辑属性',self.edit_selected),('切分所选路线',self.split_selected),('删除对象',self.delete_selected),('编辑允许操纵矩阵',self.movement_matrix),('运行情景',self.edit_scenario),('机场整体参数',self.project_settings)]:em.add_command(label=label,command=cmd)
        hm=tk.Menu(menu,tearoff=False);menu.add_cascade(label='帮助',menu=hm)
        hm.add_command(label='操作说明',command=self.help);hm.add_command(label='规范来源与覆盖状态',command=self.coverage)
        header=tk.Frame(self,bg='#172d43',height=65);header.pack(fill='x');header.pack_propagate(False)
        ttk.Label(header,text='  Airport Scene Studio',style='Title.TLabel').pack(side='left',padx=15)
        tk.Label(header,text='机场场面编辑器  /  跑道 · 滑行道 · 机坪',fg='#a5c3db',bg='#172d43',font=('Microsoft YaHei UI',10)).pack(side='left',padx=20)
        tk.Label(header,text='设计预览 · 未认证',fg='#ffd89c',bg='#172d43',font=('Microsoft YaHei UI',11,'bold')).pack(side='right',padx=22)
        tools=ttk.Frame(self);tools.pack(fill='x',padx=10,pady=7)
        for text,cmd in [('选择 / 移动',lambda:self.set_mode('SELECT')),('跑道',lambda:self.set_mode('RUNWAY')),('滑行道',lambda:self.set_mode('TAXIWAY')),('机坪',lambda:self.set_mode('APRON')),('机位',lambda:self.set_mode('STAND')),('更多对象 ▾',self.more_tools),('连接向导',lambda:self.set_mode('CONNECT')),('操纵矩阵',self.movement_matrix),('路线预览',self.preview_route),('核验',self.validate),('适合窗口',self.fit)]:ttk.Button(tools,text=text,command=cmd).pack(side='left',padx=2)
        toggles=ttk.Frame(self);toggles.pack(fill='x',padx=14,pady=(0,6))
        for title,var in [('名称',self.labels),('候选等待设施',self.facilities),('保护区',self.protection)]:ttk.Checkbutton(toggles,text=title,variable=var,command=self.refresh).pack(side='left',padx=7)
        ttk.Button(toggles,text='情景设置',command=self.edit_scenario).pack(side='right');ttk.Button(toggles,text='完成绘制 ↵',command=self.finish_draw).pack(side='right',padx=7)
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=10)
        left=ttk.Frame(body,width=235);body.add(left,weight=0)
        ttk.Label(left,text='场景对象与连接',font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',pady=8)
        self.tree=ttk.Treeview(left,columns=('kind',),show='tree headings',selectmode='browse');self.tree.heading('#0',text='名称');self.tree.heading('kind',text='类型');self.tree.column('#0',width=145);self.tree.column('kind',width=95)
        self.tree.pack(fill='both',expand=True);self.tree.bind('<<TreeviewSelect>>',self.tree_select);self.tree.bind('<Double-1>',lambda e:self.edit_selected())
        lf=ttk.Frame(left);lf.pack(fill='x',pady=7);ttk.Button(lf,text='编辑',command=self.edit_selected).pack(side='left',expand=True,fill='x');ttk.Button(lf,text='删除',command=self.delete_selected).pack(side='left',expand=True,fill='x',padx=4)
        middle=ttk.Panedwindow(body,orient='vertical');body.add(middle,weight=1)
        self.canvas=tk.Canvas(middle,bg=COLORS['background'],highlightthickness=0);middle.add(self.canvas,weight=4)
        problems=ttk.Frame(middle);middle.add(problems,weight=1)
        ph=ttk.Frame(problems);ph.pack(fill='x');self.summary=ttk.Label(ph,text='',font=('Microsoft YaHei UI',10,'bold'));self.summary.pack(side='left',padx=6,pady=6)
        ttk.Button(ph,text='导出报告',command=self.export_report).pack(side='right',padx=5)
        self.issues=ttk.Treeview(problems,columns=('state','object','rule','message'),show='headings',height=6)
        for key,title,width in [('state','状态',100),('object','对象',105),('rule','规则',130),('message','问题 / 证据',560)]:self.issues.heading(key,text=title);self.issues.column(key,width=width,stretch=key=='message')
        self.issues.pack(fill='both',expand=True)
        for state,color in STATUS_COLOR.items():self.issues.tag_configure(state,foreground=color)
        self.issues.bind('<<TreeviewSelect>>',self.issue_select);self.issues.bind('<Double-1>',self.issue_details)
        right=ttk.Frame(body,width=270);body.add(right,weight=0)
        self.inspector=tk.Text(right,width=30,wrap='word',relief='flat',bg='#ffffff',fg='#29445b',font=('Microsoft YaHei UI',10),padx=14,pady=14)
        self.inspector.pack(fill='both',expand=True)
        ttk.Button(right,text='编辑所选对象属性',command=self.edit_selected).pack(fill='x',pady=7)
        ttk.Button(right,text='聚焦所选对象',command=self.focus_selected).pack(fill='x',pady=(0,7))
        bottom=ttk.Frame(self);bottom.pack(fill='x',padx=12,pady=6);ttk.Label(bottom,textvariable=self.status).pack(side='left');ttk.Label(bottom,textvariable=self.view_status).pack(side='right')

    def _bindings(self):
        for seq,cmd in [('<Control-n>',self.new),('<Control-o>',self.open),('<Control-s>',self.save),('<Control-z>',self.undo),('<Control-y>',self.redo)]:self.bind(seq,lambda e,c=cmd:c())
        self.bind('<Escape>',lambda e:self.set_mode('SELECT'));self.bind('<Return>',lambda e:self.finish_draw())
        self.bind('<Delete>',lambda e:self.delete_selected() if e.widget==self.canvas or e.widget==self.tree else None)
        self.canvas.bind('<Button-1>',self.click);self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Double-Button-1>',lambda e:self.edit_selected() if self.mode=='SELECT' else None)
        self.canvas.bind('<ButtonPress-2>',self.pan_start);self.canvas.bind('<B2-Motion>',self.pan_move)
        self.canvas.bind('<ButtonPress-3>',self.pan_start);self.canvas.bind('<B3-Motion>',self.pan_move)
        self.canvas.bind('<MouseWheel>',self.wheel);self.canvas.bind('<Configure>',lambda e:self.redraw())
        self.canvas.bind('<Motion>',self.pointer)

    def world(self,x,y):return [(x-self.origin[0])/self.zoom,(self.origin[1]-y)/self.zoom]
    def screen(self,p):return [self.origin[0]+p[0]*self.zoom,self.origin[1]-p[1]*self.zoom]
    def set_mode(self,mode):
        self.mode=mode;self.points=[];self.connect_ports=[];self.drag=None
        hint='点击选择，拖动对象；滚轮缩放，右键/中键拖动画布。' if mode=='SELECT' else '依次点击两个路线锚点，然后配置允许操纵。' if mode=='CONNECT' else '连续点击顶点，按 Enter 或“完成绘制”；Esc取消。' if mode in AREA_KINDS else '依次点击起点和终点；Esc取消。'
        self.status.set((NAMES.get(mode,mode)+'：'+hint));self.canvas.configure(cursor='arrow' if mode=='SELECT' else 'crosshair');self.redraw()

    def more_tools(self):
        menu=tk.Menu(self,tearoff=False)
        for kind in ('APRON_TAXIWAY','STAND_TAXILANE','ROAD','PROTECTION','EQUIPMENT','CLOSED_AREA'):
            menu.add_command(label=NAMES[kind],command=lambda k=kind:self.set_mode(k))
        menu.tk_popup(self.winfo_pointerx(),self.winfo_pointery())

    def pick(self,p,paths_only=False):
        threshold=10/self.zoom;best=None
        for aid,a in self.scene.assets.items():
            if a['kind'] in PATH_KINDS:
                d,station,q=g.project(a['points'],p)
                hit=d<max(threshold,a['props']['width']/2)
                if hit and (best is None or d<best[0]):best=(d,aid,station,q)
        if best:return best
        if not paths_only:
            for mid in reversed(list(self.scene.movements)):
                d,station,q=g.project(self.scene.movement_path(mid),p)
                if d<max(threshold,self.scene.movements[mid]['width']/2):return d,mid,station,q
            for aid,a in reversed(list(self.scene.assets.items())):
                if a['kind'] in AREA_KINDS and g.inside(p,a['points']):return 0,aid,0,p
        return None

    def click(self,e):
        self.canvas.focus_set();p=self.world(e.x,e.y)
        if self.mode=='SELECT':
            picked=self.pick(p);self.selection=picked[1] if picked else None
            if self.selection in self.scene.assets:self.drag=dict(start=p,old=copy.deepcopy(self.scene.assets[self.selection]['points']),delta=[0,0])
            self.select(self.selection);return
        if self.mode=='CONNECT':
            picked=self.pick(p,True)
            if not picked:self.status.set('请选择跑道、滑行道或机坪内的明确路线，不能直接连接机坪多边形。');return
            _,aid,station,q=picked;self.connect_ports.append(dict(asset=aid,station=round(station,4),direction=1))
            if len(self.connect_ports)==2:self.connection_dialog();self.connect_ports=[]
            else:self.status.set('已选择起点：'+self.scene.assets[aid]['name']+'；请选择目标路线。')
            self.redraw();return
        self.points.append(p)
        if self.mode not in AREA_KINDS and len(self.points)==2:self.finish_draw()
        self.redraw()

    def motion(self,e):
        if self.mode=='SELECT' and self.drag and self.selection in self.scene.assets:
            p=self.world(e.x,e.y);delta=[p[0]-self.drag['start'][0],p[1]-self.drag['start'][1]];self.drag['delta']=delta
            self.canvas.delete('drag_preview');pts=[self.screen([x+delta[0],y+delta[1]]) for x,y in self.drag['old']]
            self.canvas.create_line(*[v for pt in pts for v in pt],fill='#1494ac',width=3,dash=(6,3),tags='drag_preview')

    def release(self,e):
        if self.drag and self.selection in self.scene.assets:
            dx,dy=self.drag['delta']
            if abs(dx)+abs(dy)>.1:self.scene.translate(self.selection,dx,dy);self.route_preview=None;self.refresh()
        self.drag=None;self.canvas.delete('drag_preview')

    def pan_start(self,e):self.pan_anchor=(e.x,e.y,*self.origin)
    def pan_move(self,e):
        if hasattr(self,'pan_anchor'):
            x,y,ox,oy=self.pan_anchor;self.origin=[ox+e.x-x,oy+e.y-y];self.redraw()
    def pointer(self,e):
        p=self.world(e.x,e.y);self.view_status.set(f'X {p[0]:.1f} m   Y {p[1]:.1f} m   |   {self.zoom:.3f} px/m')
    def wheel(self,e):
        p=self.world(e.x,e.y);self.zoom=max(.02,min(20,self.zoom*(1.15 if e.delta>0 else 1/1.15)))
        self.origin=[e.x-p[0]*self.zoom,e.y+p[1]*self.zoom];self.redraw()
    def fit(self):
        x0,y0,x1,y1=bounds(self.scene);w=max(300,self.canvas.winfo_width());h=max(200,self.canvas.winfo_height())
        self.zoom=min((w-70)/(x1-x0),(h-70)/(y1-y0));self.origin=[w/2-(x0+x1)/2*self.zoom,h/2+(y0+y1)/2*self.zoom];self.redraw()

    def finish_draw(self):
        if self.mode in ('SELECT','CONNECT') or not self.points:return
        if self.mode in AREA_KINDS and len(self.points)<3:self.status.set('区域至少需要三个顶点。');return
        if self.mode in PATH_KINDS and len(self.points)<2:return
        kind=self.mode;pts=copy.deepcopy(self.points)
        if g.distance(pts[0],pts[-1])<1 and kind in PATH_KINDS:self.status.set('路线长度至少1米。');return
        values={'name':NAMES[kind]+' '+str(len(self.scene.assets)+1),'width':45 if kind=='RUNWAY' else 36 if kind=='STAND' else 18,'shoulder':0}
        result=FormDialog(self,'新增'+NAMES[kind],[field('name','名称'),field('width','道面宽度 / 机位宽度 (m)','float'),field('shoulder','每侧道肩 (m)','float')],values).result
        if result:
            try:
                self.selection=self.scene.create_asset(kind,result.pop('name'),pts,**result);self.points=[];self.mode='SELECT';self.refresh();self.edit_selected()
            except ValueError as exc:messagebox.showerror('无法创建',str(exc),parent=self)
        else:self.points=[];self.set_mode('SELECT')

    def connection_dialog(self):
        a,b=self.connect_ports;ka=self.scene.assets[a['asset']]['kind'];kb=self.scene.assets[b['asset']]['kind']
        role='ENTRY' if kb=='RUNWAY' else 'EXIT_ONLY' if ka=='RUNWAY' else 'STAND_ENTRY' if kb=='STAND' else 'APRON_ACCESS' if kb in ('APRON_TAXIWAY','STAND_TAXILANE') else 'TAXIWAY_JOIN'
        values=dict(name=self.scene.assets[a['asset']]['name']+' → '+self.scene.assets[b['asset']]['name'],role=ROLE_NAMES[role],
                    from_direction='正向 +1',to_direction='正向 +1',bidirectional=False,width=min(self.scene.assets[x['asset']]['props']['width'] for x in (a,b)),handle=60,holding_distance=90,min_radius=None,maxspan=None)
        fields=[field('name','连接名称'),field('role','连接用途','text',list(ROLE_NAMES.values())),field('from_direction','起点行进切线','text',['正向 +1','反向 -1']),field('to_direction','终点行进切线','text',['正向 +1','反向 -1']),field('bidirectional','允许反向操纵','bool'),field('width','连接道面宽度 (m)','float'),field('handle','曲线控制长度 (m)','float'),field('holding_distance','候选等待距跑道中线 (m，未核验)','float'),field('min_radius','设计最小曲率半径 (m，可空)','float'),field('maxspan','允许最大翼展 (m，可空)','float')]
        result=FormDialog(self,'连接向导 · 方向独立于道面相交',fields,values).result
        if not result:return
        a['direction']=1 if result.pop('from_direction').startswith('正') else -1;b['direction']=1 if result.pop('to_direction').startswith('正') else -1
        result['role']=next(k for k,v in ROLE_NAMES.items() if v==result['role'])
        try:
            self.selection=self.scene.connect(a,b,**result);self.route_preview=None;self.refresh()
        except ValueError as exc:messagebox.showerror('连接未提交',str(exc)+'\n请重新选择锚点或调整连接类型。',parent=self)

    def select(self,oid):
        self.selection=oid
        if oid and self.tree.exists(oid):self.tree.selection_set(oid);self.tree.see(oid)
        self.update_inspector();self.redraw()
    def tree_select(self,e=None):
        chosen=self.tree.selection()
        if chosen:self.selection=chosen[0];self.update_inspector();self.redraw()

    def update_inspector(self):
        oid=self.selection;obj=self.scene.assets.get(oid) or self.scene.movements.get(oid)
        lines=['场景检查器','\n'+self.scene.data['meta']['name'],f'资产 {len(self.scene.assets)}  /  连接 {len(self.scene.movements)}',
               '\n点击对象查看属性；双击编辑。\n连接需要两个明确路线锚点。\n\n滚轮：缩放\n右键拖动：平移\n左键拖动：移动对象\nEnter：完成区域\nEsc：取消绘制']
        if obj:
            lines=[obj['name'],oid,'']
            if oid in self.scene.assets:
                lines+=[NAMES[obj['kind']],f'长度 {g.length(obj["points"]):.1f} m' if obj['kind'] in PATH_KINDS else '多边形区域']
                for key in ('width','shoulder','flow','maxspan','code_number','level_a','level_b','guidance','stop_reference','closed'):
                    if key in obj['props']:lines.append(f'{key}: {obj["props"][key]}')
            else:
                lines+=[ROLE_NAMES[obj['role']],f'{self.scene.assets[obj["from"]["asset"]]["name"]} → {self.scene.assets[obj["to"]["asset"]]["name"]}',
                        f'长度 {g.length(self.scene.movement_path(oid)):.1f} m',f'双向: {obj["bidirectional"]}',f'启用: {obj["enabled"]}',
                        f'候选等待距离: {obj["holding_distance"]} m','\n候选设施并非工程核验通过。']
            errors=[x for x in self.report.get('issues',[]) if x['object_id']==oid]
            if errors:lines+=['\n相关问题']+[STATES[x['status']]+' · '+x['message'] for x in errors[:6]]
        self.inspector.configure(state='normal');self.inspector.delete('1.0','end');self.inspector.insert('1.0','\n'.join(lines));self.inspector.configure(state='disabled')

    def edit_selected(self):
        oid=self.selection
        if oid in self.scene.movements:return self.edit_movement(oid)
        if oid not in self.scene.assets:return
        a=self.scene.assets[oid];p=a['props'];pts=a['points'];center=[sum(x for x,y in pts)/len(pts),sum(y for x,y in pts)/len(pts)]
        fields=[field('name','名称'),field('x','中心 X (m)','float'),field('y','中心 Y (m)','float'),field('width','道面/机位宽度 (m)','float'),field('shoulder','每侧道肩 (m)','float'),field('flow','允许方向','text',['BOTH','FORWARD','REVERSE']),field('maxspan','最大翼展 (m，可空)','float'),field('code_number','飞行区指标Ⅰ (可空)','int'),field('closed','关闭对象','bool'),field('source_note','设计依据 / 备注')]
        values=dict(p,name=a['name'],x=round(center[0],3),y=round(center[1],3))
        if a['kind'] in PATH_KINDS and len(pts)==2:
            u=g.unit(*pts);fields += [field('length','路径长度 (m)','float'),field('heading','真方位 / 本地朝向 (°)','float')]
            values.update(length=round(g.length(pts),4),heading=round(math.degrees(math.atan2(u[0],u[1]))%360,6))
        if a['kind']=='RUNWAY':
            for key,label,typ,choices in [('label_a','物理 A 端号码','text',None),('label_b','物理 B 端号码','text',None),('level_a','A 端类别','text',APPROACH_LEVELS),('level_b','B 端类别','text',APPROACH_LEVELS),('displaced_a','A 端入口内移 (m)','float',None),('displaced_b','B 端入口内移 (m)','float',None),('lda_a','A 端 LDA (m，可空)','float',None),('lda_b','B 端 LDA (m，可空)','float',None)]:fields.append(field(key,label,typ,choices))
        if a['kind']=='STAND':
            fields += [field('guidance','引导方式','text',['GUIDED','UNGUIDED']),field('stop_reference','停止点参考','text',['NOSEWHEEL','LEFT_SEAT']),field('entry_mode','进出方式','text',['SELF_IN_PUSH_OUT','SELF_IN_OUT','TOW_IN_OUT']),field('group','机位组'),field('configuration','主/辅配置名称'),field('excludes','互斥机位（点击多选）','multi',[(x['id'],x['name']) for x in self.scene.assets.values() if x['kind']=='STAND' and x['id']!=oid])]
        if a['kind'] in ('STAND','APRON_TAXIWAY','STAND_TAXILANE'):
            choices=['无 / 自动检查']+[f'{x["name"]} | {x["id"]}' for x in self.scene.assets.values() if x['kind']=='APRON']
            values['parent_text']=next((s for s in choices if s.endswith(p.get('parent_id') or '!')),'无 / 自动检查')
            fields.append(field('parent_text','所属机坪','text',choices))
        result=FormDialog(self,'编辑 '+a['name'],fields,values).result
        if not result:return
        try:
            name=result.pop('name');x=result.pop('x');y=result.pop('y')
            if x is None or y is None:raise ValueError('中心坐标不可为空')
            if 'length' in result:
                span=result.pop('length');heading=result.pop('heading')
                if span is None or span<=0 or heading is None:raise ValueError('长度必须为正数，方位不可为空')
                points=g.line([x,y],span,heading)
            else:points=[[px+x-center[0],py+y-center[1]] for px,py in pts]
            if 'parent_text' in result:
                v=result.pop('parent_text');result['parent_id']=v.split(' | ')[-1] if ' | ' in v else None
            self.scene.update_asset(oid,name,points,result);self.route_preview=None;self.refresh()
        except (ValueError,TypeError) as exc:messagebox.showerror('修改未提交',str(exc),parent=self)

    def edit_movement(self,mid):
        m=self.scene.movements[mid];values=dict(m,role_name=ROLE_NAMES[m['role']],
            from_station=m['from']['station'],to_station=m['to']['station'],from_direction=str(m['from']['direction']),to_direction=str(m['to']['direction']))
        fields=[field('name','连接名称'),field('role_name','连接用途','text',list(ROLE_NAMES.values())),field('enabled','允许操纵','bool'),field('bidirectional','双向（单向出口不允许）','bool'),field('width','连接宽度 (m)','float'),field('handle','曲线控制长度 (m)','float'),field('from_station','起点锚定站位 (m)','float'),field('to_station','终点锚定站位 (m)','float'),field('from_direction','起点行进方向','text',['1','-1']),field('to_direction','终点行进方向','text',['1','-1']),field('holding_distance','候选等待距中线 (m，非合格值)','float'),field('min_radius','设计最小半径 (m，可空)','float'),field('maxspan','翼展上限 (m，可空)','float'),field('stopbar','停止排灯：演示状态','text',['UNKNOWN','ON','OFF','FAILED']),field('protection_ids','关联保护区（点击多选）','multi',[(a['id'],a['name']) for a in self.scene.assets.values() if a['kind']=='PROTECTION']),field('source_note','设计依据 / 备注')]
        r=FormDialog(self,'编辑连接 '+m['name'],fields,values).result
        if not r:return
        role_name=r.pop('role_name');r['role']=next(k for k,v in ROLE_NAMES.items() if v==role_name)
        r['from']=dict(m['from'],station=r.pop('from_station'),direction=int(r.pop('from_direction')))
        r['to']=dict(m['to'],station=r.pop('to_station'),direction=int(r.pop('to_direction')))
        try:self.scene.update_movement(mid,**r);self.route_preview=None;self.refresh()
        except ValueError as exc:messagebox.showerror('修改未提交',str(exc),parent=self)

    def edit_scenario(self):
        sc=self.scene.scenario;v=dict(sc)
        fields=[field('name','情景名称'),field('date','情景日期 YYYY-MM-DD'),field('night','夜间运行','bool'),field('aircraft_wingspan','航空器翼展 (m)','float'),field('aircraft_length','航空器长度 (m)','float'),field('wheelbase','轮距/轴距数据 (m，可空)','float'),field('cockpit_to_nosewheel','驾驶舱至鼻轮 (m，可空)','float'),field('closed_assets','场景关闭对象（点击多选）','multi',[(a['id'],a['name']) for a in self.scene.assets.values()]),field('active_stands','占用机位（点击多选）','multi',[(a['id'],a['name']) for a in self.scene.assets.values() if a['kind']=='STAND']),field('permitted_movements','演示授权连接（非真实许可）','multi',[(m['id'],m['name']) for m in self.scene.movements.values()])]
        r=FormDialog(self,'运行情景 · 不控制真实机场',fields,v).result
        if not r:return
        try:self.scene.set_scenario(**r);self.route_preview=None;self.refresh()
        except (ValueError,TypeError) as exc:messagebox.showerror('修改未提交',str(exc),parent=self)

    def project_settings(self):
        r=FormDialog(self,'机场整体参数',[field('name','项目名称'),field('crs','坐标参考系 / 本地设计标识'),field('design_date','设计基准日 YYYY-MM-DD'),field('magnetic_declination','磁差 (°，东正，可空)','float'),field('airport_elevation','机场海拔 (m)','float'),field('rvr','RVR (m)','float')],
                     {'airport_elevation':0.,**self.scene.data['meta'],'rvr':self.scene.scenario['rvr']}).result
        if r:
            try:
                with self.scene.transaction('修改项目基准'):
                    self.scene.scenario['rvr']=r.pop('rvr')
                    self.scene.data['meta'].update(r)
                self.refresh()
            except (ValueError,TypeError) as exc:messagebox.showerror('修改未提交',str(exc),parent=self)

    def split_selected(self):
        aid=self.selection
        if aid not in self.scene.assets or self.scene.assets[aid]['kind'] not in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','ROAD'):
            messagebox.showinfo('选择路线','请先选择需要切分的滑行路线或服务车道。',parent=self);return
        r=FormDialog(self,'切分路线 · 锚点自动重映射',[field('station','从固定起点量取的站位 (m)','float')],{'station':g.length(self.scene.assets[aid]['points'])/2}).result
        if r:
            try:self.selection=self.scene.split_asset(aid,r['station']);self.route_preview=None;self.refresh()
            except (ValueError,TypeError) as exc:messagebox.showerror('切分未提交',str(exc),parent=self)

    def movement_matrix(self):
        win=tk.Toplevel(self);win.title('允许操纵矩阵 · 每行是一条独立连接');win.geometry('1000x470')
        grid=ttk.Treeview(win,columns=('from','to','role','allowed','reverse'),show='headings')
        for key,label in [('from','从'),('to','到'),('role','用途'),('allowed','启用'),('reverse','双向')]:grid.heading(key,text=label);grid.column(key,width=180)
        grid.pack(fill='both',expand=True,padx=12,pady=12)
        def populate():
            for x in grid.get_children():grid.delete(x)
            for mid,m in self.scene.movements.items():grid.insert('', 'end',iid=mid,values=(self.scene.assets[m['from']['asset']]['name'],self.scene.assets[m['to']['asset']]['name'],ROLE_NAMES[m['role']],'是' if m['enabled'] else '否','是' if m['bidirectional'] else '否'))
        def toggle():
            if grid.selection():
                mid=grid.selection()[0];self.scene.update_movement(mid,enabled=not self.scene.movements[mid]['enabled']);self.route_preview=None;populate();self.refresh()
        def edit():
            if grid.selection():self.edit_movement(grid.selection()[0]);populate()
        buttons=ttk.Frame(win);buttons.pack(fill='x',padx=12,pady=10)
        ttk.Button(buttons,text='启用 / 禁用所选',command=toggle).pack(side='left');ttk.Button(buttons,text='编辑用途、方向与锚点',command=edit).pack(side='left',padx=7)
        ttk.Label(buttons,text='道面相交不会自动增加矩阵中的操纵。').pack(side='right');populate()

    def preview_route(self):
        choices=[f'{a["name"]} | {aid}' for aid,a in self.scene.assets.items() if a['kind'] in PATH_KINDS]
        if not choices:return
        r=FormDialog(self,'路线预览 · 不是管制许可',[field('start','起始路线','text',choices),field('end','目标路线 / 机位','text',choices),field('require_permit','演示：跑道连接需授权且灯为OFF','bool')],dict(start=choices[0],end=choices[-1],require_permit=False)).result
        if not r:return
        result=self.scene.route(r['start'].split(' | ')[-1],r['end'].split(' | ')[-1],r['require_permit'])
        if not result:self.route_preview=None;messagebox.showinfo('没有可行路线','允许操纵、方向、关闭状态、翼展限制或演示许可条件使路线不可达。',parent=self)
        else:self.route_preview=result;self.status.set(f'路线预览 {result["length"]:.1f} m · {len(result["movements"])} 个连接 · 非管制许可')
        self.redraw()

    def refresh(self):
        self.render_items=display_list(self.scene,self.labels.get(),self.facilities.get(),self.protection.get())
        for item in self.tree.get_children():self.tree.delete(item)
        for aid,a in self.scene.assets.items():self.tree.insert('', 'end',iid=aid,text=a['name'],values=(NAMES[a['kind']],))
        for mid,m in self.scene.movements.items():self.tree.insert('', 'end',iid=mid,text=m['name'],values=(ROLE_NAMES[m['role']],))
        if self.selection and self.tree.exists(self.selection):self.tree.selection_set(self.selection)
        self.validate(silent=True);self.update_inspector();self.redraw();self.update_title()

    def redraw(self):
        if not hasattr(self,'canvas'):return
        c=self.canvas;c.delete('all');w=c.winfo_width();h=c.winfo_height()
        spacing=100*self.zoom
        if spacing>20:
            x=self.origin[0]%spacing
            while x<w:c.create_line(x,0,x,h,fill='#dbe3e9');x+=spacing
            y=self.origin[1]%spacing
            while y<h:c.create_line(0,y,w,y,fill='#dbe3e9');y+=spacing
        for item in self.render_items:
            pts=[self.screen(p) for p in item['points']];flat=[v for pt in pts for v in pt]
            if not pts:continue
            if item['type']=='text':
                c.create_text(*pts[0],text=item['text'],fill=item['fill'],font=('Microsoft YaHei UI',max(8,min(16,round(item['size']*math.sqrt(max(.2,self.zoom)))))),anchor='w')
            elif item['type']=='polygon':
                args=dict(fill=item.get('fill') or '',outline=item.get('stroke') or '',width=max(1,item['width']*self.zoom))
                if item.get('dash'):args['dash']=tuple(max(1,round(x*self.zoom)) for x in item['dash'])
                c.create_polygon(*flat,**args)
            elif len(pts)>1:
                args=dict(fill=item['stroke'],width=max(1,item['width']*self.zoom),capstyle='butt',joinstyle='round')
                if item.get('dash'):args['dash']=tuple(max(1,round(x*self.zoom)) for x in item['dash'])
                c.create_line(*flat,**args)
        if self.selection in self.scene.assets:
            a=self.scene.assets[self.selection];pts=[self.screen(p) for p in a['points']]
            if a['kind'] in AREA_KINDS:c.create_polygon(*[v for p in pts for v in p],outline='#087f9c',fill='',width=3,dash=(6,3))
            else:c.create_line(*[v for p in pts for v in p],fill='#2ab1c5',width=3,dash=(6,3))
            for x,y in pts:c.create_rectangle(x-4,y-4,x+4,y+4,fill='#ffffff',outline='#087f9c',width=2)
        elif self.selection in self.scene.movements:
            pts=[self.screen(p) for p in self.scene.movement_path(self.selection)];c.create_line(*[v for p in pts for v in p],fill='#0585aa',width=3,dash=(6,3))
        if self.route_preview and self.route_preview['points']:
            pts=[self.screen(p) for p in self.route_preview['points']];c.create_line(*[v for p in pts for v in p],fill='#057ed1',width=4,dash=(12,5))
        if self.points:
            pts=[self.screen(p) for p in self.points]
            for x,y in pts:c.create_oval(x-4,y-4,x+4,y+4,fill='#028ca6',outline='white')
            if len(pts)>1:c.create_line(*[v for p in pts for v in p],fill='#078da6',width=2,dash=(5,4))
        for port in self.connect_ports:
            q,_=g.at(self.scene.assets[port['asset']]['points'],port['station']);x,y=self.screen(q);c.create_oval(x-7,y-7,x+7,y+7,fill='#1b9cc2',outline='white',width=2)
        # North and scale are UI guides, not airport markings.
        c.create_line(w-34,58,w-34,26,arrow='last',fill='#365971',width=2);c.create_text(w-34,15,text='N',fill='#365971')
        c.create_rectangle(10,h-35,260,h-8,fill='#ffffff',outline='');c.create_text(20,h-22,anchor='w',text=f'100 m  ━━  |  {self.scene.scenario["name"]}',fill='#365971',font=('Microsoft YaHei UI',9))

    def validate(self,silent=False):
        self.report=validate_scene(self.scene)
        for x in self.issues.get_children():self.issues.delete(x)
        for i,item in enumerate(self.report['issues']):
            obj=self.scene.assets.get(item['object_id']) or self.scene.movements.get(item['object_id'])
            self.issues.insert('', 'end',iid=str(i),values=(STATES[item['status']],obj['name'] if obj else '场景',item['rule'],item['message']),tags=(item['status'],))
        s=self.report['summary'];self.summary.configure(text=f'不满足 {s["FAIL"]}  · 缺数据 {s["UNKNOWN"]}  · 未核验 {s["UNVERIFIED"]}  · 需复核 {s["REVIEW_REQUIRED"]}')
        if not silent:self.status.set('核验完成：仅检查已实现的约束；整体状态 NOT_CERTIFIED。');self.update_inspector()

    def issue_select(self,e=None):
        if self.issues.selection():
            issue=self.report['issues'][int(self.issues.selection()[0])]
            if issue['object_id']:self.select(issue['object_id'])
    def issue_details(self,e=None):
        if self.issues.selection():
            item=self.report['issues'][int(self.issues.selection()[0])]
            messagebox.showinfo(item['rule'],item['message']+'\n\n依据：'+item['source']+'\n实际：'+str(item['actual'])+'\n要求：'+str(item['required']),parent=self)

    def focus_selected(self):
        if self.selection in self.scene.assets:pts=self.scene.assets[self.selection]['points']
        elif self.selection in self.scene.movements:pts=self.scene.movement_path(self.selection)
        else:return
        q=[sum(x for x,y in pts)/len(pts),sum(y for x,y in pts)/len(pts)];self.origin=[self.canvas.winfo_width()/2-q[0]*self.zoom,self.canvas.winfo_height()/2+q[1]*self.zoom];self.redraw()
    def delete_selected(self):
        if not self.selection:return
        deps=sum(self.selection in (m['from']['asset'],m['to']['asset']) for m in self.scene.movements.values())
        if messagebox.askyesno('删除对象',f'删除所选对象，并移除 {deps} 条关联连接？可撤销。',parent=self):self.scene.delete(self.selection);self.selection=None;self.route_preview=None;self.refresh()
    def undo(self):
        if self.scene.undo():self.selection=None;self.route_preview=None;self.refresh()
    def redo(self):
        if self.scene.redo():self.selection=None;self.route_preview=None;self.refresh()
    def dirty(self):return json.dumps(self.scene.data,sort_keys=True)!=self.saved
    def update_title(self):self.title(('● ' if self.dirty() else '')+'Airport Scene Studio · '+(self.filepath.name if self.filepath else self.scene.data['meta']['name']))
    def confirm_leave(self):
        if not self.dirty():return True
        answer=messagebox.askyesnocancel('未保存的场景','保存当前修改后再继续？',parent=self)
        return self.save() if answer else answer is not None
    def new(self):
        if not self.confirm_leave():return
        self.scene=AirportScene();self.filepath=None;self.saved=json.dumps(self.scene.data,sort_keys=True);self.selection=None;self.route_preview=None;self.set_mode('SELECT');self.refresh();self.fit()
    def open(self):
        if not self.confirm_leave():return
        p=filedialog.askopenfilename(title='打开机场场景',filetypes=[('机场场景','*.airport.json'),('JSON','*.json')])
        if not p:return
        try:
            scene=AirportScene.load(p);self.scene=scene;self.filepath=Path(p);self.saved=json.dumps(scene.data,sort_keys=True);self.selection=None;self.route_preview=None;self.set_mode('SELECT');self.refresh();self.fit()
        except (ValueError,OSError,TypeError,KeyError) as exc:messagebox.showerror('打开失败',str(exc)+'\n旧版参数文件请使用“导入旧版”菜单。',parent=self)
    def save(self,save_as=False):
        p=self.filepath
        if save_as or p is None:
            chosen=filedialog.asksaveasfilename(title='保存机场场景',defaultextension='.airport.json',filetypes=[('机场场景','*.airport.json')])
            if not chosen:return False
            p=Path(chosen)
        try:self.scene.save(p);self.filepath=p;self.saved=json.dumps(self.scene.data,sort_keys=True);self.update_title();self.status.set('已保存 '+str(p));return True
        except (OSError,ValueError) as exc:messagebox.showerror('保存失败',str(exc),parent=self);return False
    def export(self,kind):
        p=filedialog.asksaveasfilename(title='导出整场设计预览',defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
        if not p:return
        try:
            (export_png if kind=='png' else export_svg)(self.scene,p);self.status.set('已导出预览 '+p+'；完整核验状态见JSON报告。')
        except (ValueError,OSError) as exc:messagebox.showerror('导出失败',str(exc),parent=self)
    def export_report(self):
        p=filedialog.asksaveasfilename(title='导出核验报告',defaultextension='.json',filetypes=[('JSON','*.json')])
        if p:
            try:Path(p).write_text(json.dumps(validate_scene(self.scene),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');self.status.set('已导出核验报告 '+p)
            except OSError as exc:messagebox.showerror('导出失败',str(exc),parent=self)
    def import_legacy(self):
        p=filedialog.askopenfilename(title='导入旧版参数',filetypes=[('JSON','*.json')])
        if not p:return
        from scene_import import import_legacy
        try:
            result=import_legacy(self.scene,p);self.selection=result['asset_ids'][0] if result['asset_ids'] else None;self.route_preview=None;self.refresh();self.fit();messagebox.showinfo('导入完成',result['message'],parent=self)
        except (ValueError,OSError,TypeError,KeyError) as exc:messagebox.showerror('导入未提交',str(exc),parent=self)
    def coverage(self):
        info=self.report.get('coverage',{});messagebox.showinfo('规范来源与覆盖',f'已登记 {info.get("mapped_topic_groups",0)} 组主题。\n原子条款覆盖率：尚未确立。\n\n图形预览与字段检查不等于CAAC认证；原图尺寸、三维保护、扫掠、标记牌与灯光完整逻辑尚未核验。\n详细来源见项目中的 Sources.json、Coverage.csv 和 Design.md。',parent=self)
    def help(self):
        messagebox.showinfo('快速操作','1. 初次启动显示演示机场。\n2. 选工具后连续点击两点画路线；区域用多点+Enter。\n3. 连接向导：先点起始路线，再点目标路线，配置方向和用途。\n4. 左键拖动对象；右键拖动画布；滚轮缩放。\n5. 双击对象编辑；操纵矩阵启用/禁用连接。\n6. 场景设置修改RVR/机型/占用。\n7. Ctrl+S保存；文件菜单导出PNG/SVG/核验报告。\n\n旧版JSON请用“导入旧版”，不要用“打开场景”。',parent=self)
    def close(self):
        if self.confirm_leave():self.destroy()

def main():
    scene=AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None
    app=AirportApp(scene);app.mainloop()

if __name__=='__main__':main()
