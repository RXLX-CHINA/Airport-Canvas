"""Viewport navigation and associative airport editing."""
from interface_language import tr
import copy
import math
import qt_compat as tk
from qt_compat import ttk
from editor6_gui import Editor6
from editor7_model import *
from marking_catalog import CATALOG,primitives
from automatic_markings import generated_markings
from curve_model import set_nodes
from pavement_geometry import crossings,turn_guides
from junction_routes import branches

class Editor7(Editor6):
    def __init__(self,scene=None):
        self._anchor_drag=None;self._guide_drag=None;self._guide_nodes={};self._nav_key=None;self._connect_preview=None;self._mark_anchor=None
        if scene is None:
            from pathlib import Path
            from airport_scene import AirportScene
            path=Path(__file__).with_name('example_editor7.airport.json')
            if path.exists():scene=AirportScene.load(path)
        super().__init__(scene)
        self.grid_visible.set(True);self.redraw()
    def update_title(self):
        super().update_title();self.title(self.title().replace('6.0','7.0'))
    def _build(self):
        super()._build();bar=ttk.Frame(self.tree.master);bar.pack(fill='x',before=self.tree)
        for label,mode in [('滑行道分段','SPLIT7'),('单独编辑引导线','EDIT_GUIDE'),('连接并预览','CONNECT')]:ttk.Button(bar,text=label,command=lambda m=mode:self.set_mode(m)).pack(side='left')
        self.preview_enabled=tk.BooleanVar(value=True);ttk.Checkbutton(bar,text='连接预览',variable=self.preview_enabled).pack(side='left')
        self.minimap=tk.Canvas(self.canvas,width=190,height=130,bg='#eef4f7',highlightthickness=1,highlightbackground='#718c9c')
        self.minimap.place(relx=1,rely=1,x=-12,y=-12,anchor='se');self.minimap.bind('<Button-1>',self.navigate);self.minimap.bind('<B1-Motion>',self.navigate)
    def refresh(self):
        super().refresh()
        if hasattr(self,'outline_all'):self.outline_all.set(self.scene.data['meta'].get('guidance_black_outline',False))
    def set_mode(self,mode):
        drag=self._anchor_drag or self._guide_drag
        if drag:
            self.scene.data=drag['data'];self.scene.revision+=1;self._anchor_drag=None;self._guide_drag=None;self._guide_nodes={}
        self._connect_preview=None;self._mark_anchor=None
        super().set_mode(mode)
        if mode=='SPLIT7':self.status.set('点击滑行道中线分段，保持原编号；右侧也可输入分段站位')
        elif mode=='EDIT_GUIDE':self.status.set('点击生成的引导线，单独修改控制柄和端点；原始采样点不作为手柄')
        elif mode=='CONNECT':self.status.set('先点起始中线，再移动到目标中线预览；第二次点击创建，右键取消')
    def pointer(self,e):
        super().pointer(e)
        if self.mode in ('CONNECT','SPLIT7') or self.mode.startswith('MARK:') and (self.mode[5:] in AXIS_MARKS or self.mode[5:].startswith('RWY_')):
            hit=snap_path(self.scene,self.world(e.x,e.y),max(.25,12/self.zoom),visible=self.can_edit_object);self._snap_hit=hit;self.canvas.delete('snap_cursor')
            if hit:
                x,y=self.screen(hit[3]);self.canvas.create_oval(x-7,y-7,x+7,y+7,outline='#e84d81',width=2,tags='snap_cursor');self.canvas.create_text(x+10,y-12,text='吸附中线',anchor='w',fill='#a52b54',tags='snap_cursor')
            if self.mode=='CONNECT' and self.connect_ports and hit:
                target=dict(asset=hit[1],station=hit[2],direction=1)
                if target['asset']!=self.connect_ports[0]['asset'] or abs(target['station']-self.connect_ports[0]['station'])>1:
                    try:self._connect_preview=preview_connection(self.scene,self.connect_ports[0],target)
                    except ValueError as exc:self._connect_preview=None;self.status.set(str(exc))
                    self.redraw()
    def control_geometry(self):
        a=self.scene.assets.get(self.selection) or getattr(self,'auto_assets',{}).get(self.selection)
        if a and a['kind']=='MARKING' and a['props']['mark_type'] in GUIDE_KEYS and len(a['points'])>=2:
            nodes=self._guide_nodes.get(self.selection)
            if nodes is None:nodes=curve_nodes_for(a['points']);self._guide_nodes[self.selection]=nodes
            return nodes[0]['p'],nodes[-1]['p'],[nodes[0]['outgoing'],nodes[-1]['incoming']]
        return super().control_geometry()
    def select(self,oid):
        if oid!=self.selection:self._guide_nodes={}
        super().select(oid)
    def click(self,e):
        p=self.world(e.x,e.y)
        if self.mode=='SPLIT7':
            hit=snap_path(self.scene,p,max(2,12/self.zoom),visible=self.can_edit_object)
            if hit and self.scene.assets[hit[1]]['kind']!='RUNWAY':
                try:self.selection=split_route(self.scene,hit[1],hit[2]);self.set_mode('SELECT');self.refresh()
                except ValueError as exc:self.status.set(str(exc))
            return
        if self.mode=='CONNECT':
            hit=snap_path(self.scene,p,max(2,12/self.zoom),visible=self.can_edit_object)
            if not hit:self.status.set('请点击跑道或滑行道中线');return
            port=dict(asset=hit[1],station=hit[2],direction=1)
            if not self.connect_ports:self.connect_ports=[port];self.status.set('移动到目标中线查看曲线预览；再点击确认');self.redraw();return
            try:
                from connection9 import preview
                ports,path,controls=preview(self.scene,self.connect_ports[0],port)
                if g.length(path)<1:raise ValueError('两个连接点距离过近')
                a,b=[self.scene.assets[x['asset']] for x in ports];role='EXIT' if a['kind']=='RUNWAY' else 'ENTRY' if b['kind']=='RUNWAY' else 'TAXIWAY_JOIN'
                from connection9 import needs_pavement
                paved=needs_pavement(self.scene,*ports)
                self.selection=self.scene.connect(*ports,role=role,name=a['name']+' → '+b['name'],geometry='BEZIER',width=min(a['props']['width'],b['props']['width']),auto_tangent=True,bezier_controls=controls,auto_branches=False,pavement_visible=paved,edges_visible=paved)
                self.connect_ports=[];self._connect_preview=None;self.set_mode('SELECT');self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        if self.mode=='EDIT_GUIDE':
            options=[]
            for oid,a in self.auto_assets.items():
                if a['props']['mark_type'] in GUIDE_KEYS:options.append((g.project(a['points'],p)[0],'auto',oid,None))
            for oid,a in self.scene.assets.items():
                if a['kind']=='MARKING' and a['props']['mark_type'] in GUIDE_KEYS:options.append((g.project(a['points'],p)[0],'auto',oid,None))
            for mid,m in self.scene.movements.items():
                options.append((g.project(self.scene.movement_path(mid),p)[0],'move',mid,'MAIN'))
                for b in branches(self.scene,m):options.append((g.project(b['points'],p)[0],'move',mid,b['side']))
            for j in crossings(self.scene):
                for guide in turn_guides(self.scene,j):options.append((g.project(guide['points'],p)[0],'junction',j,guide))
            if not options:return
            d,kind,obj,part=min(options,key=lambda x:x[0])
            if d>max(2,12/self.zoom):return
            if kind=='junction':
                nodes=curve_nodes_for(part['points']);aa,bb=obj['assets'];routes=__import__('pavement_geometry').route_objects(self.scene)
                if aa not in self.scene.assets or bb not in self.scene.assets:self.status.set('请选中所属连接，再选择分支编辑');return
                _,sa,_=g.project(routes[aa]['points'],nodes[0]['p']);_,sb,_=g.project(routes[bb]['points'],nodes[-1]['p'])
                pa=dict(asset=aa,station=sa,direction=1);pb=dict(asset=bb,station=sb,direction=1);ds=directions(self.scene,pa,pb);pa['direction'],pb['direction']=ds
                with self.scene.transaction('独立编辑交叉口转弯线'):
                    self.scene.configure_junction(obj['id'],guides=dict(self.scene.data['junctions'].get(obj['id'],{}).get('guides',{}),**{part['key']:False}))
                    mid=self.scene.connect(pa,pb,name='转弯引导线',geometry='BEZIER',pavement_visible=False,auto_signs=False,show_holding=False,bezier_controls=[nodes[0]['outgoing'],nodes[-1]['incoming']])
                self._branch='MAIN';self.select(mid);self.refresh()
            else:
                if kind=='move':self._branch=part
                self.select(obj);self.update_inspector()
            self.mode='SELECT';self.redraw();return
        if self.mode in ('SELECT','NODES'):
            geometry=self.control_geometry()
            if geometry:
                a=self.scene.assets.get(self.selection) or self.auto_assets.get(self.selection)
                for index,q in enumerate(geometry[:2]):
                    if g.distance(p,q)<9/self.zoom:
                        self._anchor_drag=dict(data=copy.deepcopy(self.scene.data),index=index);return
                if a and a['kind']=='MARKING' and a['props']['mark_type'] in GUIDE_KEYS:
                    for index,q in enumerate(geometry[2]):
                        if g.distance(p,q)<10/self.zoom:self._guide_drag=dict(data=copy.deepcopy(self.scene.data),index=index);return
        if self.mode.startswith('MARK:'):
            key=self.mode[5:];hit=snap_path(self.scene,p,max(2,12/self.zoom),visible=self.can_edit_object);spec=CATALOG[key]
            if hit and (key in AXIS_MARKS or key.startswith('RWY_')) and (key in CROSS_POINTS or key in CROSS_PATHS or spec['mode']=='POINT'):
                self.selection=place_mark(self.scene,key,hit);self.set_mode('SELECT');self.refresh();return
            if spec['mode']=='PATH' and hit:
                if not self.points:self._mark_anchor=hit;self.points=[hit[3]];self.redraw();return
                if self._mark_anchor and hit[1]==self._mark_anchor[1] and key in GUIDE_KEYS|{'RWY_CENTER','RWY_EDGE','TWY_EDGE'}:
                    lo,hi=sorted((hit[2],self._mark_anchor[2]));points=g.subpath(self.scene.assets[hit[1]]['points'],lo,hi)
                    if hit[2]<self._mark_anchor[2]:points.reverse()
                    self.selection=self.scene.create_marking(key,points,label_asset=hit[1]);self.points=[];self.set_mode('SELECT');self.refresh();return
        super().click(e)
    def edit_curve_point(self,index,p,endpoint=False):
        oid=self.selection;a=self.scene.assets.get(oid) or self.auto_assets.get(oid);nodes=copy.deepcopy(self._guide_nodes[oid])
        n=nodes[0 if index==0 else -1];field='p' if endpoint else 'outgoing' if index==0 else 'incoming'
        if endpoint:
            hit=snap_path(self.scene,p,max(.25,10/self.zoom),visible=self.can_edit_object);p=hit[3] if hit else p;delta=[p[k]-n['p'][k] for k in (0,1)]
            for key in ('p','incoming','outgoing'):n[key]=[n[key][k]+delta[k] for k in (0,1)]
        else:n[field]=list(p)
        if oid in self.scene.assets:set_nodes(self.scene,oid,nodes)
        else:edit_generated_curve(self.scene,oid,nodes)
        self._guide_nodes[oid]=nodes
    def motion(self,e):
        drag=self._anchor_drag or self._guide_drag
        if not drag:return super().motion(e)
        geometry=self.control_geometry()
        if not geometry:return
        start,end,controls=geometry
        index=drag['index']
        anchor=geometry[1-index] if self._anchor_drag else geometry[index]
        point,_=__import__('node_interaction20_8').resolve(
            self.scene,self.world(e.x,e.y),anchor,bool(getattr(e,'state',0)&1),
            max(.25,12/self.zoom),self.selection)
        drag['point']=point
        controls=list(controls)
        if self._guide_drag:controls[index]=point
        elif index==0:
            controls[0]=[controls[0][k]+point[k]-start[k] for k in (0,1)]
            start=point
        else:
            controls[1]=[controls[1][k]+point[k]-end[k] for k in (0,1)]
            end=point
        from connection9 import path_with_controls
        points=path_with_controls(start,end,controls)
        self.canvas.delete('guide_drag39')
        self.canvas.create_line(*[v for p in points for v in self.screen(p)],
                                fill='#d34f94',width=2,dash=(6,4),tags='guide_drag39')

    def release(self,e):
        drag=self._anchor_drag or self._guide_drag
        if not drag:return super().release(e)
        endpoint=bool(self._anchor_drag)
        self._anchor_drag=None
        self._guide_drag=None
        self.canvas.delete('guide_drag39')
        if 'point' not in drag:return
        try:
            with self.scene.transaction('编辑引导线端点或控制柄'):
                if self.selection in self.scene.movements:
                    move_anchor(self.scene,self.selection,self._branch,drag['index'],drag['point'])
                else:self.edit_curve_point(drag['index'],drag['point'],endpoint=endpoint)
            self.refresh()
        except ValueError as exc:self.status.set(str(exc))

    def cancel_action(self,e=None):
        d=self._anchor_drag or self._guide_drag
        if d:self._anchor_drag=None;self._guide_drag=None;self._guide_nodes={};self.canvas.delete('guide_drag39')
        self._connect_preview=None;return super().cancel_action(e)
    def update_inspector(self):
        super().update_inspector();a=self.scene.assets.get(self.selection) or self.auto_assets.get(self.selection)
        self._inspector_busy=True
        try:
            if a and a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                section=self.section('滑行道分段');self.property_field(section,'_split_station','分段站位 m',round(g.length(a['points'])/2,3));ttk.Button(self.property_body,text='在此站位分段（保留编号）',command=self.split_from_field).pack(fill='x',padx=8,pady=5)
            if a and a['kind']=='STAND':
                ttk.Button(self.property_body,text='自定义此停止线的机型列表…',command=self.aircraft_dialog).pack(fill='x',padx=8,pady=5)
            if a and a['kind']=='MARKING' and a['props']['mark_type'] in GUIDE_KEYS:
                section=self.section('单独编辑生成引导线');geometry=self.control_geometry()
                for i,p in enumerate(geometry[2]):
                    for k,key in enumerate(('x','y')):self.property_field(section,f'_gc{i}{key}',f'控制点{i+1} {key.upper()}',round(p[k],3))
            if self.selection in self.scene.movements:
                section=self.section('交汇点（沿对应中线吸附）');m=self.scene.movements[self.selection]
                paths=self.anchor_paths();geometry=self.control_geometry()
                for index,side in enumerate(('from','to')):
                    station=g.project(paths[index],geometry[index])[1]
                    self.property_field(section,'_port_'+side,('起点' if side=='from' else '终点')+'站位 m',round(station,3))
                self.property_field(section,'auto_tangent','自动识别曲线接入方向',m.get('auto_tangent',True),'bool')
        finally:self._inspector_busy=False
    def anchor_paths(self):
        m=self.scene.movements[self.selection]
        if self._branch=='MAIN':return [self.scene.assets[m[side]['asset']]['points'] for side in ('from','to')]
        source=self.scene.movement_path(self.selection)
        if self._branch=='from':source=list(reversed(source))
        return [source,self.scene.assets[m[self._branch]['asset']]['points']]
    def split_from_field(self):
        try:
            self.selection=split_route(self.scene,self.selection,float(self.editor_vars['_split_station'][0].get()));self.refresh()
        except ValueError as exc:self.property_error.configure(text=str(exc))
    def aircraft_dialog(self):
        from editor6_geometry import stop_rows
        aid=self.selection;stopid=self._stop_id;row=next(r for r in stop_rows(self.scene.assets[aid]) if r['id']==stopid)
        win=tk.Toplevel(self);win.title('停止线适用机型列表');win.geometry('380x380')
        ttk.Label(win,text='每行一个自定义机型，可使用完整型号').pack(padx=12,pady=8)
        text=tk.Text(win,width=34,height=13);text.pack(fill='both',expand=True,padx=12);values=row.get('aircraft_types') or [s for s in row.get('aircraft','').replace('/',' ').split() if s];text.insert('1.0','\n'.join(values))
        def apply():
            set_aircraft_list(self.scene,aid,stopid,parse_aircraft(text.get('1.0','end')));win.destroy();self.refresh()
        ttk.Button(win,text='保存机型列表',command=apply).pack(pady=10)
    def apply_properties(self):
        if self._inspector_busy:return
        dirty=set(self._dirty_fields);special={k for k in dirty if k.startswith('_port_') or k.startswith('_gc') or k=='_split_station'}
        if not special:
            if '_s_aircraft' in dirty:
                from editor6_geometry import stop_rows
                with self.scene.transaction('修改停止线机型列表'):
                    result=super().apply_properties()
                    if '_s_aircraft' not in self._dirty_fields:
                        row=next(r for r in self.scene.assets[self.selection]['props']['stops'] if r['id']==self._stop_id);row['aircraft_types']=parse_aircraft(row['aircraft'])
                return result
            return super().apply_properties()
        try:
            with self.scene.transaction('修改引导线和交汇站位'):
                for key in special:
                    if key.startswith('_port_'):
                        side=key[6:];m=self.scene.movements[self.selection];station=float(self.editor_vars[key][0].get());points=self.anchor_paths()[0 if side=='from' else 1]
                        if not 0<=station<=g.length(points):raise ValueError('交汇点超出道面长度')
                        q,_=g.at(points,station);move_anchor(self.scene,self.selection,self._branch,0 if side=='from' else 1,q)
                if any(k.startswith('_gc') for k in special):
                    for i in (0,1):self.edit_curve_point(i,[float(self.editor_vars[f'_gc{i}{k}'][0].get()) for k in ('x','y')])
            self._dirty_fields.difference_update(special);super().apply_properties();self.schedule_frame();self.schedule_audit();self.redraw();self.property_error.configure(text='')
        except (ValueError,KeyError) as exc:self.property_error.configure(text='未应用：'+str(exc))
    def draw_grid7(self):
        c=self.canvas
        c.delete('grid')
        w,h=max(1,c.winfo_width()),max(1,c.winfo_height())
        if self.grid_visible.get():
            unit=10**math.floor(math.log10(max(1e-9,70/self.zoom)));step=next((v*unit for v in (1,2,5,10) if v*unit*self.zoom>=40),10*unit)
            corners=[self.world(x,y) for x,y in ((0,0),(w,0),(w,h),(0,h))]
            xs,ys=zip(*corners)
            x0,x1=math.floor(min(xs)/step),math.ceil(max(xs)/step)
            y0,y1=math.floor(min(ys)/step),math.ceil(max(ys)/step)
            dark=getattr(self,'_dark_mode24',False) or getattr(getattr(self,'lighting_view',None),'active',False)
            minor,major=('#263746','#344b5e') if dark else ('#dce4e9','#ccd9e2')
            for x in range(x0,x1+1):
                c.create_line(*self.screen((x*step,y0*step)),*self.screen((x*step,y1*step)),
                              fill=major if x%5==0 else minor,tags='grid')
            for y in range(y0,y1+1):
                c.create_line(*self.screen((x0*step,y*step)),*self.screen((x1*step,y*step)),
                              fill=major if y%5==0 else minor,tags='grid')
            c.tag_lower('grid')

    def redraw(self):
        if not hasattr(self,'canvas'):return
        super().redraw()
        self.draw_grid7()
        c=self.canvas;w,h=max(1,c.winfo_width()),max(1,c.winfo_height())
        length=10**math.floor(math.log10(max(1e-9,100/self.zoom)));length*=max(v for v in (1,2,5) if v*length*self.zoom<=125);pixels=length*self.zoom
        c.create_line(20,h-25,20+pixels,h-25,fill='#29495c',width=2,tags='overlay');c.create_line(20,h-30,20,h-20,fill='#29495c',tags='overlay');c.create_line(20+pixels,h-30,20+pixels,h-20,fill='#29495c',tags='overlay');c.create_text(20+pixels/2,h-40,text=f'{length:g} m',fill='#29495c',tags='overlay')
        geometry=self.control_geometry()
        if geometry:
            for item in c.find_withtag('overlay'):
                if c.type(item)=='rectangle':c.delete(item)
            for p,q in zip(geometry[:2],geometry[2]):
                x,y=self.screen(q);c.create_line(*self.screen(p),x,y,fill='#be548f',dash=(4,3),tags='overlay');c.create_rectangle(x-5,y-5,x+5,y+5,fill='#ffdbef',outline='#a83b79',width=2,tags='overlay')
            for p in geometry[:2]:
                x,y=self.screen(p);c.create_oval(x-6,y-6,x+6,y+6,fill='#dff8e8',outline='#22865d',width=2,tags='overlay')
        if self._connect_preview and getattr(self,'preview_enabled',None) and self.preview_enabled.get():
            pts=self._connect_preview[1];c.create_line(*[v for p in pts for v in self.screen(p)],fill='#e74f88',width=2,tags='overlay')
            c.create_text(20,30,text='连接预览 · 第二次点击创建 · 右键取消',anchor='w',fill='#a52658',tags='overlay')
        self.update_minimap()
    def update_minimap(self):
        if not hasattr(self,'minimap'):return
        c=self.minimap;key=(id(self.scene),self.scene.revision)
        if key!=self._nav_key:
            from scene_render import bounds
            box=bounds(self.scene);scale=min(174/max(1,box[2]-box[0]),108/max(1,box[3]-box[1]));origin=[95-(box[0]+box[2])/2*scale,65+(box[1]+box[3])/2*scale];self._nav_transform=(origin,scale);c.delete('all')
            for a in self.scene.assets.values():
                if a['kind'] in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','APRON'):
                    pts=g.simplify(a['points'],.5/max(scale,.001));coords=[v for x,y in pts for v in (origin[0]+x*scale,origin[1]-y*scale)]
                    if a['kind']=='APRON':c.create_polygon(*coords,fill='#b1bdc5',outline='')
                    else:c.create_line(*coords,fill='#465c70',width=max(1,a['props']['width']*scale))
            c.create_text(6,5,text=tr('导航'),anchor='nw',fill='#36546b');self._nav_key=key
        origin,scale=self._nav_transform;c.delete('viewport');w,h=self.canvas.winfo_width(),self.canvas.winfo_height();corners=[self.world(x,y) for x,y in ((0,0),(w,0),(w,h),(0,h),(0,0))]
        c.create_line(*[value for x,y in corners for value in (origin[0]+x*scale,origin[1]-y*scale)],fill='#d44376',width=2,tags='viewport')
    def navigate(self,e):
        origin,scale=self._nav_transform;p=[(e.x-origin[0])/scale,(origin[1]-e.y)/scale];x,y=self.screen(p);self.origin=[self.origin[0]+self.canvas.winfo_width()/2-x,self.origin[1]+self.canvas.winfo_height()/2-y];self.redraw()

def main():
    import sys
    from airport_scene import AirportScene
    scene=AirportScene.load(sys.argv[1]) if len(sys.argv)>1 else None
    Editor7(scene).mainloop()
