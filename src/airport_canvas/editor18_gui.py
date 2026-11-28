"""Cheap pointer previews and logical numbering over immutable physical routes."""
import copy,math,sys
from pathlib import Path
import qt_compat as tk
from qt_compat import ttk
from editor17_gui import Editor17
from airport_scene import AirportScene
import scene_geometry as g
import segments18 as logical
from workflow18 import LogicalWorkflow

from export_modes21 import contours

class Editor18(Editor17):
    def __init__(self,scene=None):
        self._logical_station18=0.;self._hit_cache18=None;self._outline_cache18=None;self._logical_view18=None;self._active_piece18=None
        super().__init__(scene if scene is not None else AirportScene.load(Path(__file__).with_name('example_editor18.ACP')))
        self.route17=LogicalWorkflow()
    def update_title(self):super().update_title();self.title(self.title().replace('17.0','18.0'))
    def fast_hit18(self,q):
        from geometry11 import LineString,Point,STRtree
        key=(id(self.scene),self.scene.revision)
        if not self._hit_cache18 or self._hit_cache18[0]!=key:
            routes=list(logical.routes(self.scene).values());axes=[LineString(a['points']) for a in routes];self._hit_cache18=(key,routes,axes,STRtree(axes) if axes else None,max([a['props']['width']/2 for a in routes]+[1.]))
        _,routes,axes,tree,half=self._hit_cache18
        if tree is None:return None
        point=Point(q);tolerance=max(.25,12/max(.001,self.zoom));choices=[]
        for i in tree.query(point.buffer(max(half,tolerance))):
            i=int(i);d=axes[i].distance(point);a=routes[i]
            if self.can_edit_object(a['id']) and d<=max(tolerance,a['props']['width']/2):
                station=axes[i].project(point);p=axes[i].interpolate(station);choices.append((d,a['id'],station,[p.x,p.y]))
        return min(choices,key=lambda x:(x[0],x[1]!=self.selection)) if choices else None
    def draw_color18(self):
        from geometry11 import Point
        from route_workflow17 import visible_labels
        from segments16 import color_name
        from scene_render import rapid_f6_guides
        c=self.canvas;c.delete('color17');c.itemconfigure('map',state='hidden')
        if not getattr(getattr(self,'view_tools21_2',None),'active',False):
            self.draw_f6_buildings17()
        if not self.__dict__.get('_common_display_tool',False):
            for tag in ('overlay','frame11','semantic14','corner_handles12','cut_preview11','snap_cursor'):c.delete(tag)
            self._frame_box11=None;self._handles14=[]
        key=(id(self.scene),self.scene.revision)
        if not self._outline_cache18 or self._outline_cache18[0]!=key:self._outline_cache18=(key,contours(self.scene))
        for color,pts in self._outline_cache18[1]:c.create_line(*[v for q in pts for v in self.screen(q)],fill=color,width=1,tags='color17')
        if not self._logical_view18 or self._logical_view18[0]!=key:
            virtual={}
            guidance=__import__('guidance20').routes(self.scene)
            for aid,a in logical.routes(self.scene).items():
                if aid in self.scene.movements:continue
                if a['kind'] not in logical.TAXIS:continue
                L=g.length(a['points'])
                for p in logical.pieces(a):
                    visible=guidance.get(aid,a)['points'];lo=g.project(visible,g.at(a['points'],p['lo']*L)[0])[1];hi=g.project(visible,g.at(a['points'],p['hi']*L)[0])[1];oid=aid+':'+p['id'];virtual[oid]=dict(id=oid,kind=a['kind'],name=p['name'],points=g.subpath(visible,lo,hi),props=dict(designation=p['name']),asset=aid,part=p['id'])
            self._logical_view18=(key,virtual)
        virtual=self._logical_view18[1]
        palette={a['name']:color_name(a['name']) for a in virtual.values()}
        cache=getattr(self,'_rapid_f6_paths',None)
        if not cache or cache[0] is not self.render_items:
            cache=self._rapid_f6_paths=(self.render_items,rapid_f6_guides(self.render_items))
        for a in virtual.values():
            if a['asset'] in cache[1] or not self.can_edit_object(a['asset']):continue
            c.create_line(*[v for q in a['points'] for v in self.screen(q)],fill=palette[a['name']],
                          width=5 if (a['asset'],a['part'])==self._active_piece18 else 3,tags='color17')
        w,h=c.winfo_width(),c.winfo_height();xs,ys=zip(*(self.world(x,y) for x,y in ((0,0),(w,0),(w,h),(0,h))));box=(min(xs),min(ys),max(xs),max(ys))
        for oid,text,q in visible_labels(type('View',(),{'assets':{oid:a for oid,a in virtual.items() if self.can_edit_object(a['asset'])}})(),box):
            x,y=self.screen(q);width=max(36,len(text)*13+14);x=max(width/2+3,min(w-width/2-3,x));y=max(20,min(h-16,y-15));c.create_rectangle(x-width/2,y-11,x+width/2,y+11,fill='#21303e' if getattr(self,'_dark_mode24',False) else 'white',outline=palette[text],tags='color17');c.create_text(x,y,text=text,fill='#e5eff7' if getattr(self,'_dark_mode24',False) else '#173446',font=('Segoe UI',11,'bold'),tags='color17')
        self.draw_scale14()
    def redraw(self):
        if not hasattr(self,'canvas'):return
        if self._color17:
            if self.__dict__.get('_common_display_tool',False):
                super(Editor17,self).redraw()
            if hasattr(self,"grid_visible"):self.draw_grid7()
            self.draw_color18()
        else:super().redraw()
        if self.mode=='SPLIT7':self.draw_preview18()
        self.draw_view_badge18()
    def draw_view_badge18(self):
        # Screen-space UI only: never added to the model or export display list.
        c=self.canvas;c.delete('view_mode18')
        text='显示模式：彩色分段  ·  F6 切换' if self._color17 else '显示模式：普通机场图  ·  F6 切换'
        dark=getattr(self,'_dark_mode24',False)
        item=c.create_text(22,22,text=text,anchor='nw',fill='#d6e7f3' if dark else '#173446',font=('Microsoft YaHei',10,'bold'),tags='view_mode18')
        box=c.bbox(item)
        if box:
            bg=c.create_rectangle(box[0]-9,box[1]-6,box[2]+9,box[3]+6,fill='#202e3d' if dark else '#f7fafc',outline='#42566a' if dark else '#b6c5cf',tags='view_mode18')
            c.tag_lower(bg,item)
        c.tag_raise('view_mode18')
    def draw_preview18(self):
        c=self.canvas;c.delete('route_preview17');p=self.route17.pending
        if p and (p['revision']!=self.scene.revision or p['scene_id']!=id(self.scene)):self.route17.cancel();p=None
        hit=p or self._hover17
        if not hit or hit['aid'] not in logical.routes(self.scene):return
        a=logical.route(self.scene,hit['aid']);q,u=g.at(a['points'],hit['station']);v=[-u[1],u[0]];half=a['props']['width']/2+a['props'].get('shoulder',0)+3
        if hit.get('keep')!='DELETE':c.create_line(*self.screen([q[k]-v[k]*half for k in (0,1)]),*self.screen([q[k]+v[k]*half for k in (0,1)]),fill='#d52c7a',width=3 if p else 1,tags='route_preview17')
        if hit.get('action')=='TERMINAL':
            L=g.length(a['points']);lo,hi=(0,L) if hit['keep']=='DELETE' else (hit['station'],L) if hit['keep']=='START' else (0,hit['station']);pts=g.subpath(a['points'],lo,hi)
            if len(pts)>1:c.create_line(*[v for q in pts for v in self.screen(q)],fill='#d94444',width=4,dash=(7,4),tags='route_preview17')
    def pointer(self,e):
        if self.mode!='SPLIT7':return super().pointer(e)
        if self._pan11:return
        hit=self.fast_hit18(self.world(e.x,e.y));self._hover17=None
        if hit and not self.route17.pending and self.route17.action in ('SPLIT_KEEP','SPLIT_NEW','TERMINAL'):
            _,aid,s,q=hit;keep=self._route_inputs17.get('keep');self._hover17=dict(aid=aid,station=s,action=self.route17.action,keep=keep.get() if keep else 'START')
        # No airport redraw, no property reconstruction and no unions on motion.
        self.draw_preview18()
    def click(self,e):
        if self.mode=='SPLIT7' and not self._space11:
            hit=self.fast_hit18(self.world(e.x,e.y))
            if not hit:return
            _,aid,station,q=hit
            pending=self.route17.pending
            if pending and pending['aid']==aid and pending['action']==self.route17.action and self.route17.action.startswith('SPLIT') and abs(station-pending['station'])*self.zoom<=8:
                self.commit_route17();return
            old=self.selection;self.selection=aid;self._logical_station18=station;part=logical.piece_at(logical.route(self.scene,aid),station);active=(aid,part['id']);changed=self._active_piece18 is not None and active!=self._active_piece18;self._active_piece18=active
            if self.route17.action in ('SPLIT_KEEP','SPLIT_NEW','TERMINAL'):
                keep=self._route_inputs17.get('keep');keep=keep.get() if keep else 'START'
                try:self.route17.preview(self.scene,aid,station,keep)
                except ValueError as exc:self.status.set(str(exc));return
                if old==aid and not changed and self._route_inputs17:
                    self._route_inputs17['station'].set(f'{station:.6f}');self.draw_preview18();return
            if changed:self._route_draft17=None
            self.update_inspector();self.redraw();return
        if self.mode=='SELECT':
            hit=self.fast_hit18(self.world(e.x,e.y))
            if hit:self._logical_station18=hit[2];self._active_piece18=(hit[1],logical.piece_at(logical.route(self.scene,hit[1]),hit[2])['id'])
        return super().click(e)
    def route_inspector17(self):
        old=getattr(self,'_route_draft17',None);reuse=bool(old and old['aid']==self.selection and old['action']==self.route17.action)
        super().route_inspector17();a=logical.routes(self.scene).get(self.selection)
        if not a or a['kind'] not in logical.TAXIS:return
        part=logical.piece_at(a,self._logical_station18)
        self._active_piece18=(a['id'],part['id'])
        if not reuse:
            name=part['name']
            if self.route17.action=='SPLIT_NEW':
                used={p['name'] for route in logical.routes(self.scene).values() for p in logical.pieces(route)};n=1
                while name+'-'+str(n) in used:n+=1
                name=name+'-'+str(n)
            self._route_inputs17['name'].set(name)
        body=self.property_body.winfo_children()[0];ttk.Label(body,text='当前逻辑段：'+part['name']+'；道面对象保持完整',wraplength=260).pack(fill='x',pady=4)
    def commit_route17(self):
        try:
            if self.route17.action=='INDEPENDENT':__import__('branch_selection20_15').independent(self.scene,self.selection,self._logical_station18,self._route_inputs17['name'].get())
            elif self.route17.action=='NAME':logical.rename(self.scene,self.selection,self._logical_station18,self._route_inputs17['name'].get())
            else:
                p=self.route17.pending
                if not p or abs(float(self._route_inputs17['station'].get())-p['station'])>.0005:raise ValueError('请先左键点击或更新预览位置')
                station=p['station'];self.selection=self.route17.commit(self.scene,self._route_inputs17['name'].get());self._logical_station18=station+.01
                if p['action'].startswith('SPLIT'):self.status.set('已提交逻辑分段：'+str(len(logical.pieces(logical.route(self.scene,self.selection))))+' 段；实体几何保持不变。')
            self.selected_ids={self.selection} if self.selection else set();self._hover17=None;self._route_draft17=None;self.refresh()
        except (KeyError,ValueError) as exc:self.status.set(str(exc))
    def restore_terminal13(self,aid):logical.restore(self.scene,aid);self.route17.cancel();self._hover17=None;self.refresh()
    def split_selected(self):
        self.open_route_editor17('NAME')
    def split_from_field(self):self.split_selected()
    def delete_selected(self):
        a=logical.routes(self.scene).get(self.selection)
        if a and a['kind'] in logical.TAXIS and len(getattr(self,'selected_ids',set()))<=1:
            logical.delete_branch(self.scene,a['id']);self.selection=None;self.selected_ids=set();self.refresh();return
        return super().delete_selected()
    def merge_names11(self):
        if self.selection not in logical.routes(self.scene):return
        win=tk.Toplevel(self);win.title('合并逻辑段编号，不改变道面');win.geometry('520x520');body=ttk.Frame(win,padding=12);body.pack(fill='both',expand=True);name_var=tk.StringVar(value=logical.piece_at(logical.route(self.scene,self.selection),self._logical_station18)['name']);ttk.Entry(body,textvariable=name_var).pack(fill='x');canvas=tk.Canvas(body,highlightthickness=0);bar=ttk.Scrollbar(body,command=canvas.yview);bar.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=bar.set);frame=ttk.Frame(canvas);canvas.create_window(0,0,window=frame,anchor='nw');frame.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));choices={}
        primary=logical.piece_at(logical.route(self.scene,self.selection),self._logical_station18)
        for aid,a in logical.routes(self.scene).items():
            if a['kind'] not in logical.TAXIS:continue
            for p in logical.pieces(a):
                var=tk.BooleanVar(value=p['network']==primary['network'] or aid in self.selected_ids);choices[(aid,p['id'])]=var;ttk.Checkbutton(frame,text=f'{p["name"]}   {a["name"]}   {p["lo"]*g.length(a["points"]):.1f}–{p["hi"]*g.length(a["points"]):.1f}m',variable=var).pack(anchor='w',pady=3)
        def apply():
            try:logical.merge(self.scene,{key for key,var in choices.items() if var.get()},name_var.get());win.destroy();self.refresh()
            except ValueError as exc:self.status.set(str(exc))
        ttk.Button(body,text='确认合并编号',command=apply).pack(fill='x')
    def update_inspector(self):
        super().update_inspector()
        a=logical.routes(self.scene).get(self.selection)
        if a and a['kind']=='ROAD' and self.mode!='SPLIT7':
            self._inspector_busy=True
            try:self.property_field(self.section('交汇特殊边线延伸'),'_checker_extension18','保护范围外附加延伸 m',self.scene.data['meta'].get('road_checker_extension18',3.),'float')
            finally:self._inspector_busy=False
    def apply_properties(self):
        if not getattr(self,'_inspector_busy',False) and '_checker_extension18' in getattr(self,'_dirty_fields',set()):
            try:
                value=float(self.editor_vars['_checker_extension18'][0].get())
                if not math.isfinite(value) or value<0:raise ValueError('延伸长度须为非负数')
                with self.scene.transaction('设置交汇边线附加延伸'):self.scene.data['meta']['road_checker_extension18']=value
                self._dirty_fields.discard('_checker_extension18');self.schedule_frame()
            except ValueError as exc:self.status.set(str(exc));return
        return super().apply_properties()

def main():Editor18(AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None).mainloop()
