"""Solid exposed building edges and dashed component interfaces."""
from geometry11 import polygon,LineString,lines,unary_union
SHAPES={'RECTANGLE':'矩形','CIRCLE':'圆形','HEXAGON':'六边形','OCTAGON':'八边形','CUSTOM':'自定义多边形'}
def shape_label(value):return SHAPES.get(value,value)
def shape_value(value):return next((key for key,label in SHAPES.items() if label==value),value)

def outlines(buildings):
    shapes={a['id']:polygon(a['points']) for a in buildings};interfaces=[]
    for i,a in enumerate(buildings):
        boundary=shapes[a['id']].boundary
        for b in buildings[i+1:]:
            other=shapes[b['id']].boundary
            if not boundary.envelope.intersects(other.envelope.buffer(.000001)):continue
            # Buffering only for shared-edge detection tolerates affine roundoff.
            shared=boundary.intersection(other.buffer(.000001,cap_style=2,join_style=2))
            for line in lines(shared):
                if line.length>.0001:interfaces.append(line)
    common=unary_union(interfaces);mask=common.buffer(.00001,cap_style=2);out=[]
    for a in buildings:
        for line in lines(shapes[a['id']].boundary.difference(mask)):
            if line.length>.0001:out.append(dict(type='line',oid=a['id'],points=[list(q) for q in line.coords],stroke='#36576d',width=.35,building19=True))
    for line in lines(common):
        if line.length>.0001:out.append(dict(type='line',oid='BUILDING_INTERFACE20_3',points=[list(q) for q in line.coords],stroke='#36576d',width=.35,dash=[2,1.5],building19=True,building_interface20_3=True))
    return out
