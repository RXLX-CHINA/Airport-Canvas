"""Geometry diagnostics for connection direction, labels and stand templates."""
import math
import scene_geometry as g
from connection9 import dot

def loop(points):
    segments=list(zip(points,points[1:]))
    for i,(a,b) in enumerate(segments):
        for c,d in segments[i+2:]:
            if max(a[0],b[0])<min(c[0],d[0]) or max(c[0],d[0])<min(a[0],b[0]) or max(a[1],b[1])<min(c[1],d[1]) or max(c[1],d[1])<min(a[1],b[1]):continue
            hit=g.crossing(a,b,c,d)
            if hit and all(g.distance(hit,p)>.001 for p in (a,b,c,d)):return True
    return False

def checks(scene):
    issues=[]
    def issue(oid,rule,message,status='REVIEW_REQUIRED'):
        issues.append(dict(object_id=oid,status=status,rule=rule,message=message,source='6.2.8 / 6.2.16 / 6.2.18；二维几何检查',actual=None,required=None))
    for mid in scene.data['meta'].get('editor9_migration_skipped',[]):
        if mid in scene.movements:issue(mid,'MIGRATION_FLOW','旧连接与当前中线流向不符，已跳过自动迁移；请调整端点或流向。','FAIL')
    for mid,m in scene.movements.items():
        if m.get('legacy_attachment'):continue
        path=scene.movement_path(mid)
        if loop(path):issue(mid,'GUIDE_LOOP','连接引导线自交；调整端点和控制柄。','FAIL')
        if m['role']=='PUSHBACK':
            source=scene.assets[m['from']['asset']]
            if source['kind']=='STAND' and dot(g.unit(path[0],path[1]),g.unit(source['points'][0],source['points'][-1]))>-.01:issue(mid,'PUSH_DIRECTION','推出线没有从停机位向后离开。','FAIL')
        if m.get('follow_existing') and m['from']['asset']==m['to']['asset'] and m.get('bezier_controls'):issue(mid,'SAME_ROUTE_CONTROLS','同一路线的沿中线连接使用原路线形状；如需自由改形，请关闭“沿已有中线转接”。')
    from automatic_markings import generated_markings
    from marking_catalog import primitives
    marks=generated_markings(scene)
    for aid,a in scene.assets.items():
        if a['kind']!='STAND':continue
        p=a['props'];length=g.length(a['points']);R=p.get('lead_radius',20)
        if length<2*R+10:issue(aid,'LEAD_ROOM','机位轴线较短；引入构型或编号可能超过停止点，请调整长度、半径和编号位置。')
        boards=[primitives(x)[0]['points'] for x in marks.values() if x.get('owner')==aid and x['props']['mark_type']=='STAND_NUMBER']
        for mark in marks.values():
            if mark.get('owner')!=aid or mark['props']['mark_type']!='LEAD_IN':continue
            if any(g.inside(q,board) for q in mark['points'] for board in boards):issue(mark['id'],'LEAD_LABEL_OVERLAP','引入线穿过机位编号底板；检查单独覆盖或编号尺寸。','FAIL')
    return issues
