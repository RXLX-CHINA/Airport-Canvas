"""Explicit geometry changes, pure creation previews and F6 connector picking."""
import copy
import scene_geometry as g

def update(m,props):
    props=copy.deepcopy(props);old=m.get('geometry','AUTO');mode=props.get('geometry',old)
    if 'geometry' in props and mode=='STRAIGHT':
        if old!='STRAIGHT':m['curve_backup20_2']={k:copy.deepcopy(m[k]) for k in ('geometry','bezier_controls','follow_existing','auto_tangent') if k in m}
        m.pop('bezier_controls',None);m.pop('automatic_geometry',None);props.pop('bezier_controls',None);props.update(follow_existing=False,auto_tangent=False)
    elif 'geometry' in props and old=='STRAIGHT' and mode in ('AUTO','BEZIER'):
        props['follow_existing']=False
        if mode=='BEZIER' and 'bezier_controls' not in props and m.get('curve_backup20_2',{}).get('bezier_controls'):props['bezier_controls']=copy.deepcopy(m['curve_backup20_2']['bezier_controls'])
    m.update(props)

def creation_preview(scene,mode,points,q,props,stand_start=None,deice_hit=None):
    if mode=='MARK:TWY_ENHANCED':return []
    if mode=='CONNECT':return [] # Editor7.redraw paints the already-computed connection candidate.
    if mode=='DEICE10' and deice_hit:
        module=__import__('deice12');layout=module.layout(scene,module.draft(scene,deice_hit,q,**props));return [dict(points=layout[key]+([layout[key][0]] if key=='pavement' else []),tag='deice_preview12') for key in ('pavement','route','hold')]
    if not points:return []
    if mode=='STAND' and props.get('stand_polyline'):
        path=points+[q] if g.distance(points[-1],q)>.01 else points
        return [dict(points=path,tag='stand_preview11')] if len(path)>1 else []
    if mode=='STAND' and g.distance(points[0],q)>5:
        a=dict(id='preview',kind='STAND',name='101',points=[points[0],q],props=dict(props,stand_number='101'))
        if stand_start:a['props'].update(entry_asset=stand_start[1],entry_station=stand_start[2],entry_attached=True)
        return [dict(points=part['points'],tag='stand_preview11') for part in __import__('stand15').design(a,scene)['paths']]
    path=points+[q]
    from marking_catalog import CATALOG
    if mode in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','ROAD') or mode.startswith('MARK:') and CATALOG[mode[5:]]['mode']=='PATH':
        from curve_model import rounded_nodes,evaluate
        nodes,_=rounded_nodes(path,props.get('corner_radius',25 if mode=='TAXIWAY' else 10));path=evaluate(nodes)
    return [dict(points=path,tag='line_preview12')]

def pick_axis(scene,q,tolerance):
    import guidance20,model20
    rows=[]
    for aid,a in model20.axes(scene).items():
        d,s,p=g.project(a['points'],q)
        if d<=tolerance:rows.append((d,0 if aid in scene.movements else 1,aid))
    for aid,a in guidance20.routes(scene).items():
        owner=a['props'].get('guidance_owner20')
        if owner not in scene.assets and owner not in scene.movements:continue
        d,_,_=g.project(a['points'],q)
        if d<=tolerance:rows.append((d,2,owner))
    return min(rows)[2] if rows else None

def checks(scene,generated=None):
    from automatic_markings import generated_markings
    out=[];seen=set()
    if generated is None:generated=generated_markings(scene)
    for m in generated.values():
        p=m['props'];owner=m.get('owner')
        if p.get('paired_mandatory20_2') and p.get('auto_scaled') and owner not in seen:
            seen.add(owner);out.append(dict(object_id=owner,status='REVIEW_REQUIRED',rule='PAIRED_MANDATORY20_2',message='按项目选择在较窄道面两侧绘制强制性指令标志，字高为适应可用宽度已调整，需复核指标要求。',source='项目成对显示选择；MH5001—2021 6.2.12',actual=p['text_height'],required=p.get('design_text_height',4)))
    return out
