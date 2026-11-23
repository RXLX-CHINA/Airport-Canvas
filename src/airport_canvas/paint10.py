"""Global paint passes: surfaces, whole backings, all coloured paint and text."""
import math
import scene_geometry as g
from marking_catalog import BLACK

WAIT={'HOLD_A','HOLD_B','INTERMEDIATE','INTERMEDIATE_POINT'}
STAND_INK={'LEAD_IN','LEAD_IN_A','LEAD_IN_B','LEAD_IN_C','LEAD_IN_D','LEAD_OUT',
           'AUX_LEAD','STAND_STOP','STAND_NUMBER','UNGUIDED_STOP','ALIGNMENT','TURN_START'}

def plate(item,margin=.1):
    q=item['points'][0];angle=math.radians(item.get('rotation',0));u=[math.cos(angle),math.sin(angle)];v=[-u[1],u[0]]
    w=item.get('text_width') or len(item['text'])*item['size']*.65;h=item['size']
    return dict(type='polygon',oid=item['oid'],points=[[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in [(-w/2-margin,-h/2-margin),(w/2+margin,-h/2-margin),(w/2+margin,h/2+margin),(-w/2-margin,h/2+margin)]],fill=BLACK,black_underlay=True)

def outline_group(scene,oid,mark=None):
    mark=mark or scene.assets.get(oid,{})
    props=mark.get('props',{})
    kind=props.get('mark_type') or ''
    owner=mark.get('owner') or props.get('label_asset') or oid
    root=owner.split(':')[0]
    owner_kind=scene.assets.get(owner,scene.assets.get(root,{})).get('kind')
    if kind in STAND_INK:return 'stand'
    if kind in ('HELI_SAFETY','STAND_SAFETY','SAFETY_OVERLAP','BRIDGE_COMPOSITE','HYDRANT','PIT','SAFETY') or owner_kind=='STAND' or props.get('building_role19')=='BRIDGE':
        return 'safety'
    if owner_kind=='RUNWAY' or kind.startswith('RWY_') or kind in ('THRESHOLD_BAR','THRESHOLD_HEADS','DISPLACED_ARROW','CLOSED_RWY','AIMING_POINT','TDZ_BASIC','TDZ_CODED','PRETHRESHOLD'):
        return 'runway'
    if (owner_kind in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE') or root in scene.movements
            or oid.startswith('J:') or kind.startswith(('TWY_','HOLD_','INTERMEDIATE'))
            or kind in ('LOCATION','MANDATORY','CLOSED_TWY')):
        return 'taxi'
    return None


def set_outline_group(scene,key,enabled):
    from automatic_markings import generated_markings
    group=key.split('_')[1]
    generated=generated_markings(scene) if scene.data.get('generated_overrides') else {}
    with scene.transaction('统一设置描边'):
        meta=scene.data['meta']
        meta[key]=not enabled
        meta.setdefault('outline_group_defaults',{})[group]=enabled
        for oid,asset in scene.assets.items():
            if group=='stand' and asset['kind']=='STAND':
                asset['props']['stand_black_outline']=enabled
            if outline_group(scene,oid,asset)==group:
                asset['props']['white_outline' if group=='safety' else 'black_outline']=enabled
        for oid,movement in scene.movements.items():
            if outline_group(scene,oid)==group:movement['black_outline']=enabled
        for oid,mark in generated.items():
            if outline_group(scene,oid,mark)==group and not mark['props'].get('information_profile20_18'):
                override=scene.data['generated_overrides'].get(oid,{}).get('props',{})
                flag='white_outline' if group=='safety' else 'black_outline'
                if flag in override:override[flag]=enabled


def style(scene,items,generated=None):
    from scene_render import COLORS
    surfaces=[];under=[];ink=[];wait_done=set();aircraft_done=set();enhanced_done=set();generated=generated or {}
    aircraft_groups={};line_groups={}
    for item in items:
        if item.get('aircraft_label'):aircraft_groups.setdefault(item['oid'],[]).append(item)
        if item['type']=='line' and item.get('stroke')==COLORS['marking']:
            line_groups.setdefault(item['oid'],[]).append(item)
    def props(oid):
        if oid in scene.assets:return scene.assets[oid]['props']
        if oid in generated:
            a=generated[oid];base=scene.assets.get(a.get('owner'),{}).get('props',scene.movements.get(a.get('owner'),{}));return dict(base,**a['props'])
        if oid in scene.movements:return scene.movements[oid]
        root=oid.split(':')[0]
        if root in scene.assets:return scene.assets[root]['props']
        if root in scene.movements:return scene.movements[root]
        if oid.startswith('J:'):
            return next((a['props'] for aid,a in scene.assets.items() if aid in oid),{})
        return {}
    surface_colors=scene.data['meta'].get('surface_colors',{})
    for raw in items:
        item=dict(raw);oid=item.get('oid','');p=props(oid);kind=p.get('mark_type');fill=item.get('fill');surface=item.get('surface10') or item['type']=='polygon' and fill in (COLORS['runway'],COLORS['taxiway'],COLORS['apron'],COLORS['shoulder'])
        if surface:
            item['fill']=p.get('shoulder_color',fill) if fill==COLORS['shoulder'] else p.get('pavement_color',fill)
            if surface_colors:
                category={COLORS['runway']:'runway',COLORS['taxiway']:'taxiway',COLORS['apron']:'apron'}.get(fill)
                if fill==COLORS['shoulder']:
                    kind=scene.assets.get(oid.split(':')[0],{}).get('kind')
                    category={'RUNWAY':'runway','APRON':'apron'}.get(kind,'taxiway')
                    item['fill']=surface_colors.get(category+'_shoulder',item['fill'])
                elif category:
                    item['fill']=surface_colors.get(category+'_surface',item['fill'])
            item['surface11']=True;surfaces.append(item);continue
        meta=scene.data['meta']
        mark=generated.get(oid) or scene.assets.get(oid,{})
        group=outline_group(scene,oid,mark)
        policy=meta.get('outline_group_defaults',{})
        hide_black=group in ('runway','taxi') and meta.get(f'hide_{group}_outline21_2')
        outlined=not hide_black and (p.get('black_outline',False) or meta.get('guidance_black_outline',False))
        if group in ('runway','taxi') and group in policy:
            outlined=p.get('black_outline',policy[group])
        if item['type']=='text' and '未知' in item.get('text',''):
            outline_owner=scene.assets.get(mark.get('owner') or p.get('label_asset') or oid,{})
            outlined=(not meta.get('hide_taxi_outline21_2') and
                      outline_owner.get('props',{}).get('black_outline',policy.get('taxi',outlined)))
        if group=='stand':
            own=scene.assets.get(mark.get('owner'),{}).get('props',{})
            outlined=mark.get('props',{}).get('black_outline',
                         own.get('stand_black_outline',policy.get('stand',outlined)))
        if not outlined and (hide_black or group=='stand' and group in policy) and item.get('black_outline'):item['black_outline']=False
        if 'sign_board21_2' in item:
            ink.append(item);continue
        if kind=='LOCATION':
            owner=mark.get('owner') or p.get('label_asset')
            route=scene.assets.get(owner,{}).get('props',scene.movements.get(owner,{}))
            backing=not hide_black and route.get('black_outline',outlined)
            if item['type']=='polygon' and backing:
                # Keep the existing fill and yellow border above the wider black stroke.
                under.append(dict(item,fill=None,stroke=BLACK,
                                  width=item.get('width',.05)+.2,black_underlay=True))
            if item['type']=='text':
                item['black_outline']=False
                ink.append(item)
                continue
        if item['type']=='polygon' and fill in (BLACK,'#101010'):
            if outlined and kind in WAIT:continue
            under.append(dict(item,stroke=None))
            if item.get('stroke'):ink.append(dict(item,fill=None))
            continue
        if outlined and kind=='TWY_ENHANCED':
            if oid not in enhanced_done:
                from geometry11 import LineString,polygons,unary_union
                strips = [LineString(row['points']).buffer(.425,cap_style=2,join_style=1)
                          for row in line_groups.get(oid,()) if row.get('enhanced_axis21_2')]
                for polygon in polygons(unary_union(strips)):
                    under.append(dict(type='polygon',oid=oid,points=[list(q) for q in polygon.exterior.coords][:-1],fill='#101010',black_underlay=True,enhanced_backing11=True))
                enhanced_done.add(oid)
        elif (kind=='HELI_SAFETY' or item.get('stroke')=='#cf383e' or item.get('fill')=='#cf383e') and group!='stand' and (kind in ('HELI_SAFETY','STAND_SAFETY','SAFETY_OVERLAP','BRIDGE_COMPOSITE','HYDRANT','PIT','SAFETY') or generated.get(oid,{}).get('owner') in scene.assets and scene.assets[generated[oid]['owner']]['kind']=='STAND'):
            if p.get('white_outline',policy.get('safety',not meta.get('hide_safety_outline21_2'))):
                under.append(dict(item,fill=None,stroke='#ffffff',width=(item.get('width',.1) if item.get('stroke') else 0)+.1,black_underlay=True,white_red_outline11=True))
        elif outlined and kind in WAIT:
            if oid not in wait_done:
                mark=scene.assets.get(oid) or generated.get(oid)
                if mark:
                    pts=mark['points'];q=pts[0];u=g.unit(pts[0],pts[-1]);v=[-u[1],u[0]];half=1.15 if kind in ('HOLD_A','HOLD_B') else .25;span=p.get('width',18)/2+.1
                    if kind=='INTERMEDIATE':q,_=g.at(pts,g.length(pts)/2);u,v=v,[-v[1],v[0]];span=g.length(pts)/2+.1
                    under.append(dict(type='polygon',oid=oid,points=[[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in [(-half,-span),(half,-span),(half,span),(-half,span)]],fill=BLACK,black_underlay=True))
                wait_done.add(oid)
        elif outlined and kind in ('HYDRANT','PIT') and item['type']=='text':
            pass
        elif outlined:
            if item['type']=='line' and item.get('stroke') not in (None,BLACK,'#101010'):
                under.append(dict(item,stroke='#101010',width=item.get('width',.15)+.1,black_underlay=True))
            elif item['type']=='polygon' and (fill or item.get('stroke')):
                under.append(dict(item,fill=None,stroke='#101010',width=(item.get('width',.1) if item.get('stroke') else 0)+.1,black_underlay=True))
            elif item['type']=='text':
                if item.get('aircraft_label'):
                    if oid not in aircraft_done:
                        rows=aircraft_groups[oid];angle=math.radians(item.get('rotation',0));u=[math.cos(angle),math.sin(angle)];v=[-u[1],u[0]]
                        corners=[q for row in rows for q in plate(row,max(.05,row['size']*.15))['points']]
                        xx=[sum(q[k]*u[k] for k in (0,1)) for q in corners];yy=[sum(q[k]*v[k] for k in (0,1)) for q in corners]
                        under.append(dict(type='polygon',oid=oid,points=[[u[k]*x+v[k]*y for k in (0,1)] for x,y in [(min(xx),min(yy)),(max(xx),min(yy)),(max(xx),max(yy)),(min(xx),max(yy))]],fill=BLACK,black_underlay=True));aircraft_done.add(oid)
                else:
                    under.append(dict(item,fill='#101010',black_outline=True,black_underlay=True))
                    item['black_outline']=False
        ink.append(item)
    return __import__('rules13').trim_guide_backings(scene,surfaces+under+ink,generated)

def runway_priority(scene,items,generated):
    from scene_render import COLORS
    from marking_standards import outside_segments
    from pavement_geometry import subtract_convex
    runways=[a for a in scene.assets.values() if a['kind']=='RUNWAY']
    rank=lambda a:(max({'v':0,'0':1,'1':2,'2':2,'3':2}.get(a['props'].get('level_'+end,'1'),2) for end in ('a','b')),a['props'].get('runway_priority13',0))
    out=[]
    for item in items:
        owner=generated.get(item.get('oid'),{}).get('owner',item.get('oid'));a=scene.assets.get(owner)
        if not a or a['kind']!='RUNWAY':out.append(item);continue
        if item['type']=='polygon' and item.get('fill') in (COLORS['runway'],COLORS['taxiway'],COLORS['apron'],COLORS['shoulder']):out.append(item);continue
        higher=[b for b in runways if b['id']!=a['id'] and (rank(b),b['props']['width'],b['id'])>(rank(a),a['props']['width'],a['id'])]
        if not higher:out.append(item);continue
        def blocked(q):
            for b in higher:
                o=b['points'][0];u=g.unit(o,b['points'][-1]);d=[q[k]-o[k] for k in (0,1)];s=sum(d[k]*u[k] for k in (0,1));v=-d[0]*u[1]+d[1]*u[0]
                if 0<=s<=g.length(b['points']) and abs(v)<=b['props']['width']/2:return True
            return False
        polygons=[g.rectangle(b['points'],b['props']['width']) for b in higher]
        if item['type']=='line':
            for points,station in outside_segments(item['points'],polygons):out.append(dict(item,points=points,dash_offset=item.get('dash_offset',0)+station))
        elif item['type']=='polygon':
            pieces=[item['points']]
            for polygon in polygons:pieces=[piece for part in pieces for piece in subtract_convex(part,polygon)]
            out.extend(dict(item,points=piece) for piece in pieces)
        elif not any(blocked(q) for q in item['points']):out.append(item)
    return out
