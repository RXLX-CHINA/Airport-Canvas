"""Independent designation display, explicit route-edit state, one crossing preview."""
import copy,math,sys
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from qt_compat import ttk
from editor15_gui import Editor15
from airport_scene import AirportScene
import scene_geometry as g
import segments16 as seg
from route_workflow17 import RouteWorkflow,visible_labels

class Editor17(Editor15):
    def __init__(self,scene=None):
        self.route17=RouteWorkflow();self._color17=False;self._hover17=None;self._route_inputs17={}
        super().__init__(scene if scene is not None else AirportScene.load(Path(__file__).with_name('example_editor17.ACP')))
        menu=self.nametowidget(self.cget('menu'));view=tk.Menu(menu,tearoff=False);menu.add_cascade(label='路线与编号',menu=view)
        self._color_var17=tk.BooleanVar(value=False);view.add_checkbutton(label='彩色编号显示（独立视图） F6',variable=self._color_var17,command=self.toggle_color17)
        view.add_command(label='路线编辑：拆分 / 改号 / 截断 / 合并',command=self.open_route_editor17)
        self.bind('<F6>',lambda e:self.toggle_color17(not self._color17))
    def update_title(self):super().update_title();self.title(self.title().replace('15.1','17.0'))
    def open_route_editor17(self,action='NAME'):
        self._route_draft17=None;self._hover17=None;self._route_inputs17={}
        self.set_mode('SPLIT7')
        self.route17.choose(action)
        self.update_inspector();self.redraw()
    def toggle_color17(self,value=None):
        self._color17=self._color_var17.get() if value is None else bool(value);self._color_var17.set(self._color17)
        self.canvas.delete('color17');self.canvas.itemconfigure('map',state='normal')
        if '_map_visible21' in self.canvas.__dict__:
            # The Qt renderer keeps the latest normal display list while hidden.
            self.redraw()
        elif not self._color17:
            if self._renderer:self._renderer.items=None
            self.refresh()
        else:self.redraw()
    def set_mode(self,mode):
        if mode in ('BREAK','SPLIT7'):
            self.route17.choose('SPLIT_NEW' if mode=='BREAK' else 'SPLIT_KEEP');mode='SPLIT7'
        elif hasattr(self,'route17'):self.route17.cancel()
        self._hover17=None
        if getattr(self,'_shear15',None):self.canvas.itemconfigure('owner:'+self._shear15['aid'],state='normal')
        super().set_mode(mode)
        if mode=='SPLIT7':self.update_inspector();self.redraw();self.status.set('路线编辑：先选操作，再点选路线。切分和截断须预览后按确认提交；F6独立切换彩色显示。')
    def redraw(self):
        if not hasattr(self,'canvas'):return
        c=self.canvas;c.delete('color17');c.delete('route_preview17')
        if self._color17:
            if hasattr(self,"grid_visible"):self.draw_grid7()
            # Never replace render_items or feed simplified geometry to its renderer.
            c.itemconfigure('map',state='hidden')
            if not getattr(getattr(self,'view_tools21_2',None),'active',False):
                self.draw_f6_buildings17()
            for tag in ('overlay','frame11','semantic14','corner_handles12','cut_preview11','snap_cursor'):c.delete(tag)
            self._frame_box11=None;self._handles14=[]
            palette=seg.colors(self.scene)
            for a in self.scene.assets.values():
                if a['kind'] not in seg.TAXIS+('RUNWAY',):continue
                c.create_line(*[v for p in a['points'] for v in self.screen(p)],fill=palette.get(seg.designation(a),'#929da4'),width=5 if a['id']==self.selection else 3,tags='color17')
            w,h=c.winfo_width(),c.winfo_height();p0=self.world(0,h);p1=self.world(w,0);occupied=[]
            for aid,label,q in visible_labels(self.scene,(*p0,*p1)):
                x,y=self.screen(q);width=max(34,len(label)*9+12);x=max(width/2+4,min(w-width/2-4,x));y=max(18,min(h-18,y-15))
                for i in range(8):
                    box=(x-width/2,y-11,x+width/2,y+11)
                    if not any(not (box[2]<b[0] or box[0]>b[2] or box[3]<b[1] or box[1]>b[3]) for b in occupied):break
                    y+=24
                occupied.append(box)
                dark=getattr(self,'_dark_mode24',False)
                c.create_rectangle(*box,fill='#21303e' if dark else '#ffffff',outline=palette[label],tags='color17')
                c.create_text(x,y,text=label,font=('Segoe UI',11,'bold'),fill='#edf5fc' if dark else '#172b38',tags='color17')
            c.create_text(14,14,text='彩色编号显示  ·  F6返回机场图',anchor='nw',fill='#172b38',font=('Microsoft YaHei',10),tags='color17');self.draw_scale14()
            if self.points and self.mode in ('RUNWAY','APRON','PROTECTION','EQUIPMENT','CLOSED_AREA'):
                points=[self.screen(p) for p in self.points]
                for x,y in points:
                    c.create_oval(x-4,y-4,x+4,y+4,fill='#0f9ebb',outline='white',tags='color17')
                if len(points)>1:
                    c.create_line(*[v for p in points for v in p],fill='#0f9ebb',width=2,dash=(5,3),tags='color17')
        else:
            c.itemconfigure('map',state='normal');super().redraw()
        p=self.route17.pending
        if p and (p['revision']!=self.scene.revision or p['scene_id']!=id(self.scene)):self.route17.cancel();p=None
        hit=p or self._hover17
        if self.mode=='SPLIT7' and hit:
            a=self.scene.assets.get(hit['aid'])
            if a:
                q,u=g.at(a['points'],hit['station']);v=[-u[1],u[0]];half=a['props']['width']/2+a['props'].get('shoulder',0)+3
                c.create_line(*self.screen([q[k]-v[k]*half for k in (0,1)]),*self.screen([q[k]+v[k]*half for k in (0,1)]),fill='#d52c7a',width=3 if p else 1,dash=() if p else (4,4),tags='route_preview17')
                if hit.get('action')=='TERMINAL':
                    lo,hi=(hit['station'],g.length(a['points'])) if hit['keep']=='START' else (0,hit['station']);pts=g.subpath(a['points'],lo,hi)
                    if len(pts)>1:c.create_line(*[v for q in pts for v in self.screen(q)],fill='#d94444',width=4,dash=(7,4),tags='route_preview17')
        if self._shear15:c.itemconfigure('owner:'+self._shear15['aid'],state='hidden');c.tag_raise('shear_preview15')
    def draw_f6_buildings17(self):
        canvas=self.canvas
        hidden=self.scene.data['meta'].get('object_display',{})
        for oid,asset in self.scene.assets.items():
            if asset['kind'] not in ('RUNWAY','APRON') and not asset['props'].get('building_role19'):
                continue
            style=hidden.get(oid,{})
            if style.get('hidden') or style.get('opacity',1)<=0:
                continue
            points=asset['points']
            if asset['kind']=='RUNWAY':
                points=g.rectangle(points,asset['props']['width'])
            if len(points)<3:continue
            canvas.create_polygon(*[v for p in points for v in self.screen(p)],
                                  fill='',outline='#788a9a',width=2 if oid==self.selection else 1,
                                  tags=('color17','f6_object17','f6_owner20_2:'+oid))

    def update_inspector(self):
        if getattr(self,'mode',None)=='SPLIT7':return self.route_inspector17()
        super().update_inspector()
        a=self.scene.assets.get(self.selection)
        if a and a['kind'] in seg.TAXIS:
            self.hide_field11('_split_station')
            def remove_old_split(parent):
                for child in list(parent.winfo_children()):
                    if isinstance(child,ttk.Button) and '站位' in str(child.cget('text')) and '分段' in str(child.cget('text')):child.destroy()
                    else:remove_old_split(child)
            remove_old_split(self.property_body)
            ttk.Button(self.property_body,text='路线编辑：拆分 / 改号 / 截断 / 合并',command=self.open_route_editor17).pack(fill='x',padx=8,pady=6)
        if a and a['kind']=='STAND':
            self._inspector_busy=True
            try:self.property_field(self.section('安全线与停止标志'),'safety_include_stops17','安全线容纳无引导停止标志',a['props'].get('safety_include_stops17',True),'bool')
            finally:self._inspector_busy=False
        if a and a['kind']=='ROAD':
            self._inspector_busy=True
            try:self.property_field(self.section('与滑行道交汇'),'auto_road_hold17','自动生成驶入侧道路等待标志',a['props'].get('auto_road_hold17',True),'bool')
            finally:self._inspector_busy=False
        if a and a['props'].get('crossing_full13'):ttk.Label(self.property_body,text='人行横道：橙色手柄和旋转手柄均调整偏斜，不复制原标记。宽度跟随道面，通道进深与条纹间隔在标记属性中设置。',wraplength=260).pack(fill='x',padx=8,pady=8)
    def terminal13(self,j):
        choices=[aid for aid in j['assets'] if aid in self.scene.assets and self.scene.assets[aid]['kind'] in seg.TAXIS]
        if not choices:return
        chosen=next((aid for aid in choices if aid==self.selection),choices[0]);self.set_mode('SPLIT7');self.selection=chosen;self.route17.choose('TERMINAL')
        try:self.route17.preview(self.scene,chosen,g.project(self.scene.assets[chosen]['points'],j['point'])[1])
        except ValueError as exc:self.status.set(str(exc))
        self.update_inspector();self.redraw()
    def junction_inspector(self,jid):
        super().junction_inspector(jid)
        frames=set()
        for key in ('_terminal_asset13','_terminal_keep13','_terminal_cut14'):
            control=self._field_controls.pop(key,None)
            if control:frames.add(control.master)
            self.editor_vars.pop(key,None)
        for frame in frames:
            if frame.winfo_exists():frame.destroy()
        for child in list(self.property_body.winfo_children()):
            if isinstance(child,ttk.Button) and '末端' in str(child.cget('text')):child.destroy()
            elif isinstance(child,ttk.Label) and '裁去' in str(child.cget('text')):child.destroy()
        j=next((x for x in __import__('pavement_geometry').crossings(self.scene) if x['id']==jid),None)
        if j:ttk.Button(self.property_body,text='在此进入路线截断预览',command=lambda:self.terminal13(j)).pack(fill='x',padx=8,pady=6)
    def split_from_field(self):self.set_mode('SPLIT7')
    def route_inspector17(self):
        prior=getattr(self,'_route_inputs17',{});draft=getattr(self,'_route_draft17',None)
        if prior and draft and draft['aid']==self.selection and draft['action']==self.route17.action:
            draft.update({k:v.get() for k,v in prior.items()})
        if self._property_after:self.after_cancel(self._property_after);self._property_after=None
        self._inspector_token+=1;self._dirty_fields.clear();self._field_controls={};self.editor_vars={};self._editor_oid=self.selection
        for child in self.property_body.winfo_children():child.destroy()
        self._book15=None;self.property_title.configure(text='路线编辑');self.property_error.configure(text='')
        body=ttk.Frame(self.property_body,padding=10);body.pack(fill='both',expand=True)
        action_var=tk.StringVar(value=self.route17.action)
        def choose():self.route17.choose(action_var.get());self._hover17=None;self.update_inspector();self.redraw()
        for value,label in [('NAME','整分支独立改号（不切几何）'),('INDEPENDENT','强制独立选中分支并命名'),('SPLIT_KEEP','逻辑分段，保留同一编号'),('SPLIT_NEW','逻辑分段，新段独立编号'),('TERMINAL','末端截断（删除指定侧）'),('MERGE','合并编号（不合并几何）')]:ttk.Radiobutton(body,text=label,value=value,variable=action_var,command=choose).pack(anchor='w',pady=3)
        ttk.Separator(body).pack(fill='x',pady=8);a=__import__('segments18').routes(self.scene).get(self.selection)
        if a and a['kind'] in seg.TAXIS:
            ttk.Label(body,text='已选：'+seg.designation(a)+f'   {g.length(a["points"]):.1f} m').pack(anchor='w');name_var=tk.StringVar(value=seg.designation(a));station_var=tk.StringVar(value=format(self.route17.pending['station'] if self.route17.pending else g.length(a['points'])/2,'.9f'));keep_var=tk.StringVar(value=self.route17.pending['keep'] if self.route17.pending else 'START')
            self._route_inputs17=dict(name=name_var,station=station_var,keep=keep_var)
            if draft and draft['aid']==a['id'] and draft['action']==self.route17.action:
                name_var.set(draft['name'])
                if not self.route17.pending:station_var.set(draft['station']);keep_var.set(draft['keep'])
            self._route_draft17=dict(aid=a['id'],action=self.route17.action,name=name_var.get(),station=station_var.get(),keep=keep_var.get())
            if self.route17.action in ('NAME','INDEPENDENT','SPLIT_NEW'):
                ttk.Label(body,text='目标编号（输入后按下面的确认按钮）').pack(anchor='w',pady=(8,0));ttk.Entry(body,textvariable=name_var).pack(fill='x')
            if self.route17.action in ('SPLIT_KEEP','SPLIT_NEW','TERMINAL'):
                ttk.Label(body,text='点击路线内部预览，或输入站位 m：').pack(anchor='w',pady=(8,0));ttk.Entry(body,textvariable=station_var).pack(fill='x')
                if self.route17.action=='TERMINAL':
                    for val,label in [('START','保留起点侧 / 删除终点侧'),('END','保留终点侧 / 删除起点侧'),('DELETE','删除整条选中岔路（不删除相邻主线）')]:ttk.Radiobutton(body,text=label,value=val,variable=keep_var,command=self.preview_route17).pack(anchor='w',pady=3)
                ttk.Button(body,text='更新预览',command=self.preview_route17).pack(fill='x',pady=5)
            if self.route17.action=='MERGE':ttk.Button(body,text='选择要合并编号的段落…',command=self.merge_names11).pack(fill='x',pady=6)
            else:ttk.Button(body,text='确认独立改号' if self.route17.action in ('NAME','INDEPENDENT') else '确认提交预览',command=self.commit_route17).pack(fill='x',pady=6)
            if a['props'].get('terminal_backup13'):ttk.Button(body,text='恢复这条滑行道的完整几何',command=lambda:self.restore_terminal13(a['id'])).pack(fill='x',pady=5)
        else:ttk.Label(body,text='请在画布点击滑行道分支。',wraplength=250).pack(fill='x',pady=10)
        ttk.Label(body,text='粉线=切口，红虚线=将删除部分。右键/Esc先取消预览，再次退出编辑。Ctrl+Z撤销；F6仅改变显示，不切换工具。',wraplength=260).pack(fill='x',pady=12)
        ttk.Button(body,text='完成路线编辑',command=lambda:self.set_mode('SELECT')).pack(fill='x',pady=8)
    def preview_route17(self):
        try:self.route17.preview(self.scene,self.selection,float(self._route_inputs17['station'].get()),self._route_inputs17['keep'].get());self.redraw()
        except (KeyError,ValueError) as exc:self.status.set(str(exc))
    def commit_route17(self):
        try:
            if self.route17.action=='NAME':seg.rename_branch(self.scene,self.selection,self._route_inputs17['name'].get())
            else:
                p=self.route17.pending
                if not p or abs(float(self._route_inputs17['station'].get())-p['station'])>1e-5:raise ValueError('请先更新预览，确认画布中的切口位置')
                self.selection=self.route17.commit(self.scene,self._route_inputs17['name'].get())
            self._hover17=None;self.refresh()
        except (KeyError,ValueError) as exc:self.status.set(str(exc))
    def click(self,e):
        if self._color17 and self.mode=='SELECT' and not self._space11 and not self.__dict__.get('_common_display_tool',False):
            hit=self.taxi_hit11(self.world(e.x,e.y))
            if hit:self.select(hit[1]);return
        if self.mode=='SPLIT7' and not self._space11:
            hit=self.taxi_hit11(self.world(e.x,e.y))
            if hit:
                _,aid,s,q=hit;self.selection=aid
                if self.route17.action in ('SPLIT_KEEP','SPLIT_NEW','TERMINAL'):
                    keep=self._route_inputs17.get('keep');keep=keep.get() if keep else 'START'
                    try:self.route17.preview(self.scene,aid,s,keep)
                    except ValueError as exc:self.status.set(str(exc));return
                self.update_inspector();self.redraw()
            return
        return super().click(e)
    def pointer(self,e):
        if self.mode=='SPLIT7':
            hit=self.taxi_hit11(self.world(e.x,e.y));self._hover17=None
            if hit and not self.route17.pending and self.route17.action in ('SPLIT_KEEP','SPLIT_NEW','TERMINAL'):
                _,aid,s,q=hit;keep=self._route_inputs17.get('keep');self._hover17=dict(aid=aid,station=s,keep=keep.get() if keep else 'START',action=self.route17.action)
            self.redraw();return
        return super().pointer(e)
    def cancel_action(self,e=None):
        if self.mode=='SPLIT7':
            if self.route17.pending:self.route17.cancel();self._hover17=None;self.redraw();return
            self.set_mode('SELECT');return
        return super().cancel_action(e)
    def begin_transform11(self,e):
        a=self.scene.assets.get(self.selection)
        if a and a['props'].get('crossing_full13'):
            handle=next((k for k,x,y in reversed(self._handles14) if math.hypot(e.x-x,e.y-y)<9),None)
            if handle=='ROTATE':
                self._shear15=dict(aid=a['id'],original=copy.deepcopy(a),start17=self.world(e.x,e.y),handle17=__import__('interaction15').shear_handle(self.scene,a));return True
            if handle not in (None,'MOVE'):self.status.set('横跨宽度跟随道面；请在属性中调整通道进深。');return True
        return super().begin_transform11(e)
    def motion(self,e):
        if self._shear15 and 'start17' in self._shear15:
            d=self._shear15;q=self.world(e.x,e.y);target=[d['handle17'][k]+q[k]-d['start17'][k] for k in (0,1)];x,y=self.screen(target);e=SimpleNamespace(x=x,y=y,state=getattr(e,'state',0))
        return super().motion(e)
    def release(self,e):
        return super().release(e)

def main():Editor17(AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None).mainloop()
