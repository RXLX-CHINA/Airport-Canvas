"""Airport canvas: selection sets, real cursor snaps and sparse cubic handles."""
import copy
import math
import qt_compat as tk
from qt_compat import ttk
from PIL import Image,ImageDraw,ImageFont
from qt_canvas21 import ImageTk
from curve_gui import CurveEditor
from curve_model import TAXI_KINDS,snap
from junction_routes import branches
from editor6_geometry import stop_rows,add_stop
from marking_catalog import CATALOG
from legacy_gui import NAMES
import scene_geometry as g

class Editor6(CurveEditor):
    def __init__(self,scene=None):
        self.selected_ids=set();self._box=None;self._control_drag=None;self._batch_drag=None;self._stop_drag=None;self._branch='MAIN';self._snap_hit=None;self._stop_id=None
        if scene is None:
            from airport_scene import AirportScene
            from pathlib import Path
            path=Path(__file__).with_name('example_editor6.airport.json')
            if path.exists():scene=AirportScene.load(path)
        super().__init__(scene)
        self.canvas.bind('<Button-3>',self.cancel_action);self.canvas.unbind('<B3-Motion>')
    def update_title(self):
        super().update_title();self.title(self.title().replace('5.0','6.0'))
    def _build(self):
        super()._build()
        bar=ttk.Frame(self.tree.master);bar.pack(fill='x',before=self.tree)
        for label,mode in [('框选','BOX_SELECT'),('中间等待点','MARK:INTERMEDIATE_POINT'),('B型等待','MARK:HOLD_B'),('停止道','STOPWAY')]:ttk.Button(bar,text=label,command=lambda m=mode:self.set_mode(m)).pack(side='left')
        self.outline_all=tk.BooleanVar(value=self.scene.data['meta'].get('guidance_black_outline',False))
        ttk.Checkbutton(bar,text='全部引导线黑边',variable=self.outline_all,command=self.set_global_outline).pack(side='left')
    def set_global_outline(self):
        with self.scene.transaction('全部引导线描边'):self.scene.data['meta']['guidance_black_outline']=bool(self.outline_all.get())
        self.refresh()
    def tool_icon(self,key):
        # A visible unique key badge prevents visually identical tools being confused.
        photo=super().tool_icon(key)
        image=ImageTk.getimage(photo).convert('RGB');draw=ImageDraw.Draw(image)
        keys=list(CATALOG);code=f'{keys.index(key[5:])+1:02d}' if key.startswith('MARK:') else key[:3]
        draw.rectangle((0,28,26,39),fill='#15394d');draw.text((2,28),code,fill='white')
        return ImageTk.PhotoImage(image,master=self)
    def cancel_action(self,e=None):
        self._vertex_drag=None
        self._control_drag=None
        self._batch_drag=None
        self._stop_drag=None
        self._drag_data=None
        for tag in ('vertex_preview39','drag_preview39','asset_preview39'):
            self.canvas.delete(tag)
        self.drag=None;self._box=None;self._snap_hit=None;self.points=[];self.connect_ports=[]
        self.set_mode('SELECT');self.schedule_frame();self.status.set('已取消当前操作；中键拖动画布');return 'break'
    def pointer(self,e):
        super().pointer(e);self.canvas.delete('snap_cursor');self._snap_hit=None
        if self.mode not in TAXI_KINDS and self.mode not in ('NODES','CONNECT','MARK:INTERMEDIATE_POINT','MARK:HOLD_B'):return
        p=self.world(e.x,e.y);self._snap_hit=snap(self.scene,p,max(.02,12/self.zoom))
        if self._snap_hit:
            x,y=self.screen(self._snap_hit[3]);c=self.canvas
            c.create_oval(x-7,y-7,x+7,y+7,outline='#ec4b7c',width=2,tags='snap_cursor')
            c.create_line(x-11,y,x+11,y,fill='#ec4b7c',tags='snap_cursor');c.create_line(x,y-11,x,y+11,fill='#ec4b7c',tags='snap_cursor')
            c.create_text(x+10,y-13,text='吸附中线',anchor='w',fill='#b02758',tags='snap_cursor')
            if self.points:
                self.canvas.delete('cursor_preview');a=self.screen(self.points[-1]);c.create_line(*a,x,y,fill='#ec4b7c',dash=(4,3),tags='cursor_preview')
    def select(self,oid):
        if not getattr(self,'_preserve_set',False):self.selected_ids={oid} if oid else set()
        super().select(oid)
    def pick(self,p,paths_only=False):
        if not paths_only:
            from marking_catalog import primitives
            candidates=[]
            for aid,a in getattr(self,'auto_assets',{}).items():
                if a['props']['mark_type'] not in ('STAND_STOP','UNGUIDED_STOP'):continue
                for item in primitives(a):
                    if item['type']=='line':
                        d,s,q=g.project(item['points'],p)
                        if d<max(6/self.zoom,item.get('width',.15)/2):candidates.append((d,aid,s,q))
            if candidates:return min(candidates,key=lambda x:x[0])
        return super().pick(p,paths_only)
    def control_geometry(self):
        if self.selection not in self.scene.movements:return None
        m=self.scene.movements[self.selection]
        if m.get('geometry')=='STRAIGHT' and self._branch=='MAIN':
            path=self.scene.movement_path(m['id']);return path[0],path[-1],[]
        if self._branch!='MAIN':
            b=next((b for b in branches(self.scene,m) if b['side']==self._branch),None)
            return (b['points'][0],b['points'][-1],b['controls']) if b else None
        path=self.scene.movement_path(m['id']);start,end=path[0],path[-1];controls=m.get('bezier_controls')
        if not controls:
            controls=[]
            for field,point,sign in (('from',start,1),('to',end,-1)):
                port=m[field];_,u=g.at(self.scene.assets[port['asset']]['points'],port['station']);controls.append([point[k]+u[k]*port['direction']*m['handle']*sign for k in (0,1)])
        return start,end,controls
    def click(self,e):
        p=self.world(e.x,e.y)
        if self.mode=='BOX_SELECT':self._box=dict(start=(e.x,e.y),end=(e.x,e.y),add=bool(getattr(e,'state',0)&1));return
        if self.mode in ('SELECT','NODES'):
            geometry=self.control_geometry()
            if geometry:
                for i,q in enumerate(geometry[2]):
                    if g.distance(p,q)<10/self.zoom:
                        self._control_drag=dict(index=i,data=copy.deepcopy(self.scene.data));return
            candidates=[]
            for mid,m in self.scene.movements.items():
                for b in branches(self.scene,m):
                    d,_,_=g.project(b['points'],p)
                    if d<max(10/self.zoom,m['width']/2):candidates.append((d,mid,b['side']))
            picked=self.pick(p)
            if self.mode=='SELECT' and picked and picked[1] in self.auto_assets:
                mark=self.auto_assets[picked[1]]
                if mark['props']['mark_type'] in ('STAND_STOP','UNGUIDED_STOP'):
                    self.select(picked[1]);self._stop_drag=dict(data=copy.deepcopy(self.scene.data),start=p,owner=mark['owner'],row=picked[1].split(':STOP:')[-1] if ':STOP:' in picked[1] else 'default');return
            if self.mode=='SELECT' and len(self.selected_ids)>1 and picked and picked[1] in self.selected_ids and not getattr(e,'state',0)&4:
                self._batch_drag=dict(data=copy.deepcopy(self.scene.data),start=p);return
            if candidates and (not picked or min(candidates)[0]<picked[0]):
                _,mid,side=min(candidates);self._branch=side;self.select(mid);self.update_inspector();return
            if getattr(e,'state',0)&4 and picked:
                oid=picked[1]
                if oid in self.selected_ids:self.selected_ids.remove(oid)
                else:self.selected_ids.add(oid)
                self.redraw();return
            if self.mode=='SELECT' and not picked:
                self._box=dict(start=(e.x,e.y),end=(e.x,e.y),add=bool(getattr(e,'state',0)&1));self.drag=None;return
        if self.mode=='STOPWAY':
            self.points.append(p)
            if len(self.points)==2:
                self.selection=self.scene.create_asset('APRON','停止道',g.rectangle(self.points,45),surface_role='STOPWAY',pavement_color='#655e50');self.points=[];self.set_mode('SELECT');self.refresh()
            return
        if self.mode in ('MARK:INTERMEDIATE_POINT','MARK:HOLD_B'):
            hit=snap(self.scene,p,max(10/self.zoom,15))
            if hit:
                a=self.scene.assets[hit[1]];q,u=g.at(a['points'],hit[2]);self.selection=self.scene.create_marking(self.mode[5:],[q,[q[k]+u[k]*10 for k in (0,1)]],width=a['props']['width'],black_outline=self.scene.data['meta'].get('guidance_black_outline',False));self.set_mode('SELECT');self.refresh();return
        super().click(e)
    def drag_preview39(self,paths):
        self.canvas.delete('drag_preview39')
        for points in paths:
            if len(points)<2:continue
            self.canvas.create_line(*[v for q in points for v in self.screen(q)],
                                    fill='#00a1c3',width=2,tags='drag_preview39')

    def motion(self,e):
        if self._stop_drag:
            d=self._stop_drag
            a=self.scene.assets[d['owner']]
            rows=copy.deepcopy(stop_rows(a))
            row=next(r for r in rows if r['id']==d['row'])
            q=self.world(e.x,e.y)
            delta=[q[k]-d['start'][k] for k in (0,1)]
            u=g.unit(a['points'][0],a['points'][-1]);v=[-u[1],u[0]]
            row['offset']=row.get('offset',0)+sum(delta[k]*u[k] for k in (0,1))
            row['lateral']=row.get('lateral',0)+sum(delta[k]*v[k] for k in (0,1))
            d['candidate']=rows
            self.drag_preview39([[[q[k]+sign*v[k]*2 for k in (0,1)] for sign in (-1,1)]])
            return
        if self._box:
            self._box['end']=(e.x,e.y);self.redraw();return
        if self._batch_drag:
            d=self._batch_drag
            p=self.world(e.x,e.y)
            dx,dy=p[0]-d['start'][0],p[1]-d['start'][1]
            d['candidate']=(dx,dy)
            self.drag_preview39([[[x+dx,y+dy] for x,y in self.scene.assets[aid]['points']]
                                 for aid in self.selected_ids if aid in self.scene.assets])
            return
        if self._control_drag:
            from connection9 import path_with_controls
            drag=self._control_drag
            start,end,controls=self.control_geometry()
            controls=copy.deepcopy(controls)
            controls[drag['index']]=self.world(e.x,e.y)
            drag['candidate']=controls
            self.drag_preview39([path_with_controls(start,end,controls)])
            return
        super().motion(e)

    def release(self,e):
        if self._stop_drag:
            d=self._stop_drag;self._stop_drag=None
            self.canvas.delete('drag_preview39')
            if 'candidate' in d:
                with self.scene.transaction('拖动机位停止线'):
                    self.scene.assets[d['owner']]['props']['stops']=d['candidate']
            self.refresh();return
        if self._batch_drag:
            from editor6_geometry import translate_selection
            d=self._batch_drag;self._batch_drag=None
            self.canvas.delete('drag_preview39')
            if 'candidate' in d:
                with self.scene.transaction('移动多选对象'):
                    translate_selection(self.scene,self.selected_ids,*d['candidate'])
            self.refresh();return
        if self._box:
            box=self._box;self._box=None;x0,x1=sorted((box['start'][0],e.x));y0,y1=sorted((box['start'][1],e.y))
            if not box['add']:self.selected_ids=set()
            for aid,a in self.scene.assets.items():
                points=[self.screen(p) for p in a['points']]
                if any(x0<=x<=x1 and y0<=y<=y1 for x,y in points) or any(g.segment_box_interval(p,q,(x0,y0,x1,y1)) for p,q in zip(points,points[1:])):self.selected_ids.add(aid)
            for mid in self.scene.movements:
                pts=[self.screen(p) for p in self.scene.movement_path(mid)]
                if any(x0<=x<=x1 and y0<=y<=y1 for x,y in pts):self.selected_ids.add(mid)
            self._preserve_set=True
            try:super().select(next(iter(self.selected_ids),None))
            finally:self._preserve_set=False
            self.mode='SELECT';self.highlight_tool()
            self.status.set(f'已框选 {len(self.selected_ids)} 个对象；Ctrl 点击增减选择');self.redraw();return
        if self._control_drag:
            drag=self._control_drag;self._control_drag=None
            self.canvas.delete('drag_preview39')
            if 'candidate' in drag:
                with self.scene.transaction('拖动连接控制点'):
                    m=self.scene.movements[self.selection]
                    controls=drag['candidate']
                    if self._branch=='MAIN':
                        m.setdefault('automatic_geometry',m.get('geometry','AUTO'))
                        m.update(bezier_controls=controls,geometry='BEZIER')
                    else:m.setdefault('branch_controls',{})[self._branch]=controls
            self.refresh();return
        super().release(e)
    def copy_selected(self):
        if len(self.selected_ids)>1:
            self._multi_clipboard=(copy.deepcopy(self.scene.data),set(self.selected_ids));self.status.set(f'已复制 {len(self.selected_ids)} 个对象');return
        self._multi_clipboard=None;super().copy_selected()
    def paste_selected(self):
        if getattr(self,'_multi_clipboard',None):
            from editor6_geometry import clone_selection
            data,ids=self._multi_clipboard;self.selected_ids=clone_selection(self.scene,data,ids);self.selection=next(iter(self.selected_ids),None);self.refresh();return
        super().paste_selected()
    def delete_selected(self):
        if len(self.selected_ids)<=1:return super().delete_selected()
        with self.scene.transaction('删除框选对象'):
            for oid in list(self.selected_ids):
                if oid in self.scene.assets or oid in self.scene.movements:self.scene.delete(oid)
        self.selected_ids=set();self.selection=None;self.refresh()
    def update_inspector(self):
        super().update_inspector();oid=self.selection;a=self.scene.assets.get(oid)
        self._inspector_busy=True
        try:
            if oid in self.scene.movements:
                m=self.scene.movements[oid];section=self.section('连接曲线 · 控制点')
                choices=['MAIN']+[b['side'] for b in branches(self.scene,m)]
                if self._branch not in choices:self._branch='MAIN'
                self.property_field(section,'_branch','编辑哪条分支',self._branch,'text',choices)
                self.property_field(section,'black_outline','引导线描黑边',m.get('black_outline',self.scene.data['meta'].get('guidance_black_outline',False)),'bool')
                geometry=self.control_geometry()
                if geometry:
                    for i,p in enumerate(geometry[2]):
                        for k,key in enumerate(('x','y')):self.property_field(section,f'_c{i}{key}',f'控制点{i+1} {key.upper()}',round(p[k],3))
                ttk.Button(self.property_body,text='恢复自动连接曲线',command=self.reset_controls).pack(fill='x',padx=8,pady=5)
            if a and a['kind'] in TAXI_KINDS:
                section=self.section('道肩弯道条带');self.property_field(section,'auto_shoulder_bars','弯道自动生成',a['props'].get('auto_shoulder_bars',True),'bool')
            if a and a['kind']=='STAND':
                rows=stop_rows(a);self._stop_id=self._stop_id if any(r['id']==self._stop_id for r in rows) else rows[0]['id'] if rows else None
                section=self.section('机位停止线列表 · 按机型分别编码')
                self._stop_choices={r.get('name','')+' · '+r.get('aircraft','')+' ['+r['id']+']':r['id'] for r in rows}
                value=next((label for label,key in self._stop_choices.items() if key==self._stop_id),'')
                self.property_field(section,'_stop','当前停止线',value,'text',list(self._stop_choices))
                row=next((r for r in rows if r['id']==self._stop_id),None)
                if row:
                    for key,label,kind,default in [('name','编码','text','1'),('aircraft','停放机型列表','text','A320'),('offset','纵向偏移 m','float',0),('lateral','横向偏移 m','float',0),('rotation','旋转 °','float',0),('length','停止线长度 m','float',2),('width','线宽 m','float',.15),('visible','显示此线','bool',True)]:self.property_field(section,'_s_'+key,label,row.get(key,default),kind)
                    self.property_field(section,'_s_shape','图形（编辑器选项）',row.get('shape','T'),'text',['T','CROSS','BAR','UNGUIDED'])
                buttons=ttk.Frame(self.property_body);buttons.pack(fill='x',padx=8,pady=5)
                ttk.Button(buttons,text='增加停止线',command=self.new_stop).pack(side='left');ttk.Button(buttons,text='删除此线',command=self.delete_stop).pack(side='left')
            if a and a['kind']=='MARKING' and a['props']['mark_type'] in ('STAND_STOP','UNGUIDED_STOP'):
                section=self.section('关联停机位');self._stand_choices={v['name']+' ['+key+']':key for key,v in self.scene.assets.items() if v['kind']=='STAND'}
                self.property_field(section,'_stand','停机位列表',next((s for s,k in self._stand_choices.items() if k==a['props'].get('stand_id')),''),'text',list(self._stand_choices))
        finally:self._inspector_busy=False
    def new_stop(self):self._stop_id=add_stop(self.scene,self.selection);self.refresh()
    def delete_stop(self):
        with self.scene.transaction('删除停止线'):
            a=self.scene.assets[self.selection];a['props']['stops']=[copy.deepcopy(r) for r in stop_rows(a) if r['id']!=self._stop_id]
        self._stop_id=None;self.refresh()
    def reset_controls(self):
        with self.scene.transaction('恢复自动曲线'):
            m=self.scene.movements[self.selection]
            if self._branch=='MAIN':m.pop('bezier_controls',None);m['geometry']=m.pop('automatic_geometry','BEZIER')
            else:m.get('branch_controls',{}).pop(self._branch,None)
        self.refresh()
    def apply_properties(self):
        if self._inspector_busy:return
        dirty=set(self._dirty_fields);custom={k for k in dirty if k in ('_branch','_stop','_stand') or k.startswith('_s_') or k.startswith('_c') and len(k)==4}
        if not custom:return super().apply_properties()
        try:
            if '_branch' in custom:self._branch=self.editor_vars['_branch'][0].get()
            if '_stop' in custom:self._stop_id=self._stop_choices[self.editor_vars['_stop'][0].get()]
            with self.scene.transaction('修改停止线或曲线控制点'):
                if any(k.startswith('_s_') for k in custom):
                    a=self.scene.assets[self.selection];rows=copy.deepcopy(stop_rows(a));row=next(r for r in rows if r['id']==self._stop_id)
                    for key in custom:
                        if key.startswith('_s_'):
                            var,kind=self.editor_vars[key];row[key[3:]]=float(var.get()) if kind=='float' else var.get()
                    if '_s_shape' in custom and row.get('shape')=='UNGUIDED' and row.get('length',2)<6:
                        row['length']=6.;self._inspector_busy=True
                        try:self.editor_vars['_s_length'][0].set('6')
                        finally:self._inspector_busy=False
                    a['props']['stops']=rows
                if any(k.startswith('_c') and len(k)==4 for k in custom):
                    m=self.scene.movements[self.selection];controls=[[float(self.editor_vars[f'_c{i}{k}'][0].get()) for k in ('x','y')] for i in (0,1)]
                    if self._branch=='MAIN':m.setdefault('automatic_geometry',m.get('geometry','AUTO'));m.update(bezier_controls=controls,geometry='BEZIER')
                    else:m.setdefault('branch_controls',{})[self._branch]=controls
                if '_stand' in custom:
                    aid=self._stand_choices[self.editor_vars['_stand'][0].get()];stand=self.scene.assets[aid];q=stand['points'][-1];u=g.unit(stand['points'][0],q)
                    self.scene.update_asset(self.selection,points=[q,[q[k]+u[k]*10 for k in (0,1)]],props={'stand_id':aid})
            self._dirty_fields.difference_update(custom);super().apply_properties();self.schedule_frame();self.schedule_audit();self.redraw();self.property_error.configure(text='')
            if custom&{'_branch','_stop'}:self.update_inspector()
        except (ValueError,KeyError,StopIteration) as exc:self.property_error.configure(text='未应用：'+str(exc))
    def redraw(self):
        super().redraw()
        if not hasattr(self,'canvas'):return
        c=self.canvas
        if self._box:
            c.create_rectangle(*self._box['start'],*self._box['end'],outline='#018eaf',dash=(5,3),width=2,tags='overlay')
        for oid in self.selected_ids-{self.selection}:
            a=self.scene.assets.get(oid);points=a['points'] if a else self.scene.movement_path(oid) if oid in self.scene.movements else []
            if len(points)>1:c.create_line(*[v for p in points for v in self.screen(p)],fill='#00a4c4',width=3,dash=(5,3),tags='overlay')
        geometry=self.control_geometry()
        if geometry:
            start,end,controls=geometry
            for p,q in zip((start,end),controls):
                x,y=self.screen(q);c.create_line(*self.screen(p),x,y,fill='#be548f',dash=(4,3),tags='overlay');c.create_rectangle(x-5,y-5,x+5,y+5,fill='#ffdbef',outline='#a83b79',width=2,tags='overlay')

def main():
    import sys
    from airport_scene import AirportScene
    scene=AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None
    Editor6(scene).mainloop()
