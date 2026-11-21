"""Logical cuts never subdivide the physical route; terminal deletion is explicit."""
from route_workflow17 import RouteWorkflow
import scene_geometry as g
import math,segments18 as logical
class LogicalWorkflow(RouteWorkflow):
    def preview(self,scene,aid,station,keep='START'):
        self.pending=None
        a=logical.route(scene,aid)
        L=g.length(a['points'])
        if not math.isfinite(station) or not 0<=station<=L:raise ValueError('站位超出滑行道')
        if self.action not in ('SPLIT_KEEP','SPLIT_NEW','TERMINAL'):raise ValueError('先选择逻辑分段或末端截断')
        if keep not in ('START','END','DELETE'):raise ValueError('请选择保留侧或删除整条岔路')
        if self.action=='TERMINAL' and keep!='DELETE' and min(station,L-station)<1:raise ValueError('若要删除整个岔路，请选择“删除整条选中岔路”；局部截断须距端点1m')
        if self.action.startswith('SPLIT'):
            p=logical.piece_at(a,station)
            if min(station-p['lo']*L,p['hi']*L-station)<1:raise ValueError('切口须距当前逻辑段两端1m')
        self.pending=dict(action=self.action,aid=aid,station=station,keep=keep,revision=scene.revision,scene_id=id(scene));return self.pending
    def commit(self,scene,name=None):
        p=self.pending
        if not p:raise ValueError('请先左键点击预览')
        if p['revision']!=scene.revision or p['scene_id']!=id(scene):self.pending=None;raise ValueError('工程已改变，请重新点击预览')
        if p['action'].startswith('SPLIT'):result=logical.split(scene,p['aid'],p['station'],name,keep=p['action']=='SPLIT_KEEP')
        else:result=logical.terminal(scene,p['aid'],p['station'],p['keep'])
        self.pending=None;return result
