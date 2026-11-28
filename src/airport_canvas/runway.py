#!/usr/bin/env python3
"""Runway marking planner/renderer. All geometry is in metres; not an airport certificate."""
import argparse
import inspect
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from common import number, boolean, parse_color, image, check_size, scale_value

BASE = Path(__file__).resolve().parent

def parse_ma(value):
    s = str(value).strip()
    if not s.isascii() or not s.isdigit() or len(s) > 3:
        raise ValueError('ma must be runway number 01..36 or magnetic heading 000..360')
    n = int(s)
    if len(s) == 3 or n > 36:
        if n > 360: raise ValueError('magnetic heading must be 000..360')
        return f'{n:03d}', 'heading'
    return f'{36 if n == 0 else n:02d}', 'number'

def code_for_reference(length):
    return 1 if length < 800 else 2 if length < 1200 else 3 if length < 1800 else 4

def pair_count(distance):
    for limit, count in ((900,1),(1200,2),(1500,3),(2400,4)):
        if distance < limit: return count
    return 6

def aim_dimensions(lda,mark_width=None,inner_gap=None,mark_length=None):
    # Table 6.2.5 permits ranges. Prefer their compact end, not all maxima.
    if lda<800:start,lengths,widths,gaps=150,(30,45),(4,4),(6,6)
    elif lda<1200:start,lengths,widths,gaps=250,(30,45),(6,6),(9,9)
    elif lda<2400:start,lengths,widths,gaps=300,(45,60),(6,10),(18,22.5)
    else:start,lengths,widths,gaps=400,(45,60),(6,10),(18,22.5)
    chosen=[]
    for value,limits,name in ((mark_length,lengths,'aim length'),(mark_width,widths,'aim width'),(inner_gap,gaps,'aim inner gap')):
        value=limits[0] if value is None else value
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not limits[0]<=value<=limits[1]:raise ValueError(f'{name} must be within {limits[0]}..{limits[1]} m (table 6.2.5)')
        chosen.append(value)
    return start,*chosen

def threshold_geometry(width):
    counts={18:4,23:6,30:8,45:12,60:16}
    # Table 6.2.4-1 ends at 16 total stripes. For unlisted widths,
    # approximate the 1.8 m stripe-and-gap spacing without exceeding that count.
    n=counts.get(width,min(counts[60],max(2,2*round(width/7.2))))
    stripe=min(1.8,min(width,54)/(2*n))
    if stripe<=0: raise ValueError('Width too small for threshold markings')
    # Central gap is twice the ordinary gap, all measured between stripe edges.
    return n,stripe

def centerline_geometry(extent):
    if extent<30: return 0,0,0
    candidates=[]
    for n in range(2,int(extent/30)+1):
        lower=max(50,extent/n)
        upper=min(75,(extent-30)/(n-1),2*extent/(2*n-1))
        if upper+1e-9<lower: continue
        seg=extent-(n-1)*upper; gap=n*upper-extent
        candidates.append((abs(seg-gap),n,seg,gap))
    if not candidates: return 1,extent,0
    _,n,seg,gap=min(candidates)
    return n,seg,gap

class Runway:
    def __init__(self, length, width, level, ma, ma_type=None, att=None, add=False,
                 maxspan=None, ald=None, touchzone=None, touchzoneencode=True,
                 ltemp=False, ld=0, htemp=False, hd=0, shoulder=None,
                 shouldermark=False, lturnover=None, hturnover=None,
                 lstopway=0, hstopway=0, turnover_width=None, turnover_length=170,
                 code_number=None, reference_field_length=None, code_letter=None,
                 ald_small=None, ald_large=None, aimpoint_small=None, aimpoint_large=None):
        self.length=number(length,'length',positive=True)
        self.width=number(width,'width',positive=True)
        if isinstance(level,bool) or str(level).lower() not in ('v','0','1','2','3'):
            raise ValueError('level must be v/0/1/2/3')
        self.level=str(level).lower()
        self.ma,self.ma_type=parse_ma(ma)
        if ma_type is not None and ma_type != self.ma_type:
            raise ValueError('ma_type conflicts with ma; use 3 digits for heading')
        self.add=boolean(add,'add')
        self.att=att.upper() if isinstance(att,str) else att
        if self.att not in (None,'L','R','C'): raise ValueError('att must be L/R/C')
        self.ld=number(ld,'ld'); self.hd=number(hd,'hd')
        if self.ld+self.hd>=self.length: raise ValueError('ld + hd must be smaller than length')
        self.ltemp=boolean(ltemp,'ltemp'); self.htemp=boolean(htemp,'htemp')
        if (ltemp and not ld) or (htemp and not hd): raise ValueError('temporary threshold needs displacement > 0')
        self.shoulder=number(shoulder if shoulder is not None else 0,'shoulder')
        self.shouldermark=boolean(shouldermark,'shouldermark')
        if shouldermark and self.shoulder<1: raise ValueError('shouldermark needs shoulder >= 1m')
        for name,value in (('lturnover',lturnover),('hturnover',hturnover)):
            if value not in (None,'L','R'): raise ValueError(f'{name} must be L/R')
        self.lturnover=lturnover; self.hturnover=hturnover
        self.turnover_width=number(turnover_width if turnover_width is not None else width,'turnover_width',positive=True)
        self.turnover_length=number(turnover_length,'turnover_length',positive=True)
        if (lturnover or hturnover) and self.turnover_length>self.length:
            raise ValueError('turnover_length cannot exceed runway length')
        self.lstopway=number(lstopway,'lstopway'); self.hstopway=number(hstopway,'hstopway')
        self.touchzoneencode=boolean(touchzoneencode,'touchzoneencode')
        if touchzone is not None and (type(touchzone) is not int or not 1<=touchzone<=6):
            raise ValueError('touchzone must be integer 1..6 or null for automatic')
        self.touchzone=touchzone
        self.reference_field_length=None if reference_field_length is None else number(reference_field_length,'reference_field_length',positive=True)
        if code_number is not None and (type(code_number) is not int or code_number not in (1,2,3,4)):
            raise ValueError('code_number must be integer 1..4')
        derived=code_for_reference(self.reference_field_length) if self.reference_field_length is not None else None
        if code_number is not None and derived is not None and code_number!=derived:
            raise ValueError('code_number conflicts with reference_field_length')
        self.fa_indicator_I=code_number if code_number is not None else derived
        if self.level=='v' and self.fa_indicator_I is None:
            raise ValueError('Non-instrument runway needs code_number or reference_field_length to determine TDZ applicability')
        self.maxspan=None if maxspan is None else number(maxspan,'maxspan',positive=True)
        if self.maxspan is not None and self.maxspan>=80: raise ValueError('maxspan >= 80m outside supported A..F')
        derived_letter=None
        if self.maxspan is not None:
            derived_letter=next(letter for limit,letter in ((15,'A'),(24,'B'),(36,'C'),(52,'D'),(65,'E'),(80,'F')) if self.maxspan<limit)
        if code_letter is not None:
            code_letter=str(code_letter).upper()
            if code_letter not in ('A','B','C','D','E','F'): raise ValueError('code_letter must be A..F')
            if derived_letter and code_letter!=derived_letter: raise ValueError('code_letter conflicts with maxspan')
        self.fa_indicator_II=code_letter or derived_letter
        self.ald=ald
        for name,value,maximum in (('ald_small',ald_small,self.length-self.ld),('ald_large',ald_large,self.length-self.hd)):
            result=number(value if value is not None else ald if ald is not None else maximum,name,positive=True)
            if result>maximum: raise ValueError(f'{name} exceeds physical landing length {maximum}')
            setattr(self,name,result)
        self.aimpoint_small=aimpoint_small; self.aimpoint_large=aimpoint_large
        for name,lda in (('aimpoint_small',self.ald_small),('aimpoint_large',self.ald_large)):
            val=getattr(self,name)
            if val is not None:
                val=number(val,name,positive=True)
                if val<aim_dimensions(lda)[0] or val+aim_dimensions(lda)[1]>lda: raise ValueError(f'{name} outside permitted landing distance')
                setattr(self,name,val)
        self._compute_designators()
        self.marking_plan()

    def _compute_designators(self):
        if self.ma_type=='heading':
            n=int(float(self.ma)/10+.5)%36 or 36; heading=float(self.ma)%360
        else:
            n=int(self.ma); heading=n*10%360
        if self.add: n=n%36+1
        other=(n+17)%36+1
        self.designator_small=min(n,other); self.designator_large=max(n,other)
        self.suffix_small=self.att or ''
        self.suffix_large={'L':'R','R':'L','C':'C','':''}[self.suffix_small]
        if n==self.designator_large:
            self.suffix_small,self.suffix_large=self.suffix_large,self.suffix_small
        self.large_heading=(heading if n==self.designator_large else heading+180)%360

    def marking_plan(self):
        span=self.length-self.ld-self.hd
        tdz=self.level!='v' or self.fa_indicator_I in (3,4)
        nominal=pair_count(span)
        if self.touchzone is not None and (not tdz or self.touchzone!=nominal):
            raise ValueError(f'touchzone conflicts with standard; use null (automatic), expected {nominal if tdz else 0}')
        ends=[]
        for end,offset,lda,aim in (('small',self.ld,self.ald_small,self.aimpoint_small),('large',self.hd,self.ald_large,self.aimpoint_large)):
            start,length,width,sep=aim_dimensions(lda)
            start=start if aim is None else aim
            if start+length>lda: raise ValueError(f'{end}: landing distance too short for aiming point')
            marks=[]
            for i in range(nominal if tdz else 0):
                pos=150*(i+1)
                # Omit conflict; never move the 150m station grid.
                if pos+22.5>span or (pos<=start+length+50 and pos+22.5>=start-50): continue
                marks.append({'distance':pos,'bars':(3,3,2,2,1,1)[i] if self.touchzoneencode else 1})
            ends.append(dict(end=end,displacement=offset,lda=lda,aim_start=start,aim_length=length,
                             aim_width=width,separation=sep,tdz=marks,nominal_pairs=nominal if tdz else 0))
        stripe_count,stripe_width=threshold_geometry(self.width)
        return {'ends':ends,'threshold_count':stripe_count,'threshold_width':stripe_width,'edge_offset':min(self.width/2,30),
                'center_width':.9 if self.level in ('2','3') else .45 if self.level=='1' or
                   (self.level=='0' and self.fa_indicator_I not in (1,2)) else .3}

    def compliance_report(self):
        missing=[]
        if self.fa_indicator_I is None:
            missing.append('Missing aircraft code_number/reference_field_length: non-instrument TDZ applicability unknown')
        if self.fa_indicator_II is None: missing.append('Missing aircraft code_letter/maxspan')
        if self.lturnover or self.hturnover:
            missing.append('Turn pad schematic only: aircraft wheelbase/steering/swept wheel clearance unverified')
        if self.shouldermark: missing.append('Shoulder hatching schematic only; site-specific design review required')
        if self.width<18: missing.append('Runway width below 18m: outside supported standard-width table')
        if self.fa_indicator_II in ('C','D','E','F') and self.shoulder==0:
            missing.append('Known design issue: code C/D/E/F runway requires shoulders (4.2.1)')
        missing.extend(['Widths/shoulders/declared distances need aircraft and airport design review',
                        'PAPI/VASIS, pavement, RESA, strips, obstacles, lights and intersections not certified'])
        return dict(status='NOT_CERTIFIED',basis='MH5001-2021 marking subset, amendments I-IV; V effective 2027-05-01',limitations=missing)

    def __str__(self):
        return f'Runway {self.designator_small:02}{self.suffix_small}/{self.designator_large:02}{self.suffix_large}'

def runway_generator(**kwargs):
    return Runway(**kwargs)

class RunwayDraw:
    def __init__(self,runwayobj,scale=1,bgcolor=(0,0,0,0),edge=False,
                 runway_color=(64,64,64,255),stopway_color=(128,128,128,255)):
        self.rwy=runwayobj; self.scale=scale_value(scale); self.bgcolor=bgcolor
        self.edge=edge; self.runway_color=runway_color; self.stopway_color=stopway_color
        self.font_path=BASE/'CAAC_Runway_Code_Font.ttf'

    def meter2pixel(self,m): return int(round(m*self.scale))

    def _get_font(self,size_m):
        try: return ImageFont.truetype(str(self.font_path),max(1,self.meter2pixel(size_m)))
        except OSError as exc: raise ValueError(f'Required runway font missing: {self.font_path}') from exc

    def _label(self,num,suffix):
        try: font=ImageFont.truetype(str(self.font_path),180)
        except OSError as exc: raise ValueError(f'Required runway font missing: {self.font_path}') from exc
        def glyph(text):
            left,top,right,bottom=font.getbbox(text)
            out=image((right-left,bottom-top)); ImageDraw.Draw(out).text((-left,-top),text,font=font,fill='white')
            h=max(1,self.meter2pixel(9))
            return out.resize((max(1,round(out.width*h/out.height)),h),Image.Resampling.LANCZOS)
        digits=glyph(num)
        if not suffix: return digits
        letter=glyph(suffix); gap=self.meter2pixel(6)
        out=image((max(digits.width,letter.width),digits.height+gap+letter.height))
        out.alpha_composite(digits,((out.width-digits.width)//2,0))
        out.alpha_composite(letter,((out.width-letter.width)//2,digits.height+gap))
        return out

    @staticmethod
    def arrow_positions(start,end,length=30):
        available=end-start
        if available<length: return []
        n=max(1,int((available+30)//(length+30)))
        used=n*length+(n-1)*30; first=start+(available-used)/2
        return [first+i*(length+30) for i in range(n)]

    def _bounds(self):
        r=self.rwy; left=-r.width/2-r.shoulder; right=-left
        for side in (r.lturnover,r.hturnover):
            if side=='L': left=min(left,-r.width/2-r.turnover_width)
            if side=='R': right=max(right,r.width/2+r.turnover_width)
        return left-3,-r.lstopway-3,right+3,r.length+r.hstopway+3

    def pad_path(self,side,top):
        """Continuous schematic loop; endpoint tangents differ by 180 degrees.

        Use an eased <=30-degree divergence, straight lead-in and semicircle.
        Aircraft-specific swept clearance still requires a separate review.
        """
        r=self.rwy; sign=-1 if side=='L' else 1
        straight=10
        radius=min((r.width/2+r.turnover_width-2)/2,
                   (r.turnover_length-straight-4)/(2+3/math.tan(math.radians(30))))
        if radius<=0: raise ValueError('Turn pad too short for a continuous 180-degree guide')
        divergence=3*radius/math.tan(math.radians(30))
        y_circle=radius+2; y_turn=y_circle+straight; y_start=y_turn+divergence
        lead=60 if r.fa_indicator_I in (3,4) else 30
        far=min(r.length,y_start+lead)
        pts=[(.9,far),(.9,y_start)]
        for i in range(1,101):
            t=i/100; ease=3*t*t-2*t*t*t
            pts.append((.9+2*radius*ease,y_start-divergence*t))
        pts.append((.9+2*radius,y_circle))
        for i in range(1,181):
            t=i/180*math.pi
            pts.append((.9+radius+radius*math.cos(t),y_circle-radius*math.sin(t)))
        pts.append((.9,far))
        return [(sign*x,y if top else r.length-y) for x,y in pts]

    def render(self):
        r=self.rwy; s=self.scale; xmin,ymin,xmax,ymax=self._bounds()
        size=(math.ceil((xmax-xmin)*s)+1,math.ceil((ymax-ymin)*s)+1)
        angle=-r.large_heading%360; rad=math.radians(angle)
        check_size(size)
        check_size((math.ceil(abs(size[0]*math.cos(rad))+abs(size[1]*math.sin(rad)))+2,
                    math.ceil(abs(size[0]*math.sin(rad))+abs(size[1]*math.cos(rad)))+2))
        out=image(size); d=ImageDraw.Draw(out)
        def p(x,y): return round((x-xmin)*s),round((y-ymin)*s)
        def rect(x1,y1,x2,y2,fill='white'):
            a,b=p(min(x1,x2),min(y1,y2)); c,e=p(max(x1,x2),max(y1,y2))
            d.rectangle((a,b,max(a,c-1),max(b,e-1)),fill=fill)
        def line(points,color='white',width=.3):
            d.line([p(x,y) for x,y in points],fill=color,width=max(1,round(width*s)),joint='curve')
        rect(-r.width/2-r.shoulder,0,r.width/2+r.shoulder,r.length,self.runway_color)
        for lo,hi in ((-r.lstopway,0),(r.length,r.length+r.hstopway)):
            if lo==hi: continue
            rect(-r.width/2,lo,r.width/2,hi,self.stopway_color)
            if hi-lo>=60:
                direction=1 if hi==0 else -1
                first=lo+r.width/2+1 if direction==1 else lo+1
                last=hi-1 if direction==1 else hi-r.width/2-1
                for y in range(math.ceil(first),math.floor(last)+1,30):
                    line([(-r.width/2+1,y-direction*r.width/2),(0,y),
                          (r.width/2-1,y-direction*r.width/2)],'yellow',1)
        if r.shouldermark:
            for side in (-1,1):
                for y in range(0,math.ceil(r.length),30):
                    line([(side*(r.width/2+.5),y),(side*(r.width/2+r.shoulder-.5),min(r.length,y+r.shoulder-1))],'yellow',.9)
        for side,top in ((r.lturnover,True),(r.hturnover,False)):
            if side is None: continue
            sign=-1 if side=='L' else 1
            a,b=sorted((sign*r.width/2,sign*(r.width/2+r.turnover_width)))
            ya,yb=(0,r.turnover_length) if top else (r.length-r.turnover_length,r.length)
            rect(a,ya,b,yb,self.runway_color)
            line(self.pad_path(side,top),'yellow',.15)
        plan=r.marking_plan(); edgew=.9 if r.width>=30 else .45
        for side in (-1,1):
            e=side*plan['edge_offset']
            rect(e if side<0 else e-edgew,0,e+edgew if side<0 else e,r.length)
        n,stripe=threshold_geometry(r.width)
        for entry in plan['ends']:
            top=entry['end']=='small'; threshold=r.ld if top else r.length-r.hd
            direction=1 if top else -1
            def yy(distance): return threshold+direction*distance
            if entry['displacement']:
                rect(-r.width/2,threshold-.9,r.width/2,threshold+.9)
                temp=r.ltemp if top else r.htemp; h=10.2 if r.width<=18 else 12
                if temp:
                    count={18:3,23:3,30:4,45:5,60:7}.get(r.width,max(1,round(r.width/9)))
                    for j in range(count):
                        x=(j-(count-1)/2)*r.width/count
                        line([(x-2,yy(-2.4-h)),(x,yy(-2.4)),(x+2,yy(-2.4-h))],width=1)
                for near in self.arrow_positions(32 if temp else 12.2,entry['displacement']):
                    line([(-1.5,yy(-near-12)),(0,yy(-near)),(1.5,yy(-near-12))],width=1)
                    line([(0,yy(-near-10)),(0,yy(-near-30))],width=.3)
            for side in (-1,1):
                for j in range(n//2):
                    x=side*(1.5*stripe+j*2*stripe)
                    rect(x-stripe/2,yy(6),x+stripe/2,yy(51))
            sep=entry['separation']; aw=entry['aim_width']
            for side in (-1,1):
                a,b=sorted((side*sep/2,side*(sep/2+aw)))
                if max(abs(a),abs(b))>r.width/2: raise ValueError('Aiming point exceeds width; review width/LDA')
                rect(a,yy(entry['aim_start']),b,yy(entry['aim_start']+entry['aim_length']))
                for mark in entry['tdz']:
                    sw=1.8 if r.touchzoneencode else 3
                    for j in range(mark['bars']):
                        a,b=sorted((side*(sep/2+j*(sw+1.5)),side*(sep/2+j*(sw+1.5)+sw)))
                        if max(abs(a),abs(b))>r.width/2: raise ValueError('TDZ exceeds width; review width/LDA/encoding')
                        rect(a,yy(mark['distance']),b,yy(mark['distance']+22.5))
            num=r.designator_small if top else r.designator_large
            suffix=r.suffix_small if top else r.suffix_large
            label=self._label(f'{num:02}',suffix)
            if top: label=label.rotate(180)
            x,y=p(0,yy(63)-(0 if top else label.height/s))
            out.alpha_composite(label,(x-label.width//2,y))
        extra=24 if r.suffix_small or r.suffix_large else 9
        first=r.ld+63+extra+12; last=r.length-r.hd-63-extra-12; extent=last-first
        if extent>=30:
            n,seg,gap=centerline_geometry(extent)
            y=first
            for _ in range(n):
                w=plan['center_width']; rect(-w/2,y,w/2,y+seg); y+=seg+gap
        return out.rotate(angle,expand=True,resample=Image.Resampling.BICUBIC)

    def draw(self,canvas):
        rendered=self.render()
        if rendered.width>canvas.width or rendered.height>canvas.height:
            raise ValueError('Canvas too small; use render() or a larger canvas')
        canvas.alpha_composite(rendered,((canvas.width-rendered.width)//2,(canvas.height-rendered.height)//2))

def str_to_bool(value):
    if value.lower() in ('true','1','yes','y'): return True
    if value.lower() in ('false','0','no','n'): return False
    raise argparse.ArgumentTypeError('Expected true/false')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-f','--file'); parser.add_argument('-o','--output',default='runway.png')
    parser.add_argument('--scale',type=float,default=1)
    parser.add_argument('--bgcolor',type=parse_color,default=(0,0,0))
    parser.add_argument('--bg',type=parse_color); parser.add_argument('--stopwaybg',type=parse_color)
    parser.add_argument('--report',help='JSON marking plan and limitations')
    numeric={'length','width','maxspan','ald','ld','hd','shoulder','turnover_width','turnover_length',
             'lstopway','hstopway','reference_field_length','ald_small','ald_large','aimpoint_small','aimpoint_large'}
    integers={'code_number','touchzone'}; booleans={'add','touchzoneencode','ltemp','htemp','shouldermark'}
    keys=set(inspect.signature(Runway).parameters)-{'ma_type'}
    for key in sorted(keys):
        if key in booleans:
            parser.add_argument('--'+key,nargs='?',const=True,type=str_to_bool,default=None)
            parser.add_argument('--no-'+key,dest=key,action='store_false',default=None)
        else: parser.add_argument('--'+key,type=float if key in numeric else int if key in integers else str,default=None)
    args=parser.parse_args()
    try:
        params=json.loads(Path(args.file).read_text(encoding='utf-8')) if args.file else {}
        unknown=set(params)-keys-{'bg','stopwaybg'}
        if unknown: raise ValueError(f'Unknown keys: {sorted(unknown)}')
        for key in keys:
            if getattr(args,key) is not None: params[key]=getattr(args,key)
        bg=parse_color(args.bg if args.bg is not None else params.pop('bg',(64,64,64)))
        stop=parse_color(args.stopwaybg if args.stopwaybg is not None else params.pop('stopwaybg',(128,128,128)))
        params.pop('bg',None); params.pop('stopwaybg',None)
        runway=runway_generator(**params)
        result=RunwayDraw(runway,args.scale,runway_color=bg+(255,),stopway_color=stop+(255,)).render()
        canvas=image(result.size,args.bgcolor+(255,)); canvas.alpha_composite(result); canvas.save(args.output,'PNG')
        report={'runway':str(runway),'geometry':{key:getattr(runway,key) for key in
                ('length','width','shoulder','turnover_length','shouldermark','ld','hd')},
                'markings':runway.marking_plan(),'compliance':runway.compliance_report()}
        if args.report: Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Saved {args.output}: {canvas.width}x{canvas.height}. NOT_CERTIFIED; see --report / README.md')
    except (ValueError,OSError,TypeError,json.JSONDecodeError) as exc:
        parser.exit(2,f'Error: {exc}\n')

if __name__=='__main__': main()
