"""Project stand templates and periodic stand arrangements."""
import copy
import json
import math
from pathlib import Path

from PySide6 import QtCore as C, QtGui as G, QtWidgets as W

from stand_row47 import StandRow, edit_stop_rows


LEADS=('A','B','C','D','ICAO')
ZONES=('WORK_WAIT','TEMP_WAIT')


def caption(zh,en):
    from interface_language import language
    return en if language=='en' else zh


def validate_zone_styles(styles,kinds=None):
    if not isinstance(styles,dict):
        raise ValueError('Invalid work zone styles.')
    for key,style in styles.items():
        if not isinstance(key,str) or (kinds is not None and key not in kinds) or not isinstance(style,dict):
            raise ValueError('Invalid work zone style.')
        if any(not isinstance(style.get(k),str) or not G.QColor(style[k]).isValid() for k in ('color','outline')):
            raise ValueError('Invalid work zone colour.')
        if type(style.get('outline_width')) not in (int,float) or not 0<=style['outline_width']<=10:
            raise ValueError('Invalid work zone outline width.')


def validate_stand(value):
    if not isinstance(value,dict) or value.get('lead_type') not in LEADS:
        raise ValueError('Invalid stand preset.')
    for key in ('aircraft_span','aircraft_length'):
        if type(value.get(key)) not in (int,float) or not 1<=value[key]<=500:
            raise ValueError('Invalid aircraft dimensions.')
    if not isinstance(value.get('stops'),list) or not value['stops']:
        raise ValueError('At least one stop line is required.')
    for stop in value['stops']:
        if (not isinstance(stop,dict) or not isinstance(stop.get('aircraft'),str)
                or type(stop.get('offset')) not in (int,float) or not math.isfinite(stop['offset'])):
            raise ValueError('Invalid stop line.')
    from shapely.geometry import Polygon
    for key,points in value.get('preset_shapes',{}).items():
        family=key.split(':',1)[0]
        path=family in ('lead','combined_lead','icao_aux_lead')
        if family not in ('bridge','work','temporary','lead','combined_lead','icao_aux_lead') or not isinstance(points,list) or len(points)<(2 if path else 3):
            raise ValueError('Invalid stand polygon.')
        if any(len(q)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in q) for q in points):
            raise ValueError('Invalid stand polygon coordinates.')
        from shapely.geometry import LineString
        shape=LineString(points) if path else Polygon(points)
        if not shape.is_valid or (shape.length<.01 if path else shape.area<.01):raise ValueError('Invalid stand polygon.')
    validate_zone_styles(value.get('preset_zone_style',{}),ZONES)
    validate_zone_styles(value.get('preset_zone_overrides',{}))
    for points in value.get('preset_nodes',{}).values():
        if not isinstance(points,list) or any(not isinstance(q,list) or len(q)!=2
                or any(type(x) not in (int,float) or not math.isfinite(x) for x in q) for q in points):
            raise ValueError('Invalid stand node offsets.')
    pose=value.get('preset_pose',[0,0])
    if not isinstance(pose,list) or len(pose)!=2 or any(type(x) not in (float,int) or not math.isfinite(x) for x in pose):
        raise ValueError('Invalid lead-in endpoint.')
    allowed=('preset_pose','preset_nodes','aircraft_span','aircraft_length','lead_type','stops','preset_shapes','preset_zone_style','preset_zone_overrides',
             'has_bridge','bridge_side','show_safety','work_zone','work_zone_bridge_side','remote_stand',
             'ga_stand','stand_support','ga_frame_color','ga_outline_color','ga_text_color',
             'work_zone_left','work_zone_right','show_number')
    result={k:copy.deepcopy(value[k]) for k in allowed if k in value}
    for index,stop in enumerate(result['stops'],1):
        stop.setdefault('id',str(index))
        stop.setdefault('name',str(index))
    return result


def validate_multi(value):
    for k,lo,hi in (('count',1,200),('first',1,99999)):
        if type(value.get(k)) is not int or not lo<=value[k]<=hi:raise ValueError('Invalid arrangement size or numbering.')
    if value.get('overlap') not in ('hatch','merge','dashed') or not value.get('entries'):
        raise ValueError('Add at least one stand to the repeating sequence.')
    offsets=value.get('placements',{})
    if not isinstance(offsets,dict) or any(not k.isdecimal() or not isinstance(q,list)
            or len(q) not in (2,3) or any(type(x) not in (float,int) or not math.isfinite(x) for x in q)
            for k,q in offsets.items()):
        raise ValueError('Invalid stand arrangement coordinates.')
    edits=value.get('instance_nodes',{})
    if not isinstance(edits,dict) or any(not k.isdecimal() or not isinstance(v,dict) for k,v in edits.items()):
        raise ValueError('Invalid arrangement node offsets.')
    template=value['entries'][0]['stand']
    for nodes_ in edits.values():
        validate_stand(dict(template,preset_nodes=nodes_))
    styles=value.get('instance_zone_styles',{})
    if not isinstance(styles,dict) or any(not isinstance(k,str) or not k.isdecimal() for k in styles):
        raise ValueError('Invalid arrangement work zone styles.')
    for overrides in styles.values():validate_zone_styles(overrides)
    return dict(instance_zone_styles=copy.deepcopy(styles),instance_nodes=copy.deepcopy(edits),placements=copy.deepcopy(offsets),count=value['count'],first=value['first'],overlap=value['overlap'],
                entries=[dict(name=str(item['name']),stand=validate_stand(item['stand'])) for item in value['entries']])


def read_arrangement(filename):
    data=json.loads(Path(filename).read_text(encoding='utf-8-sig'))
    if data.get('format') not in ('acprsq','acpasq') or data.get('version')!=1:
        raise ValueError('Unsupported stand arrangement file.')
    return validate_multi(data['value'])


class ColorButton(W.QPushButton):
    colorChanged=C.Signal()

    def __init__(self):
        super().__init__(caption('选择颜色','Choose colour'))
        self.setColor('#ffffff')
        self.clicked.connect(self.choose)

    def setColor(self,value):
        self.color=G.QColor(value)
        sample=G.QPixmap(22,14)
        sample.fill(self.color)
        self.setIcon(G.QIcon(sample))
        self.setToolTip(self.color.name().upper())
        self.colorChanged.emit()

    def choose(self):
        value=W.QColorDialog.getColor(self.color,self,self.text())
        if value.isValid():self.setColor(value.name())


def open_presets(app):
    from stand13 import WORK_ZONES59,NO_WORK_ZONE
    scene=app.scene
    meta=scene.data['meta']
    title=caption('\u673a\u4f4d\u9884\u8bbe\u65b9\u6848','Stand Presets')
    dialog=W.QDialog(app.q)
    dialog.setWindowTitle(title)
    dialog.resize(1260,720)
    root=W.QVBoxLayout(dialog)
    tabs=W.QTabWidget()
    root.addWidget(tabs)
    presets=copy.deepcopy(meta.get('stand_presets',{}))
    arrangements=copy.deepcopy(meta.get('stand_arrangements',{}))
    shapes={}
    zone_overrides={}
    nodes={}
    lead_length=48.
    pose=[0.,0.]
    stops=[dict(id='1',name='1',aircraft='A320',offset=0.,lateral=0.,rotation=0.,shape='T',length=2.,width=.15,visible=True)]
    single=W.QWidget()
    sf=W.QFormLayout(single)
    single_panel=W.QSplitter()
    tabs.addTab(single_panel,caption('\u5355\u673a\u4f4d','Single Stand'))
    saved=W.QComboBox()
    name=W.QLineEdit()
    span=W.QDoubleSpinBox()
    size=W.QDoubleSpinBox()
    for control,value in ((span,36),(size,40)):
        control.setRange(1,500)
        control.setValue(value)
        control.setSuffix(' m')
    lead=W.QComboBox()
    lead.addItems(LEADS)
    stand_type=W.QComboBox()
    for code,label in [('bridge',caption('廊桥','Bridge')),('remote',caption('远机位','Remote')),
                       ('ga',caption('通航','General aviation'))]:
        stand_type.addItem(label,code)
    safety=W.QCheckBox()
    safety.setChecked(True)
    side=W.QComboBox()
    for code,label in [('LEFT',caption('\u5de6','Left')),('RIGHT',caption('\u53f3','Right'))]:side.addItem(label,code)
    zone=W.QComboBox()
    zone.addItems([*WORK_ZONES59,NO_WORK_ZONE])
    for label,widget in ((caption('\u5df2\u4fdd\u5b58\u9884\u8bbe','Saved presets'),saved),(caption('\u540d\u79f0','Name'),name),
        (caption('\u7ffc\u5c55','Wingspan'),span),(caption('\u673a\u8eab\u957f\u5ea6','Aircraft length'),size),
        (caption('\u5f15\u5165\u7ebf\u7c7b\u578b','Lead-in type'),lead),(caption('\u673a\u4f4d\u7c7b\u578b','Stand type'),stand_type),
        (caption('\u5eca\u6865\u4fa7','Bridge side'),side),(caption('\u663e\u793a\u5b89\u5168\u7ebf','Show safety line'),safety),
        (caption('\u9ed8\u8ba4\u4f5c\u4e1a\u533a','Default work zone'),zone)):
        sf.addRow(label,widget)

    def button(label,callback):
        control=W.QPushButton(label)
        control.clicked.connect(callback)
        return control

    def edit_stops():
        nonlocal stops
        updated=edit_stop_rows(dialog,stops)
        if updated is not None:stops=updated
        stop_button.setText(f'{caption("\u505c\u6b62\u7ebf\uff0f\u673a\u578b","Stop lines and aircraft")} ({len(stops)})')

    stop_button=button(caption('\u505c\u6b62\u7ebf\uff0f\u673a\u578b','Stop lines and aircraft'),edit_stops)
    sf.addRow(stop_button)
    row=W.QHBoxLayout()
    def draw_component(key,label):
        from stand11 import frame
        if not one.plan:one.refresh(fit=True)
        _,value,coords=next(iter(one.plan.values()))
        origin=coords[-1]
        _,u,v=frame(dict(points=coords,props=value))
        def world(point):
            x,y=point
            return [origin[i]+u[i]*x+v[i]*y for i in (0,1)]
        def commit(points):
            if points:
                local=[[(x-origin[0])*axis[0]+(y-origin[1])*axis[1] for axis in (u,v)] for x,y in points]
                validate_stand(dict(stand_values(),preset_shapes={**shapes,key:local}))
                shapes[key]=local
            else:shapes.pop(key,None)
            schedule()
        one.start_drawing(label,[world(q) for q in shapes.get(key,[])],
                          key.split(':',1)[0] not in ('lead','combined_lead','icao_aux_lead'),commit)

    for key,label in (('bridge',caption('\u5eca\u6865\u4f4d\u5f62\u72b6','Bridge shape')),
                      ('work',caption('\u4f5c\u4e1a\u533a\u5f62\u72b6','Work zone shape')),
                      ('temporary',caption('\u4e34\u65f6\u4f5c\u4e1a\u533a\u5f62\u72b6','Temporary zone shape'))):
        row.addWidget(button(label,lambda checked=False,k=key,l=label:draw_component(k,l)))
    sf.addRow(row)

    component_type=W.QComboBox()
    for key,zh,en in (
        ('icao_aux_lead','ICAO 辅助机位引入线','ICAO auxiliary stand lead-in'),
        ('lead','引入线','Lead-in'),('combined_lead','组合机位引入线','Combined stand lead-in'),
        ('work','作业区','Work zone'),('temporary','临时作业区','Temporary work zone'),
        ('bridge','廊桥区','Bridge area')):
        component_type.addItem(caption(zh,en),key)
    def add_component():
        family=component_type.currentData()
        index=next(i for i in range(1,len(shapes)+2) if f'{family}:{i}' not in shapes)
        key=f'{family}:{index}'
        draw_component(key,component_type.currentText())
    components=W.QHBoxLayout()
    components.addWidget(component_type)
    components.addWidget(button(caption('添加构件','Add component'),add_component))
    sf.addRow(components)

    styles={}
    defaults=meta.get('stand_zone_style',{})
    for kind,label in zip(ZONES,(caption('\u4f5c\u4e1a\u533a','Work zone'),caption('\u4e34\u65f6\u4f5c\u4e1a\u533a','Temporary zone'))):
        color,outline,width=ColorButton(),ColorButton(),W.QDoubleSpinBox()
        color.setText(caption('主色','Marking colour'))
        outline.setText(caption('描边色','Outline colour'))
        width.setRange(0,10)
        width.setDecimals(2)
        width.setSuffix(' m')
        width.setSpecialValueText(caption('无描边','No outline'))
        fields=W.QHBoxLayout()
        for field in (color,outline,width):fields.addWidget(field)
        sf.addRow(label,fields)
        styles[kind]=(color,outline,width)

    def fill_styles(values):
        for kind,(color,outline,width) in styles.items():
            style=values.get(kind,{})
            color.setColor(style.get('color','#ffffff'))
            outline.setColor(style.get('outline','#101010') if style.get('underpaint') else '#101010')
            width.setValue(style.get('outline_width',0) if style.get('underpaint') else 0)

    def zone_styles():
        return {key:dict(color=c.color.name(),outline=o.color.name(),outline_width=w.value(),underpaint=True)
                for key,(c,o,w) in styles.items()}
    fill_styles(defaults)

    def stand_values():
        return dict(aircraft_span=span.value(),aircraft_length=size.value(),
            lead_type=lead.currentText(),has_bridge=stand_type.currentData()=='bridge',
            remote_stand=stand_type.currentData()=='remote',ga_stand=stand_type.currentData()=='ga',
            bridge_side=side.currentData(),
            show_safety=safety.isChecked(),work_zone=zone.currentText(),stops=stops,
            preset_shapes={k:v for k,v in shapes.items() if v},preset_zone_style=zone_styles(),preset_zone_overrides=zone_overrides,preset_nodes=nodes,preset_pose=pose)

    def snapshot():
        return validate_stand(stand_values())

    def load_stand(value):
        nonlocal stops,shapes,nodes
        span.setValue(value['aircraft_span']);size.setValue(value['aircraft_length'])
        lead.setCurrentText(value['lead_type'])
        kind='ga' if value.get('ga_stand') else 'remote' if value.get('remote_stand') or not value.get('has_bridge',True) else 'bridge'
        stand_type.setCurrentIndex(stand_type.findData(kind))
        safety.setChecked(value.get('show_safety',True))
        side.setCurrentIndex(max(0,side.findData(value.get('bridge_side','LEFT'))))
        zone.setCurrentText(value.get('work_zone',WORK_ZONES59[0]))
        stops=copy.deepcopy(value['stops'])
        shapes=copy.deepcopy(value.get('preset_shapes',{}))
        nodes=copy.deepcopy(value.get('preset_nodes',{}))
        pose[:]=value.get('preset_pose',[0,0])
        fill_styles(value.get('preset_zone_style',defaults))
        zone_overrides.clear()
        zone_overrides.update(copy.deepcopy(value.get('preset_zone_overrides',{})))
        stop_button.setText(f'{caption("\u505c\u6b62\u7ebf\uff0f\u673a\u578b","Stop lines and aircraft")} ({len(stops)})')

    multi=W.QWidget()
    mf=W.QFormLayout(multi)
    multi_panel=W.QSplitter()
    tabs.addTab(multi_panel,caption('\u591a\u673a\u4f4d\u7ec4\u5408','Stand Arrangement'))
    multi_saved=W.QComboBox()
    multi_name=W.QLineEdit()
    select=W.QComboBox()
    sequence=W.QListWidget()
    entries=[]
    placements={}
    instance_nodes={}
    instance_zone_styles={}
    count=W.QSpinBox();count.setRange(1,200);count.setValue(6)
    first=W.QSpinBox();first.setRange(1,99999)
    overlap=W.QComboBox()
    for key,label in [('hatch',caption('\u4fdd\u7559\u4ea4\u53c9\u9634\u5f71','Keep overlap hatching')),
                      ('merge',caption('\u5408\u5e76\u5b89\u5168\u7ebf','Merge safety lines')),
                      ('dashed',caption('\u53bb\u6389\u9634\u5f71\uff0c\u4ea4\u53c9\u5b89\u5168\u7ebf\u7528\u865a\u7ebf','Remove hatching and dash overlapping safety lines'))]:
        overlap.addItem(label,key)
    for label,widget in ((caption('\u5df2\u4fdd\u5b58\u65b9\u6848','Saved arrangements'),multi_saved),
                         (caption('\u65b9\u6848\u540d\u79f0','Arrangement name'),multi_name),
                         (caption('\u9009\u62e9\u673a\u4f4d\u9884\u8bbe','Choose stand preset'),select)):
        mf.addRow(label,widget)
    base_templates={}
    for label,code,w,l,aircraft,lead_code in (
        (caption('默认廊桥位','Default bridge stand'),'bridge',36,40,'A320','A'),
        (caption('默认远机位','Default remote stand'),'remote',36,40,'B738','B'),
        (caption('默认通航位','Default GA stand'),'ga',11,9,'C172','ICAO')):
        base_templates[label]=dict(aircraft_span=w,aircraft_length=l,lead_type=lead_code,
            has_bridge=code=='bridge',remote_stand=code=='remote',ga_stand=code=='ga',
            stops=[dict(stops[0],aircraft=aircraft)])
    def append_entry():
        key=select.currentText()
        available={**base_templates,**presets}
        if key in available:
            entries.append(dict(name=key,stand=copy.deepcopy(available[key])))
            sequence.addItem(key)
    def remove_entry():
        index=sequence.currentRow()
        if index>=0:
            entries.pop(index)
            sequence.takeItem(index)
    def move_entry(step):
        index=sequence.currentRow()
        target=index+step
        if index>=0 and 0<=target<len(entries):
            entries[index],entries[target]=entries[target],entries[index]
            sequence.insertItem(target,sequence.takeItem(index))
            sequence.setCurrentRow(target)
    actions=W.QHBoxLayout()
    for label,func in ((caption('\u52a0\u5165','Add'),append_entry),(caption('\u5220\u9664','Remove'),remove_entry),
                       ('\u2191',lambda:move_entry(-1)),('\u2193',lambda:move_entry(1))):actions.addWidget(button(label,func))
    mf.addRow(actions)
    mf.addRow(caption('\u5468\u671f\u6392\u5217\u987a\u5e8f','Repeating sequence'),sequence)
    mf.addRow(caption('\u673a\u4f4d\u6570\u91cf','Stand count'),count)
    mf.addRow(caption('\u8d77\u59cb\u7f16\u53f7','First number'),first)
    mf.addRow(caption('\u76f8\u4ea4\u5904\u7406','Overlap treatment'),overlap)

    def sync_lists():
        for control,keys in ((saved,presets),(select,{**base_templates,**presets}),(multi_saved,arrangements)):
            current=control.currentText()
            with C.QSignalBlocker(control):
                control.clear()
                control.addItems(sorted(keys))
                if current in keys:control.setCurrentText(current)
    sync_lists()

    def combo_snapshot():
        return validate_multi(dict(count=count.value(),first=first.value(),overlap=overlap.currentData(),entries=entries,placements=placements,instance_nodes=instance_nodes,instance_zone_styles=instance_zone_styles))

    def load_multi(value):
        entries[:]=copy.deepcopy(value['entries'])
        instance_zone_styles.clear()
        instance_zone_styles.update(copy.deepcopy(value.get('instance_zone_styles',{})))
        instance_nodes.clear()
        instance_nodes.update(copy.deepcopy(value.get('instance_nodes',{})))
        placements.clear()
        placements.update(copy.deepcopy(value.get('placements',{})))
        sequence.clear()
        sequence.addItems([item['name'] for item in entries])
        count.setValue(value['count']);first.setValue(value['first'])
        overlap.setCurrentIndex(overlap.findData(value['overlap']))

    def select_single(key):
        if key in presets:
            name.setText(key)
            load_stand(presets[key])
    def select_multi(key):
        if key in arrangements:
            multi_name.setText(key)
            load_multi(arrangements[key])
    saved.currentTextChanged.connect(select_single)
    multi_saved.currentTextChanged.connect(select_multi)
    select_single(saved.currentText())
    select_multi(multi_saved.currentText())

    def persist(key,label,value,store):
        if not label:raise ValueError('Enter a preset name.')
        store[label]=value
        with scene.transaction('Stand presets'):
            scene.data['meta'][key]=copy.deepcopy(store)
        sync_lists()
        app.update_title()

    def read_file(ext,validate):
        extensions='*.acpark *.aspark' if ext=='acpark' else '*.acpasq *.acprsq'
        selected,_=W.QFileDialog.getOpenFileName(dialog,title,'',f'({extensions})')
        if not selected:return None
        data=json.loads(Path(selected).read_text(encoding='utf-8-sig'))
        formats=('acpark','aspark') if ext=='acpark' else ('acpasq','acprsq')
        if data.get('format') not in formats or data.get('version')!=1:raise ValueError('Unsupported preset file.')
        label=str(data['name']).strip()
        if not label:raise ValueError('Enter a preset name.')
        return label,validate(data['value'])

    def transfer(ext,key,field,validate,store,load):
        imported=read_file(ext,validate)
        if imported:
            label,value=imported
            persist(key,label,value,store)
            field.setText(label)
            load(value)

    def import_into_arrangement():
        imported=read_file('acpark',validate_stand)
        if imported:
            label,value=imported
            entries.append(dict(name=label,stand=value))
            sequence.addItem(label)

    def export(ext,field,snapshot_fn):
        value=snapshot_fn()
        label=field.text().strip()
        if not label:raise ValueError('Enter a preset name.')
        chosen,selected_filter=W.QFileDialog.getSaveFileName(dialog,title,label+'.'+ext,
                '(*.acpasq);;(*.acprsq)' if ext=='acpasq' else f'(*.{ext})')
        if chosen:
            path=Path(chosen)
            if ext=='acpasq' and (path.suffix.lower()=='.acprsq' or 'acprsq' in selected_filter):
                ext='acprsq'
            if path.suffix.lower()!=('.'+ext):path=path.with_suffix('.'+ext)
            path.write_text(json.dumps(dict(format=ext,version=1,name=label,value=value),
                                       ensure_ascii=False,indent=2),encoding='utf-8')

    def guarded(func):
        def action():
            try:func()
            except (ValueError,TypeError,KeyError,AttributeError,OSError) as error:
                W.QMessageBox.warning(dialog,title,str(error))
        return action

    def place(values,n,start,style,offsets=None,edits=None,zone_edits=None):
        dialog.accept()
        StandRow(app).start_preset(values,n,start,style,offsets,edits,zone_edits)

    def apply_global():
        values=snapshot()['preset_zone_style']
        from user_settings34 import read,write
        prefs=read(app._preferences34)
        if 'display' not in prefs:prefs.add_section('display')
        prefs['display']['stand_zone_style']=json.dumps(values)
        write(prefs,app._preferences34)
        app._stand_zone_style=values
        with scene.transaction('Work Zone Styles'):
            scene.data['meta']['stand_zone_style']=copy.deepcopy(values)
        app.refresh()

    actions.addWidget(button(caption('导入单机位','Import single stand'),
                             guarded(import_into_arrangement)))
    sf.addRow(button(caption('\u5e94\u7528\u4e3a\u5168\u5c40\u4f5c\u4e1a\u533a\u6837\u5f0f','Apply as global work zone styles'),guarded(apply_global)))
    for form,ext,key,field,read,check,store,load,draw in (
        (sf,'acpark','stand_presets',name,snapshot,validate_stand,presets,load_stand,lambda:place([snapshot()],1,first.value(),'hatch')),
        (mf,'acpasq','stand_arrangements',multi_name,combo_snapshot,validate_multi,arrangements,load_multi,
         lambda:place([x['stand'] for x in combo_snapshot()['entries']],count.value(),first.value(),overlap.currentData(),placements,instance_nodes,instance_zone_styles))):
        bar=W.QHBoxLayout()
        funcs=(lambda k=key,f=field,r=read,s=store:persist(k,f.text().strip(),r(),s),
               lambda e=ext,k=key,f=field,c=check,s=store,l=load:transfer(e,k,f,c,s,l),
               lambda e=ext,f=field,r=read:export(e,f,r),draw)
        for label,func in zip((caption('\u4fdd\u5b58\u5230\u5de5\u7a0b','Save to ACP'),caption('\u5bfc\u5165','Import'),
                               caption('\u53e6\u5b58\u4e3a','Save As')+' .'+ext,caption('\u5f00\u59cb\u7ed8\u5236','Start Drawing')),funcs):
            bar.addWidget(button(label,guarded(func)))
        form.addRow(bar)
    from stand_preview import StandPreview
    from airport_scene import AirportScene
    from stand_overlap9 import pair_key
    from itertools import combinations

    def preview_scene(multiple):
        sample=AirportScene()
        sample.data['meta']['stand_zone_style']=defaults
        info={}
        values=[item['stand'] for item in entries] if multiple else [stand_values()]
        if not values:return sample,info
        total=count.value() if multiple else 1
        pitch=max(value['aircraft_span'] for value in values)+5
        with sample.transaction('Preview'):
            sample.create_asset('APRON','Preview',[[-60,-100],[150,-100],[150,pitch*total+100],[-60,pitch*total+100]])
            for i in range(total):
                value=copy.deepcopy(values[i%len(values)])
                position,depth,*side_shift=placements.get(str(i),(0,0)) if multiple else (0,0)
                start_y=i*pitch+position
                number=str(first.value()+i) if multiple else '1'
                value['stand_number']=number
                if multiple and str(i) in instance_nodes:
                    value['preset_nodes']={**value.get('preset_nodes',{}),**instance_nodes[str(i)]}
                if multiple and str(i) in instance_zone_styles:
                    value['preset_zone_overrides']={**value.get('preset_zone_overrides',{}),**instance_zone_styles[str(i)]}
                tilt=value.get('preset_pose',[0,0])
                coords=[[0,start_y],[max(15,lead_length+depth+tilt[0]),start_y+tilt[1]+sum(side_shift)]]
                oid=sample.create_asset('STAND',number,coords,width=value['aircraft_span'],**value)
                stand=sample.assets.pop(oid)
                oid=f'A-preview-{i}'
                stand['id']=oid
                sample.assets[oid]=stand
                info[oid]=(i,value,coords)
        if multiple and overlap.currentData() in ('dashed','merge'):
            key='dashed_stand_overlaps' if overlap.currentData()=='dashed' else 'merged_stand_overlaps'
            sample.data['meta'][key]={pair_key(a,b):True for a,b in combinations(info,2)}
        return sample,info

    def edit_node(preview,multiple,key,index,point,inserting=False,deleting=False):
        owner=next((oid for oid in preview.plan if key==oid or key.startswith('AUTO:'+oid+':')),None)
        if owner is None:return
        i,value,coords=preview.plan[owner]
        if deleting:
            if key==owner:return False
            suffix=key.removeprefix('AUTO:'+owner+':')
            target=instance_nodes.setdefault(str(i),{}) if multiple else nodes
            if index is None:
                target['@'+suffix]=[]
            else:
                points=list(preview.nodes.get(key,()))
                if len(points)<=(3 if key in preview.closed else 2):return False
                points.pop(index)
                if key in preview.closed:
                    try:__import__('polygon_edit20_7').checked(points)
                    except ValueError:return False
                from stand11 import frame
                _,u,v=frame(dict(points=coords,props=value))
                ox,oy=coords[-1]
                target['@'+suffix]=[[(x-ox)*u[0]+(y-oy)*u[1],(x-ox)*v[0]+(y-oy)*v[1]] for x,y in points]
            schedule()
            return True
        old=preview.nodes[key][index] if not inserting else point
        dx,dy=point[0]-old[0],point[1]-old[1]
        if key==owner:
            if inserting:return False
            if multiple:
                pos,depth,*shift=placements.get(str(i),(0,0))
                lateral=sum(shift)
                if index:
                    depth=max(15-lead_length,depth+dx)
                    lateral+=dy
                else:
                    pos+=dy
                    lateral-=dy
                placements[str(i)]=[pos,depth,lateral]
            else:
                sign=1 if index else -1
                pose[0]=max(15-lead_length,pose[0]+sign*dx)
                pose[1]+=sign*dy
            schedule()
            return True
        target=instance_nodes.setdefault(str(i),{}) if multiple else nodes
        suffix=key.removeprefix('AUTO:'+owner+':')
        from stand11 import frame
        _,u,v=frame(dict(points=coords,props=value))
        if inserting or '@'+suffix in value.get('preset_nodes',{}):
            points=copy.deepcopy(preview.nodes[key])
            if inserting:points.insert(index,point)
            else:points[index]=point
            ox,oy=coords[-1]
            target['@'+suffix]=[[(x-ox)*u[0]+(y-oy)*u[1],(x-ox)*v[0]+(y-oy)*v[1]] for x,y in points]
            schedule()
            return True
        offsets=target.setdefault(suffix,copy.deepcopy(value.get('preset_nodes',{}).get(
            suffix,[[0.,0.] for _ in preview.nodes[key]])))
        if len(offsets)!=len(preview.nodes[key]):
            offsets[:]=[[0.,0.] for _ in preview.nodes[key]]
        from stand11 import frame
        _,(ux,uy),_=frame(dict(points=coords,props=value))
        offsets[index][0]+=dx*ux+dy*uy
        offsets[index][1]+=-dx*uy+dy*ux
        schedule()
        return True

    one=StandPreview(caption,lambda:preview_scene(False),lambda *a:edit_node(one,False,*a),
                     lambda *a:edit_node(one,False,*a,inserting=True),
                     lambda key,index:edit_node(one,False,key,index,None,deleting=True))
    many=StandPreview(caption,lambda:preview_scene(True),lambda *a:edit_node(many,True,*a),
                      lambda *a:edit_node(many,True,*a,inserting=True),
                      lambda key,index:edit_node(many,True,key,index,None,deleting=True))
    for panel,preview,form in ((single_panel,one,single),(multi_panel,many,multi)):
        selected_style=W.QGroupBox(caption('所选作业区配色','Selected work zone colours'))
        fields=W.QFormLayout(selected_style)
        color,outline,width=ColorButton(),ColorButton(),W.QDoubleSpinBox()
        width.setRange(0,10)
        width.setDecimals(2)
        width.setSuffix(' m')
        reset=W.QPushButton(caption('恢复默认','Use inherited colours'))
        fields.addRow(caption('主色','Marking colour'),color)
        fields.addRow(caption('描边色','Outline colour'),outline)
        fields.addRow(caption('描边宽度','Outline width'),width)
        fields.addRow(reset)
        form.layout().insertRow(0,selected_style)

        def selection(p=preview):
            mark=p.zone_marks.get(p.key)
            if mark:
                owner=mark['owner']
                number,_,_=p.plan[owner]
                return mark,number,p.key.removeprefix('AUTO:'+owner+':')

        def sync(mark_lookup=selection,p=preview,group=selected_style,c=color,o=outline,w=width,b=reset):
            hit=mark_lookup()
            group.setVisible(bool(hit))
            if not hit:return
            from stand13 import work_zone_style
            mark,index,key=hit
            style=work_zone_style(p.render_scene,mark)
            with C.QSignalBlocker(c),C.QSignalBlocker(o),C.QSignalBlocker(w):
                c.setColor(style.get('color','#ffffff'))
                o.setColor(style.get('outline','#101010') if style.get('underpaint') else '#101010')
                w.setValue(style.get('outline_width',0) if style.get('underpaint') else 0)
            overrides=zone_overrides if p is one else instance_zone_styles.get(str(index),{})
            b.setEnabled(key in overrides)

        def change(clear=False,mark_lookup=selection,p=preview,c=color,o=outline,w=width):
            hit=mark_lookup()
            if not hit:return
            _,index,key=hit
            overrides=zone_overrides if p is one else instance_zone_styles.setdefault(str(index),{})
            if clear:overrides.pop(key,None)
            else:overrides[key]=dict(color=c.color.name(),outline=o.color.name(),outline_width=w.value(),underpaint=True)
            schedule()

        preview.selectionChanged.connect(sync)
        for signal in (color.colorChanged,outline.colorChanged,width.valueChanged):
            signal.connect(lambda *_,apply=change:apply())
        reset.clicked.connect(lambda checked=False,apply=change:apply(True))
        selected_style.hide()
        panel.addWidget(preview)
        scroll=W.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form)
        panel.addWidget(scroll)
        panel.setSizes([820,410])
    timer=C.QTimer(dialog)
    timer.setSingleShot(True)
    def redraw_preview():
        preview=(one,many)[tabs.currentIndex()]
        preview.refresh(fit=not preview.initialized)
        preview.initialized=bool(preview.plan)
    def schedule(*_):
        timer.start(35)
    one.initialized=many.initialized=False
    def draft(page):
        if page==0:return copy.deepcopy(dict(stand_values(),draft_name=name.text()))
        return copy.deepcopy(dict(draft_name=multi_name.text(),entries=entries,count=count.value(),first=first.value(),
                                  overlap=overlap.currentData(),placements=placements,instance_nodes=instance_nodes,instance_zone_styles=instance_zone_styles))
    history=[[draft(0)],[draft(1)]]
    cursor=[0,0]
    restoring=False
    def record(*_):
        if restoring:return
        for page in range(2):
            value=draft(page)
            stack=history[page]
            if value!=stack[cursor[page]]:
                del stack[cursor[page]+1:]
                stack.append(value)
                cursor[page]+=1
    def travel(step):
        nonlocal restoring
        page=tabs.currentIndex()
        preview=(one,many)[page]
        if preview.view.draft is not None:
            preview.view.travel_drawing(step)
            return
        record()
        index=cursor[page]+step
        if not 0<=index<len(history[page]):return
        cursor[page]=index
        restoring=True
        try:
            value=copy.deepcopy(history[page][index])
            (name,multi_name)[page].setText(value.pop('draft_name'))
            (load_stand,load_multi)[page](value)
        finally:restoring=False
        redraw_preview()
    for keys,step in (('Ctrl+Z',-1),('Ctrl+Y',1),('Ctrl+Shift+Z',1)):
        shortcut=G.QShortcut(G.QKeySequence(keys),dialog)
        shortcut.activated.connect(lambda delta=step:travel(delta))
    timer.timeout.connect(record)
    timer.timeout.connect(redraw_preview)
    for ctrl in (span,size,count,first):
        ctrl.valueChanged.connect(schedule)
    for ctrl in (lead,stand_type,side,zone,overlap,saved,multi_saved):
        ctrl.currentIndexChanged.connect(schedule)
    safety.toggled.connect(schedule)
    for fields in styles.values():
        fields[0].colorChanged.connect(schedule)
        fields[1].colorChanged.connect(schedule)
        fields[2].valueChanged.connect(schedule)
    name.textEdited.connect(schedule)
    multi_name.textEdited.connect(schedule)
    for btn in dialog.findChildren(W.QPushButton):
        btn.clicked.connect(schedule)
    tabs.currentChanged.connect(schedule)
    C.QTimer.singleShot(0,redraw_preview)
    dialog.exec()
