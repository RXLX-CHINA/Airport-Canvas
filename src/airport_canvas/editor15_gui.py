"""Airport Canvas 15: tabbed properties and bound semantic editing."""
import copy,json,math,sys,threading,queue
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from qt_compat import ttk,filedialog,messagebox
from editor14_gui import Editor14
from airport_scene import AirportScene
import scene_geometry as g
import stand15 as stand
import interaction15 as ix

class Editor15(Editor14):
    def __init__(self,scene=None):
        self._book15=None;self._tab15='基本';self._export15=None;self._shear15=None
        if scene is None:
            p=Path(__file__).with_name('example_editor15.ACP');scene=AirportScene.load(p) if p.exists() else AirportScene()
        super().__init__(scene);self.adapt_window15();self.sharp_icon15();self.nav_close15()
        self.export_progress15=ttk.Progressbar(self.review_count.master,length=160,mode='determinate',maximum=100);self.export_progress15.pack(side='right',padx=8);self.export_progress15.pack_forget()
    def _build(self):super()._build();self.adapt_window15()
    def adapt_window15(self):
        w,h,x,y=ix.window_geometry(ix.work_area(self));self.minsize(min(920,w),min(560,h));self.geometry(f'{w}x{h}+{x}+{y}')
    def sharp_icon15(self):
        from PIL import Image
        from qt_canvas21 import ImageTk
        self._icons15=[]
        for n in (16,24,32,48,64,128,256):
            p=Path(__file__).with_name(f'icon_{n}.png')
            if p.exists():
                with Image.open(p) as im:self._icons15.append(ImageTk.PhotoImage(im.copy()))
        if self._icons15:self.iconphoto(True,*reversed(self._icons15))
    def nav_close15(self):
        if not hasattr(self,'nav_frame11'):return
        header=self.nav_frame11.winfo_children()[0]
        from qt_core21 import Qt
        title, close = header.winfo_children()
        self.nav_close_button = close
        close.q.setAccessibleName('隐藏导航窗口')
        close.q.setFixedSize(24, 24)
        close.q.setProperty('acRole','navClose')
        layout = header.q.layout()
        layout.removeItem(header._pack_spacer21)
        header._pack_spacer21 = None
        layout.setContentsMargins(7, 0, 3, 0)
        layout.setStretchFactor(title.q, 1)
        layout.setAlignment(close.q, Qt.AlignmentFlag.AlignVCenter)
    def update_title(self):super().update_title();self.title(self.title().replace('14.0','15.1').replace('15.0','15.1'))
    def refresh(self):
        self.migrate15(self.scene);return super().refresh()
    @staticmethod
    def migrate15(scene):
        if scene.data['meta'].get('editor15_migrated'):return
        oldpast=scene.past[:];oldfuture=scene.future[:]
        with scene.transaction('升级完整引导线和编号绑定'):
            for m in scene.movements.values():
                if m.get('role') in ('EXIT_ONLY','RAPID_EXIT') and m.get('legacy_attachment'):
                    taxi=next((scene.assets[m[k]['asset']] for k in ('from','to') if scene.assets[m[k]['asset']]['kind']!='RUNWAY'),None)
                    if taxi:
                        m.update(show_holding=True,show_enhanced=True,width=taxi['props']['width'],shoulder=taxi['props'].get('shoulder',0));runway_port=next(m[k] for k in ('from','to') if scene.assets[m[k]['asset']]['kind']=='RUNWAY');anchor=g.at(scene.assets[runway_port['asset']]['points'],runway_port['station'])[0];taxi_port=next(m[k] for k in ('from','to') if m[k]['asset']==taxi['id']);taxi_port['station']=g.project(taxi['points'],anchor)[1]
            overrides=scene.data['generated_overrides']
            if any(':STAND_NUMBER' in oid for oid in overrides):
                marks=__import__('automatic_markings').generated_markings(scene)
                for aid,a in scene.assets.items():
                    if a['kind']!='STAND':continue
                    numbers=[m for m in marks.values() if m.get('owner')==aid and m['props']['mark_type']=='STAND_NUMBER']
                    if numbers and any(m['id'] in overrides for m in numbers):stand.slide_number(scene,aid,0,numbers[0]['points'][0])
            scene.data['meta']['editor15_migrated']=True
        scene.past=oldpast;scene.future=oldfuture
    def ensure_book15(self):
        if self._book15 is None or not self._book15.notebook.winfo_exists():self._book15=__import__('inspector15').PropertyBook(self.property_body,self._tab15)
        return self._book15
    def section(self,title):return self.ensure_book15().section(title)
    def property_field(self,parent,key,label,value,kind='float',choices=None):
        self.ensure_book15()
        return super().property_field(parent,key,label,value,kind,choices)
    def update_inspector(self):
        if self._book15 and self._book15.notebook.winfo_exists():self._tab15=self._book15.current()
        super().update_inspector();a=self.scene.assets.get(self.selection)
        self._inspector_busy=True
        try:
            if a and a['kind']=='STAND':
                self.hide_field11('move_snap14');sec=self.section('引入线绑定与吸附');self.property_field(sec,'snap_tolerance15','控制点吸附距离 m',a['props'].get('snap_tolerance15',2.),'float')
                if a['props'].get('auxiliary'):
                    self.hide_field11('lead_type');self.property_field(sec,'lead_type','辅助机位引入构型',a['props'].get('lead_type','A'),'radio',['A','B','C','D','ICAO'])
            if a and a['props'].get('crossing_full13'):
                self.hide_field11('crossing_skew13');sec=self.section('横道剪切');self.property_field(sec,'crossing_skew13','横跨方向倾斜角 °',a['props'].get('crossing_skew13',0),'float')
        finally:self._inspector_busy=False
        self.ensure_book15().actions(self.property_body);self._book15.tidy()
    def scroll_sidebar(self,e):
        if self._book15 and self._book15.notebook.winfo_exists():
            if e.widget is self.property_canvas:
                self._book15.canvases[self._book15.current()].yview_scroll(-3 if e.delta>0 else 3,'units')
                return 'break'
            widget=e.widget
            while widget is not None:
                for name,page in self._book15.pages.items():
                    if widget is page:self._book15.canvases[name].yview_scroll(-3 if e.delta>0 else 3,'units');return 'break'
                widget=getattr(widget,'master',None)
        return super().scroll_sidebar(e)
    def begin_transform11(self,e):
        if not self._frame_box11 or not self.selection:return False
        key=next((k for k,x,y in reversed(self._handles14) if math.hypot(e.x-x,e.y-y)<8),None)
        if key is None and self.border_hit11(e.x,e.y,self._frame_box11[3]):
            box,center,_,_=self._frame_box11;self.apply_properties();roots,items,_=self.frame11();self._transform14=dict(kind='MOVE',roots=roots,items=items,box=box,target=box,center=center,start=self.world(e.x,e.y),delta=[0.,0.],angle=0.,snap=None);self._marquee12=None;self.canvas.focus_set();return True
        return super().begin_transform11(e)
    def start_stand_drag14(self,a,kind,key,e):
        super().start_stand_drag14(a,kind,key,e);self._stand_drag14['start15']=self.world(e.x,e.y)
    def motion(self,e):
        if self._shear15:
            d=self._shear15;self.canvas.itemconfigure('owner:'+d['aid'],state='hidden');candidate=copy.deepcopy(d['original']);assets=dict(self.scene.assets);assets[candidate['id']]=candidate;preview=SimpleNamespace(assets=assets);ix.shear(preview,candidate['id'],self.world(e.x,e.y));d['angle']=candidate['props']['crossing_skew13'];self.canvas.delete('shear_preview15')
            for item in __import__('marking_catalog').primitives(candidate):self.canvas.create_polygon(*[v for p in item['points'] for v in self.screen(p)],outline='#008fab',fill='#ffffff',tags='shear_preview15')
            return
        if self._stand_drag14 and getattr(e,'state',0)&1:
            start=self._stand_drag14['start15'];q=__import__('project10').constrain(start,self.world(e.x,e.y));x,y=self.screen(q);e=SimpleNamespace(x=x,y=y,state=e.state)
        if self._transform14 and self._transform14['kind'] not in ('MOVE','ROTATE'):
            d=self._transform14;p=self.world(e.x,e.y);dx,dy=p[0]-d['start'][0],p[1]-d['start'][1];x0,y0,x1,y1=d['box'];kind=d['kind']
            if 'W' in kind:x0=min(x1-.2,x0+dx)
            if 'E' in kind:x1=max(x0+.2,x1+dx)
            if 'N' in kind:y1=max(y0+.2,y1+dy)
            if 'S' in kind:y0=min(y1-.2,y0+dy)
            d['target']=ix.resize_target(d['box'],(x0,y0,x1,y1),kind,bool(e.state&1));self.canvas.delete('preview14');xx0,yy0,xx1,yy1=d['target'];self.canvas.create_polygon(*[v for q in ((xx0,yy0),(xx0,yy1),(xx1,yy1),(xx1,yy0)) for v in self.screen(q)],fill='',outline='#00a7c2',width=2,tags='preview14');return
        return super().motion(e)
    def release(self,e):
        if self._shear15:
            d=self._shear15;self._shear15=None;self.canvas.delete('shear_preview15');self.canvas.itemconfigure('owner:'+d['aid'],state='normal');self._renderer.items=None
            if 'angle' in d:self.scene.update_asset(d['aid'],props={'crossing_skew13':d['angle']})
            self.refresh();return
        if self._stand_drag14 and self._stand_drag14.get('candidate'):
            d=self._stand_drag14;self._stand_drag14=None;self.canvas.delete('preview14')
            with self.scene.transaction('调整机位引入线和编号'):
                p=self.scene.assets[d['aid']]['props']
                for key in ('entry_bindings15','entry_attached','junction_edits14','junction_type14','label_station14'):
                    if key in d['candidate']:p[key]=copy.deepcopy(d['candidate'][key])
                if d['kind']=='NUMBER':
                    for oid in list(self.scene.data['generated_overrides']):
                        if oid.startswith('AUTO:'+d['aid']+':STAND_NUMBER'):self.scene.data['generated_overrides'].pop(oid)
            self.refresh();return
        if self._transform14 and self._transform14['kind'] not in ('MOVE','ROTATE'):
            d=self._transform14;self._transform14=None;self.canvas.delete('preview14')
            try:ix.resize(self.scene,d['roots'],d['box'],d['target']);self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        return super().release(e)
    def redraw(self):
        if hasattr(self,'canvas'):
            self.canvas.delete('frame11');self._frame_box11=None;self._handles14=[]
        super().redraw()
        if not hasattr(self,'canvas'):return
        if self.selection and self.mode=='SELECT':self.draw_frame11()
        self.canvas.delete('shear15');a=self.scene.assets.get(self.selection)
        if a and a['props'].get('crossing_full13') and a['props'].get('crossing_asset13') in self.scene.assets and self.mode=='SELECT':
            x,y=self.screen(ix.shear_handle(self.scene,a));self.canvas.create_polygon(x,y-7,x+7,y,x,y+7,x-7,y,fill='#ffdf86',outline='#aa6c12',width=2,tags='shear15');self._shear_handle15=(x,y,a['id'])
        else:self._shear_handle15=None
    def click(self,e):
        self.canvas.delete('cross_preview14');self.canvas.delete('zebra_preview16')
        h=getattr(self,'_shear_handle15',None)
        if h and math.hypot(e.x-h[0],e.y-h[1])<10:
            a=self.scene.assets[h[2]];self._shear15=dict(aid=a['id'],original=copy.deepcopy(a));return
        return super().click(e)
    def pointer(self,e):
        super().pointer(e)
        if self.mode=='SELECT' and self._frame_box11:
            handle=next((k for k,x,y in reversed(self._handles14) if math.hypot(e.x-x,e.y-y)<8),None)
            self.canvas.configure(cursor='crosshair' if handle=='ROTATE' else 'sizing' if handle not in (None,'MOVE') else 'fleur' if handle=='MOVE' or self.border_hit11(e.x,e.y,self._frame_box11[3]) else '')
        if self.mode=='DEICE10' and not self._deice_hit12:
            self.canvas.delete('deice_snap15');hit=__import__('editor7_model').snap_path(self.scene,self.world(e.x,e.y),max(.25,15/self.zoom))
            if hit and self.scene.assets[hit[1]]['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                x,y=self.screen(hit[3]);self.canvas.create_oval(x-9,y-9,x+9,y+9,outline='#e03288',width=3,tags='deice_snap15');self.canvas.create_text(x+14,y-14,text='吸附滑行道中线',fill='#b22268',anchor='w',tags='deice_snap15')
    def draw_scale14(self):
        c=self.canvas;c.delete('scale14');units=self.scene.data['meta'].get('scale_units14','BOTH')
        if units=='OFF':return
        from layout14 import nice_length
        rows=[('m',1.),('ft',.3048)] if units=='BOTH' else [('ft',.3048)] if units=='FT' else [('m',1.)];bottom=c.winfo_height()-12;lengths=[nice_length(self.zoom,f) for _,f in rows];width=max(p for n,p in lengths)+16;height=24*len(rows)
        dark=getattr(self,'_dark_mode24',False)
        background,ink=('#202e3d','#d6e7f3') if dark else ('#f7fafc','#264659')
        c.create_rectangle(14,bottom-height,14+width,bottom+4,fill=background,outline='',tags='scale14')
        for i,((label,factor),(n,pixels)) in enumerate(zip(rows,lengths)):
            y=bottom-i*24;x=22;c.create_line(x,y-4,x,y,x+pixels,y,x+pixels,y-4,fill=ink,width=2,tags='scale14');c.create_text(x+pixels/2,y-11,text=f'{n:g} {label}',fill=ink,font=('Segoe UI',8),tags='scale14')
    def gesture11(self):return self._shear15 or super().gesture11()
    def cancel_action(self,e=None):
        if self._shear15:self.canvas.itemconfigure('owner:'+self._shear15['aid'],state='normal')
        self._shear15=None
        for tag in ('shear_preview15','deice_snap15'):self.canvas.delete(tag)
        return super().cancel_action(e)
    def set_mode(self,mode):
        self._shear15=None
        if hasattr(self,'canvas'):
            for tag in ('shear_preview15','deice_snap15'):self.canvas.delete(tag)
        return super().set_mode(mode)
    def open_review(self):
        from scene_rules import validate_scene
        self.report=validate_scene(self.scene)
        if self._review and self._review.winfo_exists():self._review.destroy()
        win=tk.Toplevel(self);self._review=win;win.title('Airport Canvas 审阅');win.geometry('1000x600');frame=ttk.Frame(win,padding=10);frame.pack(fill='both',expand=True);frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
        tree=ttk.Treeview(frame,columns=('state','object','rule','message'),show='headings');ys=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);xs=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview);tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set);tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew')
        for key,label,width in [('state','状态',130),('object','对象',150),('rule','规则',220),('message','说明',680)]:tree.heading(key,text=label);tree.column(key,width=width,stretch=False)
        issues=copy.deepcopy(self.report['issues'])
        for i,item in enumerate(issues):a=self.scene.assets.get(item['object_id']) or self.scene.movements.get(item['object_id']);tree.insert('','end',iid=str(i),values=(item['status'],a['name'] if a else '',item['rule'],item['message']))
        def locate(e=None):
            if tree.selection():oid=issues[int(tree.selection()[0])]['object_id'];self.select(oid);self.focus_selected()
        tree.bind('<<TreeviewSelect>>',locate);buttons=ttk.Frame(win,padding=10);buttons.pack(fill='x');ttk.Button(buttons,text='刷新审阅',command=self.open_review).pack(side='left');ttk.Button(buttons,text='导出审阅',command=self.export_report).pack(side='right')
    def help(self):return __import__('markdown15').show(self,Path(__file__).with_name('USER_GUIDE.md'),'Airport Canvas 15 功能与使用说明')
    def terminal13(self,j):
        if '_terminal_cut14' not in self.editor_vars:return super().terminal13(j)
        aid=self._terminal_choices13[self.editor_vars['_terminal_asset13'][0].get()];keep='END' if self.editor_vars['_terminal_cut14'][0].get()=='起点侧' else 'START';station=j['stations'][j['assets'].index(aid)]
        try:ix.terminal(self.scene,aid,station,keep,jid=j['id']);self.select(aid);self.refresh()
        except ValueError as exc:self.status.set(str(exc))
    def demo10(self):Editor15(AirportScene.load(Path(__file__).with_name('example_editor15.ACP')))
    def export(self,kind):
        self.apply_properties();win=tk.Toplevel(self);win.title('导出 '+kind.upper());win.geometry('440x650');width=tk.StringVar(value='960' if kind=='gif' else '3200');dpi=tk.StringVar(value='150');extent=tk.StringVar(value='全机场');transparent=tk.BooleanVar(value=False);scales=tk.BooleanVar(value=True);info=tk.StringVar()
        from export_modes21 import MODES,mode_items
        from export14 import export_filename,mode_extent
        active = ('F8' if getattr(getattr(self,'chart_view',None),'active',False)
                  else 'F7' if getattr(getattr(self,'lighting_view',None),'active',False)
                  else 'F5' if getattr(getattr(self,'view_tools21_2',None),'active',False)
                  else 'F6' if getattr(self,'_color17',False) else 'MAP')
        all_label = '所有模式（ZIP）'
        modes = {MODES['F7']:'F7'} if kind=='gif' else {label:key for key,label in MODES.items()}
        mode_var = tk.StringVar(value=MODES['F7' if kind=='gif' else active])
        from scene_render import display_list
        boards=tk.BooleanVar(value=self.scene.data['meta'].get('enlarge_boards26',False))
        full={}
        def export_geometry():
            mode=(bool(boards.get()),mode_var.get())
            if mode not in full:
                items=display_list(self.scene,self.labels.get(),self.facilities.get(),self.protection.get(),board_enlarged=mode[0])
                selected = modes.get(mode[1])
                if selected=='F8':
                    from chart_f8 import saved_region,layout_items,settings
                    items,_=mode_items(self.scene,selected,items)
                    items=layout_items(items,settings(self.scene).get('page',{}).get('airport_rotation',0.))
                    full[mode]=(items,saved_region(self.scene,items))
                    return full[mode]
                if selected and selected!='MAP':
                    items,_ = mode_items(self.scene,selected,items)
                if selected is None:
                    f7,_ = mode_items(self.scene,'F7',items)
                    whole = mode_extent(self.scene,[*items,*f7])
                else:
                    whole = mode_extent(self.scene,items)
                full[mode]=(items,whole)
            return full[mode]
        def box():
            if extent.get()=='当前视图':
                xs,ys=zip(*(self.world(x,y) for x in (0,self.canvas.winfo_width()) for y in (0,self.canvas.winfo_height())))
                return min(xs),min(ys),max(xs),max(ys)
            items,whole=export_geometry()
            if extent.get()=='选中对象':
                import transform11
                roots=self.selected_roots11()
                visible=transform11.visual_items(self.scene,roots,items,self.auto_assets)
                selected=transform11.bounds(visible)
                if selected is None:
                    visible=transform11.visual_items(self.scene,roots,self.render_items,self.auto_assets)
                    selected=transform11.bounds(visible)
                if selected:
                    margin=max(.5,max(selected[2]-selected[0],selected[3]-selected[1])*.03)
                    return selected[0]-margin,selected[1]-margin,selected[2]+margin,selected[3]+margin
                raise ValueError('请先选择要导出的对象')
            return whole
        def size_box():
            extent_box=box()
            if modes.get(mode_var.get())=='F8':
                from chart_f8 import adjust_region,page_box,settings
                config=settings(self.scene).get('page',{})
                return page_box(adjust_region(extent_box,config),config)
            return extent_box
        export_modes = list(modes)+([] if kind=='gif' else [all_label])
        win.geometry('486x540')
        body=ttk.Frame(win,padding=18)
        body.pack(fill='both',expand=True)
        heading=ttk.Label(body,text='导出灯光动画' if kind=='gif' else f'导出 {kind.upper()}')
        font=heading.q.font();font.setPointSize(16);font.setBold(True);heading.q.setFont(font)
        heading.pack(anchor='w',pady=(0,11))
        form=ttk.Frame(body,padding=8)
        form.pack(fill='x')
        form.columnconfigure(1,weight=1)
        for row,(label,var,choices) in enumerate([
            ('显示模式',mode_var,export_modes),('导出范围',extent,['全机场','当前视图','选中对象']),
            ('宽度（像素）',width,['960','1200','2400','3200','8000','16000']),
            ('DPI',dpi,['96','150','300','600']),
        ]):
            if (kind=='gif' and var is dpi) or (kind=='svg' and var in (width,dpi)):
                continue
            ttk.Label(form,text=label).grid(row=row,column=0,sticky='w',padx=(0,12),pady=5)
            ttk.Combobox(form,textvariable=var,values=choices,
                         state='normal' if var is width else 'readonly').grid(row=row,column=1,sticky='ew',pady=5)
        options=ttk.Frame(body,padding=8)
        options.pack(fill='x',pady=(8,0))
        for label,var in [('透明背景',transparent),('显示米／英尺比例尺',scales),('按固定倍率放大标记牌',boards)]:
            if kind!='gif' or var is scales:
                ttk.Checkbutton(options,text=label,variable=var).pack(anchor='w',pady=3)
        def update(*_):
            if kind=='svg':
                info.set('SVG 矢量图 · 尺寸由所选范围决定')
                return
            try:w,h=__import__('export14').dimensions(size_box(),int(width.get()));info.set(f'{w} × {h} px；RGBA最低占用{w*h*4/1048576:.1f} MiB'+('\n超出2400万像素建议预算，仅警告，不禁止导出。' if w*h>24_000_000 else ''))
            except (ValueError,OverflowError):info.set('输入正整数像素宽度')
        for var in (width,extent,boards,mode_var):var.trace_add('write',update)
        summary=ttk.Label(body,textvariable=info,wraplength=420,padding=10)
        summary.q.setProperty('acRole','dialogSummary')
        summary.pack(fill='x',pady=(8,14))
        update()
        def save():
            try:
                w,h=__import__('export14').dimensions(size_box(),int(width.get()));dots=int(dpi.get())
                if not 36<=dots<=1200:raise ValueError('DPI应为36～1200')
                if kind!='svg' and w*h>24_000_000:messagebox.showwarning('大尺寸导出',f'预计图像{w}×{h}，仅像素缓冲需约{w*h*4/1048576:.0f}MiB，实际峰值更高。尺寸不受软件固定上限阻止。',parent=win)
                bundle = mode_var.get()==all_label
                mode = modes.get(mode_var.get(),'MAP')
                extension = 'zip' if bundle else kind
                project = Path(self.filepath).stem if self.filepath else self.scene.data['meta'].get('name','机场项目')
                name = export_filename(project,mode,(w,h),kind)
                if bundle:
                    name = name.rsplit('.',1)[0].replace('_普通机场图_','_全部模式_')+'_'+kind.upper()+'.zip'
                from user_settings34 import last_directory,remember_directory
                preferences=getattr(self,'_preferences34',None)
                path=filedialog.asksaveasfilename(parent=win,initialfile=name,
                    initialdir=last_directory(preferences,'export') if preferences else '',
                    defaultextension='.'+extension,filetypes=[(extension.upper(),'*.'+extension)])
                if not path:return
                if preferences:
                    try:remember_directory(preferences,'export',path)
                    except OSError:pass
                args=dict(kind=kind,width=w,dpi=dots,transparent=transparent.get(),box=None if bundle and extent.get()=='全场景' else box(),labels=self.labels.get(),facilities=self.facilities.get(),protection=self.protection.get(),scale_bar=scales.get(),board_enlarged=boards.get(),mode=mode,bundle=bundle,project_name=project);win.destroy();self.start_export15(path,args)
            except (ValueError,OverflowError) as exc:messagebox.showerror('导出设置',str(exc),parent=win)
        actions=ttk.Frame(body)
        actions.pack(fill='x',side='bottom')
        ttk.Button(actions,text='选择位置并导出',command=save).pack(side='right',padx=(8,0))
        ttk.Button(actions,text='取消',command=win.destroy).pack(side='right')

    def start_export15(self,path,args):
        if self._export15:messagebox.showinfo('导出中','请等待当前导出完成',parent=self);return
        q=queue.Queue()
        cancelled=self._export_cancel=threading.Event()
        with self.processing('正在准备导出快照'):
            snapshot=AirportScene(self.scene.data)
            snapshot.multicore_enabled=getattr(self,'multicore_enabled',True)
        self._export15=q;self.export_progress15.pack(side='right',padx=8);self.export_progress15.configure(value=0);self.status.set('导出准备中')
        class ExportCancelled(Exception):
            pass

        def report_progress(n,label):
            if cancelled.is_set():raise ExportCancelled()
            q.put(('progress',n,label))

        def worker():
            temporary=Path(path).with_name(Path(path).name+'.canvas-export.tmp')
            try:
                size=__import__('export14').export(snapshot,temporary,progress=report_progress,**args)
                if cancelled.is_set():raise ExportCancelled()
                temporary.replace(path)
                q.put(('done',size,str(path)))
            except ExportCancelled:
                pass
            except Exception as exc:
                q.put(('error',str(exc)))
            finally:
                try:temporary.unlink(missing_ok=True)
                except OSError:pass
        threading.Thread(target=worker,name='airport-export').start()
        self.after(40,self.poll_export15)
    def poll_export15(self):
        q=self._export15
        if q is None:return
        terminal=False
        while not q.empty():
            item=q.get()
            if item[0]=='progress':self.export_progress15.configure(value=item[1]);self.status.set(f'导出 {item[1]:.0f}% — {item[2]}')
            elif item[0]=='done':terminal=True;self.export_progress15.configure(value=100);self.status.set('导出完成：'+item[2])
            else:terminal=True;self.status.set('导出失败：'+item[1]);messagebox.showerror('导出失败',item[1],parent=self)
        if terminal:self._export15=None;self.after(2500,self.export_progress15.pack_forget)
        else:self.after(40,self.poll_export15)

def main():Editor15(AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None).mainloop()
