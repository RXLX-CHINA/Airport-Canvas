"""Dependency-derived, individually editable pavement-marking components."""
import copy
import math
import scene_geometry as g
from marking_catalog import CATALOG, TAXI_MARKING_EDGE_CLEARANCE
from pavement_geometry import crossings
from scene_rules import holding_plan

def synthetic(owner,key,points,suffix='',**props):
    p=dict(shoulder=0.,flow='BOTH',closed=False);p.update(copy.deepcopy(CATALOG[key]['defaults']));p.update(props,mark_type=key)
    name=CATALOG[key]['name']+(' · '+str(p['text']) if p.get('text') else '')
    if suffix.startswith('a:'):name='A端 · '+name
    elif suffix.startswith('b:'):name='B端 · '+name
    return dict(id='AUTO:'+owner+':'+(suffix or key),kind='MARKING',name=name,owner=owner,points=points,props=p)

def entry_markings_hidden(scene,aid):
    movement=scene.movements.get(aid)
    if movement:
        if movement.get('role')!='RAPID_EXIT':return False
        if movement.get('hide_entry_markings43'):return True
        if movement.get('legacy_attachment'):
            return any(entry_markings_hidden(scene,movement[side]['asset']) for side in ('from','to'))
        return False
    props=scene.assets.get(aid,{}).get('props',{})
    return bool(props.get('rapid_exit') and props.get('hide_entry_markings43'))

def entry_mark_hidden(scene,mark):
    props=mark['props']
    if (props.get('mark_type') not in ('HOLD_A','HOLD_B','MANDATORY','TWY_ENHANCED')
            and props.get('sign_role23') not in ('RUNWAY_NUMBER','CAT_HOLD','HOLD_BOARD','VACATED')):
        return False
    owners=(mark.get('owner'),props.get('label_asset'),props.get('sign_axis21_2'),
            props.get('enhanced_source20'))
    return any(owner and entry_markings_hidden(scene,owner.split(':')[0]) for owner in owners)

def holding_locations(scene):
    """Candidate designs only; final holding distance remains an engineering input."""
    result=[]
    for mid,m in scene.movements.items():
        if not m.get('show_holding',True) or entry_markings_hidden(scene,mid):continue
        h=holding_plan(scene,mid)
        if h and 'point' in h:
            props = m
            if m.get('legacy_attachment'):
                props = next((a['props'] for side in ('from','to')
                              if (a:=scene.assets[m[side]['asset']])['kind'] != 'RUNWAY'),m)
            result.append(dict(h,owner=mid,key='hold',width=props['width'],
                               auto_signs=m.get('auto_signs',True),
                               code_letter=props.get('code_letter') or m.get('code_letter','C')))
    junctions=list(crossings(scene))
    runways=[a for a in scene.assets.values() if a['kind']=='RUNWAY']
    for t in scene.assets.values():
        if t['kind'] not in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):continue
        total=g.length(t['points'])
        for end,station in enumerate((0.,total)):
            point,tangent=g.at(t['points'],station)
            for r in runways:
                distance,runway_station,on_axis=g.project(r['points'],point)
                runway_tangent=g.unit(*r['points'])
                cross_track=abs((point[0]-on_axis[0])*runway_tangent[1]-(point[1]-on_axis[1])*runway_tangent[0])
                if distance>r['props']['width']/2 or distance-cross_track>.05:continue
                pair={r['id'],t['id']}
                if any(set(j['assets'])==pair and abs(j['stations'][j['assets'].index(t['id'])]-station)<r['props']['width'] for j in junctions):continue
                junctions.append(dict(id=f"END:{t['id']}:{r['id']}:{end}",assets=[r['id'],t['id']],
                    stations=[runway_station,station],tangents=[runway_tangent,tangent],point=point,
                    holding_offset=cross_track))
    for j in junctions:
        if any(k not in scene.assets for k in j['assets']):continue
        aa=[scene.assets[k] for k in j['assets']]
        if not any(a['kind']=='RUNWAY' for a in aa):continue
        i=0 if aa[0]['kind']=='RUNWAY' else 1;r=aa[i];t=aa[1-i];p=t['props']
        if t['kind']=='RUNWAY' or entry_markings_hidden(scene,t['id']):continue
        if not p.get('auto_markings',True) or not p.get('show_holding',True):continue
        u=j['tangents'][i];v=j['tangents'][1-i];normal=(-u[1],u[0]);sine=abs(sum(x*y for x,y in zip(v,normal)))
        if sine<.1:continue
        distance=p.get('holding_distance') or 90.;delta=max(0.,distance-j.get('holding_offset',0.))/sine;total=g.length(t['points']);station=j['stations'][1-i]
        for side in (-1,1):
            s=station+side*delta
            if not 0<=s<=total:continue
            q,tangent=g.at(t['points'],s);tangent=[-side*x for x in tangent]
            outside=s+side*47
            enhanced=g.subpath(t['points'],max(0,min(total,outside)),s)
            if any(h['runway']==r['id'] and g.distance(h['point'],q)<3
                   and sum(x*y for x,y in zip(h['tangent'],tangent))>.9 for h in result):continue
            result.append(dict(owner=t['id'],key=j['id']+':'+str(side),runway=r['id'],point=q,tangent=tangent,
                span=p['width']+2*p.get('shoulder',0),width=p['width'],enhanced=enhanced,station=s,
                auto_signs=p.get('auto_signs',True),code_letter=p.get('code_letter','C'),status='UNVERIFIED'))
    return result

def fit_mandatory(mark):
    p=mark['props']
    if 'mandatory_width21_2' not in p:return
    width=p['mandatory_width21_2']
    side=p['mandatory_side21_2']
    h=p['text_height']
    q=p['mandatory_hold21_2']
    u=g.unit(mark['points'][0],mark['points'][-1]);v=(-u[1],u[0])
    rows=p['text'].replace('\n',' / ').split(' / ')
    span=max(len(row.strip()) for row in rows)
    margin=p.get('margin',.5)
    nominal_ratio=p.get('character_ratio',.6)
    gap=1.075
    budget=width-2*TAXI_MARKING_EDGE_CLEARANCE
    if side:
        budget=budget/2-gap
    if budget<=.1:return
    margin=min(margin,budget/5)
    ink=budget-2*margin
    min_ratio=max(.4,min(nominal_ratio,.5))
    h=min(h,ink/max(.4,span*min_ratio))
    ratio=min(.72,ink/max(.01,span*h))
    cross=side*(budget/2+gap)
    depth=(len(rows)*h+(len(rows)-1)*.5)/2+margin+2.05
    anchor=[q[k]-u[k]*depth+v[k]*cross for k in (0,1)]
    p.update(text_height=h,character_ratio=ratio,margin=margin,mandatory_panel_width=budget)
    mark['points']=[anchor,[anchor[k]+u[k]*10 for k in (0,1)]]


REMOVABLE_RUNWAY_MARKS = frozenset(('MANDATORY','TWY_ENHANCED'))


def remove_runway_instruction_markings(scene):
    ids=[aid for aid,asset in scene.assets.items()
         if asset['kind']=='MARKING' and asset['props']['mark_type'] in REMOVABLE_RUNWAY_MARKS]
    with scene.transaction('去除强制性指令标识和增强型中线'):
        for aid in ids:scene.delete(aid)
        scene.data['meta']['suppress_runway_instruction_markings']=True


def generated_markings(scene,apply_overrides=True,*,stand_designs=None):
    result={}
    def add(owner,key,pts,suffix='',**p):
        a=synthetic(owner,key,pts,suffix,**p);result[a['id']]=a;return a
    for aid,a in scene.assets.items():
        p=a['props'];pts=a['points']
        if a['kind']=='RUNWAY' and p.get('auto_markings',True) and not (p.get('closed') and p.get('closure_kind')=='PERMANENT'):
            result.update(runway_components(a))
        elif a['kind']=='STAND' and p.get('auto_markings',True):
            length=g.length(pts);u=g.unit(pts[0],pts[-1]);q=pts[-1]
            if p.get('helicopter_stand'):
                from stand15 import rounded_lead
                add(aid,'LEAD_IN',rounded_lead(a),'HELIPAD_LEAD_IN',line_width=max(.15,p.get('lead_width',.15)))
                add(aid,'HELIPAD',[q,[q[k]+u[k]*10 for k in (0,1)]],'HELIPAD',
                    width=p.get('aircraft_span',12),number=p.get('stand_number') or a['name'])
                continue
            from stand_profiles import lead_design
            design=lead_design(a,scene)
            if stand_designs is not None:
                stand_designs[aid]=design
            from stand10 import bridge
            result.update(bridge(a,scene))
            from stand13 import support
            result.update(support(scene,a))
            arrow=p.get('lead_type')=='ICAO'
            for part in design['paths']:
                suffix='LEAD_IN' if part['key']=='ALIGN' else 'LEAD_BRANCH:'+part['key']
                add(aid,'LEAD_IN',part['points'],suffix,line_width=max(.15,p.get('lead_width',.15)),dash=2 if p.get('auxiliary',False) else None,gap=2,icao_arrow=arrow)
                arrow=False
            from stand13 import preset_polygon
            extra_types={'lead':'LEAD_IN','combined_lead':'LEAD_IN','icao_aux_lead':'ICAO_AUX_LEAD','work':'WORK_WAIT',
                         'temporary':'TEMP_WAIT','bridge':'BRIDGE_COMPOSITE'}
            for key in p.get('preset_shapes',{}):
                family,separator,_=key.partition(':')
                if separator and family in extra_types:
                    add(aid,extra_types[family],preset_polygon(a,key,[]),'CUSTOM:'+key,
                        line_width=.15 if family.endswith('lead') else .1,stand_part=True)
            if p.get('show_number',True) and not p.get('ga_stand'):
                for i,n in enumerate(design['numbers']):
                    origin=n['point'];direction=n['direction']
                    add(aid,'STAND_NUMBER',[origin,[origin[k]+direction[k]*10 for k in (0,1)]],'STAND_NUMBER' if i==0 else 'STAND_NUMBER:'+str(i),text=p.get('stand_number') or a['name'],text_height=p.get('number_height',4.),text_rotation_offset=n['text_rotation_offset'],rectangular_number=p.get('lead_type')=='ICAO')
            from editor6_geometry import stop_components
            if not p.get('auxiliary',False):result.update(stop_components(a))
            if p.get('remote_stand'):
                from stand15 import remote_exit_lines
                for index,path in enumerate(remote_exit_lines(a,scene)):
                    add(aid,'LEAD_OUT',path,f'REMOTE_EXIT:{index}',line_width=max(.15,p.get('lead_width',.15)))
            if p.get('show_safety',bool(p.get('ga_stand'))):
                from stand_profiles import safety_profile
                polygon=safety_profile(scene,a)
                if p.get('ga_stand'):
                    from stand13 import ga_color
                    add(aid,'STAND_SAFETY',polygon,ga_frame_color=ga_color(p,'ga_frame_color'),
                        ga_outline_color=ga_color(p,'ga_outline_color'))
                else:
                    add(aid,'STAND_SAFETY',polygon,line_width=.1,dash=2 if p.get('auxiliary',False) else None,gap=2,continuous_safety14=True,open_stand_nose58=p.get('remote_stand',False))
        elif a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE') and p.get('auto_markings',True) and p.get('auto_signs',True):
            q,u=g.at(pts,g.length(pts)*.5);v=(-u[1],u[0]);q=[q[k]+-v[k]*(p['width']/4) for k in (0,1)]
            add(aid,'LOCATION',[q,[q[k]+u[k]*10 for k in (0,1)]],text=p.get('designation') or (__import__('re').match(r'[A-Za-z][A-Za-z0-9]*',a['name']).group() if __import__('re').match(r'[A-Za-z][A-Za-z0-9]*',a['name']) else 'T'),text_height=4)
            if p.get('maxspan'):
                q,u=g.at(pts,min(30,g.length(pts)*.2));add(aid,'MAX_SPAN',[q,[q[k]+u[k]*10 for k in (0,1)]],text='MAX SPAN '+str(p['maxspan'])+' m',maxspan=p['maxspan'])
    suppress_instructions=scene.data['meta'].get('suppress_runway_instruction_markings',False)
    for h in holding_locations(scene):
        owner=h['owner'];q=h['point'];u=h['tangent'];v=(-u[1],u[0]);key=h['key']
        add(owner,'HOLD_A',[q,[q[k]+u[k]*10 for k in (0,1)]],key+':HOLD_A',width=h['span'])
        movement=scene.movements.get(owner,{})
        if not suppress_instructions and movement.get('show_enhanced',True):
            add(owner,'TWY_ENHANCED',h['enhanced'],key+':TWY_ENHANCED')
        if suppress_instructions or not h['auto_signs']:continue
        r=scene.assets[h['runway']];text=r['props'].get('label_a','09')+'-'+r['props'].get('label_b','27');height=2 if h['code_letter'] in ('A','B') else 4
        text_width=len(text)*height*.6;background_width=text_width+1
        settings=scene.movements.get(owner,scene.assets.get(owner,{}).get('props',{}));paired=settings.get('paired_mandatory20_2',True)
        for side in ((-1,1) if paired or h['width']>=23 else (0,)):
            # 1 m clear of centreline outer edge and >1 m behind holding paint.
            transverse=side*(background_width/2+1.075)
            anchor=[q[k]-u[k]*(1.05+1+height/2+.5)+v[k]*transverse for k in (0,1)]
            add(owner,'MANDATORY',[anchor,[anchor[k]+u[k]*10 for k in (0,1)]],key+':MANDATORY:'+str(side),text=text,text_height=height,character_ratio=.6,margin=.5,paired_mandatory20_2=paired,
                mandatory_width21_2=h['width'],mandatory_side21_2=side,mandatory_hold21_2=q)
    for mid,m in scene.movements.items():
        if m['role']=='PUSHBACK' and m.get('guide_visible',True):
            path=scene.movement_path(mid);q=path[-1];u=g.unit(path[-2],q)
            add(mid,'PUSH_WAIT',[q,[q[k]+u[k]*10 for k in (0,1)]],width=1,line_width=.15)
        if m.get('geometry')=='RAPID' and m.get('join_reverse_visible',True) and m.get('guide_visible',True):
            from junction_routes import branches
            branch=next(iter(branches(scene,m)),None)
            if branch:
                entry=add(mid,'TWY_CENTER',branch['points'],'JOIN_REVERSE',line_width=.15);entry['name']='反向接入引导线'
        if m['role'] not in ('EXIT_ONLY','RAPID_EXIT') or not m.get('auto_signs',True):continue
        path=scene.movement_path(mid);taxi=scene.assets[m['to']['asset']]
        width=taxi['props']['width'];anchor=None
        for a,b in reversed(list(zip(path,path[1:]))):
            da=g.project(taxi['points'],a)[0];db=g.project(taxi['points'],b)[0]
            if db<=width<=da and abs(da-db)>1e-9:
                ratio=(width-db)/(da-db);q=[b[k]+ratio*(a[k]-b[k]) for k in (0,1)];u=g.unit(b,a);anchor=(q,u);break
        if anchor:
            q,u=anchor;add(mid,'NO_ENTRY',[q,[q[k]+u[k]*10 for k in (0,1)]],text='NO ENTRY',text_height=2 if m.get('code_letter','C') in ('A','B') else 4,character_ratio=.4,margin=.5)
    from roads10 import generated as road_generated
    result.update(road_generated(scene))
    result.update(__import__('roads17').generated(scene))
    from deice11 import generated as deice_generated
    result.update(deice_generated(scene))
    from holding10 import refine_generated
    result=refine_generated(scene,result)
    from marks11 import refine
    result=refine(scene,result)
    from stand_overlap9 import derived
    pairs=scene.data['meta'].get('merged_stand_overlaps',{})
    dashed=scene.data['meta'].get('dashed_stand_overlaps',{})
    result.update(derived(result,set(pairs)|set(dashed)))
    from marking_standards import permanently_closed,closure_components
    result={oid:a for oid,a in result.items() if not permanently_closed(scene,a.get('owner'))}
    result.update(closure_components(scene))
    result=__import__('model20').locations(scene,result)
    result=__import__('segments18').locations(scene,result)
    result.update(__import__('directions20_18').generated(scene))
    result=__import__('enhanced19').refine(scene,result)
    result=__import__('styles19').normalize(scene,__import__('rules13').refine(scene,result),reposition=True)
    result=__import__('runway20').relocate(scene,result)
    result={oid:mark for oid,mark in result.items() if not entry_mark_hidden(scene,mark)}
    for mark in result.values():
        fit_mandatory(mark)
    from marking_standards import closure_entries,no_entry_boards
    result.update(closure_entries(scene))
    from holding_point_boards import hp_boards
    result.update(hp_boards(scene,result))

    from stand11 import frame
    for oid,mark in list(result.items()):
        owner=mark['owner']
        stand=scene.assets.get(owner,{})
        overrides=stand.get('props',{}).get('preset_nodes',{})
        suffix=oid.removeprefix('AUTO:'+owner+':')
        absolute=overrides.get('@'+suffix)
        if absolute==[]:
            del result[oid]
            continue
        if absolute:
            from stand13 import preset_polygon
            mark['points']=preset_polygon(dict(stand,props=dict(stand['props'],preset_shapes={suffix:absolute})),suffix,[])
            continue
        edits=overrides.get(suffix)
        if not edits or len(edits)!=len(mark['points']):continue
        _,u,v=frame(stand)
        mark['points']=[[x+du*u[0]+dv*v[0],y+du*u[1]+dv*v[1]]
                        for (x,y),(du,dv) in zip(mark['points'],edits)]
    if apply_overrides:
        for oid,data in scene.data.get('generated_overrides',{}).items():
            if oid not in result:continue
            if data.get('hidden'):del result[oid];continue
            a=result[oid]
            if data.get('editable_nodes'):
                from curve_model import evaluate
                origin=a['points'][0];u=g.unit(origin,a['points'][-1]);v=[-u[1],u[0]];length=max(.01,g.distance(origin,a['points'][-1]));nodes=copy.deepcopy(data['editable_nodes'])
                for n in nodes:
                    for field in ('p','incoming','outgoing'):
                        x,y=n[field];n[field]=[origin[k]+u[k]*x*length+v[k]*y for k in (0,1)]
                a['points']=evaluate(nodes)
            p=a['points'][0];angle=math.radians(data.get('rotation',0));scale=data.get('scale',1);c=math.cos(angle)*scale;s=math.sin(angle)*scale
            a['points']=[[p[0]+(q[0]-p[0])*c-(q[1]-p[1])*s+data.get('dx',0),p[1]+(q[0]-p[0])*s+(q[1]-p[1])*c+data.get('dy',0)] for q in a['points']]
            a['props'].update(data.get('props',{}));a['name']=data.get('name',a['name'])
    for oid,board in no_entry_boards(scene,(*result.values(),*scene.assets.values())).items():
        if not apply_overrides or not scene.data['generated_overrides'].get(oid,{}).get('hidden'):
            result[oid]=board
    for mark in result.values():
        if mark['props']['mark_type']=='RWY_CIRCLE':
            aid=mark.get('owner') or mark['props'].get('label_asset');center=result.get('AUTO:'+str(aid)+':RWY_CENTER')
            if center:mark['props']['line_width']=center['props']['line_width']
    return __import__('styles19').normalize(scene,result)

def number_position(p,end):
    base=70 if p.get('show_thresholds',True) else 20
    return max(base,51+15+4.5+4) if p.get('show_thresholds',True) and len(p.get('label_'+end,''))>2 else base

def number_clearance(p,end):return max(35,number_position(p,end)+(20 if p.get('show_thresholds',True) else 15))

def runway_components(a):
    from runway import aim_dimensions,pair_count
    p=a['props'];pts=a['points'];aid=a['id'];total=g.length(pts);out={};u=g.unit(*pts)
    def add(key,origin,tangent,suffix,**props):
        entry=synthetic(aid,key,[origin,[origin[k]+tangent[k]*10 for k in (0,1)]],suffix,**props);out[entry['id']]=entry
    da=p.get('displaced_a',0);db=p.get('displaced_b',0)
    white=.9 if any(p.get(k) in ('2','3') for k in ('level_a','level_b')) else .45 if any(p.get(k) in ('0','1') for k in ('level_a','level_b')) else .3
    if p.get('center_circle',False):
        add('RWY_CIRCLE',g.at(pts,(da+total-db)/2)[0],u,'RWY_CIRCLE',width=p['width']/2,line_width=white)
    if p.get('center_visible',True) and total-da-db>180:
        entry=synthetic(aid,'RWY_CENTER',g.subpath(pts,da+number_clearance(p,'a'),total-db-number_clearance(p,'b')),'RWY_CENTER',line_width=white);out[entry['id']]=entry
    for end,sign,disp in (('a',1,da),('b',-1,db)):
        origin=disp if sign==1 else total-disp;t=[x*sign for x in u]
        def pos(station):return g.at(pts,max(0,min(total,origin+sign*station)))[0]
        if disp:
            q=pos(0);v=(-u[1]*p['width']/2,u[0]*p['width']/2)
            entry=synthetic(aid,'THRESHOLD_BAR',[[q[0]-v[0],q[1]-v[1]],[q[0]+v[0],q[1]+v[1]]],end+':THRESHOLD_BAR');out[entry['id']]=entry
            for station in range(35,int(disp),60):add('DISPLACED_ARROW',pos(-station-30),t,end+':ARROW:'+str(station))
            if p.get('temporary_'+end,False):add('THRESHOLD_HEADS',pos(-2),t,end+':THRESHOLD_HEADS',width=p['width'])
        if total-disp<100:continue
        if p.get('show_thresholds',True):add('RWY_THRESHOLD',pos(6),t,end+':RWY_THRESHOLD',width=p['width'])
        if p.get('show_numbers',True):add('RWY_NUMBER',pos(number_position(p,end)),t,end+':RWY_NUMBER',text=p.get('label_'+end,'09'),text_height=9)
        lda=p.get('lda_'+end) or total-disp;distance,length,width,sep=aim_dimensions(lda,p.get('aim_width_'+end),p.get('aim_gap_'+end),p.get('aim_length_'+end))
        if p.get('show_aimpoints',True) and lda>=distance+length and sep+2*width<=p['width']+.001:add('AIMING_POINT',pos(distance),t,end+':AIMING_POINT',lda=lda,width=p['width'],aim_width=width,aim_gap=sep,aim_length=length)
        if p.get('show_tdz',True) and (p.get('level_'+end,'1')!='v' or p.get('code_number') in (3,4)):
            code2=p.get('code_number')==2 and p.get('level_'+end)=='0'
            stations=[distance+150] if code2 else [150*(i+1) for i in range(pair_count(total-da-db))]
            for i,station in enumerate(stations):
                if station+22.5>total-da-db or station<=distance+length+50 and station+22.5>=distance-50:continue
                key='TDZ_CODED' if sep+2*(3*1.8+2*1.5)<=p['width'] else 'TDZ_BASIC'
                if sep+6<=p['width']:add(key,pos(station),t,end+':TDZ:'+str(i),width=sep,bars=(3,3,2,2,1,1)[i])
    return out

def update_generated(scene,oid,name,points,props):
    originals=generated_markings(scene,False);original=originals[oid];p=original['points'][0];q=points[0]
    u=g.unit(original['points'][0],original['points'][-1]);v=g.unit(points[0],points[-1]);angle=math.degrees(math.atan2(v[1],v[0])-math.atan2(u[1],u[0]))
    with scene.transaction('编辑自动生成标记'):
        scene.data['generated_overrides'][oid]=dict(name=name,dx=q[0]-p[0],dy=q[1]-p[1],rotation=angle,scale=g.length(points)/g.length(original['points']),props={k:v for k,v in props.items() if original['props'].get(k)!=v})
        if original['props']['mark_type']=='STAND_NUMBER':
            for pairid,paired in originals.items():
                if pairid!=oid and paired.get('owner')==original.get('owner') and paired['props']['mark_type']=='STAND_NUMBER':scene.data['generated_overrides'][pairid]=copy.deepcopy(scene.data['generated_overrides'][oid])
        # Reuse the same validation as an independently drawn marker.
        check=copy.deepcopy(original);check.update(name=name,points=copy.deepcopy(points));check['props'].update(props)
        scene.assets[oid]=check
        try:scene.validate_structure()
        finally:del scene.assets[oid]

def detach_generated(scene,oid):
    a=generated_markings(scene)[oid]
    with scene.transaction('分离自动标记'):
        aid=scene.create_marking(a['props']['mark_type'],a['points'],a['name'],**{k:v for k,v in a['props'].items() if k!='mark_type'})
        scene.assets[aid]['container_id']=a['owner'] if a['owner'] in scene.assets else None
        scene.data['generated_overrides'].setdefault(oid,{})['hidden']=True
    return aid



def standardize_runway_mandatory(scene):
    marks = generated_markings(scene,False)
    ids = {oid for oid,mark in marks.items() if mark['props'].get('mark_type')=='MANDATORY'
           and 'mandatory_width21_2' in mark['props']}
    overrides = scene.data['generated_overrides']
    layout_fields = {'text_height','character_ratio','margin','mandatory_panel_width',
                     'mandatory_width21_2','mandatory_side21_2','mandatory_hold21_2','background'}
    geometry_fields = ('dx','dy','rotation','scale','editable_nodes')
    changed = [oid for oid in ids & overrides.keys()
               if layout_fields.intersection(overrides[oid].get('props',{}))
               or any(key in overrides[oid] for key in geometry_fields)]
    if changed:
        with scene.transaction('统一跑道编号强制指令标识'):
            for oid in changed:
                override = overrides[oid]
                for key in geometry_fields:
                    override.pop(key,None)
                for key in layout_fields:
                    override.get('props',{}).pop(key,None)
    return len(ids)
