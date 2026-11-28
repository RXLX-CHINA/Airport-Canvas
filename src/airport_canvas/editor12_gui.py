"""Polyline marking authoring, per-corner radius handles and default marquee."""
import copy,math
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from qt_compat import ttk
from editor11_gui import Editor11
from airport_scene import AirportScene
from marking_catalog import CATALOG
from curve_model import editable_vertices,rounded_nodes,evaluate,rebuild_rounded
import scene_geometry as g

class Editor12(Editor11):
    def __init__(self,scene=None):
        self._marquee12=None;self._edit12=None;self._corner_handles12=[];self._deice_hit12=None
        if scene is None:
            p=Path(__file__).with_name('example_editor12.airport.json');scene=AirportScene.load(p) if p.exists() else AirportScene()
        super().__init__(scene)
    def update_title(self):
        super().update_title();self.title(self.title().replace('11.0','12.0'))
    def set_mode(self,mode):
        self._marquee12=None;self._edit12=None;self._deice_hit12=None
        if hasattr(self,'canvas'):
            for tag in ('line_preview12','corner_preview12','deice_preview12','marquee12'):self.canvas.delete(tag)
        super().set_mode(mode)
        if mode=='DEICE10':self.status.set('先点滑行道中线确定除冰等待坪入口中心，再点坪内远端角点；进出线及出口等待线自动生成，无灯光')
        elif mode.startswith('MARK:') and CATALOG[mode[5:]]['mode']=='PATH':self.status.set('连续点选折线顶点，Enter完成；Shift约束方向；节点编辑中拖圆形手柄调整各拐点半径')
    def draft_defaults11(self,mode):
        values=super().draft_defaults11(mode)
        if mode.startswith('MARK:') and CATALOG[mode[5:]]['mode']=='PATH':values.setdefault('corner_radius',10.)
        if mode=='DEICE10':values.update(deice_radius=20.,deice_code='C')
        return values
    def update_inspector(self):
        super().update_inspector()
        if self._draft11:return
        a=self.scene.assets.get(self.selection)
        if not a:return
        self._inspector_busy=True
        try:
            p=a['props']
            if a['kind']=='RUNWAY':
                sec=self.section('中心圆与入口内移')
                self.property_field(sec,'center_circle','绘制跑道中心圆',p.get('center_circle',False),'bool')
                for end,label in [('a','A端'),('b','B端')]:
                    self.hide_field11('displaced_'+end)
                    self.property_field(sec,'displaced_'+end,label+' 入口内移 m',p.get('displaced_'+end,0),'float')
                    self.property_field(sec,'temporary_'+end,label+' 临时内移（入口箭头列）',p.get('temporary_'+end,False),'bool')
            if a['kind']=='STAND':
                sec=self.section('安全线颈部与保障区域');self.property_field(sec,'safety_neck','小头颈部长度 m',p.get('safety_neck',15),'float');self.property_field(sec,'stand_support','另一侧作业等待区及轮挡区',p.get('stand_support',True),'bool')
            if p.get('deice_layout12'):
                sec=self.section('旁通除冰等待坪布局')
                for key,label,default in [('deice_width','总宽 m',140),('deice_depth','进深 m',95),('deice_radius','进出转弯半径 m',20),('deice_hold_distance','出口等待线距滑行道中线 m',__import__('deice12').SEPARATION[p.get('deice_code','C')])]:self.property_field(sec,key,label,p.get(key,default),'float')
                self.property_field(sec,'deice_code','净距校核类别',p.get('deice_code','C'),'text',list('ABCDEF'))
                ttk.Label(self.property_body,text='出口采用单条黄色虚线；不生成灯光。若宽度、进深或等待净距不足，审阅将报告错误。',wraplength=280,padding=8).pack(fill='x')
            elif p.get('role')=='DEICING':
                ttk.Button(self.property_body,text='按参考图重建为旁通除冰等待坪',command=self.upgrade_deice12).pack(fill='x',padx=8,pady=6)
            if self.line_asset12(a):
                sec=self.section('折线顶点 / 圆角手柄');vertices=editable_vertices(a);self.vertex_index=min(self.vertex_index,len(vertices)-1)
                self.property_field(sec,'_line_vertex12','当前顶点',str(self.vertex_index+1),'text',[str(i+1) for i in range(len(vertices))])
                self.property_field(sec,'_line_radius12','该拐点圆角半径 m',p.get('corner_radii',{}).get(str(self.vertex_index),p.get('corner_radius',10)),'float')
                ttk.Label(self.property_body,text='节点编辑：方块移动折线顶点，圆柄沿入边拖动改变该点半径；右键取消。',wraplength=280,padding=8).pack(fill='x')
        finally:self._inspector_busy=False
        self.reveal_inspector11()
    @staticmethod
    def line_asset12(a):return a['kind']=='MARKING' and CATALOG[a['props']['mark_type']]['mode']=='PATH'
    def upgrade_deice12(self):
        try:__import__('deice12').upgrade(self.scene,self.selection);self.refresh();self.status.set('已关联最近的滑行道并重建进出路线、出口等待线和道面；Ctrl+Z可撤销')
        except ValueError as exc:self.status.set(str(exc))
    def apply_properties(self):
        if self._inspector_busy:return
        own_changed=False
        if not self._draft11 and self.selection in self.scene.assets:
            a=self.scene.assets[self.selection];dirty=set(self._dirty_fields)
            if '_line_vertex12' in dirty:
                self.vertex_index=int(self.editor_vars['_line_vertex12'][0].get())-1;self._dirty_fields.discard('_line_vertex12');super().apply_properties();self.update_inspector();self.redraw();return
            if '_line_radius12' in dirty:
                try:
                    radii=copy.deepcopy(a['props'].get('corner_radii',{}));radii[str(self.vertex_index)]=float(self.editor_vars['_line_radius12'][0].get());rebuild_rounded(self.scene,a['id'],radii=radii);self._dirty_fields.discard('_line_radius12');own_changed=True
                except ValueError as exc:self.property_error.configure(text=str(exc));return
        super().apply_properties()
        __import__('deice12').refresh(self.scene)
        if own_changed:self.refresh()
    def click(self,e):
        if self.mode=='SELECT' and not self._space11:
            if not getattr(e,'state',0)&4 and self.begin_transform11(e):return
            self.canvas.focus_set();self._marquee12=dict(start=(e.x,e.y),end=(e.x,e.y),add=bool(getattr(e,'state',0)&(1|4)),hit=self.pick(self.world(e.x,e.y)),active=False);return
        if self.mode=='NODES':
            if self.begin_nodes12(e):return
            hit=self.pick(self.world(e.x,e.y));asset=self.scene.assets.get(hit[1]) if hit else None
            if asset and (self.line_asset12(asset) or asset['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','ROAD')):
                self.vertex_index=0;self.select(asset['id']);self.redraw();return
            selected=self.scene.assets.get(self.selection)
            if selected and self.line_asset12(selected):return
        if self.mode=='DEICE10':
            self.apply_properties();p=self.world(e.x,e.y)
            if not self._deice_hit12:
                from editor7_model import snap_path
                hit=snap_path(self.scene,p,max(.25,15/self.zoom),visible=self.can_edit_object)
                if not hit or self.scene.assets[hit[1]]['kind'] not in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):self.status.set('请先点选滑行道中线');return
                self._deice_hit12=hit;self.points=[hit[3]];self.redraw();return
            try:
                aid=__import__('deice12').create(self.scene,self._deice_hit12,p,**self._draft_values11);self.selection=aid;self.set_mode('SELECT');self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        if self.mode.startswith('MARK:') and CATALOG[self.mode[5:]]['mode']=='PATH':
            # Cross-sectional holding marks retain their one-click axis tool.
            from editor7_model import CROSS_PATHS,snap_path
            key=self.mode[5:];e=self.event10(e);p=self.world(e.x,e.y);hit=snap_path(self.scene,p,max(.25,12/self.zoom),visible=self.can_edit_object)
            if key in CROSS_PATHS and hit:return super().click(e)
            if hit:p=hit[3]
            if not self.points or g.distance(self.points[-1],p)>.05:self.points.append(p)
            self.redraw();return
        return super().click(e)
    def finish_draw(self):
        if self.mode.startswith('MARK:') and CATALOG[self.mode[5:]]['mode']=='PATH':
            if len(self.points)<2:return
            self.apply_properties();vertices=copy.deepcopy(self.points);radius=self._draft_values11.get('corner_radius',10)
            try:
                nodes,effective=rounded_nodes(vertices,radius)
                with self.scene.transaction('绘制圆角折线标记'):
                    aid=self.scene.create_marking(self.mode[5:],evaluate(nodes),corner_radius=radius,corner_radii={},effective_radii=effective)
                    self.scene.assets[aid].update(design_vertices=vertices,curve_nodes=nodes)
                self.selection=aid;self.set_mode('SELECT');self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        return super().finish_draw()
    def begin_nodes12(self,e):
        a=self.scene.assets.get(self.selection)
        if not a or not (self.line_asset12(a) or a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','ROAD')):return False
        for x,y,index,kind in reversed(self._corner_handles12):
            if math.hypot(e.x-x,e.y-y)>9:continue
            self.vertex_index=index
            props=a['props']
            self._edit12=dict(aid=a['id'],index=index,kind=kind,vertices=copy.deepcopy(editable_vertices(a)),
                              radii=copy.deepcopy(props.get('corner_radii',{})),radius=props.get('corner_radius',10))
            if self._selected_form!=a['id'] or self._dirty_fields:
                self.update_inspector()
            elif self.line_asset12(a):
                self._inspector_busy=True
                try:
                    self.editor_vars['_line_vertex12'][0].set(str(index+1))
                    self.editor_vars['_line_radius12'][0].set(
                        props.get('corner_radii',{}).get(str(index),props.get('corner_radius',10)))
                finally:
                    self._inspector_busy=False
            return True
        return False
    def motion(self,e):
        if self._marquee12:
            d=self._marquee12;d['end']=(e.x,e.y);d['active']=math.dist(d['start'],d['end'])>=4;self.draw_marquee12();return
        if self._edit12:
            d=self._edit12;verts=copy.deepcopy(d['vertices']);radii=copy.deepcopy(d['radii']);i=d['index'];p=self.world(e.x,e.y)
            if d['kind']=='VERTEX':
                anchor=verts[i-1] if i else verts[1]
                tangent=g.unit(verts[i-1],verts[i]) if i else g.unit(verts[0],verts[1])
                p,hit=__import__('node_interaction20_8').resolve(self.scene,p,anchor,bool(getattr(e,'state',0)&1),max(.25,12/self.zoom),d['aid'],tangent,visible=self.can_edit_object)
                verts[i]=p
            else:
                incoming=g.unit(verts[i-1],verts[i]);outgoing=g.unit(verts[i],verts[i+1]);angle=math.acos(max(-1,min(1,sum(incoming[k]*outgoing[k] for k in (0,1)))))
                distance=max(0,sum((verts[i][k]-p[k])*incoming[k] for k in (0,1)));radii[str(i)]=min(distance,g.distance(verts[i-1],verts[i])*.49,g.distance(verts[i],verts[i+1])*.49)/max(1e-6,math.tan(angle/2))
                self.status.set(f'顶点 {i+1} 圆角半径 {radii[str(i)]:.2f} m')
            if d.get('candidate')==(verts,radii):
                return
            try:
                nodes,_=rounded_nodes(verts,d['radius'],radii)
                coords=[v for p in evaluate(nodes) for v in self.screen(p)]
                d['candidate']=(verts,radii)
                if self.canvas.find_withtag('corner_preview12'):
                    self.canvas.coords('corner_preview12',*coords)
                else:
                    self.canvas.create_line(*coords,fill='#00a1c3',width=3,tags='corner_preview12')
            except ValueError:pass
            return
        return super().motion(e)
    def release(self,e):
        if self._marquee12:
            d=self._marquee12;self._marquee12=None;self.canvas.delete('marquee12')
            if not d['active']:
                hit=d['hit'];oid=__import__('transform11').owner(self.scene,hit[1],self.auto_assets) if hit else None
                if d['add'] and oid:
                    if oid in self.selected_ids:self.selected_ids.remove(oid)
                    else:self.selected_ids.add(oid)
                    self._preserve_set=True
                    try:self.select(oid if oid in self.selected_ids else next(iter(self.selected_ids),None))
                    finally:self._preserve_set=False
                else:self.select(oid)
                return
            from geometry11 import LineString,polygon
            x0,x1=sorted((d['start'][0],e.x));y0,y1=sorted((d['start'][1],e.y));box=polygon([self.world(x0,y0),self.world(x1,y0),self.world(x1,y1),self.world(x0,y1)])
            found=set()
            for oid,a in self.scene.assets.items():
                if not self.can_edit_object(oid):continue
                pts=a['points'];path=LineString(pts+[pts[0]] if a['kind'] in ('APRON','PROTECTION','EQUIPMENT','CLOSED_AREA') else pts)
                if path.intersects(box):found.add(__import__('transform11').owner(self.scene,oid,self.auto_assets))
            for oid,a in self.auto_assets.items():
                if not self.can_edit_object(oid):continue
                if len(a['points'])>1 and LineString(a['points']).intersects(box):found.add(__import__('transform11').owner(self.scene,oid,self.auto_assets))
            found={oid for oid in found if self.can_edit_object(oid)}
            self.selected_ids={oid for oid in self.selected_ids|found if self.can_edit_object(oid)} if d['add'] else found;self._preserve_set=True
            try:self.select(next(iter(self.selected_ids),None))
            finally:self._preserve_set=False
            self.redraw();self.status.set(f'已框选 {len(self.selected_ids)} 个对象');return
        if self._edit12:
            d=self._edit12;self._edit12=None;self.canvas.delete('corner_preview12')
            if 'candidate' in d:
                try:rebuild_rounded(self.scene,d['aid'],d['candidate'][0],d['radius'],d['candidate'][1]);self.refresh()
                except ValueError as exc:self.status.set(str(exc))
            return
        return super().release(e)
    def cancel_action(self,e=None):
        self._marquee12=None;self._edit12=None;self._deice_hit12=None
        self.canvas.delete('marquee12');self.canvas.delete('corner_preview12');return super().cancel_action(e)
    def gesture11(self):return self._marquee12 or self._edit12 or super().gesture11()
    def draw_marquee12(self):
        self.canvas.delete('marquee12');d=self._marquee12
        if d and d['active']:
            self.canvas.create_rectangle(*d['start'],*d['end'],outline='#007fce',width=1.5,
                                         fill='#49aee8',fill_alpha=.22,tags='marquee12')
    def redraw(self):
        super().redraw();self._corner_handles12=[]
        if not hasattr(self,'canvas'):return
        self.canvas.delete('corner_handles12');self.canvas.delete('deice_preview12');a=self.scene.assets.get(self.selection)
        if self.mode=='NODES' and a and (self.line_asset12(a) or a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','ROAD')):
            self.canvas.delete('overlay');verts=editable_vertices(a);self.canvas.create_line(*[v for q in verts for v in self.screen(q)],fill='#078ca6',dash=(3,5),tags='corner_handles12')
            for i,q in enumerate(verts):
                x,y=self.screen(q);self.canvas.create_rectangle(x-5,y-5,x+5,y+5,fill='white',outline='#007d9a',width=2,tags='corner_handles12');self._corner_handles12.append((x,y,i,'VERTEX'))
                if 0<i<len(verts)-1:
                    u=g.unit(verts[i-1],q);v=g.unit(q,verts[i+1]);angle=math.acos(max(-1,min(1,sum(u[k]*v[k] for k in (0,1)))))
                    if angle<1e-5:continue
                    r=a['props'].get('corner_radii',{}).get(str(i),a['props'].get('corner_radius',10));dist=min(r*math.tan(angle/2),g.distance(verts[i-1],q)*.49,g.distance(q,verts[i+1])*.49);dist=max(12/self.zoom,dist)
                    h=[q[k]-u[k]*dist for k in (0,1)];hx,hy=self.screen(h);self.canvas.create_line(x,y,hx,hy,fill='#d58912',dash=(3,3),tags='corner_handles12');self.canvas.create_oval(hx-5,hy-5,hx+5,hy+5,fill='#ffe8b5',outline='#c7820b',width=2,tags='corner_handles12');self._corner_handles12.append((hx,hy,i,'RADIUS'))
        self.draw_marquee12()
    def pointer(self,e):
        if self._marquee12 or self._edit12:return
        super().pointer(e)
        if self.mode=='DEICE10' and self._deice_hit12:
            self.canvas.delete('deice_preview12')
            try:
                module=__import__('deice12');d=module.layout(self.scene,module.draft(self.scene,self._deice_hit12,self.world(e.x,e.y),**self._draft_values11))
                for key in ('pavement','route','hold'):
                    pts=d[key]+[d[key][0]] if key=='pavement' else d[key];self.canvas.create_line(*[v for p in pts for v in self.screen(p)],fill='#039db1',width=2,dash=(4,3) if key!='route' else (),tags='deice_preview12')
            except ValueError as exc:self.status.set(str(exc))
        if self.mode.startswith('MARK:') and CATALOG[self.mode[5:]]['mode']=='PATH' and self.points:
            event=self.event10(e);pts=self.points+[self.world(event.x,event.y)]
            try:nodes,_=rounded_nodes(pts,self._draft_values11.get('corner_radius',10));points=evaluate(nodes)
            except ValueError:return
            self.canvas.delete('line_preview12');self.canvas.create_line(*[v for p in points for v in self.screen(p)],fill='#00a0bb',width=2,tags='line_preview12')
    def demo10(self):Editor12(AirportScene.load(Path(__file__).with_name('example_editor12.airport.json')))

def main():Editor12().mainloop()
