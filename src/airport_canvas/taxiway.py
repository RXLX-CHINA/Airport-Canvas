#!/usr/bin/env python3
"""Connected taxiway sketches with circular transitions and union pavement edges.

direction uses screen coordinates: 0=right, 90=down. Child position is the
arc-length station where its turn STARTS on the parent's centerline.
length includes the turning arc. This is a geometric sketch, not swept-path approval.
"""
import argparse
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from common import number, boolean, parse_color, image, check_size, scale_value

def meter2pixel(m,scale): return int(round(m*scale))

def rotate_point(x,y,angle_deg):
    a=math.radians(angle_deg)
    return x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a)

class Taxiway:
    def __init__(self,direction=0,width=10,length=100,children=None,turn_radius=20,
                 is_rapid=False,angle=0,code_number=None):
        self.direction=number(direction,'direction',minimum=-360)%360
        self.width=number(width,'width',positive=True)
        self.length=number(length,'length',positive=True)
        self.turn_radius=number(turn_radius,'turn_radius',positive=True)
        if self.turn_radius<=self.width/2: raise ValueError('turn_radius must exceed half width')
        self.is_rapid=boolean(is_rapid,'is_rapid'); self.angle=number(angle,'angle')
        if is_rapid and not 25<=self.angle<=45: raise ValueError('Rapid exit angle must be 25..45 degrees')
        if code_number is not None and (type(code_number) is not int or code_number not in (1,2,3,4)):
            raise ValueError('code_number must be integer 1..4')
        self.code_number=code_number
        self.children=list(children or [])
        self.start_x=self.start_y=self.end_x=self.end_y=0
        self.rect=None

    def add_child(self,taxiway,side,position,is_rapid=None,angle=None):
        if side not in ('L','R'): raise ValueError('side must be L/R')
        position=self.resolve_position(position)
        rapid=taxiway.is_rapid if is_rapid is None else boolean(is_rapid,'is_rapid')
        angle=taxiway.angle if angle is None else number(angle,'angle')
        if rapid and not 25<=angle<=45: raise ValueError('Rapid exit angle must be 25..45 degrees')
        self.children.append(dict(taxiway=taxiway,side=side,position={'meters':position},is_rapid=rapid,angle=angle))
        return self

    def resolve_position(self,value):
        if isinstance(value,dict):
            if set(value)=={'fraction'}: pos=number(value['fraction'],'fraction')*self.length
            elif set(value)=={'meters'}: pos=number(value['meters'],'position')
            else: raise ValueError('position object needs exactly meters or fraction')
        else:
            pos=number(value,'position')
            # Legacy fractional positions; new configs should use explicit units.
            if isinstance(value,float) and 0<value<1: pos*=self.length
        if not 0<=pos<=self.length: raise ValueError('Child position outside parent')
        return pos

    def to_dict(self):
        return dict(direction=self.direction,width=self.width,length=self.length,
                    turn_radius=self.turn_radius,is_rapid=self.is_rapid,angle=self.angle,
                    code_number=self.code_number,children=[dict(taxiway=c['taxiway'].to_dict(),
                    side=c['side'],position=c['position'],is_rapid=c['is_rapid'],angle=c['angle']) for c in self.children])

    @classmethod
    def from_dict(cls,data):
        allowed={'direction','width','length','turn_radius','is_rapid','angle','children','code_number'}
        if set(data)-allowed: raise ValueError(f'Unknown taxiway keys: {sorted(set(data)-allowed)}')
        obj=cls(**{k:v for k,v in data.items() if k!='children'})
        for child in data.get('children',[]):
            if set(child)-{'taxiway','side','position','is_rapid','angle'}: raise ValueError('Unknown child keys')
            obj.add_child(cls.from_dict(child['taxiway']),child['side'],child['position'],child.get('is_rapid'),child.get('angle'))
        return obj

class TaxiwayDraw:
    def __init__(self,taxiway,scale=1,bgcolor=(0,0,0,0),taxiway_color=(100,100,100,255),
                 edge_color=(255,255,0,255),center_color=(255,255,0,255)):
        self.taxiway=taxiway; self.scale=scale_value(scale); self.bgcolor=bgcolor
        self.taxiway_color=taxiway_color; self.edge_color=edge_color; self.center_color=center_color

    def m2p(self,m): return meter2pixel(m,self.scale)

    def layout(self):
        layouts=[]; visited=set()
        def walk(obj,start,heading,turn=0,rapid=False,inherited_code=None):
            if id(obj) in visited: raise ValueError('Taxiway graph must be a tree without cycles/shared nodes')
            visited.add(id(obj))
            radius=obj.turn_radius; arc=abs(math.radians(turn))*radius
            if arc>obj.length: raise ValueError('Taxiway length is shorter than turning arc; increase length or reduce radius')
            code=obj.code_number or inherited_code
            if rapid and code is not None and radius<(550 if code in (3,4) else 275):
                raise ValueError('Rapid exit radius below recommended MH5001 table 4.9.10 value; review aircraft/speed design')
            sign=1 if turn>=0 else -1; sweep=abs(math.radians(turn))
            def point_at(station):
                if arc and station<=arc:
                    theta=station/radius
                    x=radius*math.sin(theta); y=sign*radius*(1-math.cos(theta))
                    tangent=heading+math.degrees(theta)*sign
                else:
                    x=radius*math.sin(sweep)+(station-arc)*math.cos(sweep)
                    y=sign*(radius*(1-math.cos(sweep))+(station-arc)*math.sin(sweep))
                    tangent=heading+turn
                x,y=rotate_point(x,y,heading)
                return (start[0]+x,start[1]+y),tangent
            # <=1 degree per arc sample, straight parts need only their endpoints.
            steps=max(1,math.ceil(abs(turn)))
            stations=[arc*i/steps for i in range(steps+1)] if arc else [0]
            if obj.length>arc: stations.append(obj.length)
            points=[point_at(st)[0] for st in stations]
            obj.start_x,obj.start_y=points[0]; obj.end_x,obj.end_y=points[-1]
            record=dict(taxiway=obj,points=points,stations=stations,start_heading=heading,
                        end_heading=heading+turn,turn=turn,arc_length=arc)
            layouts.append(record)
            for child in obj.children:
                if child['side'] not in ('L','R'): raise ValueError('side must be L/R')
                station=obj.resolve_position(child['position'])
                position,tangent=point_at(station)
                signed=(-1 if child['side']=='L' else 1)*(child['angle'] if child['is_rapid'] else 90)
                walk(child['taxiway'],position,tangent,signed,child['is_rapid'],code)
        walk(self.taxiway,(0,0),self.taxiway.direction,inherited_code=self.taxiway.code_number)
        return layouts

    def render(self):
        layout=self.layout(); s=self.scale
        xmin=min(x-r['taxiway'].width/2 for r in layout for x,y in r['points'])-2
        xmax=max(x+r['taxiway'].width/2 for r in layout for x,y in r['points'])+2
        ymin=min(y-r['taxiway'].width/2 for r in layout for x,y in r['points'])-2
        ymax=max(y+r['taxiway'].width/2 for r in layout for x,y in r['points'])+2
        size=(math.ceil((xmax-xmin)*s)+1,math.ceil((ymax-ymin)*s)+1)
        check_size(size)
        def p(pt): return round((pt[0]-xmin)*s),round((pt[1]-ymin)*s)
        mask=image(size,0,'L'); md=ImageDraw.Draw(mask)
        for r in layout:
            pts=[p(pt) for pt in r['points']]
            width=max(1,round(r['taxiway'].width*s))
            md.line(pts,fill=255,width=width,joint='curve')
            # Round joins inside each corridor; true exposed edges derived from the union below.
            for x,y in pts:
                rad=width/2
                md.ellipse((round(x-rad),round(y-rad),round(x+rad),round(y+rad)),fill=255)
        out=image(size,self.bgcolor)
        pavement=image(size,self.taxiway_color); out.paste(pavement,(0,0),mask)
        # Both yellow lines lie within the union, so no parent edge crosses a junction.
        line_px=max(1,math.ceil(.15*s)); gap_px=max(1,math.ceil(.15*s))
        def erode(pixels):
            return mask.filter(ImageFilter.MinFilter(2*pixels+1)) if pixels else mask
        outer=ImageChops.subtract(mask,erode(line_px))
        inner=ImageChops.subtract(erode(line_px+gap_px),erode(2*line_px+gap_px))
        edges=ImageChops.lighter(outer,inner)
        out.paste(image(size,self.edge_color),(0,0),edges)
        d=ImageDraw.Draw(out)
        for r in layout:
            pts=[p(pt) for pt in r['points']]
            # Contrast border for shallow/light pavement; no disconnected crossing bars.
            if sum(self.taxiway_color[:3])/3>150:
                d.line(pts,fill='black',width=max(3,math.ceil(.25*s)),joint='curve')
            d.line(pts,fill=self.center_color,width=max(1,math.ceil(.15*s)),joint='curve')
        return out

    def draw(self,canvas):
        out=self.render()
        if out.width>canvas.width or out.height>canvas.height:
            raise ValueError('Canvas too small; use render() or a larger canvas')
        canvas.alpha_composite(out,((canvas.width-out.width)//2,(canvas.height-out.height)//2))

    def compliance_report(self):
        self.layout()
        return dict(status='NOT_CERTIFIED',limitations=[
            'Taxiway-only sketch: no runway connection, holding positions or enhanced centerlines modeled',
            'Aircraft swept path, main-wheel clearance, shoulder, stopping distance and pavement not certified',
            'Rapid radius recommendations checked only when code_number is supplied',
            'Child position denotes beginning of turn on parent centerline; length includes arc'])

def generate_test_json():
    root=Taxiway(length=100,width=10)
    child=Taxiway(length=50,width=10,turn_radius=20)
    root.add_child(child,'R',{'meters':50})
    root.add_child(Taxiway(length=60,width=10,turn_radius=20,is_rapid=True,angle=30),'L',{'fraction':.8})
    child.add_child(Taxiway(length=40,width=8,turn_radius=15),'L',{'meters':30})
    return root

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-f','--file'); parser.add_argument('-o','--output',default='taxiway.png')
    parser.add_argument('--scale',type=float,default=1)
    parser.add_argument('--bgcolor',type=parse_color,default=(0,0,0))
    parser.add_argument('--report')
    args=parser.parse_args()
    try:
        taxiway=Taxiway.from_dict(json.loads(Path(args.file).read_text(encoding='utf-8'))) if args.file else generate_test_json()
        drawer=TaxiwayDraw(taxiway,args.scale); result=drawer.render()
        canvas=image(result.size,args.bgcolor+(255,)); canvas.alpha_composite(result); canvas.save(args.output,'PNG')
        if args.report: Path(args.report).write_text(json.dumps(drawer.compliance_report(),indent=2),encoding='utf-8')
        print(f'Saved {args.output}: {canvas.width}x{canvas.height}. NOT_CERTIFIED; see README.md')
    except (ValueError,OSError,TypeError,KeyError,json.JSONDecodeError) as exc:
        parser.exit(2,f'Error: {exc}\n')

if __name__=='__main__': main()
