"""One explicit route operation, one pending preview, one atomic commit."""
from dataclasses import dataclass
import math
import scene_geometry as g
import segments16 as seg

@dataclass
class RouteWorkflow:
    action:str='NAME'
    pending:object=None
    def choose(self,action):
        if action not in ('NAME','INDEPENDENT','SPLIT_KEEP','SPLIT_NEW','TERMINAL','MERGE'):raise ValueError('未知路线操作')
        self.action=action;self.pending=None
    def preview(self,scene,aid,station,keep='START'):
        if scene.assets[aid]['kind'] not in seg.TAXIS:raise ValueError('请选择滑行道')
        length=g.length(scene.assets[aid]['points'])
        if self.action.startswith('SPLIT') and scene.assets[aid]['props'].get('terminal_backup13'):raise ValueError('此线仍处于可恢复的截断状态，请先恢复完整几何再拆分，避免重复恢复道面')
        if not math.isfinite(station) or not 1<=station<=length-1:raise ValueError('位置须距离两端至少1m')
        if keep not in ('START','END'):raise ValueError('请选择保留侧')
        if self.action not in ('SPLIT_KEEP','SPLIT_NEW','TERMINAL'):raise ValueError('先选择切分或截断')
        self.pending=dict(action=self.action,aid=aid,station=station,keep=keep,revision=scene.revision,scene_id=id(scene))
        return self.pending
    def commit(self,scene,name=None):
        p=self.pending
        if not p:raise ValueError('请先在路线内部点选预览位置')
        if p['scene_id']!=id(scene) or p['revision']!=scene.revision: self.pending=None;raise ValueError('工程已变化，请重新预览')
        if p['action']=='SPLIT_KEEP':result=__import__('editor7_model').split_route(scene,p['aid'],p['station'],keep_name=True)
        elif p['action']=='SPLIT_NEW':
            if not name or not name.strip():raise ValueError('请输入新段编号')
            if name.strip()==seg.designation(scene.assets[p['aid']]):raise ValueError('新段编号与原编号相同；若需保留编号，请选择“拆分几何，保留同一编号”')
            result=seg.split(scene,p['aid'],p['station'],name)
        else:__import__('interaction15').terminal(scene,p['aid'],p['station'],p['keep']);result=p['aid']
        self.pending=None;return result
    def cancel(self):self.pending=None

def visible_labels(scene,world_box):
    """Name anchors are chosen from visible subpaths, not offscreen midpoints."""
    result=[]
    for a in scene.assets.values():
        if a['kind'] not in seg.TAXIS:continue
        intervals=[];station=0.
        for p,q in zip(a['points'],a['points'][1:]):
            L=g.distance(p,q);hit=g.segment_box_interval(p,q,world_box)
            if hit:
                lo,hi=station+hit[0]*L,station+hit[1]*L
                if intervals and abs(intervals[-1][1]-lo)<1e-5:intervals[-1]=(intervals[-1][0],hi)
                else:intervals.append((lo,hi))
            station+=L
        for lo,hi in intervals:
            if hi-lo>.05:result.append((a['id'],seg.designation(a),g.at(a['points'],(lo+hi)/2)[0]))
    return result
