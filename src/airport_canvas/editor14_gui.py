"""Airport Canvas: semantic junction handles, arc labels and direct resize."""
import copy,json,math,sys
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from qt_compat import ttk,filedialog,messagebox
from editor13_gui import Editor13
from airport_scene import AirportScene
import scene_geometry as g
import transform11 as tr
import stand15 as stand14
from project10 import TAXIS

class Editor14(Editor13):
    def __init__(self,scene=None):
        self._stand_drag14=None;self._transform14=None;self._semantic_handles14=[];self._handles14=[];self._cross_preview14=None
        if scene is None:
            p=Path(__file__).with_name('example_editor14.ACP');scene=AirportScene.load(p) if p.exists() else AirportScene()
        self.migrate14(scene);super().__init__(scene)
        try:
            self._icon14=tk.PhotoImage(file=str(Path(__file__).with_name('AirportCanvas.png')));self.iconphoto(True,self._icon14)
            if sys.platform=='win32':self.iconbitmap(str(Path(__file__).with_name('AirportCanvas.ico')))
        except (tk.TclError,OSError):pass
        menu=self.nametowidget(self.cget('menu'));display=tk.Menu(menu,tearoff=False);self.display_menu14=display;menu.add_cascade(label='显示',menu=display);scale=tk.Menu(display,tearoff=False);display.add_cascade(label='比例尺',menu=scale);self._scale_units14=tk.StringVar(value=self.scene.data['meta'].get('scale_units14','BOTH'))
        for label,value in [('米制与英尺比例尺','BOTH'),('米制比例尺','M'),('英尺比例尺','FT'),('隐藏比例尺','OFF')]:scale.add_radiobutton(label=label,value=value,variable=self._scale_units14,command=self.scale_setting14)
    def scale_setting14(self):
        with self.scene.transaction('设置比例尺单位'):self.scene.data['meta']['scale_units14']=self._scale_units14.get()
        self.redraw();self.update_title()
    @staticmethod
    def migrate14(scene):
        if scene.data['meta'].get('editor14_migrated'):return
        oldpast=scene.past[:];oldfuture=scene.future[:]
        with scene.transaction('升级Airport Canvas 14'):
            for a in scene.assets.values():
                p=a['props']
                if a['kind'] in TAXIS:p['hold_include_shoulders13']=True
                if a['kind']=='STAND':p.setdefault('move_snap14',True)
            scene.data['meta'].update(editor14_migrated=True,scale_units14='BOTH')
        scene.past=oldpast;scene.future=oldfuture
    def update_title(self):
        super().update_title();self.title(self.title().replace('13.0','14.0'))
    def draft_defaults11(self,mode):
        values=super().draft_defaults11(mode)
        if mode=='STAND':values.update(lead_radius=35.,number_height=4.)
        return values
    def root14(self):
        a=self.scene.assets.get(self.selection)
        if a and a['kind']=='STAND':return a
        group=self.scene.data['groups'].get(self.selection,{})
        return self.scene.assets.get(group.get('stand_root13'))
    def edit_leads13(self):
        self.set_mode('NODES');self._lead_edit13=False;self.redraw();self.status.set('拖动交汇方点改变构型；拖动编号沿弧线移动；不直接编辑单段贝塞尔曲线')
    def child13(self,oid):
        part=self.auto_assets.get(oid)
        if part and part['props']['mark_type']=='STAND_NUMBER':
            self._child13=False;self.set_mode('SELECT');self.select(part['owner']);self.status.set('直接拖动编号沿引入弧线移动，配对编号同步');return
        return super().child13(oid)
    def redraw(self):
        super().redraw()
        if not hasattr(self,'canvas'):return
        c=self.canvas;c.delete('lead_handles13');c.delete('semantic14');self._semantic_handles14=[];a=self.root14()
        if a and self.mode in ('SELECT','NODES') and not self._child13:
            for h in stand14.handles(a,self.scene):
                if h['kind']=='NUMBER':continue
                x,y=self.screen(h['point']);c.create_rectangle(x-5,y-5,x+5,y+5,fill='#e8fbff',outline='#007f9e',width=2,tags='semantic14');self._semantic_handles14.append((x,y,h))
        self.draw_scale14()
    def draw_scale14(self):
        c=self.canvas;c.delete('scale14');units=self.scene.data['meta'].get('scale_units14','BOTH')
        if units=='OFF':return
        from layout14 import nice_length
        rows=[('m',1.),('ft',.3048)] if units=='BOTH' else [('ft',.3048)] if units=='FT' else [('m',1.)]
        height=56 if len(rows)==2 else 34;bottom=c.winfo_height()-14
        dark=getattr(self,'_dark_mode24',False)
        fill,edge,ink=('#202e3d','#42566a','#d6e7f3') if dark else ('#f7fafc','#c4d4de','#264659')
        c.create_rectangle(12,bottom-height-10,190,bottom+5,fill=fill,outline=edge,tags='scale14')
        for i,(label,factor) in enumerate(rows):
            n,pixels=nice_length(self.zoom,factor);y=bottom-i*26;x=22
            c.create_line(x,y-5,x,y,x+pixels,y,x+pixels,y-5,fill=ink,width=2,tags='scale14');c.create_text(x+pixels/2,y-12,text=f'{n:g} {label}',fill=ink,font=('Segoe UI',9),tags='scale14')
        c.tag_raise('scale14')
    def draw_frame11(self,box=None,screen_box=None):
        c=self.canvas;c.delete('frame11');self._handles14=[]
        if box is None:_,_,box=self.frame11()
        if screen_box is not None:
            x0,y0,x1,y1=screen_box
            if box is None:
                xs,ys=zip(*(self.world(x,y) for x in (x0,x1) for y in (y0,y1)))
                box=(min(xs),min(ys),max(xs),max(ys))
        elif box is not None:
            xs,ys=zip(*(self.screen((x,y)) for x in (box[0],box[2]) for y in (box[1],box[3])))
            x0,y0,x1,y1=min(xs),min(ys),max(xs),max(ys)
        else:self._frame_box11=None;return
        pad=8;x0-=pad;y0-=pad;x1+=pad;y1+=pad;cx=(x0+x1)/2;cy=(y0+y1)/2
        c.create_rectangle(x0,y0,x1,y1,outline='#1592aa',width=2,dash=(5,3),tags='frame11')
        for key,x,y in [('NW',x0,y0),('N',cx,y0),('NE',x1,y0),('E',x1,cy),('SE',x1,y1),('S',cx,y1),('SW',x0,y1),('W',x0,cy)]:
            c.create_rectangle(x-4,y-4,x+4,y+4,fill='white',outline='#07899e',width=2,tags='frame11');self._handles14.append((key,x,y))
        ry=y0-28
        if ry<12:ry=y1+28
        c.create_line(cx,y0 if ry<y0 else y1,cx,ry,fill='#07899e',tags='frame11');c.create_oval(cx-6,ry-6,cx+6,ry+6,fill='#dbf6fc',outline='#07899e',width=2,tags='frame11');self._handles14.append(('ROTATE',cx,ry))
        c.create_line(cx-6,cy,cx+6,cy,fill='#07899e',width=2,tags='frame11');c.create_line(cx,cy-6,cx,cy+6,fill='#07899e',width=2,tags='frame11');self._handles14.append(('MOVE',cx,cy))
        self._frame_box11=(box,self.world(cx,cy),[(cx,ry)],[x0,y0,x1,y1])
    def begin_transform11(self,e):
        if not self._frame_box11 or not self.selection:return False
        hit=next((key for key,x,y in reversed(self._handles14) if math.hypot(e.x-x,e.y-y)<9),None)
        box,center,_,visual=self._frame_box11
        if hit is None and self.border_hit11(e.x,e.y,visual):
            x0,y0,x1,y1=visual;hit=min([('W',abs(e.x-x0)),('E',abs(e.x-x1)),('N',abs(e.y-y0)),('S',abs(e.y-y1))],key=lambda x:x[1])[0]
        if hit is None:return False
        self.apply_properties();roots,items,_=self.frame11();self._transform14=dict(kind=hit,roots=roots,items=items,box=box,target=box,center=center,start=self.world(e.x,e.y),delta=[0.,0.],angle=0.,snap=None)
        self._marquee12=None;self.canvas.focus_set();return True
    def start_stand_drag14(self,a,kind,key,e):
        self._stand_drag14=dict(aid=a['id'],kind=kind,key=key,original=copy.deepcopy(a));self._marquee12=None;self.canvas.focus_set()
    def click(self,e):
        if self.mode in ('SELECT','NODES') and not self._space11 and not self._child13:
            for x,y,h in reversed(self._semantic_handles14):
                if math.hypot(e.x-x,e.y-y)<9:
                    self.start_stand_drag14(self.root14(),h['kind'],h['key'],e);return
            hit=self.pick(self.world(e.x,e.y));mark=self.auto_assets.get(hit[1]) if hit else None
            if mark and mark['props']['mark_type']=='STAND_NUMBER':
                a=self.scene.assets.get(mark.get('owner'))
                if a and a['kind']=='STAND':
                    numberids=[m['id'] for m in self.auto_assets.values() if m.get('owner')==a['id'] and m['props']['mark_type']=='STAND_NUMBER'];self.select(a['id']);self.start_stand_drag14(a,'NUMBER',str(numberids.index(mark['id'])),e);return
        if self.mode=='MARK:PEDESTRIAN':
            hit=__import__('layout14').crossing(self.scene,self.world(e.x,e.y),12/max(.001,self.zoom))
            if not hit:self.status.set('靠近服务车道或滑行道中线，预览后单击放置');return
            self.selection=__import__('roads13').zebra(self.scene,hit['hit']);self.set_mode('SELECT');self.refresh();return
        return super().click(e)
    def motion(self,e):
        if self._stand_drag14:
            d=self._stand_drag14;a=copy.deepcopy(d['original']);assets=dict(self.scene.assets);assets[a['id']]=a;preview=SimpleNamespace(assets=assets,data={'generated_overrides':copy.deepcopy(self.scene.data['generated_overrides'])});q=self.world(e.x,e.y)
            if d['kind']=='NUMBER':stand14.slide_number(preview,a['id'],int(d['key']),q)
            else:stand14.move_junction(preview,a['id'],d['key'],q)
            d['candidate']=a['props'];self.canvas.delete('preview14');design=stand14.design(a,preview)
            for path in design['paths']:
                pts=g.simplify(path['points'],.3/max(self.zoom,.01));self.canvas.create_line(*[z for p in pts for z in self.screen(p)],fill='#00a7c2',width=2,tags='preview14')
            for n in design['numbers']:
                x,y=self.screen(n['point']);self.canvas.create_rectangle(x-7,y-7,x+7,y+7,outline='#00a7c2',width=2,tags='preview14')
            return
        if self._transform14:
            d=self._transform14;p=self.world(e.x,e.y);kind=d['kind'];dx,dy=p[0]-d['start'][0],p[1]-d['start'][1];box=d['box']
            if kind=='ROTATE':
                d['angle']=math.atan2(p[1]-d['center'][1],p[0]-d['center'][0])-math.atan2(d['start'][1]-d['center'][1],d['start'][0]-d['center'][0])
                if getattr(e,'state',0)&1:d['angle']=round(d['angle']/(math.pi/4))*math.pi/4
                transform=lambda q:tr.point(q,d['center'],d['angle'],[0,0])
            elif kind=='MOVE':
                if getattr(e,'state',0)&1:p=__import__('project10').constrain(d['start'],p);dx,dy=p[0]-d['start'][0],p[1]-d['start'][1]
                if tr.generated_signs_only(self.scene,d['roots'],self.auto_assets):
                    d['delta'],d['snap'] = [dx,dy],None
                else:
                    d['delta'],d['snap']=stand14.snap_delta(self.scene,d['roots'],[dx,dy],12/max(.001,self.zoom))
                    d['bridge_snap20_5']=__import__('bridge_snap20_5').candidate(self.scene,d['roots'],d['delta'],max(2,18/max(.001,self.zoom)))
                    if d['bridge_snap20_5']:d['delta']=d['bridge_snap20_5'][3];d['snap']=None
                transform=lambda q:[q[k]+d['delta'][k] for k in (0,1)]
            else:
                x0,y0,x1,y1=box
                if 'W' in kind:x0=min(x1-.2,x0+dx)
                if 'E' in kind:x1=max(x0+.2,x1+dx)
                if 'N' in kind:y1=max(y0+.2,y1+dy)
                if 'S' in kind:y0=min(y1-.2,y0+dy)
                d['target']=(x0,y0,x1,y1);sx=(x1-x0)/max(.01,box[2]-box[0]);sy=(y1-y0)/max(.01,box[3]-box[1]);transform=lambda q:[x0+(q[0]-box[0])*sx,y0+(q[1]-box[1])*sy]
            self.canvas.delete('preview14');points=[]
            tolerance=.8/max(.001,self.zoom)
            if kind=='MOVE':
                cached=d.get('preview_paths')
                if not cached or cached[0]!=tolerance:
                    paths=[]
                    for item in d['items'][:300]:
                        if item['type']=='text' or item.get('black_underlay'):continue
                        pts=item['points']
                        if item['type']=='polygon':pts=[*pts,pts[0]]
                        if len(pts)>1:paths.append(g.simplify(pts,tolerance))
                    cached=d['preview_paths']=(tolerance,paths)
                for path in cached[1]:
                    pts=[transform(q) for q in path]
                    self.canvas.create_line(*[z for p in pts for z in self.screen(p)],
                                            fill='#00a7c2',width=1,tags='preview14')
            else:
                for item in d['items'][:300]:
                    if item['type']=='text' or item.get('black_underlay'):continue
                    pts=[transform(q) for q in item['points']]
                    points.extend(pts)
                    if item['type']=='polygon':pts=pts+[pts[0]]
                    if len(pts)>1:
                        self.canvas.create_line(*[z for p in g.simplify(pts,tolerance) for z in self.screen(p)],
                                                fill='#00a7c2',width=1,tags='preview14')
            if kind=='MOVE':
                x0,y0,x1,y1=box
                points=[transform(q) for q in ((x0,y0),(x0,y1),(x1,y0),(x1,y1))]
            if points:self.draw_frame11((min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)))
            if d['snap']:
                x,y=self.screen(d['snap'][3]);self.canvas.create_oval(x-8,y-8,x+8,y+8,outline='#d9388b',width=2,tags='preview14')
            return
        return super().motion(e)
    def release(self,e):
        if self._stand_drag14:
            d=self._stand_drag14;self._stand_drag14=None;self.canvas.delete('preview14')
            if 'candidate' in d:
                with self.scene.transaction('拖动机位交汇点或沿弧线移动编号'):
                    p=self.scene.assets[d['aid']]['props']
                    for key in ('junction_edits14','junction_type14','label_station14'):
                        if key in d['candidate']:p[key]=d['candidate'][key]
                    if d['kind']=='NUMBER':
                        for oid in list(self.scene.data['generated_overrides']):
                            if oid.startswith('AUTO:'+d['aid']+':STAND_NUMBER'):self.scene.data['generated_overrides'].pop(oid)
                self.refresh()
            return
        if self._transform14:
            d=self._transform14;self._transform14=None;self.canvas.delete('preview14')
            try:
                if d['kind'] in ('MOVE','ROTATE') and tr.generated_signs_only(self.scene,d['roots'],self.auto_assets):
                    tr.move_generated_signs(self.scene,d['roots'],self.auto_assets,d['center'],d['angle'],d['delta'],d['items'])
                    self.refresh()
                    return
                with self.scene.transaction('调整选中对象'):
                    if d['kind'] in ('MOVE','ROTATE'):
                        tr.apply(self.scene,d['roots'],d['center'],d['angle'],d['delta'])
                        if d['snap']:
                            aid,parent,station,q=d['snap'];self.scene.assets[aid]['props'].update(entry_asset=parent,entry_station=station,entry_attached=True)
                    else:__import__('layout14').scale(self.scene,d['roots'],d['box'],d['target'])
                self.refresh()
            except (ValueError,KeyError) as exc:self.status.set('未提交：'+str(exc));self.refresh()
            return
        return super().release(e)
    def pointer(self,e):
        if self._stand_drag14 or self._transform14:return
        super().pointer(e)
        if self.mode=='MARK:PEDESTRIAN':
            self.canvas.delete('cross_preview14');hit=__import__('layout14').crossing(self.scene,self.world(e.x,e.y),12/max(.001,self.zoom));self._cross_preview14=hit
            if hit:
                from marking_catalog import primitives
                q,u=hit['point'],hit['direction'];a=dict(id='preview',points=[q,[q[k]+u[k]*10 for k in (0,1)]],props=dict(mark_type='PEDESTRIAN',width=hit['width'],crossing_full13=True,crossing_depth14=4,spacing=.6))
                for item in primitives(a):self.canvas.create_polygon(*[v for p in item['points'] for v in self.screen(p)],fill='#ffffff',outline='#008baa',width=1,tags='cross_preview14')
                self.status.set('预览横跨整个道面；条纹沿道路方向，条纹排列横跨道路；单击放置')
        if self.mode=='SELECT':
            key=next((k for k,x,y in reversed(self._handles14) if math.hypot(e.x-x,e.y-y)<9),None)
            self.canvas.configure(cursor='crosshair' if key=='ROTATE' else 'fleur' if key=='MOVE' else 'sizing' if key else '')
    def cancel_action(self,e=None):
        self._stand_drag14=None;self._transform14=None
        if hasattr(self,'canvas'):self.canvas.delete('preview14');self.canvas.delete('cross_preview14')
        return super().cancel_action(e)
    def set_mode(self,mode):
        self._stand_drag14=None;self._transform14=None
        if hasattr(self,'canvas'):self.canvas.delete('preview14');self.canvas.delete('cross_preview14')
        return super().set_mode(mode)
    def gesture11(self):return self._stand_drag14 or self._transform14 or super().gesture11()
    def update_inspector(self):
        super().update_inspector()
        if self._draft11:return
        a=self.scene.assets.get(self.selection);self._inspector_busy=True
        try:
            if a and a['kind']=='STAND':
                sec=self.section('机位交汇与移动');self.property_field(sec,'move_snap14','整套移动时吸附滑行道中线',a['props'].get('move_snap14',True),'bool')
                ttk.Label(sec,text='拖动交汇方点改变引入线；编号沿弧线拖动并自动让线。外框方柄缩放，圆柄旋转，中心十字移动。',wraplength=260).grid(row=10,column=0,columnspan=2,sticky='w')
                ttk.Button(self.property_body,text='建立组合机位（2套 / 3套）…',command=self.combine_dialog14).pack(fill='x',padx=8,pady=5)
            if a and a['props'].get('deice_layout12'):
                sec=self.section('道面底色');self.property_field(sec,'deice_inherit14','自动同步所在道面颜色',a['props'].get('deice_inherit14',True),'bool')
        finally:self._inspector_busy=False
    def combine_dialog14(self):
        a=self.root14()
        if not a:return
        win=tk.Toplevel(self);win.title('组合机位');count=tk.StringVar(value='3');parallel=tk.BooleanVar(value=True);spacing=tk.StringVar(value='24');angle=tk.StringVar(value='15');primary=tk.StringVar(value='CENTER')
        for label,var,choices in [('机位套数',count,['2','3']),('主要机位',primary,['CENTER','SIDES'])]:ttk.Label(win,text=label).pack(anchor='w',padx=16);ttk.Combobox(win,textvariable=var,values=choices,state='readonly').pack(fill='x',padx=16,pady=4)
        ttk.Checkbutton(win,text='平行组合（取消后为非平行组合）',variable=parallel).pack(anchor='w',padx=16)
        for label,var in [('左右间距 m',spacing),('非平行夹角 °',angle)]:ttk.Label(win,text=label).pack(anchor='w',padx=16);ttk.Entry(win,textvariable=var).pack(fill='x',padx=16)
        ttk.Label(win,text='主线连续、辅线断续；两侧编号带L/R。几何模板仍需按实际机型检查净距。',wraplength=300).pack(padx=16,pady=8)
        def apply():
            try:stand14.combine(self.scene,a['id'],int(count.get()),parallel.get(),float(spacing.get()),float(angle.get()),primary.get());win.destroy();self.refresh()
            except ValueError as exc:messagebox.showerror('组合机位',str(exc),parent=win)
        ttk.Button(win,text='生成组合机位',command=apply).pack(pady=10)
    def junction_inspector(self,jid):
        super().junction_inspector(jid)
        if '_terminal_keep13' in self.editor_vars:
            self.hide_field11('_terminal_keep13');self._inspector_busy=True
            try:sec=self.section('选择截去哪一侧');self.property_field(sec,'_terminal_cut14','截去侧','终点侧','radio',['起点侧','终点侧'])
            finally:self._inspector_busy=False
            ttk.Label(self.property_body,text='起点/终点按滑行道绘制方向。选择截去侧后，点击上方“将路口设为末端”。',wraplength=270,padding=8).pack(fill='x')
    def terminal13(self,j):
        if '_terminal_cut14' not in self.editor_vars:return super().terminal13(j)
        aid=self._terminal_choices13[self.editor_vars['_terminal_asset13'][0].get()];keep='END' if self.editor_vars['_terminal_cut14'][0].get()=='起点侧' else 'START';station=j['stations'][j['assets'].index(aid)]
        try:__import__('rules13').set_terminal(self.scene,aid,station,keep,jid=j['id']);self.select(aid);self.refresh()
        except ValueError as exc:self.status.set(str(exc))
    def export(self,kind):
        self.apply_properties();win=tk.Toplevel(self);win.title('导出 '+kind.upper());win.geometry('400x490');width=tk.StringVar(value='3200');dpi=tk.StringVar(value='150');extent=tk.StringVar(value='全机场');transparent=tk.BooleanVar(value=False);scales=tk.BooleanVar(value=True);labels=tk.BooleanVar(value=self.labels.get());fac=tk.BooleanVar(value=self.facilities.get());protect=tk.BooleanVar(value=self.protection.get());info=tk.StringVar()
        from scene_render import bounds
        full=bounds(self.scene)
        def box():
            if extent.get()=='当前视图':
                p=self.world(0,self.canvas.winfo_height());q=self.world(self.canvas.winfo_width(),0);return (*p,*q)
            if extent.get()=='选中对象':return self.frame11()[2] or full
            return full
        for label,var,choices in [('像素宽度',width,['1600','2400','3200','4800','8000']),('DPI（打印元数据）',dpi,['96','150','300','600']),('导出范围',extent,['全机场','当前视图','选中对象'])]:ttk.Label(win,text=label).pack(anchor='w',padx=18,pady=(10,0));ttk.Combobox(win,textvariable=var,values=choices).pack(fill='x',padx=18)
        for text,var in [('透明背景',transparent),('导出米制及英尺比例尺',scales),('对象文字标签',labels),('设施图层',fac),('保护区域图层',protect)]:ttk.Checkbutton(win,text=text,variable=var).pack(anchor='w',padx=18,pady=3)
        def update(*_):
            try:w,h=__import__('export14').dimensions(box(),int(width.get()));info.set(f'{w} × {h} px；保持范围纵横比；RGBA约{w*h*4/1048576:.1f} MiB')
            except ValueError as exc:info.set(str(exc))
        for var in (width,extent):var.trace_add('write',update)
        ttk.Label(win,textvariable=info,wraplength=360).pack(padx=18,pady=10);update()
        def save():
            try:
                __import__('export14').dimensions(box(),int(width.get()));dots=int(dpi.get())
                if not 36<=dots<=1200:raise ValueError('DPI应为36～1200')
                p=filedialog.asksaveasfilename(parent=win,title='导出机场图',defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)])
                if not p:return
                size=__import__('export14').export(self.scene,p,kind,int(width.get()),dots,transparent.get(),box(),labels.get(),fac.get(),protect.get(),scales.get());win.destroy();self.status.set(f'已导出 {size[0]}×{size[1]}：{p}')
            except (ValueError,OSError) as exc:messagebox.showerror('导出失败',str(exc),parent=win)
        ttk.Button(win,text='选择位置并导出',command=save).pack(pady=8)
    def demo10(self):Editor14(AirportScene.load(Path(__file__).with_name('example_editor14.ACP')))

def main():Editor14(AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None).mainloop()

