"""Persistent airport scene, transactional edits and directed movement graph."""
import copy
from contextlib import contextmanager
from datetime import date
import heapq
import json
import math
from pathlib import Path
import uuid
import scene_geometry as g

MAX_PROJECT_BYTES=110_000_000

PATH_KINDS={'RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','STAND','ROAD'}
AREA_KINDS={'APRON','PROTECTION','EQUIPMENT','CLOSED_AREA'}
KINDS=PATH_KINDS|AREA_KINDS|{'MARKING'}
ROLES={'ENTRY','EXIT','EXIT_ONLY','RAPID_EXIT','CROSSING','TAXIWAY_JOIN','APRON_ACCESS','STAND_ENTRY','PUSHBACK','ROAD_CROSSING'}
STATUSES={'PASS','FAIL','UNKNOWN','UNVERIFIED','NOT_APPLICABLE','REVIEW_REQUIRED'}

def finite(v,name,low=None,positive=False):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise ValueError(f'{name}: must be finite numeric')
    if low is not None and v<low or positive and v<=0: raise ValueError(f'{name}: invalid range')
    return float(v)

class AirportScene:
    def __init__(self,data=None):
        self.data=copy.deepcopy(data) if data else dict(format='runway-generator-scene',version=1,
            meta=dict(name='未命名机场',units='m',crs='LOCAL_DESIGN',magnetic_declination=None,
                      design_date='2026-11-17',ruleset='MH5001-2021 / 修订案I-IV：部分实现'),
            scenario=dict(name='日间设计',date='2026-11-17',night=False,rvr=1000,
                          aircraft_wingspan=36,aircraft_length=40,wheelbase=None,
                          cockpit_to_nosewheel=None,closed_assets=[],active_stands=[],
                          permitted_movements=[],show_simulation=False),
            assets={},movements={},overrides=[])
        self.data.setdefault('junctions',{})
        self.data.setdefault('groups',{})
        self.data.setdefault('generated_overrides',{})
        self.revision=0
        self.on_commit=None
        self.past=[];self.future=[];self._transaction_depth=0;self.validate_structure()

    @property
    def assets(self): return self.data['assets']
    @property
    def movements(self): return self.data['movements']
    @property
    def scenario(self): return self.data['scenario']

    def validate_structure(self):
        d=self.data
        if not isinstance(d,dict) or d.get('format')!='runway-generator-scene' or d.get('version')!=1:
            raise ValueError('Not a supported airport scene (version 1)')
        for name in ('assets','movements','meta','scenario'):
            if not isinstance(d.get(name),dict): raise ValueError(f'Missing/invalid {name}')
        if 'bitmap_layers' in d:
            from bitmap_layers46 import validate
            validate(d)
        if d['meta'].get('units')!='m': raise ValueError('Scene geometry must use metres')
        finite(d['meta'].get('grid_north_true_heading',0),'grid north true heading')
        if d['meta'].get('traffic_side','RIGHT') not in ('LEFT','RIGHT'):raise ValueError('traffic_side must be LEFT or RIGHT')
        if 'jet_warning_distance' in d['meta']:finite(d['meta']['jet_warning_distance'],'jet warning distance',0,positive=True)
        if d['meta'].get('magnetic_declination') is not None:
            decl=finite(d['meta']['magnetic_declination'],'magnetic_declination')
            if not -180<=decl<=180:raise ValueError('Magnetic declination outside -180..180')
        for value in (d['meta'].get('design_date'),d['scenario'].get('date')): date.fromisoformat(value)
        sc=d['scenario']
        for key in ('night','show_simulation'):
            if type(sc.get(key)) is not bool: raise ValueError(f'{key} must be boolean')
        for key in ('rvr','aircraft_wingspan','aircraft_length'):
            finite(sc.get(key),key,0,positive=True)
        for key in ('wheelbase','cockpit_to_nosewheel'):
            if sc.get(key) is not None: finite(sc[key],key,0,positive=True)
        for key in ('closed_assets','active_stands','permitted_movements'):
            if not isinstance(sc.get(key),list): raise ValueError(f'{key} must be a list')
        from editor6_geometry import validate_editor_data
        validate_editor_data(self)
        if len(self.assets)>2000 or len(self.movements)>4000: raise ValueError('Scene exceeds supported object budget')
        for aid,a in self.assets.items():
            if not isinstance(a,dict) or a.get('id')!=aid or a.get('kind') not in KINDS: raise ValueError('Invalid asset identity/kind')
            if not isinstance(a.get('name'),str) or not a['name'].strip() or not isinstance(a.get('props'),dict): raise ValueError('Invalid asset fields')
            pts=a.get('points')
            if not isinstance(pts,list) or not 2<=len(pts)<=5000: raise ValueError('Asset point count must be 2..5000')
            for pt in pts:
                if not isinstance(pt,list) or len(pt)!=2: raise ValueError('Point requires x,y')
                for x in pt:
                    finite(x,'coordinate')
                    if abs(x)>1e7: raise ValueError('Local coordinate out of supported range')
            for vertex in a.get('design_vertices',[]):
                if len(vertex)!=2:raise ValueError('Invalid design vertex')
                for value in vertex:finite(value,'design vertex')
            for node in a.get('curve_nodes',[]):
                for field in ('p','incoming','outgoing'):
                    if len(node[field])!=2:raise ValueError('Invalid curve node')
                    for value in node[field]:finite(value,'curve control')
            p=a['props']
            __import__('segments18').validate_asset(a)
            for key in ('stopway_a','stopway_b'):
                if key in p:finite(p[key],key,0)
            for key in ('sync_number','sync_suffix','rapid_exit','has_bridge','outward'):
                if key in p and type(p[key]) is not bool:raise ValueError(key+' must be boolean')
            import re
            for key in ('pavement_color','shoulder_color'):
                if key in p and not re.fullmatch(r'#[0-9a-fA-F]{6}',p[key]):raise ValueError('Color requires #RRGGBB')
            if p.get('runway_suffix','') not in ('','L','C','R'):raise ValueError('Invalid runway suffix')
            if 'auto_number' in p and type(p['auto_number']) is not bool:raise ValueError('auto_number must be boolean')
            if 'corner_radius' in p:finite(p['corner_radius'],'corner radius',0)
            for key in ('lead_radius','aircraft_span','fuselage_width','safety_clearance','wing_station'):
                if key in p:finite(p[key],key,0,positive=True)
            if a['kind']=='STAND' and p.get('wing_station',1)>=p.get('aircraft_length',sc['aircraft_length']):raise ValueError('Wing station outside aircraft length')
            if a['kind']=='STAND' and p.get('lead_type','A') not in ('A','B','C','D','ICAO'):raise ValueError('Invalid lead-in type')
            if a['kind']=='STAND':
                if p.get('lead_direction','BOTH') not in ('BOTH','LEFT','RIGHT'):raise ValueError('Invalid lead-in direction')
                if not 45<=p.get('lead_label_angle',60)<=75:raise ValueError('A/D编号轴线角须在45～75度之间')
                for field in ('lead_g','lead_h','lead_i','lead_j','lead_k','lead_l','lead_m','lead_n','lead_p'):
                    if field in p:finite(p[field],field,0,positive=True)
            if 'text_rotation_offset' in p:finite(p['text_rotation_offset'],'text rotation')
            for key in ('stop_length','stop_width','number_height','aircraft_text_height','lead_width','aircraft_length','bay_length','home_diameter','row_spacing'):
                if key in p:finite(p[key],key,0,positive=True)
            for key in ('home_dx','home_dy'):
                if key in p:finite(p[key],key)
            for key in ('direction_arrow','show_home'):
                if key in p and type(p[key]) is not bool:raise ValueError(key+' must be boolean')
            if p.get('code_letter','C') not in 'ABCDEF' or len(p.get('code_letter','C'))!=1:raise ValueError('code_letter must be A..F')
            for key in ('fillet_radius','turn_radius'):
                if key in p:finite(p[key],key,0,positive=True)
            for key in ('auto_markings','center_visible','edges_visible','shoulder_markings','show_numbers','show_thresholds','show_aimpoints','show_tdz'):
                if key in p and type(p[key]) is not bool:raise ValueError(key+' must be boolean')
            finite(p.get('width'),'width',0,positive=True);finite(p.get('shoulder'),'shoulder',0)
            if p.get('flow') not in ('BOTH','FORWARD','REVERSE'): raise ValueError('Unknown flow')
            if type(p.get('closed')) is not bool: raise ValueError('closed must be boolean')
            for key in ('maxspan','wheelbase','holding_distance','lda_a','lda_b','min_radius'):
                if p.get(key) is not None: finite(p[key],key,0,positive=True)
            if p.get('code_number') is not None and (type(p['code_number']) is not int or p['code_number'] not in (1,2,3,4)):
                raise ValueError('code_number must be null or integer 1..4')
            if a['kind']=='MARKING':
                from marking_catalog import CATALOG
                if p.get('mark_type') not in CATALOG:raise ValueError('Unknown pavement marking template')
                for field in ('dash','gap','surface_length','body_length','arrow_length','character_ratio','aircraft_height'):
                    if p.get(field) is not None:finite(p[field],field,0,positive=True)
                if p.get('surface_length',90)>100000:raise ValueError('铺筑面长度超出支持范围')
                for field in ('color','surface_color'):
                    if p.get(field) is not None and not re.fullmatch(r'#[0-9a-fA-F]{6}',p[field]):raise ValueError('标志颜色须为 #RRGGBB')
                if 'aircraft_types' in p and p['aircraft_types'] is not None:
                    if not isinstance(p['aircraft_types'],list) or len(p['aircraft_types'])>100 or any(not isinstance(x,str) or not x.strip() or len(x)>80 for x in p['aircraft_types']):raise ValueError('机型列表须为不超过100项的文字列表')
                if p['mark_type']=='CHOCKS' and p['width']<1:raise ValueError('轮挡放置区边长不得小于1 m（6.2.20）。')
                if CATALOG[p['mark_type']]['shape']=='apron_vehicle' and (p['width']<=p.get('line_width',.125) or p.get('bay_length',10)<=p.get('line_width',.125)):raise ValueError('车位外尺寸须大于边线宽度。')
                if CATALOG[p['mark_type']]['shape']=='apron_bridge' and p.get('show_home',False) and p.get('home_diameter',3)<=p.get('line_width',.125):raise ValueError('回位圆外径须大于圆圈线宽。')
                if p['mark_type']=='AIMING_POINT':
                    from runway import aim_dimensions
                    aim_dimensions(p.get('lda',2400),p.get('aim_width'),p.get('aim_gap'),p.get('aim_length'))
                finite(p.get('line_width',.15),'marking line width',0,positive=True)
                finite(p.get('text_height',4),'marking character height',0,positive=True)
                finite(p.get('spacing',2),'marking spacing',0,positive=True)
                if p.get('lda') is not None:finite(p['lda'],'marking LDA',0,positive=True)
                if 'bars' in p and (type(p['bars']) is not int or p['bars'] not in (1,2,3)):raise ValueError('TDZ bars must be 1, 2 or 3')
                if type(p.get('background',True)) is not bool:raise ValueError('Marking background must be boolean')
                if not isinstance(p.get('text',''),str) or len(p.get('text',''))>200:raise ValueError('Marking text must be at most 200 characters')
                if CATALOG[p['mark_type']]['mode']=='AREA' and not g.simple_polygon(pts):raise ValueError('Marking area requires a simple polygon')
                if g.length(pts)<.05:raise ValueError('Marking orientation/path needs two distinct points')
            elif a['kind'] in PATH_KINDS:
                if g.length(pts)<1: raise ValueError('Path must be at least one metre')
            elif not g.simple_polygon(pts): raise ValueError('Polygon must be simple, non-degenerate and at least 1 square metre')
            if a['kind']=='RUNWAY':
                if len(pts)!=2: raise ValueError('Runway must be a straight two-point axis')
                for key in ('level_a','level_b'):
                    if p.get(key) not in ('v','0','1','2','3'): raise ValueError('Runway category must be v/0/1/2/3')
                da=finite(p.get('displaced_a',0),'displaced_a',0);db=finite(p.get('displaced_b',0),'displaced_b',0)
                if da+db>=g.length(pts): raise ValueError('Displaced thresholds overlap')
                for key,offset in (('lda_a',da),('lda_b',db)):
                    if p.get(key) is not None and p[key]>g.length(pts)-offset: raise ValueError(f'{key} exceeds physical landing length')
                from runway import aim_dimensions
                for end,disp in (('a',da),('b',db)):aim_dimensions(p.get('lda_'+end) or g.length(pts)-disp,p.get('aim_width_'+end),p.get('aim_gap_'+end),p.get('aim_length_'+end))
            if a['kind']=='STAND':
                if p.get('guidance') not in ('GUIDED','UNGUIDED'): raise ValueError('Unknown stand guidance')
                if p.get('stop_reference') not in ('NOSEWHEEL','LEFT_SEAT'): raise ValueError('Unknown stop reference')
            if p.get('parent_id') is not None and (p['parent_id'] not in self.assets or self.assets[p['parent_id']]['kind']!='APRON'):
                raise ValueError('Associated apron does not exist')
            for other in p.get('excludes',[]):
                if other==aid or other not in self.assets or self.assets[other]['kind']!='STAND':raise ValueError('Mutually exclusive stand must reference another stand')
        for mid,m in self.movements.items():
            if m.get('geometry','AUTO') not in ('AUTO','BEZIER','STRAIGHT','RAPID'):raise ValueError('Unknown connection geometry')
            for key in ('exit_angle','exit_radius','join_radius','rapid_min_straight'):
                if key in m:finite(m[key],key,0,positive=True)
            if m.get('id')!=mid or m.get('role') not in ROLES: raise ValueError('Invalid movement')
            if type(m.get('enabled')) is not bool or type(m.get('bidirectional')) is not bool: raise ValueError('Movement flags must be boolean')
            if m.get('stopbar') not in ('UNKNOWN','ON','OFF','FAILED'):raise ValueError('Unknown stopbar state')
            for zid in m.get('protection_ids',[]):
                if zid not in self.assets or self.assets[zid]['kind']!='PROTECTION':raise ValueError('Movement protection area missing')
            if m['role'] in ('EXIT_ONLY','RAPID_EXIT','PUSHBACK') and m['bidirectional']:
                raise ValueError('Exit-only, rapid-exit and pushback movements are one-way')
            finite(m.get('width'),'movement width',0,positive=True)
            finite(m.get('handle'),'handle',0,positive=True)
            finite(m.get('holding_distance'),'candidate holding distance',0,positive=True)
            if m.get('maxspan') is not None: finite(m['maxspan'],'movement maxspan',0,positive=True)
            if m.get('min_radius') is not None: finite(m['min_radius'],'min_radius',0,positive=True)
            if m.get('shoulder') is not None:finite(m['shoulder'],'connector shoulder',0)
            for flag in ('auto_branches','lock_tangents','follow_existing','guide_visible','pavement_visible','edges_visible','show_holding','rapid_auto_fit','rapid_auto_radius','join_reverse_visible','reverse_join_pavement'):
                if flag in m and type(m[flag]) is not bool:raise ValueError(flag+' must be boolean')
            for key in ('from','to'):
                port=m.get(key,{})
                if port.get('asset') not in self.assets: raise ValueError('Movement has dangling asset')
                asset=self.assets[port['asset']]
                if asset['kind'] not in PATH_KINDS: raise ValueError('Connect to an explicit route inside an apron, not its polygon')
                finite(port.get('station'),'port station',0)
                if port['station']>g.length(asset['points'])+1e-6: raise ValueError('Port station outside asset; adjust its anchor before shortening')
                if type(port.get('direction')) is not int or port['direction'] not in (-1,1): raise ValueError('Port direction must be integer -1 or 1')
            if m['from']['asset']==m['to']['asset'] and abs(m['from']['station']-m['to']['station'])<.01:
                raise ValueError('A movement cannot connect the same port to itself')
            ka=self.assets[m['from']['asset']]['kind'];kb=self.assets[m['to']['asset']]['kind']
            if m['role'] in ('EXIT','EXIT_ONLY','RAPID_EXIT') and (ka!='RUNWAY' or kb in ('RUNWAY','ROAD')):
                raise ValueError('Exit must run from a runway to an aircraft taxi route')
            if m['role']=='ENTRY' and (kb!='RUNWAY' or ka in ('RUNWAY','ROAD')):
                raise ValueError('Entry must run from an aircraft taxi route to a runway')
            if (ka=='ROAD')!=(kb=='ROAD'):
                raise ValueError('Vehicle and aircraft routing graphs cannot be joined; use a geometric road crossing with a control point')
        if any(x not in self.assets for x in sc['closed_assets']+sc['active_stands']): raise ValueError('Scenario refers to missing asset')
        if any(x not in self.movements for x in sc['permitted_movements']): raise ValueError('Scenario refers to missing movement')
        for jid,settings in d.get('junctions',{}).items():
            finite(settings.get('radius',25),'junction turn radius',0,positive=True)
            if any(type(v) is not bool for v in settings.get('guides',{}).values()):raise ValueError('Guide visibility must be boolean')
            for flag in ('straight_0','straight_1'):
                if flag in settings and type(settings[flag]) is not bool:raise ValueError('Straight visibility must be boolean')
        from scene_hierarchy import validate_hierarchy
        validate_hierarchy(self)
        if not isinstance(d.get('generated_overrides'),dict):raise ValueError('Invalid automatic marking overrides')
        for key,override in d['generated_overrides'].items():
            if not key.startswith('AUTO:') or not isinstance(override,dict):raise ValueError('Invalid automatic marking identity')
            for field in ('dx','dy','rotation'):
                if field in override:finite(override[field],field)
            if 'scale' in override:finite(override['scale'],'generated marking scale',0,positive=True)
            if 'hidden' in override and type(override['hidden']) is not bool:raise ValueError('hidden must be boolean')
            props=override.get('props',{})
            if not isinstance(props,dict):raise ValueError('Invalid automatic marking properties')
            for field in ('width','line_width','text_height','spacing','lda'):
                if field in props:finite(props[field],field,0,positive=True)

        __import__('model20').validate(self)

    @contextmanager
    def transaction(self,label,*,location_only=False):
        if self._transaction_depth:
            self._transaction_depth+=1
            try:yield
            finally:self._transaction_depth-=1
            return
        old=copy.deepcopy(self.data)
        if location_only:
            try:
                yield
            except Exception:
                self.data=old
                raise
            if self.data!=old:
                self.revision+=1
                self.past.append((label,old))
                self.past=self.past[-80:]
                self.future.clear()
                if self.on_commit:self.on_commit(self)
            return
        self._route_cache=None;self._cross_cache=None
        __import__('workspace20_18').invalidate_scene(self)
        self._transaction_depth=1
        try:
            yield
            __import__('workspace20_18').invalidate_scene(self)
            __import__('roads13').reconcile(self)
            __import__('roads13').refresh_zebra(self)
            __import__('rules13').sync_marks(self)
            __import__('layout14').sync(self)
            __import__('interaction15').sync(self)
            __import__('model20').sync(self)
            __import__('runway20').sync_manual(self)
            __import__('terminal19').sync(self)
            __import__('enhanced19').sync(self)
            __import__('styles19').sync(self)
            __import__('signs21_2').sync(self)
            self.validate_structure()
        except Exception:
            self.data=old
            self._route_cache=None;self._cross_cache=None
            raise
        finally:
            self._transaction_depth=0
            __import__('workspace20_18').invalidate_scene(self)
        if self.data!=old:
            self.revision+=1
            self.past.append((label,old));self.past=self.past[-80:];self.future.clear()
            if self.on_commit:self.on_commit(self)

    def move_generated_signs(self, changes, *, fixed_pose=True):
        """Commit a rigid generated sign transform without rebuilding route topology."""
        if any(not oid.startswith('AUTO:') or
               set(pose)!={'dx','dy','rotation'} or
               not all(math.isfinite(value) for value in pose.values())
               for oid,pose in changes.items()):
            raise ValueError('Invalid generated sign pose')
        current = self.data['generated_overrides']
        changes = {oid:pose for oid,pose in changes.items() if any(
                   current.get(oid,{}).get(key,0)!=value for key,value in pose.items())}
        if not changes:
            return
        if not self._transaction_depth:
            old = copy.deepcopy(self.data)
        for oid,pose in changes.items():
            override=current.setdefault(oid,{})
            override.update(pose)
            if fixed_pose:
                override['sign_fixed_pose']=True
        if not self._transaction_depth:
            self.revision += 1
            self.past.append(('移动或旋转自动标识',old))
            self.past = self.past[-80:]
            self.future.clear()
            if self.on_commit:self.on_commit(self)

    def undo(self):
        if not self.past:return False
        label,data=self.past.pop();self.future.append((label,copy.deepcopy(self.data)));self.data=data;self.revision+=1
        if self.on_commit:self.on_commit(self)
        return True
    def redo(self):
        if not self.future:return False
        label,data=self.future.pop();self.past.append((label,copy.deepcopy(self.data)));self.data=data;self.revision+=1
        if self.on_commit:self.on_commit(self)
        return True

    def create_asset(self,kind,name,points,**props):
        aid='A-'+uuid.uuid4().hex[:10]
        defaults=dict(width=45 if kind=='RUNWAY' else 18 if kind=='TAXIWAY' else 12,
                      shoulder=7.5 if kind=='TAXIWAY' else 0.,closed=False,closure_kind='PERMANENT',flow='BOTH',code_number=None,maxspan=None,
                      min_radius=None,holding_distance=None,source_note='',parent_id=None,
                      fillet_radius=25.,turn_radius=25.,center_visible=True,edges_visible=True,
                      shoulder_markings=False,auto_markings=True)
        if kind=='RUNWAY': defaults.update(label_a='09',label_b='27',level_a='1',level_b='1',displaced_a=0.,displaced_b=0.,lda_a=None,lda_b=None)
        if kind=='ROAD': defaults.update(width=7.,shoulder=0.,center_visible=False,auto_signs=False)
        if kind=='STAND': defaults.update(lead_radius=35.,move_snap14=True,show_safety=True,width=36,guidance='GUIDED',stop_reference='NOSEWHEEL',entry_mode='SELF_IN_PUSH_OUT',group='',configuration='',excludes=[])
        if kind=='MARKING':defaults.update(line_width=.15,text_height=4.,text='',spacing=2.,background=True,mark_type=props.get('mark_type'),verified_template=False)
        if kind=='RUNWAY':defaults['auto_number']=not ('label_a' in props or 'label_b' in props)
        defaults.update(props)
        with self.transaction('新增 '+name):self.assets[aid]=dict(id=aid,kind=kind,name=name or kind,points=copy.deepcopy(points),props=defaults)
        if kind=='RUNWAY' and defaults.get('auto_number'):
            from curve_model import number_runway
            number_runway(self,aid)
        return aid

    def update_asset(self,aid,name=None,points=None,props=None):
        with self.transaction('修改 '+self.assets[aid]['name']):
            a=self.assets[aid]
            if name is not None and name!=a['name']:
                from editor7_model import sync_name
                sync_name(self,aid,name)
            if points is not None and a['kind']=='STAND' and not a['props'].get('stand_polyline') and a['props'].get('entry_attached',True) and a['props'].get('entry_asset') in self.assets and abs(g.length(points)-g.length(a['points']))>1e-6:
                origin=a['points'][0];u=g.unit(points[0],points[-1]);L=g.length(points);points=[list(origin),[origin[k]+u[k]*L for k in (0,1)]]
            if points is not None:
                from curve_model import sync_authoring
                sync_authoring(a,points)
                a['points']=copy.deepcopy(points)
            if props:
                if (a['kind']=='MARKING' and a['props'].get('mark_type') in ('HOLD_A','HOLD_B')
                        and 'width' in props and props['width']!=a['props'].get('width')):
                    a['props']['hold_width_manual']=True
                a['props'].update(copy.deepcopy(props))
            if a['props'].get('deice_layout12'):a['points']=__import__('deice12').layout(self,a)['pavement']
            if a['kind']=='STAND':
                p=a['props'];parent=p.get('entry_asset')
                if props and props.get('entry_attached'):
                    if __import__('model20').axis(self,parent) is None:
                        options=[(g.project(b['points'],a['points'][0])[0],bid) for bid,b in self.assets.items() if b['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')]
                        if not options or min(options)[0]>20:raise ValueError('请先将机位入口移到滑行道中线附近，再绑定入口')
                        parent=min(options)[1];p['entry_asset']=parent
                    distance,station,q=g.project(__import__('model20').axis(self,parent)['points'],a['points'][0]);delta=[q[k]-a['points'][0][k] for k in (0,1)];a['points']=[[point[k]+delta[k] for k in (0,1)] for point in a['points']];p.update(entry_station=station,entry_attached=True)
                elif points is not None and __import__('model20').axis(self,parent):
                    distance,station,q=g.project(__import__('model20').axis(self,parent)['points'],a['points'][0]);p.update(entry_station=station,entry_attached=distance<.05)
            if props and props.get('closed'):a['props'].setdefault('closure_kind','PERMANENT')
            if props and 'route_type' in props and a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
                from project10 import SUBTYPES,rapid_option
                a['kind']=SUBTYPES.get(props['route_type'],a['kind'])
                if props['route_type']=='快速脱离道':rapid_option(self,aid,True)
                elif a['props'].get('rapid_exit'):rapid_option(self,aid,False)
            if a['kind']=='RUNWAY' and props:
                from project10 import synchronize
                numbering_changes=dict(props)
                if 'runway_suffix' in props:numbering_changes.setdefault('label_a',a['props'].get('label_a','09')[:2]+props['runway_suffix'])
                synchronize(a['props'],numbering_changes)
            if a['kind']=='ROAD':
                from roads10 import refresh_attachments
                refresh_attachments(self,aid)
            if props and ('label_a' in props or 'label_b' in props) and 'auto_number' not in props:a['props']['auto_number']=False
            if a['kind']=='RUNWAY' and a['props'].get('auto_number',False):
                from curve_model import number_runway
                number_runway(self,aid)
            if points is not None and a['kind']=='RUNWAY':
                from curve_model import follow_welds
                follow_welds(self,aid)
            if points is not None or props:
                from stand10 import refresh_entries
                refresh_entries(self,aid)
                from editor7_model import refresh_attached_marks
                refresh_attached_marks(self,aid)
                from marks11 import refresh_axis
                refresh_axis(self,aid)
                __import__('deice12').refresh(self)
                from route_geometry import rapid_layout
                for m in self.movements.values():
                    if m.get('geometry')=='RAPID' and aid in (m['from']['asset'],m['to']['asset']):
                        layout=rapid_layout(self,m);m['to']['station']=layout['station'];m['to']['direction']=layout['direction']

    def translate(self,aid,dx,dy):
        finite(dx,'dx');finite(dy,'dy')
        from scene_hierarchy import descendants
        with self.transaction('移动对象及组内子项'):
            for item in [aid]+descendants(self,aid):
                if item in self.assets:
                    a=self.assets[item];a['points']=[[x+dx,y+dy] for x,y in a['points']]
                    if a.get('design_vertices'):a['design_vertices']=[[x+dx,y+dy] for x,y in a['design_vertices']]
                    for node in a.get('curve_nodes',[]):
                        for key in ('p','incoming','outgoing'):node[key]=[node[key][0]+dx,node[key][1]+dy]

    def delete(self,oid):
        with self.transaction('删除对象及其连接'):
            if oid in self.movements: del self.movements[oid]
            elif oid in self.assets:
                del self.assets[oid]
                for mid in list(self.movements):
                    if oid in (self.movements[mid]['from']['asset'],self.movements[mid]['to']['asset']):del self.movements[mid]
                for a in self.assets.values():
                    if a['props'].get('parent_id')==oid:a['props']['parent_id']=None
                    a['props']['excludes']=[x for x in a['props'].get('excludes',[]) if x!=oid]
                for m in self.movements.values():m['protection_ids']=[x for x in m['protection_ids'] if x!=oid]
                self.data['junctions']={k:v for k,v in self.data.get('junctions',{}).items() if oid not in v.get('assets',[])}
            elif oid in self.data['groups']:del self.data['groups'][oid]
            from scene_hierarchy import all_objects
            for obj in all_objects(self).values():
                if obj.get('container_id')==oid:obj['container_id']=None
            self.data['generated_overrides']={k:v for k,v in self.data['generated_overrides'].items() if not k.startswith('AUTO:'+oid+':')}
            for field in ('closed_assets','active_stands'): self.scenario[field]=[x for x in self.scenario[field] if x in self.assets]
            self.scenario['permitted_movements']=[x for x in self.scenario['permitted_movements'] if x in self.movements]

    def connect(self,from_port,to_port,role='TAXIWAY_JOIN',name='',**props):
        mid='M-'+uuid.uuid4().hex[:10]
        from_port=copy.deepcopy(from_port);to_port=copy.deepcopy(to_port)
        if from_port.pop('_follow_existing',False):props.setdefault('follow_existing',True)
        if role=='PUSHBACK':
            from connection9 import pushback_ports
            ports,_,controls=pushback_ports(self,from_port,to_port);from_port,to_port=ports
            props.setdefault('bezier_controls',controls);props.setdefault('pavement_visible',False);props.setdefault('edges_visible',False);props.setdefault('shoulder',0.);props.setdefault('show_holding',False)
        pa,_=g.at(self.assets[from_port['asset']]['points'],from_port['station'])
        pb,_=g.at(self.assets[to_port['asset']]['points'],to_port['station'])
        m=dict(id=mid,name=name or role,**{'from':copy.deepcopy(from_port),'to':copy.deepcopy(to_port)},
               role=role,enabled=True,bidirectional=False,width=12.,handle=max(5,g.distance(pa,pb)*.4),
               maxspan=None,min_radius=None,holding_distance=90.,protection_ids=[],source_note='',
               sign_mode='AUTO',stopbar='UNKNOWN',evidence_status='UNVERIFIED',
               shoulder=7.5,guide_visible=True,pavement_visible=True,edges_visible=True,show_holding=True,
               geometry='AUTO',exit_angle=30.,exit_radius=550.,join_radius=25.,auto_signs=True,
               rapid_auto_fit=True,rapid_auto_radius=False,rapid_min_straight=1.,join_reverse_visible=True,reverse_join_pavement=True)
        m.update(props)
        if role=='RAPID_EXIT' and 'geometry' not in props and not props.get('legacy_attachment'):
            from route_geometry import rapid_layout
            try:
                layout=rapid_layout(self,m);m['geometry']='RAPID';m['to']['station']=layout['station'];m['to']['direction']=layout['direction']
            except ValueError:
                m['geometry']='BEZIER';m['source_note']='无法自动构造平行道快速出口；保留可编辑曲线，需专项复核。'
        with self.transaction('连接 '+m['name']):self.movements[mid]=m
        return mid

    def update_movement(self,mid,**props):
        with self.transaction('修改连接'):__import__('connection20_2').update(self.movements[mid],props)

    def create_marking(self,mark_type,points,name=None,**props):
        from marking_catalog import CATALOG
        if mark_type not in CATALOG:raise ValueError('Unknown marking template')
        defaults=copy.deepcopy(CATALOG[mark_type].get('defaults',{}));defaults.update(props)
        if mark_type in ('HYDRANT','PIT') and 'text' not in props:
            prefix='H' if mark_type=='HYDRANT' else 'J';used={a['props'].get('text') for a in self.assets.values() if a['kind']=='MARKING'};index=1
            while prefix+str(index) in used:index+=1
            defaults['text']=prefix+str(index)
        defaults['mark_type']=mark_type
        return self.create_asset('MARKING',name or CATALOG[mark_type]['name'],points,**defaults)

    def configure_junction(self,junction_id,**settings):
        from pavement_geometry import crossings
        junction=next((x for x in crossings(self) if x['id']==junction_id),None)
        if junction is None:raise ValueError('Junction no longer exists; refresh after moving its roads')
        with self.transaction('编辑岔路口引导线'):
            data=self.data['junctions'].setdefault(junction_id,dict(assets=junction['assets'],radius=25.,guides={}))
            data.update(copy.deepcopy(settings))

    def movement_path(self,mid):
        m=self.movements[mid]; pts=[];tangents=[]
        for key in ('from','to'):
            port=m[key];p,u=g.at(self.assets[port['asset']]['points'],port['station'])
            pts.append(p);tangents.append((u[0]*port['direction'],u[1]*port['direction']))
        if m.get('legacy_attachment'):return pts
        if m.get('geometry')=='STRAIGHT':return pts
        if m.get('follow_existing'):
            from connection9 import existing_plan
            plan=existing_plan(self,m['from'],m['to'],m.get('bezier_controls'),m.get('join_radius',25))
            if plan:return plan['points']
            return [pts[0],pts[0]]
        if m.get('bezier_controls'):
            from curve_model import node,evaluate
            first=node(pts[0]);last=node(pts[-1]);first['outgoing']=m['bezier_controls'][0];last['incoming']=m['bezier_controls'][1]
            return evaluate([first,last])
        if m.get('geometry')=='STRAIGHT':return pts
        if m.get('geometry')=='RAPID':
            from route_geometry import rapid_path
            return rapid_path(self,m)
        from connection9 import safe_controls,path_with_controls
        if m['role']=='PUSHBACK':
            from connection9 import pushback_ports
            _,path,_=pushback_ports(self,m['from'],m['to']);return path
        return path_with_controls(*pts,safe_controls(*pts,*tangents,m['handle']))

    def create_group(self,name,parent=None):
        from scene_hierarchy import create_group
        return create_group(self,name,parent)

    def reparent(self,oid,parent=None):
        from scene_hierarchy import reparent
        return reparent(self,oid,parent)

    def split_asset(self,aid,station):
        """Split a non-runway path atomically and remap all station anchors."""
        a=self.assets[aid];total=g.length(a['points'])
        finite(station,'split station',0,positive=True)
        if a['kind'] not in PATH_KINDS or a['kind'] in ('RUNWAY','STAND') or not 1<=station<=total-1:
            raise ValueError('Split a taxi route at least 1m from its ends; runway/stand physical identity is not split')
        with self.transaction('切分路线并重映射锚点'):
            original=copy.deepcopy(a);left=g.subpath(a['points'],0,station);right=g.subpath(a['points'],station,total)
            self.assets[aid]['points']=left
            bid=self.create_asset(a['kind'],a['name']+' / 后段',right,**original['props'])
            self.assets[bid]['props']['network_id']='N-'+uuid.uuid4().hex[:10]
            self.assets[bid]['props']['designation']=self.assets[bid]['name']
            if original.get('curve_nodes'):
                from curve_model import split_curve_nodes,evaluate
                ln,rn=split_curve_nodes(original['curve_nodes'],station)
                for key,nodes in ((aid,ln),(bid,rn)):
                    self.assets[key]['curve_nodes']=nodes;self.assets[key]['points']=evaluate(nodes)
                    # Cubic subdivision preserves exactly the drawn curve at the identifier break.
                    self.assets[key]['design_vertices']=[n['p'][:] for n in nodes]
                    self.assets[key]['props']['split_curve_preserved']=True
            if aid in self.scenario['closed_assets']:self.scenario['closed_assets'].append(bid)
            for m in self.movements.values():
                for side in ('from','to'):
                    port=m[side]
                    if port['asset']==aid:
                        if port['station']>station:
                            port['asset']=bid;port['station']=(port['station']-station)*g.length(self.assets[bid]['points'])/(total-station)
                        else:port['station']*=g.length(self.assets[aid]['points'])/station
            __import__('signs21_2').remap_split(self,aid,bid,station,total)
            join=self.connect(dict(asset=aid,station=g.length(self.assets[aid]['points']),direction=1),dict(asset=bid,station=0.,direction=1),
                              'TAXIWAY_JOIN',a['name']+' 连续节点',width=a['props']['width'],bidirectional=True,
                              legacy_attachment=True,handle=1)
            self.movements[join]['source_note']='路线切分产生的零距离拓扑连续节点。'
        return bid

    def is_closed(self,aid):
        a=self.assets[aid]
        if a['props']['closed'] or aid in self.scenario['closed_assets']:return True
        for area in self.assets.values():
            if area['kind']=='CLOSED_AREA' and g.intersects_area(a['points'],area['points']):return True
        return False

    def movement_available(self,m,reverse=False):
        if m.get('follow_existing'):
            from connection9 import existing_plan
            if existing_plan(self,m['from'],m['to']) is None:return False
        if not m['enabled'] or any(self.is_closed(m[p]['asset']) for p in ('from','to')):return False
        span=self.scenario['aircraft_wingspan']
        if m.get('maxspan') is not None and span>m['maxspan']:return False
        for side in ('from','to'):
            a=self.assets[m[side]['asset']];limit=a['props'].get('maxspan')
            if limit is not None and span>limit:return False
            flow=a['props']['flow'];direction=m[side]['direction']*(-1 if reverse else 1)
            if flow=='FORWARD' and direction<0 or flow=='REVERSE' and direction>0:return False
        path=self.movement_path(m['id'])
        for area in self.assets.values():
            if area['kind']=='CLOSED_AREA' and g.intersects_area(path,area['points']):return False
        return True

    def route(self,start_asset,end_asset,require_permit=False):
        """Port graph with directed asset subpaths; apron polygons are not traversable."""
        if start_asset not in self.assets or end_asset not in self.assets:raise ValueError('Select start/end assets')
        if any(self.assets[x]['kind'] not in PATH_KINDS or self.is_closed(x) for x in (start_asset,end_asset)):return None
        if (self.assets[start_asset]['kind']=='ROAD')!=(self.assets[end_asset]['kind']=='ROAD'):return None
        graph={}; stations={aid:{0.,g.length(a['points'])} for aid,a in self.assets.items() if a['kind'] in PATH_KINDS}
        # Orientation is part of the graph state. Reaching a port must not
        # silently authorize a U-turn on an otherwise bidirectional pavement.
        def node(a,s,d):return f'{a}@{s:.6f}/{d}'
        def edge(a,b,points,mid=None):graph.setdefault(a,[]).append((b,g.length(points),points,mid))
        for m in self.movements.values():
            for key in ('from','to'):stations[m[key]['asset']].add(float(m[key]['station']))
        for aid,st in stations.items():
            a=self.assets[aid]
            if self.is_closed(aid):continue
            limit=a['props'].get('maxspan')
            if limit is not None and self.scenario['aircraft_wingspan']>limit:continue
            ss=sorted(st)
            for lo,hi in zip(ss,ss[1:]):
                pts=g.subpath(a['points'],lo,hi)
                if a['props']['flow']!='REVERSE':edge(node(aid,lo,1),node(aid,hi,1),pts)
                if a['props']['flow']!='FORWARD':edge(node(aid,hi,-1),node(aid,lo,-1),list(reversed(pts)))
        for m in self.movements.values():
            forward=self.movement_available(m);reverse=m['bidirectional'] and self.movement_available(m,True)
            if not forward and not reverse:continue
            involved_runway=any(self.assets[m[k]['asset']]['kind']=='RUNWAY' for k in ('from','to'))
            if require_permit and involved_runway and (m['id'] not in self.scenario['permitted_movements'] or m['stopbar']!='OFF'):continue
            a=node(m['from']['asset'],m['from']['station'],m['from']['direction']);b=node(m['to']['asset'],m['to']['station'],m['to']['direction']);pts=self.movement_path(m['id'])
            if forward:edge(a,b,pts,m['id'])
            if reverse:
                ra=node(m['to']['asset'],m['to']['station'],-m['to']['direction'])
                rb=node(m['from']['asset'],m['from']['station'],-m['from']['direction'])
                edge(ra,rb,list(reversed(pts)),m['id'])
        start='__START__';end='__END__'
        for direction in (1,-1):
            edge(start,node(start_asset,0,direction),[self.assets[start_asset]['points'][0]])
            edge(node(end_asset,g.length(self.assets[end_asset]['points']),direction),end,[self.assets[end_asset]['points'][-1]])
        queue=[(0,start)];best={start:0};previous={}
        while queue:
            cost,current=heapq.heappop(queue)
            if cost>best[current]:continue
            if current==end:
                pieces=[];used=[]
                while current!=start:
                    prev,pts,mid=previous[current];pieces.append(pts)
                    if mid:used.append(mid)
                    current=prev
                return dict(length=cost,points=[pt for seg in reversed(pieces) for pt in seg],movements=list(reversed(used)),status='PREVIEW_NOT_CLEARANCE')
            for target,weight,pts,mid in graph.get(current,[]):
                new=cost+weight
                if new<best.get(target,float('inf')):
                    best[target]=new;previous[target]=(current,pts,mid);heapq.heappush(queue,(new,target))
        return None

    def set_scenario(self,**props):
        with self.transaction('修改运行情景'):self.scenario.update(copy.deepcopy(props))

    def save(self,path):
        self.validate_structure();target=Path(path)
        temp=target.with_name(target.name+'.tmp')
        text=json.dumps(self.data,ensure_ascii=False,indent=2,allow_nan=False)
        payload=text.encode('utf-8')
        if len(payload)>MAX_PROJECT_BYTES:
            raise ValueError('工程文件超过 110 MB，请减少底图或缩小图片。')
        temp.write_bytes(payload);temp.replace(target)

    @classmethod
    def load(cls,path):
        path=Path(path)
        if path.stat().st_size>MAX_PROJECT_BYTES:raise ValueError('Scene exceeds 110 MB input budget')
        return cls(json.loads(path.read_text(encoding='utf-8-sig')))

    @classmethod
    def demo(cls):
        s=cls();s.data['meta']['name']='示例机场 · 跑道 / 滑行道 / 机坪'
        r=s.create_asset('RUNWAY','09 / 27',[[-1200,0],[1200,0]],width=45,shoulder=7.5,code_number=4)
        t=s.create_asset('TAXIWAY','A 平行滑行道',[[-1100,230],[1100,230]],width=23,shoulder=7.5,code_number=4)
        ap=s.create_asset('APRON','P1 客机坪',[[-650,370],[1000,370],[1000,850],[-650,850]],width=1)
        a=s.create_asset('APRON_TAXIWAY','P1 机坪滑行道',[[-300,440],[850,440]],width=23,parent_id=ap)
        s.connect(dict(asset=t,station=700.,direction=1),dict(asset=r,station=1000.,direction=1),'ENTRY','A1 跑道入口',width=23)
        s.connect(dict(asset=r,station=500.,direction=1),dict(asset=t,station=550.,direction=1),'EXIT_ONLY','A2 仅作出口',width=23)
        s.connect(dict(asset=t,station=650.,direction=1),dict(asset=a,station=0.,direction=1),'APRON_ACCESS','P1 入口',width=23,bidirectional=True)
        for i,x in enumerate((-100,250,600),101):
            stand=s.create_asset('STAND',str(i),[[x,550],[x,710]],width=38,maxspan=36,parent_id=ap,group='P1')
            s.connect(dict(asset=a,station=x+300.,direction=1),dict(asset=stand,station=0.,direction=1),'STAND_ENTRY',f'{i} 引入',width=16)
            s.connect(dict(asset=stand,station=0.,direction=-1),dict(asset=a,station=x+350.,direction=-1),'PUSHBACK',f'{i} 推出',width=16)
        s.past.clear();return s

