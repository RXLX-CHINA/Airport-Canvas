"""Auditable implemented checks; missing engineering evidence never passes."""
import csv
from pathlib import Path
import math
import scene_geometry as g

SOURCE='https://www.caac.gov.cn/XXGK/XXGK/TZTG/202506/P020250701401698137311.pdf'

def holding_plan(scene,mid):
    m=scene.movements[mid]
    runway=None;taxiway=None
    for key in ('from','to'):
        a=scene.assets[m[key]['asset']]
        if a['kind']=='RUNWAY':runway=a
        else:taxiway=a
    if runway is None:return None
    path=scene.movement_path(mid)
    # A legacy attachment is a logical link with coincident endpoints. Its
    # actual exit geometry is the attached route, not that zero-length link.
    if m.get('legacy_attachment'):
        path=[list(p) for p in taxiway['points']];port=next(m[k] for k in ('from','to') if m[k]['asset']==taxiway['id'])
        if port['station']<g.length(path)/2:path=list(reversed(path))
    elif scene.assets[m['from']['asset']]['kind']=='RUNWAY':path=list(reversed(path))
    u=g.unit(*runway['points']);origin=runway['points'][0]
    def off(p):return abs((p[0]-origin[0])*(-u[1])+(p[1]-origin[1])*u[0])
    target=m['holding_distance'];station=0;found=None
    for a,b in zip(path,path[1:]):
        da,db=off(a),off(b);seg=g.distance(a,b)
        if da>=target>=db and abs(da-db)>1e-9:
            t=(da-target)/(da-db);found=station+t*seg;break
        station+=seg
    if found is None:return dict(status='UNKNOWN',reason='连接长度/位置不能容纳候选等待距离',movement=mid)
    point,tangent=g.at(path,found)
    start=max(0,found-47)
    enhanced=g.subpath(path,start,found)
    # Only one candidate holding position per exit-only junction; no fabricated B line.
    return dict(status='UNVERIFIED',movement=mid,runway=runway['id'],point=point,tangent=list(tangent),
                span=m['width']+2*m.get('shoulder',taxiway['props'].get('shoulder',0)),station=found,
                toward_path=path,enhanced=enhanced,enhanced_length=found-start,
                black_border_excluded=True,edge_break_gap=.9,shoulder_bar_omit_distance=7.5,
                source=SOURCE,hold_count=1,type='A_CANDIDATE',
                reason='候选位置；未核验表4.12.6全部条件、保护区、航空器扫掠及原图尺寸')

def validate_scene(scene):
    scene.validate_structure();issues=[]
    def issue(oid,status,rule,message,source='软件数据/几何约束',actual=None,required=None):
        issues.append(dict(object_id=oid,status=status,rule=rule,message=message,source=source,actual=actual,required=required))
    issue(None,'UNVERIFIED','SCOPE','规则库为部分实现；不等同于CAAC认证。未核验项不能算通过。','MH5001-2021及修订案')
    if scene.scenario['date']>='2027-05-01':
        issue(None,'UNVERIFIED','VERSION','当前规则档未编译第五修订案，所选日期需要升级规则包。','第五修订案施行公告')
    if scene.data['meta'].get('magnetic_declination') is None:
        issue(None,'UNKNOWN','CRS','未提供磁差/历元；当前只使用本地设计坐标，不推断跑道磁号码。')
    for aid,a in scene.assets.items():
        p=a['props'];kind=a['kind']
        if p.get('turn_pad'):issue(aid,'UNVERIFIED','TURN_PAD_SWEEP','掉头坪为参数化设计；需按最大机型核查鼻轮转角、轮迹及道面边缘净距。','4.3 / 6.2.9')
        if kind=='STAND':issue(aid,'UNVERIFIED','STAND_PROFILE','引入线构型与机型包络需核对原图、最大机型和发动机危险区。','6.2.16 / 6.2.18')
        for key,value in p.get('effective_radii',{}).items():
            requested=p.get('corner_radii',{}).get(key,p.get('corner_radius',25))
            if value<requested-.01:issue(aid,'REVIEW_REQUIRED','FILLET_FIT','短线段限制圆角半径；实际值小于请求值。','几何空间约束',value,requested)
        if kind=='MARKING':
            from marking_catalog import CATALOG
            spec=CATALOG[p['mark_type']]
            issue(aid,'UNVERIFIED','MARKING_TEMPLATE',spec['review'],spec['clause'])
        if scene.is_closed(aid):issue(aid,'NOT_APPLICABLE','CLOSED','当前场景关闭，不参与通行寻路。')
        if kind in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
            issue(aid,'UNKNOWN','PHYSICAL','缺少完整轮距、驾驶舱位置、道面承载/坡度/净距证据。','4.9、4.13及3.6修订条款')
            if p.get('maxspan') is not None and scene.scenario['aircraft_wingspan']>p['maxspan']:
                issue(aid,'FAIL','SPAN','当前航空器翼展超过路线配置上限。','配置的适用机型限制',scene.scenario['aircraft_wingspan'],p['maxspan'])
        if kind=='RUNWAY':
            from runway import aim_dimensions,threshold_geometry
            count,stripe=threshold_geometry(p['width'])
            issue(aid,'PASS' if 0<=p['width']/2-count*stripe<=3 or p['width']>60 else 'REVIEW_REQUIRED','THRESHOLD_EDGE','入口条纹数量与横向范围检查；靠近边线本身并不代表错误。','6.2.4',round(p['width']/2-count*stripe,3),'边缘距离≤3 m；宽跑道另受27 m半宽限制')
            for end in ('a','b'):
                lda=p.get('lda_'+end) or g.length(a['points'])-p.get('displaced_'+end,0)
                _,length,width,gap=aim_dimensions(lda,p.get('aim_width_'+end),p.get('aim_gap_'+end),p.get('aim_length_'+end))
                clearance=p['width']/2-gap/2-width
                issue(aid,'FAIL' if clearance<0 else 'REVIEW_REQUIRED' if clearance<(.9 if p['width']>=30 else .45) else 'PASS','AIM_EDGE_'+end.upper(),'瞄准点条块外缘至道面边距离；负值时不自动绘出越界条块。','表6.2.5',round(clearance,3),'检查道面边及边线占用；尺寸仍须符合表6.2.5')
            if p.get('code_number') is None:issue(aid,'UNKNOWN','RUNWAY_CODE','请提供飞行区指标Ⅰ；不从物理长度猜测。','第2章及4.12')
            issue(aid,'UNVERIFIED','RUNWAY_MARKINGS','跑道端类别分别保存；统一场景标志为预览，完整跑道标志可使用旧入口导出。','6.2.2—6.2.7')
        if kind in ('APRON_TAXIWAY','STAND_TAXILANE','STAND'):
            parent=p.get('parent_id')
            aprons=[scene.assets[parent]] if parent in scene.assets and scene.assets[parent]['kind']=='APRON' else [x for x in scene.assets.values() if x['kind']=='APRON']
            if not aprons or not all(any(g.inside(pt,ap['points']) for ap in aprons) for pt in a['points']):
                issue(aid,'FAIL','APRON_CONTAINMENT','机位/机坪路线端点未完整位于关联机坪内；检查布局与所属机坪。')
        if kind=='STAND':
            if p.get('stop_length',2)<2 or p.get('stop_width',.15)<.15:
                issue(aid,'FAIL','STAND_STOP_SIZE','有引导停止线长度应不小于2 m，宽度应不小于0.15 m。','6.2.16(7)')
            if not .15<=p.get('aircraft_text_height',.2)<=.3:
                issue(aid,'REVIEW_REQUIRED','AIRCRAFT_TEXT','机型编码字高宜为0.15～0.3 m。','6.2.16(7)')
            expected='NOSEWHEEL' if p['guidance']=='GUIDED' else 'LEFT_SEAT'
            if p['stop_reference']!=expected:issue(aid,'FAIL','STOP_REFERENCE','停止点参考与引导方式不一致。','6.2.16(7)',p['stop_reference'],expected)
            else:issue(aid,'PASS','STOP_REFERENCE','停止参考字段与所选引导方式一致；不代表停靠净距通过。','6.2.16(7)')
            issue(aid,'UNKNOWN','STAND_CLEARANCE','未核验邻机、廊桥、设备区、发动机危险区和真实航空器包络。','4.13.5、6.2.16—6.2.20')
            active=scene.scenario['active_stands']
            if aid in active and any(x in active for x in p.get('excludes',[])):
                issue(aid,'FAIL','STAND_MUTEX','互斥主辅机位同时处于活动占用状态。','机位配置互斥约束')
    for mid,m in scene.movements.items():
        pts=scene.movement_path(mid);r=g.radius(pts);role=m['role']
        if g.length(pts)<1 and not m.get('legacy_attachment'):issue(mid,'FAIL','CONNECTOR_LENGTH','连接过短；调整锚点或曲线控制长度。')
        if m.get('min_radius') is not None:
            issue(mid,'FAIL' if r+1e-5<m['min_radius'] else 'PASS','CURVE_RADIUS',
                  '中心线曲率与用户配置半径比较；并非航空器扫掠验证。','用户设计约束',None if math.isinf(r) else round(r,2),m['min_radius'])
        if role=='RAPID_EXIT':
            runway=scene.assets[m['from']['asset']];code=runway['props'].get('code_number')
            p0,u0=g.at(runway['points'],m['from']['station']);other=scene.assets[m['to']['asset']]
            if m.get('legacy_attachment') and not other['props'].get('rapid_radius'):
                issue(mid,'REVIEW_REQUIRED','RAPID_PREFAB','手绘快速脱离道尚无已拟合的出口圆弧；核对出口角、半径、直线段及接收路线。','4.9.10',other['props'].get('rapid_fit_note'),None)
                continue
            _,u1=g.at(other['points'],m['to']['station'])
            dot=max(-1,min(1,sum(u0[k]*m['from']['direction']*u1[k]*m['to']['direction'] for k in (0,1))))
            if m.get('legacy_attachment') and len(other.get('curve_nodes',[]))>=4:
                nodes=other['curve_nodes'];path=other['points']
                if m['to']['station']>g.length(path)/2:nodes=list(reversed(nodes));path=list(reversed(path))
                heading=g.unit(nodes[1]['p'],nodes[2]['p']);angle=math.degrees(math.acos(max(-1,min(1,sum(u0[k]*m['from']['direction']*heading[k] for k in (0,1))))))
                end=g.project(path,nodes[1]['p'])[1];turnout_radius=g.radius(g.subpath(path,0,end))
            elif m.get('geometry')=='RAPID':
                from route_geometry import rapid_layout,reverse_join
                plan=rapid_layout(scene,m);angle=plan['exit_angle'];turnout_radius=plan['r']
                if (m.get('join_reverse_visible',True) or m.get('reverse_join_pavement',True)) and reverse_join(scene,m) is None:issue(mid,'REVIEW_REQUIRED','REVERSE_JOIN','当前道路流向或有限路段约束不允许反向接入；未强行绘制。','设计几何与运行流向约束')
            else:angle=math.degrees(math.acos(dot));turnout_radius=r
            issue(mid,'PASS' if 25-1e-8<=angle<=45+1e-8 else 'FAIL','RAPID_ANGLE','快速出口进出端切线交角。','4.9.10',round(angle,2),'25..45°')
            if code:
                recommend=550 if code in (3,4) else 275
                issue(mid,'REVIEW_REQUIRED' if turnout_radius<recommend else 'PASS','RAPID_RADIUS',
                      '转出圆弧半径与参考值比较；低于推荐值需设计复核。','4.9.10及表4.9.10',None if math.isinf(turnout_radius) else round(turnout_radius,2),recommend)
            else:issue(mid,'UNKNOWN','RAPID_CODE','未提供代码，无法选择快速出口参考半径。','表4.9.10')
            issue(mid,'UNKNOWN','RAPID_STOP','尚未核验转出速度、湿道面制动和后续可停住直线。','4.9.10')
        hold=holding_plan(scene,mid)
        if hold:
            issue(mid,hold['status'],'HOLD_LOCATION',hold['reason'],'4.12.6、6.2.10及第四修订案')
            if hold.get('point'):
                if role in ('EXIT_ONLY','RAPID_EXIT'):
                    issue(mid,'PASS','S4_HOLD_COUNT','派生候选A型等待位置数量为1；位置与完整构型仍未核验。',SOURCE,hold['hold_count'],1)
                else:issue(mid,'UNKNOWN','HOLD_COMBINATION','仅生成一个候选A型；是否需要B型及组合/位置关系尚待专项数据。','6.2.10')
                if hold['enhanced_length']<47-1e-6:issue(mid,'FAIL','ENHANCED_SPACE','候选等待位置外侧不足47m；不能把截短预览当作满足长度。','6.2.8(6)',hold['enhanced_length'],47)
                issue(mid,'UNVERIFIED','FACILITY_TEMPLATE','预览应用全宽、边线断开及条带避让；A/B型完整原图和复杂交汇构型尚待核验。',SOURCE)
            protections=[x for x in m.get('protection_ids',[]) if x in scene.assets and scene.assets[x]['kind']=='PROTECTION']
            issue(mid,'UNVERIFIED' if protections else 'UNKNOWN','PROTECTION',
                  '保护区为二维设计多边形；尚未核验三维边界/航空器影响。' if protections else '未关联ILS/MLS、净空/内过渡等保护区。','4.12.3—4.12.6')
            if scene.scenario['night'] or scene.scenario['rvr']<550:
                issue(mid,'UNKNOWN','LIGHTING','需按昼夜/RVR、交通密度和例外条件核验牌灯、光学、电路及联锁，不能只看图形。','第7—11章')
        if not scene.movement_available(m):issue(mid,'NOT_APPLICABLE','MOVEMENT_POLICY','连接已关闭、方向或翼展受限，不参与当前场景寻路。')
        issue(mid,'UNKNOWN','SWEPT_PATH','当前连接为连续三次曲线；尚未按航空器轮迹和驾驶舱位置完成扫掠验证。','4.9.2—4.9.5')
    # A geometric crossing remains disconnected; make this visible rather than silently joining.
    paths=[a for a in scene.assets.values() if a['kind'] in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','ROAD')]
    linked={frozenset((m['from']['asset'],m['to']['asset'])) for m in scene.movements.values()}
    from shapely import STRtree, box
    segments=[]
    envelopes=[]
    for asset in paths:
        axis=list(zip(asset['points'],asset['points'][1:]))
        segments.append(axis)
        bounds=[]
        for a,b in axis:
            # Match the endpoint tolerance in scene_geometry.crossing.
            dx=abs(b[0]-a[0])*1e-9+1e-8
            dy=abs(b[1]-a[1])*1e-9+1e-8
            bounds.append(box(min(a[0],b[0])-dx,min(a[1],b[1])-dy,
                              max(a[0],b[0])+dx,max(a[1],b[1])+dy))
        envelopes.append(bounds)
    trees=[STRtree(bounds) for bounds in envelopes]
    for i,a in enumerate(paths):
        for j in range(i+1,len(paths)):
            b=paths[j]
            if frozenset((a['id'],b['id'])) in linked:
                continue
            left,right=trees[j].query(envelopes[i])
            if any(g.crossing(*segments[i][k],*segments[j][l]) for k,l in zip(left,right)):
                message=f'与 {b["name"]} 仅几何相交，尚无允许操纵；需明确连接或保留仅交叉。'
                if (a['kind']=='ROAD')!=(b['kind']=='ROAD'):message=f'与 {b["name"]} 存在航空器/车辆交叉，需独立道路等待及控制方案。'
                issue(a['id'],'REVIEW_REQUIRED','UNCONNECTED_CROSSING',message,'显式连接/道路控制约束')
    from automatic_markings import generated_markings
    from marking_standards import marking_checks
    from audit9 import checks
    generated=generated_markings(scene)
    issues.extend(marking_checks(scene,generated))
    issues.extend(checks(scene,generated))
    from deice11 import checks as deice_checks
    issues.extend(deice_checks(scene))
    issues.extend(__import__('rules13').checks(scene))
    issues.extend(__import__('terminal19').checks(scene))
    issues.extend(__import__('styles19').checks(scene,generated))
    issues.extend(__import__('model20').checks(scene))
    issues.extend(__import__('connection20_2').checks(scene,generated))
    issues.extend(__import__('runway20').checks(scene,generated))
    return dict(status='NOT_CERTIFIED',scenario=scene.scenario.copy(),issues=issues,
                coverage=coverage_summary(),summary={state:sum(x['status']==state for x in issues) for state in ('PASS','FAIL','UNKNOWN','UNVERIFIED','NOT_APPLICABLE','REVIEW_REQUIRED')})

def coverage_summary():
    path=Path(__file__).resolve().parent/'Coverage.csv'
    groups=0
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:groups=sum(1 for _ in csv.DictReader(f))
    return dict(mapped_topic_groups=groups,atomic_coverage_percent=None,source_inventory_complete=False,
                message='章节清单不是逐条规则覆盖；未实现/未核验项不计为通过。')
