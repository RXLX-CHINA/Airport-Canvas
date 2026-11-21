"""Polyline authoring, editable fillets and unobtrusive CAD selection."""
import copy
import math
import qt_compat as tk
from qt_compat import ttk,colorchooser
from live_gui import LiveEditor
from curve_model import TAXI_KINDS,create_rounded,rebuild_rounded,snap,number_runway,runway_heading,editable_vertices
import scene_geometry as g
TAXI_KINDS=TAXI_KINDS+('ROAD',)

class CurveEditor(LiveEditor):
    def __init__(self,scene=None):
        self.vertex_index=0;self._vertex_drag=None;self._clipboard=None
        if scene is None:
            from pathlib import Path
            from airport_scene import AirportScene
            path=Path(__file__).with_name('example_curve.airport.json')
            if path.exists():scene=AirportScene.load(path)
        super().__init__(scene)
        for key,cmd in [('<Control-c>',self.copy_selected),('<Control-v>',self.paste_selected),('<Control-x>',self.cut_selected),('<Control-d>',self.duplicate_selected)]:
            self.bind(key,lambda e,f=cmd:self.shortcut(e,f))
        self.canvas.bind('<Double-Button-1>',self.double_click)
    def update_title(self):
        super().update_title();self.title(self.title().replace('4.0','5.0'))
    def _build(self):
        super()._build()
        bar=ttk.Frame(self.tree.master);bar.pack(fill='x',before=self.tree)
        for label,mode in [('节点编辑','NODES'),('打断编号','BREAK'),('掉头坪','TURN_PAD')]:ttk.Button(bar,text=label,command=lambda m=mode:self.set_mode(m)).pack(side='left')
    def set_mode(self,mode):
        self._vertex_drag=None
        super().set_mode(mode)
        if mode in TAXI_KINDS:self.status.set('连续点击折线顶点 · Enter 完成并生成圆角 · Esc 取消 · 自动吸附已有滑行道中线')
        elif mode=='NODES':self.status.set('选择滑行道后拖动蓝色顶点 · 双击折线插入顶点 · 右侧可修改半径、坐标或删除顶点')
        elif mode=='BREAK':self.status.set('点击滑行道中线打断编号；道面保持连续')
        elif mode=='TURN_PAD':self.status.set('在跑道靠近端部点击放置掉头坪；右侧可调整半径、长度和左右侧')
    def shortcut(self,event,cmd):
        if isinstance(event.widget,(tk.Entry,tk.Text,ttk.Entry,ttk.Combobox,ttk.Spinbox)):return
        cmd();return 'break'
    def copy_selected(self):
        oid=self.selection
        obj=self.scene.assets.get(oid) or self.auto_assets.get(oid)
        if not obj:self.status.set('请选择一个道面、滑行道或标注对象');return
        self._clipboard=copy.deepcopy(obj);self.status.set('已复制对象；Ctrl+V 粘贴，Ctrl+D 重复')
    def paste_selected(self):
        if not self._clipboard:return
        obj=copy.deepcopy(self._clipboard);pts=[[x+20,y-20] for x,y in obj['points']]
        with self.scene.transaction('粘贴对象'):
            props=obj['props'];props.pop('network_id',None);props.pop('network_group',None)
            aid=self.scene.create_asset(obj['kind'],obj['name']+' 副本',pts,**props)
            a=self.scene.assets[aid]
            if obj.get('design_vertices'):a['design_vertices']=[[x+20,y-20] for x,y in obj['design_vertices']]
            if obj.get('curve_nodes'):
                a['curve_nodes']=obj['curve_nodes']
                for n in a['curve_nodes']:
                    for key in ('p','incoming','outgoing'):n[key]=[n[key][0]+20,n[key][1]-20]
        self.selection=aid;self.refresh()
    def cut_selected(self):
        if self.selection in self.scene.assets or self.selection in self.auto_assets:self.copy_selected();self.delete_selected()
    def duplicate_selected(self):self.copy_selected();self.paste_selected()
    def click(self,e):
        p=self.world(e.x,e.y)
        if self.mode in TAXI_KINDS:
            hit=snap(self.scene,p,max(.02,12/self.zoom))
            self.points.append(hit[3] if hit else p);self.redraw();return
        if self.mode=='TURN_PAD':
            from turn_pad import create_turn_pad
            hits=[(g.project(a['points'],p)[0],aid,g.project(a['points'],p)[1]) for aid,a in self.scene.assets.items() if a['kind']=='RUNWAY']
            if not hits:self.status.set('请先绘制跑道');return
            d,aid,station=min(hits)
            if d>self.scene.assets[aid]['props']['width']+20:self.status.set('请点击跑道附近');return
            try:self.selection=create_turn_pad(self.scene,aid,station);self.mode='SELECT';self.refresh()
            except ValueError as exc:self.property_error.configure(text=str(exc))
            return
        if self.mode=='BREAK':
            hit=snap(self.scene,p,max(2,12/self.zoom))
            if hit:
                try:self.selection=self.scene.split_asset(hit[1],hit[2]);self.mode='NODES';self.refresh()
                except ValueError as exc:self.status.set(str(exc))
            return
        if self.mode=='NODES' and self.selection not in self.scene.assets:
            hit=snap(self.scene,p,max(3,12/self.zoom))
            if hit:self.vertex_index=0;self.select(hit[1])
            return
        if self.mode in ('SELECT','NODES') and self.selection in self.scene.assets:
            a=self.scene.assets[self.selection]
            if a['kind'] in TAXI_KINDS:
                vertices=editable_vertices(a)
                if vertices:
                    distance,i=min((g.distance(p,q),i) for i,q in enumerate(vertices))
                    if distance<10/self.zoom:
                        self.apply_properties();self.vertex_index=i
                        self._vertex_drag=dict(aid=a['id'],index=i,vertices=copy.deepcopy(vertices),data=copy.deepcopy(self.scene.data))
                        self.update_inspector();return
            if self.mode=='NODES':
                hit=snap(self.scene,p,max(3,12/self.zoom))
                if hit:self.vertex_index=0;self.select(hit[1])
                return
        super().click(e)
    def motion(self,e):
        if self._vertex_drag:
            drag=self._vertex_drag;vertices=copy.deepcopy(drag['vertices']);p=self.world(e.x,e.y)
            if drag['index'] in (0,len(vertices)-1):
                hit=snap(self.scene,p,max(.02,12/self.zoom),drag['aid']);p=hit[3] if hit else p
            vertices[drag['index']]=p
            try:
                from curve_model import rounded_nodes,evaluate
                a=self.scene.assets[drag['aid']]
                nodes,_=rounded_nodes(vertices,a['props'].get('corner_radius',25),a['props'].get('corner_radii'))
                drag['candidate']=vertices
                self.canvas.delete('vertex_preview39')
                self.canvas.create_line(*[v for q in evaluate(nodes) for v in self.screen(q)],
                                        fill='#00a1c3',width=2,tags='vertex_preview39')
            except ValueError as exc:self.status.set(str(exc))
            return
        super().motion(e)
    def release(self,e):
        if self._vertex_drag:
            drag=self._vertex_drag;self._vertex_drag=None
            self.canvas.delete('vertex_preview39')
            if 'candidate' in drag:
                try:
                    with self.scene.transaction('拖动曲线顶点'):
                        self.scene.assets[drag['aid']]['design_vertices']=drag['candidate']
                        rebuild_rounded(self.scene,drag['aid'])
                except ValueError as exc:self.status.set(str(exc))
            self.refresh();return
        super().release(e)
    def finish_draw(self):
        if self.mode in TAXI_KINDS:
            if len(self.points)<2:return
            try:
                self.selection=create_rounded(self.scene,self.mode,'T'+str(sum(a['kind'] in TAXI_KINDS for a in self.scene.assets.values())+1),self.points,tolerance=max(.02,12/self.zoom))
                self.points=[]
                if not self.repeat.get():self.mode='SELECT'
                self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        super().finish_draw()
    def double_click(self,e):
        if self.mode!='NODES' or self.selection not in self.scene.assets:return 'break'
        a=self.scene.assets[self.selection]
        if a['kind'] not in TAXI_KINDS:return 'break'
        vertices=copy.deepcopy(editable_vertices(a));p=self.world(e.x,e.y)
        d,index,q=min((g.project([x,y],p)[0],i,g.project([x,y],p)[2]) for i,(x,y) in enumerate(zip(vertices,vertices[1:])))
        if d<max(3,12/self.zoom):
            vertices.insert(index+1,q);self.vertex_index=index+1
            try:rebuild_rounded(self.scene,a['id'],vertices);self.refresh()
            except ValueError as exc:self.status.set(str(exc))
        return 'break'
    def remove_vertex(self):
        a=self.scene.assets.get(self.selection)
        if not a:return
        vertices=copy.deepcopy(editable_vertices(a))
        if len(vertices)<=2:self.status.set('至少保留两个顶点');return
        vertices.pop(min(self.vertex_index,len(vertices)-1));self.vertex_index=max(0,self.vertex_index-1)
        try:rebuild_rounded(self.scene,a['id'],vertices);self.refresh()
        except ValueError as exc:self.status.set(str(exc))
    def choose_color(self,key):
        a=self.scene.assets.get(self.selection) or self.auto_assets.get(self.selection)
        if not a:return
        color=colorchooser.askcolor(a['props'].get(key,'#737b83'),parent=self,title='选择颜色')[1]
        if color:self.editor_vars[key][0].set(color)
    def update_inspector(self):
        super().update_inspector();a=self.scene.assets.get(self.selection) or self.auto_assets.get(self.selection)
        if not a:return
        self._inspector_busy=True
        try:
            p=a['props'];section=self.section('颜色与标注')
            for key,label,default in [('pavement_color','道面颜色','#454b53' if a['kind']=='RUNWAY' else '#9199a1' if a['kind']=='APRON' else '#737b83'),('shoulder_color','道肩颜色','#c7cbd0')]:
                control=self.property_field(section,key,label,p.get(key,default),'text')
                from property_rows import field_container,next_row
                target=field_container(section,control);row=next_row(target)
                ttk.Button(target,text='选择'+label,command=lambda k=key:self.choose_color(k)).grid(row=row,column=0,columnspan=2,sticky='ew')
            if __import__('paint10').outline_group(self.scene,a['id'],a)=='safety':
                self.property_field(section,'white_outline','标注描白边',p.get('white_outline',p.get('building_role19')!='BRIDGE' and not self.scene.data['meta'].get('hide_safety_outline21_2')),'bool')
            if a['kind']=='STAND':
                default=self.scene.data['meta'].get('outline_group_defaults',{}).get('stand',False)
                self.property_field(section,'stand_black_outline','机位标记描黑边',p.get('stand_black_outline',default),'bool')
            self.property_field(section,'black_outline','标注描黑边',p.get('black_outline',False),'bool')
            if a['kind'] in TAXI_KINDS:
                vertices=editable_vertices(a);self.vertex_index=min(self.vertex_index,len(vertices)-1)
                section=self.section('折线顶点与圆角')
                self.property_field(section,'corner_radius','统一圆角半径 m',p.get('corner_radius',25))
                self.property_field(section,'_vertex','当前顶点',str(self.vertex_index+1),'text',[str(i+1) for i in range(len(vertices))])
                v=vertices[self.vertex_index]
                self.property_field(section,'_vx','顶点 X / m',round(v[0],4));self.property_field(section,'_vy','顶点 Y / m',round(v[1],4))
                self.property_field(section,'_radius','此点半径 m',p.get('corner_radii',{}).get(str(self.vertex_index),p.get('corner_radius',25)))
                ttk.Button(self.property_body,text='删除当前顶点',command=self.remove_vertex).pack(fill='x',padx=8,pady=4)
                effective=p.get('effective_radii',{});text='短线段会限制可用半径。'
                if effective:text+=' 实际圆角：'+', '.join(f'{int(k)+1}点 {r:.2f}m' for k,r in effective.items())
                ttk.Label(self.property_body,text=text,wraplength=250,padding=8).pack(fill='x')
            if a['kind']=='STAND':
                section=self.section('机位引入线与机型包络')
                self.property_field(section,'lead_type','引入线类型',p.get('lead_type','A'),'radio',list('ABCD'))
                for key,label,default in [('lead_radius','引入转弯半径 m',20),('aircraft_length','飞机长度 m',40),('aircraft_span','飞机翼展 m',36),('fuselage_width','机身宽度 m',4),('wing_station','机翼距机头 m',18),('safety_clearance','包络净距 m',4.5)]:self.property_field(section,key,label,p.get(key,default))
            if a['kind']=='RUNWAY':
                section=self.section('磁航向与自动编号')
                self.property_field(section,'auto_number','自动编号',p.get('auto_number',False),'bool')
                self.property_field(section,'runway_suffix','平行跑道后缀',p.get('runway_suffix',''),'text',['','L','C','R'])
                self.property_field(section,'_north','网格北真方位 °',self.scene.data['meta'].get('grid_north_true_heading',0))
                self.property_field(section,'_decl','磁偏角 °（东正西负）',self.scene.data['meta'].get('magnetic_declination'),'text')
                heading,_,_,known=runway_heading(self.scene,a)
                self._magnetic_label=ttk.Label(self.property_body,text=f'磁航向 {heading:.2f}°' if known else '磁偏角未设置：编号为暂定值。请填写机场设计日期对应磁偏角。',wraplength=250,padding=8);self._magnetic_label.pack(fill='x')
            if p.get('turn_pad'):
                section=self.section('掉头坪 · 4.3 / 6.2.9')
                for key,label in [('pad_radius','转弯半径 m'),('pad_straight','转弯前直线 m'),('pad_margin','道面余量 m')]:self.property_field(section,key,label,p[key])
                # Side is exposed by Editor10 as an explicit left/right choice.
                ttk.Label(self.property_body,text='需按最大机型复核机轮轨迹、鼻轮转角与边缘净距。',wraplength=250,padding=8).pack(fill='x')
        finally:self._inspector_busy=False
    def apply_properties(self):
        if self._inspector_busy:return
        special=self._dirty_fields & {'_vertex','_vx','_vy','_radius','corner_radius','_north','_decl','pad_radius','pad_straight','pad_margin','pad_side'}
        if not special:
            result=super().apply_properties()
            self.sync_runway_form()
            return result
        a=self.scene.assets.get(self.selection) or self.auto_assets.get(self.selection)
        if not a:return
        try:
            if '_vertex' in special:
                self._dirty_fields.remove('_vertex');self.vertex_index=int(self.editor_vars['_vertex'][0].get())-1
                super().apply_properties();self.update_inspector();self.redraw();return
            with self.scene.transaction('修改圆角或坐标基准'):
                if special & {'_north','_decl'}:
                    meta=self.scene.data['meta'];north=float(self.editor_vars['_north'][0].get());value=self.editor_vars['_decl'][0].get().strip()
                    decl=None if value in ('','None') else float(value)
                    if not math.isfinite(north):raise ValueError('北向必须为有限数值')
                    meta.update(grid_north_true_heading=north,magnetic_declination=decl)
                    for aid,obj in self.scene.assets.items():
                        if obj['kind']=='RUNWAY' and obj['props'].get('auto_number'):number_runway(self.scene,aid)
                if a['kind'] in TAXI_KINDS:
                    vertices=copy.deepcopy(editable_vertices(a));p=a['props'];radii=copy.deepcopy(p.get('corner_radii',{}))
                    if special & {'_vx','_vy'}:vertices[self.vertex_index]=[float(self.editor_vars[k][0].get()) for k in ('_vx','_vy')]
                    radius=float(self.editor_vars['corner_radius'][0].get())
                    if '_radius' in special:radii[str(self.vertex_index)]=float(self.editor_vars['_radius'][0].get())
                    if 'corner_radius' in special:radii={}
                    rebuild_rounded(self.scene,a['id'],vertices,radius,radii)
                if a['props'].get('turn_pad'):
                    from turn_pad import update_turn_pad
                    values={k:float(self.editor_vars[k][0].get()) for k in special if k.startswith('pad_')}
                    update_turn_pad(self.scene,a['id'],values)
            self._dirty_fields.difference_update(special);super().apply_properties();self.sync_runway_form();self.property_error.configure(text='');self.schedule_frame();self.schedule_audit();self.redraw()
        except (ValueError,TypeError,KeyError) as exc:self.property_error.configure(text='未应用：'+str(exc))
    def sync_runway_form(self):
        a=self.scene.assets.get(self.selection)
        if not a or a['kind']!='RUNWAY':return
        busy=self._inspector_busy;self._inspector_busy=True
        try:
            for key in ('label_a','label_b','auto_number'):
                if key in self.editor_vars and key not in self._dirty_fields:self.editor_vars[key][0].set(a['props'].get(key,False if key=='auto_number' else ''))
            heading,_,_,known=runway_heading(self.scene,a);label=getattr(self,'_magnetic_label',None)
            if label is not None and label.winfo_exists():label.configure(text=f'磁航向 {heading:.2f}°' if known else '磁偏角未设置：编号为暂定值。')
        finally:self._inspector_busy=busy
    def redraw(self):
        super().redraw()
        if not hasattr(self,'canvas'):return
        a=self.scene.assets.get(self.selection)
        if not a:return
        c=self.canvas;pts=[self.screen(p) for p in a['points']]
        # An outer halo leaves the centre and pavement readable; no opaque fill.
        if len(pts)>1:
            line=c.create_line(*[v for p in pts for v in p],fill='#16bdd2',width=5,stipple='gray25',tags=('overlay','selection_halo'))
            c.tag_lower(line,'overlay')
        if a['kind'] in TAXI_KINDS:
            # Hide sampled-curve boxes; only original design vertices are handles.
            for item in c.find_withtag('overlay'):
                if c.type(item)=='rectangle':c.delete(item)
            vertices=editable_vertices(a);screen=[self.screen(p) for p in vertices]
            if len(screen)>1:c.create_line(*[v for p in screen for v in p],fill='#0093b0',dash=(3,5),width=1,tags='overlay')
            for i,(x,y) in enumerate(screen):
                c.create_oval(x-5,y-5,x+5,y+5,fill='#08a8c7' if i==self.vertex_index else 'white',outline='#007d9a',width=2,tags='overlay')
                if self.mode=='NODES':c.create_text(x+9,y-10,text=str(i+1),fill='#006b85',tags='overlay')
        for item in self.render_items:
            if item['oid']==a['id'] and item['type']=='polygon' and item.get('fill'):
                polygon=[self.screen(p) for p in item['points']]
                c.create_polygon(*[v for p in polygon for v in p],fill='',outline='#0098b6',width=2,dash=(5,4),tags=('overlay','selection_extent'))

def main():
    import sys
    from airport_scene import AirportScene
    scene=AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None
    CurveEditor(scene).mainloop()
