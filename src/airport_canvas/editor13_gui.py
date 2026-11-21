"""ACP projects, real stand groups, child editing and stand branch handles."""
from contextlib import nullcontext
import copy,json,math,sys
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from qt_compat import ttk,filedialog,messagebox
from editor12_gui import Editor12
from airport_scene import AirportScene
import scene_geometry as g
import transform11 as tr

def acp_path(path):
    path=Path(path)
    if str(path).lower().endswith('.airport.json'):return Path(str(path)[:-13]+'.ACP')
    return path if path.suffix.lower()=='.acp' else path.with_suffix('.ACP')

class Editor13(Editor12):
    def __init__(self,scene=None):
        self._child13=False;self._lead_edit13=False;self._lead_drag13=None;self._lead_handles13=[]
        if scene is None:
            p=Path(__file__).with_name('example_editor13.ACP');scene=AirportScene.load(p) if p.exists() else AirportScene()
        self.migrate13(scene);super().__init__(scene)
    @staticmethod
    def migrate13(scene):
        past=scene.past[:];future=scene.future[:]
        __import__('stand13').ensure_groups(scene)
        if not scene.data['meta'].get('editor13_migrated'):
            with scene.transaction('更新道路转弯衔接'):
                __import__('roads13').reconcile(scene);scene.data['meta']['editor13_migrated']=True
        scene.past=past;scene.future=future
    def refresh(self):
        self.migrate13(self.scene);return super().refresh()
    def update_title(self):
        super().update_title();self.title(self.title().replace('12.0','13.0'))
    def sync_tree(self):
        super().sync_tree()
        for oid,a in self.auto_assets.items():
            root=self.scene.assets.get(a.get('owner'));gid=root['props'].get('stand_group13') if root and root['kind']=='STAND' else None
            if gid and self.tree.exists(gid) and self.tree.exists(oid):self.tree.move(oid,gid,'end')
    def tree_select(self,e=None):
        if self._syncing_tree or not self.tree.selection():return
        oid=self.tree.selection()[0]
        self._child13=oid in self.auto_assets or bool(self.scene.assets.get(oid,{}).get('props',{}).get('stand_owner13'));self._editing_guide11=self._child13
        super().tree_select(e)
    def select(self,oid):
        if oid in self.scene.data['groups'] or self.scene.assets.get(oid,{}).get('kind')=='STAND':self._child13=False
        if not self._child13:self._editing_guide11=False
        return super().select(oid)
    def delete_selected(self):
        if self._child13:return super().delete_selected()
        roots=self.selected_roots11()
        if any(oid in self.scene.data['groups'] and self.scene.data['groups'][oid].get('stand_root13') for oid in roots):
            from scene_hierarchy import descendants
            with self.scene.transaction('删除所选机位组'):
                for oid in roots:
                    for child in reversed(descendants(self.scene,oid)):
                        if child in self.scene.assets or child in self.scene.data['groups'] or child in self.scene.movements:self.scene.delete(child)
                    self.scene.delete(oid)
            self.selection=None;self.selected_ids=set();self.refresh();return
        return super().delete_selected()
    def copy_selected(self):
        group=self.scene.data['groups'].get(self.selection);old=self.selection
        if group and group.get('stand_root13'):self.selection=group['stand_root13']
        try:return super().copy_selected()
        finally:self.selection=old
    def set_mode(self,mode):
        self._lead_edit13=False;self._lead_drag13=None
        if mode!='SELECT':self._child13=False
        return super().set_mode(mode)
    def selected_roots11(self):
        if self._child13 and self.selection:return {self.selection}
        roots=super().selected_roots11()
        return {self.scene.assets[oid]['props'].get('stand_group13',oid) if oid in self.scene.assets and self.scene.assets[oid]['kind']=='STAND' else oid for oid in roots}
    def frame11(self):
        if self._child13 and self.selection:
            items=[i for i in self.render_items if i.get('oid')==self.selection];return {self.selection},items,tr.bounds(items)
        return super().frame11()
    def release(self,e):
        if self._lead_drag13:
            d=self._lead_drag13;self._lead_drag13=None;self.canvas.delete('lead_preview13')
            if d.get('candidate'):
                with self.scene.transaction('编辑成套机位引导控制点'):
                    p=self.scene.assets[d['aid']]['props'];p.setdefault('lead_edits13',{}).update(d['candidate']);p['lead_edit_type13']=p.get('lead_type','A')
                self.refresh()
            return
        if self._child13 and self._marquee12 and not self._marquee12['active']:
            d=self._marquee12;self._marquee12=None;self.canvas.delete('marquee12');self.select(d['hit'][1] if d['hit'] else None);return
        return super().release(e)
    def click(self,e):
        if self._lead_edit13 and self.mode=='NODES':
            for x,y,key,index,field in reversed(self._lead_handles13):
                if math.hypot(x-e.x,y-e.y)>9:continue
                a=self.scene.assets[self.selection];design=__import__('stand13').design(a,self.scene);nodes={p['key']:__import__('stand13').part_nodes(a,p['key'],self.scene) for p in design['paths']};self._lead_drag13=dict(aid=a['id'],key=key,index=index,field=field,nodes=nodes);return
            return
        if self.mode=='MARK:PEDESTRIAN':
            p=self.world(e.x,e.y);options=[]
            for aid,a in self.scene.assets.items():
                if a['kind'] not in ('ROAD','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):continue
                distance,station,q=g.project(a['points'],p)
                if distance<max(12/self.zoom,a['props']['width']/2):options.append((distance,0 if a['kind']=='ROAD' else 1,aid,station,q))
            if not options:self.status.set('请点击服务车道或滑行道中线放置横跨道面的人行横道');return
            distance,_,aid,station,q=min(options);self.selection=__import__('roads13').zebra(self.scene,(distance,aid,station,q));self.set_mode('SELECT');self.refresh();return
        return super().click(e)
    def motion(self,e):
        if not self._lead_drag13:return super().motion(e)
        d=self._lead_drag13;a=self.scene.assets[d['aid']];o,u,v=__import__('stand13').frame(a);p=self.world(e.x,e.y)
        if d['field']=='p' and d['index']==0 and (d['key'].startswith('ENTRY') or d['key']=='LABEL_STUB') and a['props'].get('entry_asset') in self.scene.assets and a['props'].get('entry_attached',True):p=g.project(self.scene.assets[a['props']['entry_asset']]['points'],p)[2]
        q=[sum((p[k]-o[k])*axis[k] for k in (0,1)) for axis in (u,v)];nodes=copy.deepcopy(d['nodes']);selected=nodes[d['key']][d['index']];old=selected[d['field']];delta=[q[k]-old[k] for k in (0,1)];changed={d['key']}
        if d['field']=='p':
            for key,parts in nodes.items():
                for node in parts:
                    if g.distance(node['p'],old)<.01:
                        changed.add(key)
                        for field in ('p','incoming','outgoing'):node[field]=[node[field][k]+delta[k] for k in (0,1)]
        else:selected[d['field']]=q
        d['candidate']={key:nodes[key] for key in changed};self.canvas.delete('lead_preview13')
        from curve_model import evaluate
        for parts in nodes.values():
            world=copy.deepcopy(parts)
            for node in world:
                for field in ('p','incoming','outgoing'):node[field]=[o[k]+u[k]*node[field][0]+v[k]*node[field][1] for k in (0,1)]
            self.canvas.create_line(*[z for p in evaluate(world) for z in self.screen(p)],fill='#00a0c0',width=2,tags='lead_preview13')
    def redraw(self):
        super().redraw()
        if not hasattr(self,'canvas'):return
        if self._child13 and self.mode=='SELECT':self.draw_frame11()
        self.canvas.delete('lead_handles13');self._lead_handles13=[]
        if not self._lead_edit13 or self.selection not in self.scene.assets:return
        self.canvas.delete('overlay');a=self.scene.assets[self.selection];module=__import__('stand13');o,u,v=module.frame(a)
        for part in module.design(a,self.scene)['paths']:
            nodes=module.part_nodes(a,part['key'],self.scene)
            for index,node in enumerate(nodes):
                fields=['p']+(['outgoing'] if index<len(nodes)-1 else [])+(['incoming'] if index>0 else [])
                anchor=self.screen([o[k]+u[k]*node['p'][0]+v[k]*node['p'][1] for k in (0,1)])
                for field in fields:
                    q=node[field];x,y=self.screen([o[k]+u[k]*q[0]+v[k]*q[1] for k in (0,1)])
                    if field=='p':self.canvas.create_rectangle(x-4,y-4,x+4,y+4,fill='white',outline='#008da5',width=2,tags='lead_handles13')
                    else:
                        self.canvas.create_line(*anchor,x,y,fill='#c07a23',dash=(3,4),tags='lead_handles13');self.canvas.create_oval(x-4,y-4,x+4,y+4,fill='#ffe8b6',outline='#c07a23',width=2,tags='lead_handles13')
                    self._lead_handles13.append((x,y,part['key'],index,field))
    def cancel_action(self,e=None):
        self._lead_drag13=None;self.canvas.delete('lead_preview13');return super().cancel_action(e)
    def gesture11(self):return self._lead_drag13 or super().gesture11()
    def edit_leads13(self):
        aid=self.selection;self.set_mode('NODES');self.selection=aid;self._lead_edit13=True;self.redraw();self.status.set('机位引入线：方块移动交汇端点，圆柄调整曲率；共同交汇点同步移动，右键取消')
    def child13(self,oid):
        self.set_mode('SELECT');self._child13=True;self._editing_guide11=True;self.select(oid);self.redraw()
    def update_inspector(self):
        super().update_inspector()
        if self._draft11:return
        a=self.scene.assets.get(self.selection);group=self.scene.data['groups'].get(self.selection)
        if group and group.get('stand_root13'):
            ttk.Button(self.property_body,text='编辑机位定位与参数',command=lambda:self.select(group['stand_root13'])).pack(fill='x',padx=8,pady=5)
        self._inspector_busy=True
        try:
            if a and a['kind']=='STAND':
                ttk.Button(self.property_body,text='编辑 A/B/C/D 各段曲率与交汇点',command=self.edit_leads13).pack(fill='x',padx=8,pady=5)
                sec=self.section('组内子元素（可独立编辑）')
                for oid,part in self.auto_assets.items():
                    if part.get('owner')==a['id']:ttk.Button(sec,text=part['name'],command=lambda oid=oid:self.child13(oid)).pack(fill='x',pady=2)
            if self._child13:
                part=self.auto_assets.get(self.selection);root=part.get('owner') if part else a['props'].get('stand_owner13') if a else None
                if root in self.scene.assets:ttk.Button(self.property_body,text='返回整套机位',command=lambda:(setattr(self,'_child13',False),setattr(self,'_editing_guide11',False),self.select(root))).pack(fill='x',padx=8,pady=5)
                if part:ttk.Button(self.property_body,text='转为可编辑子对象（脱离自动生成）',command=self.detach_child13).pack(fill='x',padx=8,pady=5)
            if a and a['kind']=='RUNWAY':
                sec=self.section('跑道交汇与中心圆净距');self.property_field(sec,'runway_priority13','同类跑道标志优先级',a['props'].get('runway_priority13',0),'int');self.property_field(sec,'circle_clearance13','中心圆外中线净空 m',a['props'].get('circle_clearance13',3.),'float');ttk.Label(sec,text=f'中心圆外缘半径：{a["props"]["width"]/4:g} m（随跑道宽度联动）').grid(row=3,column=0,columnspan=2,sticky='w')
            if a and a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                sec=self.section('等待标志宽度');self.property_field(sec,'hold_include_shoulders13','A型等待标志包含道肩',a['props'].get('hold_include_shoulders13',True),'bool')
                if a['props'].get('terminal_backup13'):ttk.Button(self.property_body,text='取消末端并恢复原延伸段',command=lambda:self.restore_terminal13(a['id'])).pack(fill='x',padx=8,pady=5)
            if a and a['props'].get('crossing_full13'):
                sec=self.section('全宽人行横道');self.property_field(sec,'crossing_skew13','偏斜角 °（可拖动旋转）',a['props'].get('crossing_skew13',0),'float')
        finally:self._inspector_busy=False
        self.reveal_inspector11()
    def junction_inspector(self,jid):
        super().junction_inspector(jid)
        from pavement_geometry import crossings
        j=next((j for j in crossings(self.scene) if j['id']==jid),None)
        if not j:return
        self._inspector_busy=True
        try:
            taxis=[aid for aid in j['assets'] if aid in self.scene.assets and self.scene.assets[aid]['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')]
            if taxis:
                choices={self.scene.assets[aid]['name']+' ['+aid[-4:]+']':aid for aid in taxis};self._terminal_choices13=choices
                sec=self.section('滑行道末端');self.property_field(sec,'_terminal_asset13','截断的滑行道',next(iter(choices)),'text',list(choices));self.property_field(sec,'_terminal_keep13','保留哪一段','START','radio',['START','END']);ttk.Button(self.property_body,text='将所选滑行道在此路口设为末端',command=lambda:self.terminal13(j)).pack(fill='x',padx=8,pady=5)
        finally:self._inspector_busy=False
    def detach_child13(self):
        from automatic_markings import detach_generated
        root=self.auto_assets[self.selection]['owner']
        with self.scene.transaction('分离并保留机位子对象'):
            aid=detach_generated(self.scene,self.selection);self.scene.assets[aid]['props']['stand_owner13']=root;self.scene.assets[aid]['container_id']=self.scene.assets[root]['props'].get('stand_group13',root)
        self.selection=aid;self._child13=True;self.refresh()
    def terminal13(self,j):
        aid=self._terminal_choices13[self.editor_vars['_terminal_asset13'][0].get()];keep=self.editor_vars['_terminal_keep13'][0].get();station=j['stations'][j['assets'].index(aid)]
        try:__import__('rules13').set_terminal(self.scene,aid,station,keep,jid=j['id']);self.select(aid);self.refresh()
        except ValueError as exc:self.status.set(str(exc))
    def restore_terminal13(self,aid):__import__('rules13').set_terminal(self.scene,aid,0,enabled=False);self.refresh()
    def open(self, filename=None):
        if not self.confirm_leave():return
        from user_settings34 import last_directory
        preferences=getattr(self,'_preferences34',None)
        directory=last_directory(preferences,'open') if preferences else ''
        p=filename or filedialog.askopenfilename(initialdir=directory,title='打开机场工程',filetypes=[('Airport Canvas Project','*.ACP *.acp'),('旧版工程 JSON','*.airport.json *.json'),('所有文件','*.*')])
        if not p:return
        try:
            activity = getattr(self,'opening_project',None)
            with activity(p) if activity else getattr(self,'processing',nullcontext)('正在读取机场工程'):
                scene = AirportScene.load(p)
                self.migrate13(scene)
                self.select(None)
                self.scene = scene
                self.filepath = Path(p)
                self.saved = json.dumps(self.scene.data,sort_keys=True)
                self.selection = None
                self.set_mode('SELECT')
                self.refresh()
                self.fit()
            self.status.set('已导入 '+Path(p).name)
        except (OSError,ValueError,TypeError,KeyError) as exc:messagebox.showerror('打开失败',str(exc),parent=self)
    def save(self,save_as=False):
        self.apply_properties()
        if getattr(self,'_dirty_fields',set()) & {'route_type','_connected_route_type39'}:
            self.status.set('请先修正滑行道类型设置，再保存工程。')
            return False
        p=self.filepath
        if save_as or p is None or p.suffix.lower()!='.acp':
            chosen=filedialog.asksaveasfilename(title='保存机场工程',defaultextension='.ACP',filetypes=[('Airport Canvas Project','*.ACP')],initialfile=acp_path(p).name if p else '新机场.ACP')
            if not chosen:return False
            p=acp_path(chosen)
        try:
            with getattr(self,'processing',nullcontext)('正在保存机场工程'):
                self.scene.save(p);self.filepath=Path(p);self.saved=json.dumps(self.scene.data,sort_keys=True);self.update_title();self.status.set('已保存 '+str(p));return True
        except (OSError,ValueError) as exc:messagebox.showerror('保存失败',str(exc),parent=self);return False
    def demo10(self):Editor13(AirportScene.load(Path(__file__).with_name('example_editor13.ACP')))
    def help(self):
        path=Path(__file__).with_name('USER_GUIDE.md');win=tk.Toplevel(self);win.title('功能与使用说明 · Editor13');win.geometry('900x720');text=tk.Text(win,wrap='word',font=('Microsoft YaHei UI',10));scroll=ttk.Scrollbar(win,command=text.yview);scroll.pack(side='right',fill='y');text.configure(yscrollcommand=scroll.set);text.pack(fill='both',expand=True);text.insert('1.0',path.read_text(encoding='utf8'));text.configure(state='disabled')

def main():Editor13(AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None).mainloop()
