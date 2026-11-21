"""Polygon vertex edits and anchored pier length edits."""
import copy,math
import scene_geometry as g
from geometry11 import Polygon,polygon
def eligible(a):
    if not a or len(a.get('points',[]))<3:return False
    p=a['props']
    if p.get('deice_layout12') or p.get('turn_pad'):return False
    if a['kind'] in ('APRON','EQUIPMENT','PROTECTION','CLOSED_AREA'):return True
    return a['kind']=='MARKING' and __import__('marking_catalog').CATALOG[p['mark_type']]['mode']=='AREA'
def checked(points):
    shape=Polygon(points)
    if not shape.is_valid or shape.area<.01 or any(not all(math.isfinite(v) for v in q) for q in points):raise ValueError('多边形不能自交，面积应大于0.01平方米。')
def set_vertex(scene,aid,index,q):
    a=scene.assets[aid]
    if not eligible(a):raise ValueError('此对象请使用对应的专用几何工具。')
    points=copy.deepcopy(a['points']);points[index]=list(q);checked(points)
    with scene.transaction('编辑几何顶点'):a['points']=points;building_collisions(scene,{aid})
def pier_length(a):return (g.distance(a['points'][0],a['points'][3])+g.distance(a['points'][1],a['points'][2]))/2
def building_collisions(scene,changed):
    import terminal19 as t
    buildings=t.buildings(scene)
    for a in buildings:
        if a['id'] not in changed:continue
        for b in buildings:
            if b['id']!=a['id'] and polygon(a['points']).intersection(polygon(b['points'])).area>.001:raise ValueError('修改会使建筑或廊桥重叠，请先调整附近组件。')
def resize_pier(scene,aid,length):
    import terminal19 as t
    a=scene.assets[aid]
    if a['props'].get('building_role19')!='PIER' or len(a['points'])!=4:raise ValueError('请选择四边形指廊。')
    if not math.isfinite(length) or length<=0:raise ValueError('指廊长度必须大于0。')
    old=copy.deepcopy(a);points=copy.deepcopy(a['points'])
    for start,end in ((0,3),(1,2)):
        u=g.unit(points[start],points[end]);points[end]=[points[start][k]+u[k]*length for k in (0,1)]
    checked(points)
    with scene.transaction('调整指廊长度'):
        a['points']=points;changed={aid}
        for b in t.buildings(scene):
            if b['props'].get('pier_id19')!=aid:continue
            center=[(b['points'][0][k]+b['points'][1][k])/2 for k in (0,1)];_,index,station,_=t.edge(old,center);p,z,_,_=t.frame(old,index);newp,newz,_,_=t.frame(a,index);station=station/g.distance(p,z)*g.distance(newp,newz)
            width=g.distance(b['points'][0],b['points'][1]);depth=g.distance(b['points'][1],b['points'][2]);b['points']=t.quad(a,index,station,width,depth);changed.add(b['id'])
        building_collisions(scene,changed)
