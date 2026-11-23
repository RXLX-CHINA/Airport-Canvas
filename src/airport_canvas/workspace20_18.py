"""Workspace commands, independent of numbering and display modes."""
import math
import scene_geometry as g

def invalidate_scene(scene):
    for key in ('_route_cache','_cross_cache','_guidance20','_road10_cache','_enhanced_cache19'):scene.__dict__[key]=None

def build(editor):
    import qt_compat as tk
    from qt_compat import ttk
    menu=editor.nametowidget(editor.cget('menu'))
    edit=menu.entrycget('编辑','menu')
    operations=tk.Menu(edit,tearoff=False)
    edit.add_cascade(label='布尔运算',menu=operations)
    for title,op in [('并集','UNION'),('交集','INTERSECTION'),('差集（第一个减第二个）','DIFFERENCE')]:
        operations.add_command(label=title,command=lambda operation=op:boolean(editor,operation))
    info=tk.Menu(menu,tearoff=False);menu.add_cascade(label='信息引导',menu=info)
    for label,key in [('自动道面信息标志 · 8.2.13','auto_information20_18'),('自动方向标记牌 · 9.7.4.3','auto_boards20_18'),('F6保留机位及引入线','f6_stands20_18')]:
        variable=tk.BooleanVar(master=editor,value=editor.scene.data['meta'].get(key,True));editor.__dict__.setdefault('_options20_18',{})[key]=variable
        info.add_checkbutton(label=label,variable=variable,command=lambda k=key,v=variable:option(editor,k,v.get()))
    info.add_separator();info.add_command(label='恢复选中滑行道的截断',command=lambda:restore(editor))
    icon = editor.action_icon11('TRUNCATE20_18')
    editor._photos['action11TRUNCATE20_18'] = icon
    button = ttk.Button(editor.tool_buttons['SELECT'].master, image=icon,
                        command=lambda: choose_cut(editor,False), padding=4)
    button.bind('<Button-3>',lambda e:choose_cut(editor,True))
    button.q.setAccessibleName('末端截断')
    button.pack(side='left', padx=2)
    editor.tool_buttons['TRUNCATE20_18'] = button
    editor.tip11(button,'点击工具按钮：左键选删左端，右键选删右端。画布左键确认，右键取消。')

def choose_cut(editor,right):
    editor._truncate_right21_2 = right
    editor.set_mode('TRUNCATE20_18')
    return 'break'

def option(editor,key,value):
    with editor.scene.transaction('显示与信息引导选项'):editor.scene.data['meta'][key]=bool(value)
    editor.refresh()

def restore(editor):
    try:__import__('segments18').restore(editor.scene,editor.selection);editor.refresh()
    except (KeyError,ValueError) as exc:editor.status.set(str(exc))

def boolean(editor,operation):
    try:
        current=set(editor.selected_ids)
        order=[aid for aid in getattr(editor,'_boolean_order',()) if aid in current]
        if operation=='DIFFERENCE' and set(order)!=current:
            raise ValueError('请依次单选被减对象，再按 Ctrl 选中减去的对象。')
        ids=__import__('apron_ops20_18').boolean(editor.scene,order[0] if order else editor.selection,order+sorted(current-set(order)),operation)
        editor.select(ids[0]);editor.selected_ids=set(ids);editor.refresh();editor.status.set('布尔运算完成；Ctrl+Z撤销。孔洞保留，多个区域置于同一组。')
    except (KeyError,ValueError) as exc:editor.status.set(str(exc))

SPECIAL_APRONS={
    'APRON_CARGO23':('货机坪','CARGO'),
    'APRON_RUNUP23':('试车坪','RUNUP'),
    'APRON_DEICE_POLY':('除冰坪','DEICING'),
}


def finish_special_apron(editor):
    from geometry11 import Polygon
    points=list(editor.points)
    if len(points)<3:
        editor.status.set('至少需要三个顶点。')
        return
    shape=Polygon(points)
    if not shape.is_valid or shape.area<=0:
        editor.status.set('多边形边缘不能交叉。')
        return
    name,code=SPECIAL_APRONS[editor.mode]
    aid=editor.scene.create_asset('APRON',name,points,destination_code23=code,
                                  apron_shape20_18='POLYGON',**({'role':'DEICING'} if code=='DEICING' else {}))
    editor.set_mode('SELECT')
    editor.select(aid)
    editor.refresh()


def apron_click(editor,e):
    if editor.mode in SPECIAL_APRONS:
        point=list(editor.world(e.x,e.y))
        if not editor.points or g.distance(editor.points[-1],point)>.01:editor.points.append(point)
        preview(editor,e)
        return 'break'
    q=editor.world(e.x,e.y);anchor=editor.__dict__.get('_apron_anchor20_18')
    if anchor is None:editor._apron_anchor20_18=q;editor.status.set('请选择第二个对角点；右键取消。');return 'break'
    try:
        kind='TRAPEZOID' if editor.mode=='APRON_TRAP20_18' else 'RECTANGLE';points=__import__('apron_ops20_18').shape(kind,anchor,q)
        areas={'APRON_CARGO23':('货机坪','CARGO'),'APRON_RUNUP23':('试车坪','RUNUP')}
        title,code=areas.get(editor.mode,('机坪','APRON'))
        aid=editor.scene.create_asset('APRON',title,points,destination_code23=code,apron_shape20_18=kind);editor._apron_anchor20_18=None;editor.canvas.delete('workspace20_18');editor.select(aid);editor.refresh()
    except ValueError as exc:editor.status.set(str(exc))
    return 'break'

def cut_plan(editor,e,right=False):
    hit=editor.fast_hit18(editor.world(e.x,e.y))
    if not hit:return None
    _,aid,station,_=hit;a=__import__('segments18').route(editor.scene,aid)
    if aid in editor.scene.movements:raise ValueError('连接道请用节点编辑调整端点；该工具用于独立滑行道末端截断。')
    station=__import__('segments18').terminal_station(editor.scene,aid,station)
    L=g.length(a['points'])
    if min(station,L-station)<1:raise ValueError('截断处应距两端至少1m。')
    delete_start=(tuple(a['points'][0])<tuple(a['points'][-1]))!=right
    return aid,station,'END' if delete_start else 'START'

def cut(editor,e,right=False):
    try:
        plan=cut_plan(editor,e,right)
        if not plan:editor.status.set('请点击需要截断的滑行道道面。');return 'break'
        with editor.processing('正在截断滑行道并重建路口'):
            __import__('segments18').terminal(editor.scene,*plan)
            editor.select(plan[0])
            editor.refresh()
        preview(editor,e)
        editor.status.set('已删除右端。Ctrl+Z撤销；信息引导菜单可恢复截断。' if right else '已删除左端。Ctrl+Z撤销；信息引导菜单可恢复截断。')
    except ValueError as exc:editor.status.set(str(exc))
    return 'break'

def preview(editor,e):
    c=editor.canvas;c.delete('workspace20_18');q=editor.world(e.x,e.y)
    if editor.mode=='TRUNCATE20_18':
        try:
            plan=cut_plan(editor,e,editor.__dict__.get('_truncate_right21_2',False))
            if not plan:return
            aid,s,keep=plan;a=__import__('segments18').route(editor.scene,aid);p,u=g.at(a['points'],s);v=[-u[1],u[0]];half=a['props']['width']/2+a['props'].get('shoulder',0)+2
            c.create_line(*editor.screen([p[k]-v[k]*half for k in (0,1)]),*editor.screen([p[k]+v[k]*half for k in (0,1)]),fill='#c5316c',width=3,tags='workspace20_18')
            pts=g.subpath(a['points'],0 if keep=='END' else s,s if keep=='END' else g.length(a['points']))
            c.create_line(*[n for p in pts for n in editor.screen(p)],fill='#d74646',width=4,dash=(6,4),tags='workspace20_18')
        except ValueError as exc:editor.status.set(str(exc))
    elif editor.mode in SPECIAL_APRONS:
        points=[*editor.points,list(editor.world(e.x,e.y))]
        if len(points)>1:
            if len(points)>2:points.append(points[0])
            editor.canvas.create_line(*[v for p in points for v in editor.screen(p)],
                                      fill='#e7c640',width=2,dash=(5,3),tags='workspace20_18')
    elif editor.__dict__.get('_apron_anchor20_18') is not None:
        try:
            pts=__import__('apron_ops20_18').shape('TRAPEZOID' if editor.mode=='APRON_TRAP20_18' else 'RECTANGLE',editor._apron_anchor20_18,q)
            c.create_polygon(*[n for p in pts for n in editor.screen(p)],fill='',outline='#008da8',width=3,tags='workspace20_18')
        except ValueError:pass

def stand_items(scene,items,marks=None):
    from automatic_markings import generated_markings
    if marks is None:marks=generated_markings(scene)
    stands={aid for aid,a in scene.assets.items() if a['kind']=='STAND'}
    types={'LEAD_IN','LEAD_IN_A','LEAD_IN_B','LEAD_IN_C','LEAD_IN_D','STAND_NUMBER','STAND_STOP','UNGUIDED_STOP','SAFETY','ALIGNMENT','TURN_START'};ids=set(stands)
    for a in list(scene.assets.values())+list(marks.values()):
        if a['props'].get('mark_type') in types or a.get('owner') in stands or a['props'].get('parent_id') in stands:ids.add(a['id'])
    ids.update(mid for mid,m in scene.movements.items() if m.get('role')=='STAND_ENTRY')
    numbers={a['id'] for a in (*scene.assets.values(),*marks.values())
             if a['props'].get('mark_type')=='STAND_NUMBER'}
    ids.difference_update(numbers)
    return [item for item in items if item.get('oid') in ids and item.get('type') in ('line','polygon','text')]

def overlay(editor):
    c=editor.canvas;c.delete('merged_selection20_18')
    native=hasattr(c,'register_world')
    if not native:c.delete('stand_context20_18')
    if editor._color17 and not getattr(getattr(editor,'view_tools21_2',None),'active',False) and editor.scene.data['meta'].get('f6_stands20_18',True):
        items=editor.__dict__.get('render_items');key=(id(editor.scene.data),editor.scene.revision,id(items),getattr(editor,'_dark_mode24',False));cache=editor.__dict__.get('_stand_context20_18')
        if not cache or cache[0]!=key:
            if items is None:items=__import__('scene_render').display_list(editor.scene)
            stand=stand_items(editor.scene,items,editor.__dict__.get('auto_assets'))
            stops={}
            for row in stand:
                mark=editor.__dict__.get('auto_assets',{}).get(row['oid']) or editor.scene.assets.get(row['oid'],{})
                props=mark.get('props',{})
                if props.get('mark_type') in ('STAND_STOP','UNGUIDED_STOP'):
                    owner=mark.get('owner') or props.get('parent_id')
                    stops.setdefault(owner,[]).extend(row['points'])
            labels=[dict(type='text',points=[item['points'][-1]],text=item['props'].get('stand_number') or item['name'],
                         size=10,fill='#d6e7f3' if getattr(editor,'_dark_mode24',False) else '#173446',stand_label=True,
                         stop_points=stops.get(item['id'],()))
                    for item in editor.scene.assets.values() if item['kind']=='STAND']
            cache=(key,[item for item in stand if item['type']!='text'],
                   [item for item in stand if item['type']=='text']+labels,stand+labels)
            editor._stand_context20_18=cache
        def label_position(item):
            x,y=editor.screen(item['points'][0])
            if item.get('stand_label'):
                stop_positions=[editor.screen(p) for p in item['stop_points']]
                if stop_positions:
                    y=min(y,*(point[1] for point in stop_positions))
                y-=12
            return x,y
        if native:
            from qt_renderer21 import CanvasRenderer
            renderer=editor.__dict__.get('_stand_renderer')
            if renderer is None:
                renderer=editor._stand_renderer=CanvasRenderer(c,'stand_context20_18')
            previous=renderer.items
            renderer.render(cache[1],editor.origin,editor.zoom)
            if previous is not cache[1] or not editor.__dict__.get('_stand_visible'):
                c.itemconfigure('stand_context20_18',state='normal')
                editor._stand_visible=True
            zoom=editor.zoom
            turn=math.degrees(getattr(c,'rotation21_2',0.))
            label_style=(key,turn,tuple(10 if item.get('stand_label') else max(7,min(16,int(item.get('size',1)*zoom))) for item in cache[2]))
            if label_style!=editor.__dict__.get('_stand_label_style'):
                c.delete('stand_text_f6')
                editor._stand_label_style=label_style
                editor._stand_labels=[
                    c.create_text(*label_position(item),text=item['text'],
                                  fill=item.get('fill','#75501d'),font=('Segoe UI',size),
                                  angle=0 if item.get('stand_label') else item.get('rotation',0)-turn,tags='stand_text_f6')
                    for item,size in zip(cache[2],label_style[2])]
            else:
                for identifier,item in zip(editor._stand_labels,cache[2]):
                    c.coords(identifier,*label_position(item))
        for item in (() if native else cache[3]):
            zoom=editor.__dict__.get('zoom',1);points=[n for p in item['points'] for n in editor.screen(p)];tag='stand_context20_18';width=max(1,min(3,item.get('width',.15)*zoom))
            if item['type']=='text':c.create_text(*label_position(item),text=item['text'],fill=item.get('fill','#75501d'),font=('Segoe UI',max(7,min(16,int(item.get('size',1)*zoom)))),angle=item.get('rotation',0)-math.degrees(getattr(c,'rotation21_2',0.)),tags=tag)
            elif item['type']=='polygon':c.create_polygon(*points,fill=item.get('fill') or '',outline=item.get('stroke') or '',width=width,tags=tag)
            elif len(points)>=4:c.create_line(*points,fill=item.get('stroke') or '#8c7d25',width=width,tags=tag)
    elif native and editor.__dict__.get('_stand_visible'):
        c.itemconfigure('stand_context20_18',state='hidden')
        editor._stand_visible=False
        c.delete('stand_text_f6')
        editor._stand_label_style=None
    if editor._color17 and len(editor.__dict__.get('selected_ids',set()))>1:
        routes=__import__('segments18').routes(editor.scene)
        for aid in editor.selected_ids:
            if aid in routes:c.create_line(*[n for p in routes[aid]['points'] for n in editor.screen(p)],fill='#00a8c6',width=6,dash=(7,4),tags='merged_selection20_18')

def sync_tree(editor):
    tree=editor.__dict__.get('tree');ids=editor.__dict__.get('selected_ids',set())
    if tree is not None and len(ids)>1 and ids<=set(__import__('segments18').routes(editor.scene)):
        existing=tuple(aid for aid in sorted(ids) if tree.exists(aid))
        if set(tree.selection())!=set(existing):tree.selection_set(existing)
