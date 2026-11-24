"""Metre-based geometry; local X east/Y north, headings clockwise from north."""
import math
import bisect

class PathIndex:
    """One cumulative-length table for repeated station queries."""
    def __init__(self,points):
        self.points=points;self.stations=[0.]
        for a,b in zip(points,points[1:]):self.stations.append(self.stations[-1]+distance(a,b))
        self.length=self.stations[-1]
    def at(self,station):
        station=max(0,min(self.length,station));i=max(0,min(len(self.points)-2,bisect.bisect_right(self.stations,station)-1))
        a,b=self.points[i:i+2];u=unit(a,b);d=station-self.stations[i]
        return [a[0]+u[0]*d,a[1]+u[1]*d],u

    def subpath(self,start,end):
        if start>end:
            return list(reversed(self.subpath(end,start)))
        first,_=self.at(start)
        last,_=self.at(end)
        result=[first]
        begin=bisect.bisect_right(self.stations,start,1)
        stop=bisect.bisect_left(self.stations,end-1e-8,begin)
        for point in self.points[begin:stop]:
            if distance(result[-1],point)>1e-8:
                result.append(list(point))
        if distance(result[-1],last)>1e-8 or len(result)==1:
            result.append(last)
        return result

def simplify(points,tolerance=.004):
    if len(points)<3:return points
    a,b=points[0],points[-1];u=unit(a,b);best=0;index=0
    for i,p in enumerate(points[1:-1],1):
        d=abs((p[0]-a[0])*u[1]-(p[1]-a[1])*u[0])
        if d>best:best=d;index=i
    if best<=tolerance:return [a,b]
    return simplify(points[:index+1],tolerance)[:-1]+simplify(points[index:],tolerance)

def segment_box_interval(a,b,box):
    lo,hi=0.,1.
    for i in (0,1):
        d=b[i]-a[i];low=box[i];high=box[i+2]
        if abs(d)<1e-12:
            if not low<=a[i]<=high:return None
        else:
            x,y=sorted(((low-a[i])/d,(high-a[i])/d));lo=max(lo,x);hi=min(hi,y)
            if lo>hi:return None
    return lo,hi

def distance(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])
def length(points): return sum(distance(a,b) for a,b in zip(points,points[1:]))
def unit(a,b):
    d=distance(a,b)
    return ((b[0]-a[0])/d,(b[1]-a[1])/d) if d>1e-9 else (1.,0.)
def at(points,station):
    if not points or len(points)<2: raise ValueError('Path needs at least two points')
    total=length(points)
    if not -1e-7<=station<=total+1e-7: raise ValueError('Station outside path')
    station=max(0,min(total,station))
    for a,b in zip(points,points[1:]):
        d=distance(a,b)
        if d<1e-9: continue
        if station<=d+1e-8:
            u=unit(a,b)
            return [a[0]+u[0]*station,a[1]+u[1]*station],u
        station-=d
    return list(points[-1]),unit(points[-2],points[-1])
def project(points,p):
    best=(float('inf'),0,None); offset=0
    for a,b in zip(points,points[1:]):
        d=distance(a,b)
        if d<1e-9: continue
        u=unit(a,b); s=max(0,min(d,(p[0]-a[0])*u[0]+(p[1]-a[1])*u[1]))
        q=[a[0]+u[0]*s,a[1]+u[1]*s]
        candidate=(distance(q,p),offset+s,q)
        if candidate[0]<best[0]: best=candidate
        offset+=d
    return best
def line(center,span,heading):
    a=math.radians(heading); u=(math.sin(a),math.cos(a))
    return [[center[0]-u[0]*span/2,center[1]-u[1]*span/2],
            [center[0]+u[0]*span/2,center[1]+u[1]*span/2]]
def cubic(a,b,start_tangent,end_tangent,handle=None,steps=80):
    d=distance(a,b)
    if d<.01: return [list(a),list(b)]
    h=handle if handle is not None else d*.4
    c=[a[0]+start_tangent[0]*h,a[1]+start_tangent[1]*h]
    e=[b[0]-end_tangent[0]*h,b[1]-end_tangent[1]*h]
    return [[(1-t)**3*a[k]+3*(1-t)**2*t*c[k]+3*(1-t)*t*t*e[k]+t**3*b[k] for k in (0,1)]
            for t in [i/steps for i in range(steps+1)]]
def radius(points):
    result=float('inf')
    for a,b,c in zip(points,points[1:],points[2:]):
        twice=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
        if twice>1e-8: result=min(result,distance(a,b)*distance(b,c)*distance(c,a)/(2*twice))
    return result
def subpath(points,start,end):
    if start>end: return list(reversed(subpath(points,end,start)))
    first,_=at(points,start); last,_=at(points,end); result=[first]; offset=0
    for a,b in zip(points,points[1:]):
        offset+=distance(a,b)
        if start<offset<end-1e-8 and distance(result[-1],b)>1e-8: result.append(list(b))
    if distance(result[-1],last)>1e-8 or len(result)==1:result.append(last)
    return result
def rectangle(points,width):
    if len(points)!=2: raise ValueError('Rectangle requires straight axis')
    a,b=points; u=unit(a,b); n=(-u[1]*width/2,u[0]*width/2)
    return [[a[0]+n[0],a[1]+n[1]],[b[0]+n[0],b[1]+n[1]],
            [b[0]-n[0],b[1]-n[1]],[a[0]-n[0],a[1]-n[1]]]
def inside(p,poly):
    hit=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]: hit=not hit
    return hit
def crossing(a,b,c,d):
    def cross(u,v): return u[0]*v[1]-u[1]*v[0]
    u=(b[0]-a[0],b[1]-a[1]);v=(d[0]-c[0],d[1]-c[1]);w=(c[0]-a[0],c[1]-a[1])
    den=cross(u,v)
    if abs(den)<1e-10: return None
    t=cross(w,v)/den;s=cross(w,u)/den
    tolerance=1e-9
    if -tolerance<=t<=1+tolerance and -tolerance<=s<=1+tolerance:
        t=max(0.,min(1.,t))
        return [a[0]+t*u[0],a[1]+t*u[1]]
    return None
def simple_polygon(poly):
    if len(poly)<3: return False
    area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1])))/2
    if area<1: return False
    n=len(poly)
    for i in range(n):
        for j in range(i+1,n):
            if j in (i,(i+1)%n) or i==(j+1)%n: continue
            if crossing(poly[i],poly[(i+1)%n],poly[j],poly[(j+1)%n]): return False
    return True

def intersects_area(points,poly):
    return any(inside(p,poly) for p in points) or any(crossing(a,b,c,d) is not None
        for a,b in zip(points,points[1:]) for c,d in zip(poly,poly[1:]+poly[:1]))
