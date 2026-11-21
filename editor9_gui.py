"""Explicit pushback authoring and prominent maximum-span component."""
from pathlib import Path
import math
import qt_compat as tk
from qt_compat import ttk
from airport_scene import AirportScene
from editor8_gui import Editor8
from connection9 import pushback_ports
from editor7_model import snap_path
import scene_geometry as g

class Editor9(Editor8):
    def __init__(self,scene=None):
        self._push_source=None
        if scene is None:scene=AirportScene.load(Path(__file__).with_name('example_editor9.airport.json'))
        super().__init__(scene)
    def update_title(self):
        super().update_title();self.title(self.title().replace('8.0','9.0'))
    def _build(self):
        super()._build();bar=ttk.Frame(self.tree.master);bar.pack(fill='x',before=self.tree)
        ttk.Button(bar,text='↩ 推出路径',command=lambda:self.set_mode('PUSHBACK9')).pack(side='left')
        ttk.Button(bar,text='翼展限制 MAX SPAN',command=lambda:self.set_mode('MARK:MAX_SPAN')).pack(side='left')
    def refresh(self):
        if not self.scene.data['meta'].get('editor9_connection_migration'):
            from connection9 import needs_pavement,preview
            candidates=[m for m in self.scene.movements.values() if m['role'] in ('TAXIWAY_JOIN','APRON_ACCESS') and m.get('auto_tangent') and not m.get('bezier_controls') and not needs_pavement(self.scene,m['from'],m['to'])]
            if candidates:
                import copy
                with self.scene.transaction('升级旧版自动连接（可撤销）'):
                    for m in candidates:
                        old=copy.deepcopy(m)
                        try:ports,_,controls=preview(self.scene,m['from'],m['to'])
                        except ValueError:
                            self.scene.data['meta'].setdefault('editor9_migration_skipped',[]).append(m['id']);continue
                        follow=ports[0].pop('_follow_existing',False)
                        m.update({'from':ports[0],'to':ports[1]},bezier_controls=controls,follow_existing=follow,auto_branches=False,pavement_visible=False,edges_visible=False,editor8_backup=old)
                    self.scene.data['meta']['editor9_connection_migration']=True
            else:self.scene.data['meta']['editor9_connection_migration']=True
        super().refresh()
    def set_mode(self,mode):
        self._push_source=None
        if hasattr(self,'canvas'):self.canvas.delete('push_preview')
        super().set_mode(mode)
        if mode=='PUSHBACK9':self.status.set('先点停机位，再点目标滑行中线；白色预览从鼻轮停止点向后推出，右键取消')
    def push_hit(self,p):
        hits=[]
        for aid,a in self.scene.assets.items():
            if a['kind']=='STAND':
                d,s,q=g.project(a['points'],p)
                if d<=max(12/self.zoom,a['props']['width']/2):hits.append((d,aid))
        return min(hits)[1] if hits else None
    def pointer(self,e):
        if self.mode=='PUSHBACK9' and self._push_source:
            hit=snap_path(self.scene,self.world(e.x,e.y),max(2,12/self.zoom))
            self.canvas.delete('push_preview')
            if hit:
                try:
                    ports,path,_=pushback_ports(self.scene,self._push_source,dict(asset=hit[1],station=hit[2],direction=1));coords=[v for q in path for v in self.screen(q)]
                    self.canvas.create_line(*coords,fill='white',width=2,dash=(5,5),tags='push_preview')
                except ValueError as exc:self.status.set(str(exc))
            return
        super().pointer(e)
    def click(self,e):
        if self.mode=='PUSHBACK9':
            p=self.world(e.x,e.y)
            if self._push_source is None:
                aid=self.push_hit(p)
                if aid:self._push_source=dict(asset=aid,station=g.length(self.scene.assets[aid]['points']),direction=-1);self.status.set('移动到目标滑行中线预览；点击提交推出路径')
                else:self.status.set('请先点选停机位')
                return
            hit=snap_path(self.scene,p,max(2,12/self.zoom))
            if hit:
                target=dict(asset=hit[1],station=hit[2],direction=1)
                try:
                    ports,_,controls=pushback_ports(self.scene,self._push_source,target)
                    self.selection=self.scene.connect(*ports,role='PUSHBACK',name='推出 · '+self.scene.assets[ports[0]['asset']]['name'],bezier_controls=controls,auto_branches=False,auto_signs=False)
                    self.canvas.delete('push_preview');self.set_mode('SELECT');self.refresh()
                except ValueError as exc:self.status.set(str(exc))
            return
        super().click(e)
    def repair_connection(self):
        from connection9 import preview,needs_pavement
        m=self.scene.movements[self.selection]
        if m['role']=='RAPID_EXIT':
            self.status.set('快速脱离道请使用专用出口半径、脱离角和反向接入参数；此操作不替换快速出口构型');return
        with self.scene.transaction('修复连接拓扑'):
            if m['role']=='PUSHBACK':ports,_,controls=pushback_ports(self.scene,m['from'],m['to']);paved=False
            else:ports,_,controls=preview(self.scene,m['from'],m['to']);paved=needs_pavement(self.scene,*ports)
            m.update({'from':ports[0],'to':ports[1]},bezier_controls=controls,auto_branches=False,pavement_visible=paved,edges_visible=paved)
            m['follow_existing']=ports[0].pop('_follow_existing',False)
        self.refresh()

    def update_inspector(self):
        super().update_inspector();a=self.scene.assets.get(self.selection);m=self.scene.movements.get(self.selection)
        self._inspector_busy=True
        try:
            if m:
                sec=self.section('连接拓扑')
                ttk.Button(self.property_body,text='修复此连接的重复道面与回钩',command=self.repair_connection).pack(fill='x',padx=8,pady=5)
                if m.get('editor8_backup'):ttk.Button(self.property_body,text='还原此连接升级前的设置',command=self.restore_connection).pack(fill='x',padx=8,pady=5)
                self.property_field(sec,'auto_branches','自动生成反向分支',m.get('auto_branches',True),'bool')
                self.property_field(sec,'lock_tangents','移动交汇点时保持相切',m.get('lock_tangents',True),'bool')
                self.property_field(sec,'follow_existing','沿已有中线转接',m.get('follow_existing',False),'bool')
                if m.get('follow_existing'):self.property_field(sec,'join_radius','转接圆角半径 m',m.get('join_radius',25))
            if a and a['kind']=='STAND':
                sec=self.section('引入线构型细节')
                self.property_field(sec,'lead_direction','允许引入方向',a['props'].get('lead_direction','BOTH'),'radio',['BOTH','LEFT','RIGHT'])
                for key,label,default in [('lead_label_angle','A/D编号轴线角 °',60),('lead_g','G 留白 m',.5),('lead_h','H 横向净距 m',.5),('lead_i','I 续线留白 m',1),('lead_j','J 下留白 m',1),('lead_k','K 上留白 m',2),('lead_l','L 编号间距 m',1),('lead_m','M 短线 m',1),('lead_n','N 编号底距 m',1),('lead_p','P 编号上留白 m',2)]:self.property_field(sec,key,label,a['props'].get(key,default))
                self.property_field(sec,'show_safety','显示折线机位安全线',a['props'].get('show_safety',True),'bool')
        finally:self._inspector_busy=False
    def restore_connection(self):
        import copy
        m=self.scene.movements.get(self.selection)
        if m and m.get('editor8_backup'):
            with self.scene.transaction('还原升级前连接'):self.scene.movements[self.selection]=copy.deepcopy(m['editor8_backup'])
            self.refresh()
    def apply_properties(self):
        m=self.scene.movements.get(self.selection)
        reset=m and m.get('follow_existing') and 'join_radius' in getattr(self,'_dirty_fields',set())
        if reset:
            old=m.get('join_radius',25)
            with self.scene.transaction('修改沿中线转接半径'):
                super().apply_properties()
                if m.get('join_radius',25)!=old:m.pop('bezier_controls',None)
            self.schedule_frame()
        else:super().apply_properties()

def main():Editor9().mainloop()

if __name__=='__main__':main()
