"""Bounded WYSIWYG workspace, prefab inspector and lightweight affine gestures."""
import copy
import math
import time
from pathlib import Path
from types import SimpleNamespace
import qt_compat as tk
from PySide6.QtWidgets import QSizePolicy
from qt_compat import ttk
from PIL import Image,ImageDraw
from qt_canvas21 import ImageTk
from editor10_gui import Editor10
from airport_scene import AirportScene
from marking_catalog import CATALOG
from project10 import TAXIS,SUBTYPES
import scene_geometry as g
import transform11 as tr

class HoverTip:
    def __init__(self,widget,text):
        self.widget=widget;self.text=text;self.pending=None;self.window=None
        widget.bind('<Enter>',self.enter,add='+');widget.bind('<Leave>',self.hide,add='+');widget.bind('<ButtonPress>',self.hide,add='+');widget.bind('<Destroy>',self.hide,add='+')
    def enter(self,event=None):
        self.hide();self.pending=self.widget.after(350,self.show)
    def show(self):
        self.pending=None
        if not self.widget.winfo_exists():return
        from qt_core21 import C, Qt
        tip = tk.Label(self.widget, text=self.text)
        self.window = tip
        tip.q.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        tip.q.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        tip.q.setTextFormat(Qt.TextFormat.PlainText)
        tip.q.setStyleSheet(
            'background:#21374c;color:white;border:1px solid #34536c;'
            'border-radius:4px;padding:3px 6px;font-size:12px;'
        )
        tip.q.setMaximumWidth(260)
        tip.q.setWordWrap(True)
        tip.q.ensurePolished()
        tip.q.adjustSize()
        area = self.widget.q.screen().availableGeometry()
        anchor = self.widget.q.mapToGlobal(C.QPoint(0, self.widget.q.height()))
        x = max(area.left(), min(anchor.x() + 8, area.right() - tip.q.width() + 1))
        y = anchor.y() + 5
        if y + tip.q.height() > area.bottom() + 1:
            y = anchor.y() - self.widget.q.height() - tip.q.height() - 5
        tip.q.move(x, max(area.top(), y))
        tip.q.show()
    def hide(self,event=None):
        if self.pending:
            try:self.widget.after_cancel(self.pending)
            except tk.TclError:pass
            self.pending=None
        if self.window:
            try:self.window.destroy()
            except tk.TclError:pass
            self.window=None

class Editor11(Editor10):
    def __init__(self,scene=None):
        self._tips11=[];self._draft11=None;self._draft_values11={};self._object_drag11=None;self._pan11=None;self._space11=False;self._nav_drag11=None;self._editing_guide11=False;self._axis_path11=None;self._stand_start11=None;self._frame_box11=None;self._layout_guard11=False;self._inspector_job11=None
        if scene is None:
            path=Path(__file__).with_name('example_editor11.airport.json');scene=AirportScene.load(path) if path.exists() else AirportScene()
        from migrate11 import migrate
        migrate(scene)
        super().__init__(scene)
        self.bind('<KeyPress-space>',self.space_press11,add='+');self.bind('<KeyRelease-space>',self.space_release11,add='+');self.bind('<Control-m>',lambda event:self.shortcut(event,self.merge_names11))
    def update_title(self):
        super().update_title();self.title(self.title().replace('10.0','11.0'))
    def refresh(self):
        from migrate11 import migrate
        migrate(self.scene)
        return super().refresh()
    def destroy(self):
        if self._inspector_job11:
            try:self.after_cancel(self._inspector_job11)
            except tk.TclError:pass
            self._inspector_job11=None
        for tip in self._tips11:tip.hide()
        return super().destroy()
    def tip11(self,widget,text):self._tips11.append(HoverTip(widget,text))
    def tool_icon(self,key):
        if not key.startswith('SIGN23:'):
            return super().tool_icon(key)
        from PIL import Image, ImageDraw, ImageFont
        kind=key.partition(':')[2]
        image=Image.new('RGBA',(72,40))
        draw=ImageDraw.Draw(image)
        ink='#18202a'
        yellow='#ffdb64'
        red='#ce3c43'
        white='#ffffff'
        def panel(left,right,fill):
            draw.rounded_rectangle((left,7,right,33),3,fill=fill,outline=ink,width=2)
        def arrow(x,y,color,up=False):
            pts=[(-9,-2),(2,-2),(2,-7),(9,0),(2,7),(2,2),(-9,2)]
            draw.polygon([(x+b,y-a) if up else (x+a,y+b) for a,b in pts],fill=color)
        if kind=='ROAD_STOP_BOARD':
            draw.polygon([(26,5),(46,5),(54,13),(54,27),(46,35),(26,35),(18,27),(18,13)],
                         fill=red,outline=white,width=2)
            draw.rectangle((28,18,44,22),fill=white)
        elif kind=='NO_ENTRY_BOARD':
            panel(18,54,red)
            draw.ellipse((26,11,46,29),outline=white,width=3)
            draw.rectangle((29,18,43,22),fill=white)
        elif kind in ('RUNWAY_NUMBER','CAT_HOLD','HOLD_BOARD','FREQUENCY','FREQUENCY_PAVEMENT'):
            panel(4,68,red)
            if kind=='RUNWAY_NUMBER':panel(4,23,ink)
            label={'RUNWAY_NUMBER':'09-27','CAT_HOLD':'CAT II','HOLD_BOARD':'A3','FREQUENCY':'HP 1','FREQUENCY_PAVEMENT':'HP'}[kind]
            draw.text((43 if kind=='RUNWAY_NUMBER' else 36,20),label,fill=white,anchor='mm',
                      font=ImageFont.load_default(size=15))
        elif kind in ('LOCATION_BOARD','POSITION_HP','VACATED'):
            panel(8,64,ink)
            if kind=='VACATED':
                panel(30,65,yellow)
                for y in (14,18):draw.line((34,y,61,y),fill=ink,width=2)
                for y in (23,27):
                    for x in (35,44,53):draw.line((x,y,x+5,y),fill=ink,width=2)
            draw.text((19 if kind=='VACATED' else 36,20),'HP' if kind=='POSITION_HP' else 'A',
                      fill=yellow,anchor='mm',font=ImageFont.load_default(size=16))
        else:
            panel(4,68,yellow)
            if kind=='PAVEMENT':
                draw.rectangle((0,0,71,39),fill='#4a555f')
                panel(13,59,yellow)
            if kind=='DIRECTION_GROUP':panel(27,44,ink)
            label={'DESTINATION_BOARD':'AP','DESTINATION_GROUP':'27','TAKEOFF':'2500','RUNWAY_EXIT':'G2'}.get(kind,'A')
            draw.text((25 if kind!='DIRECTION_GROUP' else 35,20),label,
                      fill=yellow if kind=='DIRECTION_GROUP' else ink,anchor='mm',
                      font=ImageFont.load_default(size=15))
            arrow(55 if kind!='PAVEMENT' else 48,20,ink,kind=='RUNWAY_EXIT')
        return ImageTk.PhotoImage(image,master=self)

    def _build(self):
        super()._build();body=self.canvas.master;self._body11=body
        left=self.nametowidget(body.panes()[0]);right=self.nametowidget(body.panes()[2]);left.configure(width=205);right.configure(width=330);left.pack_propagate(False);right.pack_propagate(False)
        body.bind('<Configure>',self.layout11,add='+');self.after_idle(self.layout11)
        # Remove transient tool options from the drawing palette. Values remain
        # in these variables so older drawing helpers can read the inspector.
        for child in self.tool_body.winfo_children():child.destroy()
        self.tool_buttons={};self._palette_groups11=[]
        style=ttk.Style(self);style.configure('Category11.TButton',background='#d6e4ee',foreground='#173f59',font=('Microsoft YaHei UI',10,'bold'),padding=(7,8));style.configure('Item11.TButton',background='#f4f7f9',font=('Microsoft YaHei UI',9),padding=(5,4),anchor='w')
        def group(title,entries,opened=False):
            if not entries:return
            frame=ttk.Frame(self.tool_body)
            frame.pack(fill='x',padx=3,pady=3)
            frame._ensure_layout().setAlignment(tk.Qt.AlignmentFlag.AlignTop)
            content=ttk.Frame(frame)
            def show_children(expanded):
                button.configure(text=('▾ ' if expanded else '▸ ')+title)
                if expanded:content.pack(fill='x',pady=(2,0))
                else:content.pack_forget()
            def toggle():
                button.palette_open = not bool(content.winfo_manager())
                show_children(button.palette_open)
            button=ttk.Button(frame,style='Category11.TButton',command=toggle)
            button.pack(fill='x')
            policy=button.q.sizePolicy()
            policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
            button.q.setSizePolicy(policy)
            button.palette_open=opened
            button.show_palette_children=show_children
            self._palette_groups11.append((title,button,content))
            show_children(opened)
            for mode,label in entries:
                photo=self.tool_icon(mode);small=ImageTk.PhotoImage(ImageTk.getimage(photo).resize((28,17),Image.Resampling.LANCZOS),master=self);self._photos['draw11'+mode]=small
                b=ttk.Button(content,text=' '+label,image=small,compound='left',style='Item11.TButton',command=lambda mode=mode:self.set_mode(mode));b.pack(fill='x',pady=1);self.tool_buttons[mode]=b;self.tip11(b,label+'\n选择后在右侧设置类型、尺寸和显示侧')
        group('预制绘画',[('RUNWAY','跑道'),('TAXIWAY','滑行路线'),('STAND','廊桥机位'),('ROAD','服务车道'),('APRON','机坪'),('APRON_RECT20_18','矩形机坪'),('APRON_TRAP20_18','梯形机坪'),('APRON_CARGO23','货机坪'),('APRON_RUNUP23','试车坪'),('DEICE10','除冰坪'),('APRON_DEICE_POLY','多边形除冰坪'),('TURN_PAD','跑道掉头坪'),('STOPWAY','停止道')],True)
        group('目的地与方向标识与标记牌',[
            ('SIGN23:PAVEMENT','目的地与方向标识'),('SIGN23:DIRECTION_BOARD','方向标记牌'),
            ('SIGN23:DESTINATION_BOARD','目的地标记牌'),('SIGN23:TAKEOFF','交叉点起飞标记牌'),
            ('SIGN23:HOLD_BOARD','跑道等待位置标记牌'),('SIGN23:FREQUENCY','HP 等待点标记牌'),('SIGN23:FREQUENCY_PAVEMENT','HP 等待点道面标识')]+
            [('SIGN23:'+kind,label) for kind,label,_ in __import__('boards24').TEMPLATES])
        common=set()
        service=(set(__import__('roads10').ROAD_MARKS)|{'ROAD_DIVIDER','ROAD_EDGE','ROAD_STAGGER'})-{'PEDESTRIAN'}
        for title in dict.fromkeys(spec['group'] for spec in CATALOG.values()):
            entries=[('MARK:'+key,spec['name']) for key,spec in CATALOG.items() if spec['group']==title and key not in common|service]
            if title==CATALOG['TWY_CENTER']['group']:entries.append(('PUSHBACK9','推出路径'))
            group(title,entries)
        group('区域',[('PROTECTION','保护区'),('EQUIPMENT','设备区域'),('CLOSED_AREA','关闭区域')])
        # Locate the two inherited rows by their controls, not child indices.
        bars=[]
        for child in self.winfo_children():
            if isinstance(child,ttk.Frame):
                texts=[str(w.cget('text')) for w in child.winfo_children() if isinstance(w,(ttk.Button,ttk.Checkbutton))]
                if '↖ 选择' in texts or '所有车道尾流提示' in texts:bars.append(child)
        for bar in bars:
            for child in bar.winfo_children():child.destroy()
        primary=bars[0];secondary=bars[-1];self.display_row11=secondary
        actions=[('SELECT','选择 V',lambda:self.set_mode('SELECT')),('UNDO','撤销 Ctrl+Z',self.undo),('REDO','重做 Ctrl+Y',self.redo),('OPEN','打开 Ctrl+O',self.open),('SAVE','保存 Ctrl+S',self.save),('FIT','适合画布',self.fit),('NODES','节点编辑',lambda:self.set_mode('NODES')),('BREAK','打断编号 · 中线垂线预览',lambda:self.set_mode('BREAK')),('SPLIT7','保留编号分段',lambda:self.set_mode('SPLIT7')),('BOX_SELECT','框选',lambda:self.set_mode('BOX_SELECT')),('CONNECT','连接并预览',lambda:self.set_mode('CONNECT')),('EDIT_GUIDE','独立编辑连接曲线',lambda:self.set_mode('EDIT_GUIDE')),('JUNCTION','岔路口设置',lambda:self.set_mode('JUNCTION')),('MERGE','智能合并滑行道命名 Ctrl+M',self.merge_names11),('JET','所有服务车道添加来向尾流提示',self.all_jet10),('PARALLEL','平行跑道编号',self.parallel10)]
        for key,label,command in actions:
            photo=self.action_icon11(key);self._photos['action11'+key]=photo;b=ttk.Button(primary,image=photo,command=command,padding=4);b.pack(side='left',padx=2);self.tip11(b,label)
            if key in ('SELECT','NODES','BREAK','SPLIT7','BOX_SELECT','CONNECT','EDIT_GUIDE','JUNCTION'):self.tool_buttons[key]=b
        self.nav_visible11=tk.BooleanVar(value=self.scene.data['meta'].get('nav_visible',True))
        self.display_options23=[('网格',self.grid_visible,self.redraw),('辅助名称',self.labels,self.refresh),('等待标记',self.facilities,self.refresh),('保护区',self.protection,self.refresh),('连接预览',self.preview_enabled,self.redraw),('导航窗口',self.nav_visible11,self.toggle_nav11)]
        secondary.pack_forget()
        self.minimap.destroy();self.nav_frame11=ttk.Frame(self.canvas,relief='solid',borderwidth=1);header=tk.Frame(self.nav_frame11,bg='#d7e6ef',height=23);header.pack(fill='x');header.pack_propagate(False);header.q.setFixedHeight(28)
        header.q.setProperty('acRole','navHeader');header.q.setStyleSheet('')
        title=tk.Label(header,text='导航 · 拖动标题移动',bg='#d7e6ef',fg='#355668',font=('Microsoft YaHei UI',8));title.pack(side='left',padx=5);title.q.setProperty('acRole','navTitle');title.q.setStyleSheet('');self.nav_header11=header.q
        close=ttk.Button(header,text='×',width=2,command=lambda:(self.nav_visible11.set(False),self.toggle_nav11()));close.pack(side='right');self.tip11(close,'隐藏导航窗口；可从视图选项重新开启')
        for widget in (header,title):widget.bind('<ButtonPress-1>',self.nav_press11);widget.bind('<B1-Motion>',self.nav_motion11);widget.bind('<ButtonRelease-1>',self.nav_release11)
        self.minimap=tk.Canvas(self.nav_frame11,width=190,height=130,bg='#eef4f7',highlightthickness=0);self.minimap.q.setMinimumWidth(0);self.minimap.pack(fill='both',expand=True);self.minimap.bind('<Button-1>',self.navigate);self.minimap.bind('<B1-Motion>',self.navigate);self._nav_key=None;self.toggle_nav11()
        self.canvas.viewport_layout11=self.place_nav11
        self.after_idle(self.place_nav11)
    def layout11(self,event=None):
        if self._layout_guard11 or not hasattr(self,'_body11'):return
        width=self._body11.winfo_width()
        if width<650:return
        self._layout_guard11=True
        try:self._body11.sashpos(0,205);self._body11.sashpos(1,max(550,width-330))
        finally:self._layout_guard11=False
    def action_icon11(self,key):
        mapping=dict(SELECT=0,NODES=1,BREAK=2,SPLIT7=3,BOX_SELECT=4,CONNECT=5,EDIT_GUIDE=6,JUNCTION=7)
        if key in mapping:return self.operation_icon10(mapping[key])
        im=Image.new('RGB',(28,25),'#edf2f6');d=ImageDraw.Draw(im);c='#25596f'
        if key == 'TRUNCATE20_18':
            im = Image.new('RGBA', (28, 25))
            d = ImageDraw.Draw(im)
            d.line((21, 4, 21, 21), fill=c, width=2)
            d.line((8, 8, 18, 17), fill=c, width=2)
            d.line((8, 17, 18, 8), fill=c, width=2)
            for y in (6, 16):
                d.ellipse((3, y, 9, y + 5), outline=c, width=2)
        elif key in ('UNDO','REDO'):
            d.arc((5,3,24,23),20,290,fill=c,width=2);d.polygon([(2,8),(12,4),(10,13)],fill=c)
            if key=='REDO':im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif key=='OPEN':d.polygon([(2,6),(11,6),(14,10),(26,10),(22,23),(3,23)],fill='#e2bc57',outline=c)
        elif key=='SAVE':d.rectangle((4,2,24,23),fill=c);d.rectangle((8,3,20,10),fill='#cbdce7');d.rectangle((8,14,20,22),fill='white')
        elif key=='FIT':
            for x,y,dx,dy in [(3,3,1,1),(24,3,-1,1),(3,22,1,-1),(24,22,-1,-1)]:d.line((x,y+dy*6,x,y,x+dx*6,y),fill=c,width=2)
        elif key=='MERGE':d.rounded_rectangle((1,4,14,14),3,outline=c,width=2);d.rounded_rectangle((12,12,26,22),3,outline=c,width=2);d.line((9,10,19,17),fill='#2c9f78',width=2)
        elif key=='JET':d.polygon([(14,2),(27,23),(1,23)],fill='#cf383e');d.line((8,18,21,18),fill='white',width=2);d.line((10,13,19,13),fill='white',width=2)
        elif key=='PARALLEL':
            for x in (7,20):d.rectangle((x-3,1,x+3,24),fill=c);d.line((x,4,x,8),fill='white');d.line((x,12,x,16),fill='white')
        return ImageTk.PhotoImage(im,master=self)
    def set_mode(self,mode):
        if self._object_drag11:self.cancel_action()
        self._editing_guide11=mode in ('NODES','EDIT_GUIDE');self._axis_path11=None;self._stand_start11=None;self._stand_exit_pending58=False;self._stand_exit_hit58=None;self._stand_exit_vertices69=[];self.canvas.delete('enhanced_two_point39')
        super().set_mode(mode)
        self._draft11=mode if mode not in ('SELECT','NODES','BREAK','SPLIT7','BOX_SELECT','CONNECT','EDIT_GUIDE','JUNCTION') else None
        if self._draft11:self.selection=None
        self.update_inspector();self.redraw()
    def draft_defaults11(self,mode):
        saved=self.scene.data['meta'].get('tool_defaults',{}).get(getattr(self,'_prefab19',None) or mode,{})
        if mode=='STAND':base=dict(lead_type='A',stand_polyline=False,has_bridge=True,lead_radius=20.,aircraft_length=40.,aircraft_span=36.,safety_clearance=4.5)
        elif mode in TAXIS:base=dict(route_type='滑行道',width=23.,shoulder=7.5,corner_radius=25.)
        elif mode=='ROAD':base=dict(width=7.,corner_radius=12.,auto_jet_blast=True)
        elif mode=='DEICE10':base=dict(deice_aircraft_length=40.,deice_wingspan=36.,deice_clearance=4.5,deice_bays=1,deice_vehicles=2,deice_crossfall=.8,deice_crossfall_mode='SINGLE',deice_collection=True)
        elif mode.startswith('MARK:'):
            key=mode[5:];road=key in __import__('roads10').ROAD_MARKS;base=dict(axis_side='BOTH' if road else 'A' if key in __import__('marks11').BLOCKS else 'CENTER')
        else:base={}
        base.update(saved);return base
    def update_inspector(self):
        draft=self._draft11
        if draft:
            if self._property_after:self.after_cancel(self._property_after);self._property_after=None
            self._inspector_token+=1;self._dirty_fields.clear();self._selected_form=None;self._editor_oid=None;self.editor_vars={};self._field_controls={};self._inspector_busy=True
            for child in self.property_body.winfo_children():child.destroy()
            try:
                title={'STAND':{'REMOTE_STAND':'远机位','GA_STAND':'通航机场机位','HELI_STAND':'直升机坪（带引入线）'}.get(getattr(self,'_prefab19',None),'廊桥机位'),'TAXIWAY':'滑行路线','ROAD':'服务车道','DEICE10':'除冰坪'}.get(draft,CATALOG[draft[5:]]['name'] if draft.startswith('MARK:') else draft)
                self.property_title.configure(text='绘制 · '+title);self._draft_values11=self.draft_defaults11(draft);sec=self.section('预制参数')
                from stand13 import GA_FIELDS
                for key,value in self._draft_values11.items():
                    if key in ('ga_stand','remote_stand','stand_support','has_bridge','hangar19','auxiliary') and getattr(self,'_prefab19',None)=='GA_STAND':continue
                    label={'work_zone':'作业区类型','work_zone_left':'左侧作业区类型','work_zone_right':'右侧作业区类型','stand_polyline':'逐点绘制折线','lead_type':'引入线构型','has_bridge':'带廊桥','lead_radius':'引入半径 m','aircraft_length':'机长 m','aircraft_span':'翼展 m','safety_clearance':'安全净距 m','route_type':'滑行路线类型','width':'道面宽度 m','shoulder':'每侧道肩 m','corner_radius':'圆角半径 m','auto_jet_blast':'自动尾流警示','axis_side':'显示侧','deice_aircraft_length':'除冰飞机长度 m','deice_wingspan':'除冰飞机翼展 m','deice_clearance':'外围净宽 m','deice_bays':'除冰机位数','deice_vehicles':'车辆数量','deice_crossfall':'横坡 %','deice_crossfall_mode':'横坡形式','deice_collection':'除冰液回收'}.get(key,key)
                    if key in GA_FIELDS:label=GA_FIELDS[key][0]
                    if key=='aircraft_span' and self._draft_values11.get('helicopter_stand'):label='机位直径 m'
                    choices=list(__import__('stand13').WORK_ZONES59)+([__import__('stand13').NO_WORK_ZONE] if key=='work_zone_bridge_side' else []) if key.startswith('work_zone') else list('ABCD') if key=='lead_type' else list(SUBTYPES) if key=='route_type' else ['A','B','BOTH'] if key=='axis_side' and draft[5:] in __import__('roads10').ROAD_MARKS else ['CENTER','A','B','BOTH'] if key=='axis_side' else ['SINGLE','SYMMETRIC'] if key=='deice_crossfall_mode' else None
                    kind='bool' if isinstance(value,bool) else 'int' if key in ('deice_bays','deice_vehicles') else 'radio' if key=='lead_type' else 'text' if isinstance(value,str) else 'float'
                    self.property_field(sec,'_draft_'+key,label,value,kind,choices)
                text='点击滑行道中线作为入口，再点击停止位置；也可在空白处绘制后再吸附入口。' if draft=='STAND' else '依次点击折线顶点，Enter完成；Shift限制方向。' if draft in TAXIS+('ROAD',) else '点击除冰坪两个对角；内区停机，外围预留独立车辆活动空间。' if draft=='DEICE10' else '在绘图区放置；右键取消。'
                ttk.Label(self.property_body,text=text,wraplength=280,padding=10).pack(fill='x')
            finally:self._inspector_busy=False
        else:
            super().update_inspector();self._inspector_busy=True
            try:
                a=self.scene.assets.get(self.selection)
                if a and a['kind']=='STAND' and a['props'].get('ga_stand'):
                    from stand13 import GA_FIELDS
                    section=self.section('通航机场机位')
                    for key,(label,default) in GA_FIELDS.items():
                        self.property_field(section,key,label,a['props'].get(key,default),'text')
                if a and a['kind']=='ROAD':
                    self.hide_field11('center_visible')
                    sec=self.section('服务车道标记');self.property_field(sec,'_road_side11','放置车道',self.lane10.get(),'text',['A','B','BOTH'])
                    self.property_field(sec,'road_center_visible','自动车道分界线',a['props'].get('road_center_visible',True),'bool');self.property_field(sec,'road_auto_arrows','自动路口箭头',a['props'].get('road_auto_arrows',True),'bool');self.property_field(sec,'road_turn_guides','路口引导线',a['props'].get('road_turn_guides','NEAR_SIDE'),'text',['NEAR_SIDE','ALL','HIDDEN'])
                    for key in ('SPEED','JET_BLAST','PEDESTRIAN','ROAD_STOP','ROAD_ARROW','ROAD_DIVIDER'):
                        ttk.Button(self.property_body,text='绘制 '+CATALOG[key]['name'],command=lambda key=key:self.road_tool11(key)).pack(fill='x',padx=8,pady=2)
                if a and a['props'].get('role')=='DEICING':
                    sec=self.section('除冰坪 · MH5001 4.14')
                    for key,label,default in [('deice_aircraft_length','飞机长度 m',40),('deice_wingspan','飞机翼展 m',36),('deice_clearance','外围净宽 m',4.5),('deice_bays','机位数量',1),('deice_vehicles','除冰车辆数量',2),('deice_crossfall','横坡 %',None)]:self.property_field(sec,key,label,a['props'].get(key,default),'int' if key in ('deice_bays','deice_vehicles') else 'float')
                    self.property_field(sec,'deice_crossfall_mode','横坡形式',a['props'].get('deice_crossfall_mode','SINGLE'),'radio',['SINGLE','SYMMETRIC']);self.property_field(sec,'deice_collection','除冰液收集设施',a['props'].get('deice_collection',False),'bool')
                    ttk.Label(self.property_body,text='外围净宽宜≥4.5m；单面横坡≤1.0%，对称双面坡≤1.5%。保持时间、净距和承载仍需专项复核。',wraplength=280,padding=8).pack(fill='x')
                if a and a['kind']=='MARKING' and (a['props'].get('axis_placement11') or a['props'].get('attached_mark') or a['props'].get('road_id') or a['props'].get('axis_path11')):
                    sec=self.section('中线吸附位置');self.property_field(sec,'_axis_side11','显示侧',a['props'].get('axis_side',a['props'].get('lane_side','CENTER')),'text',['A','B','BOTH'] if a['props'].get('road_id') else ['CENTER','A','B','BOTH'])
                if a and a['kind']=='STAND':
                    for key in ('outward','width','shoulder','center_visible','edges_visible'):self.hide_field11(key)
                    sec=self.section('整套机位关系');self.property_field(sec,'bridge_side','廊桥侧',a['props'].get('bridge_side','LEFT'),'radio',['LEFT','RIGHT']);self.property_field(sec,'entry_attached','入口绑定中线',a['props'].get('entry_attached',bool(a['props'].get('entry_asset'))),'bool')
                    ttk.Label(self.property_body,text='选中引入线、安全线、编号或停止线时，边框移动/旋转作用于整套机位。宽端开口，窄端封闭。',wraplength=280,padding=8).pack(fill='x')
                mark=a or self.auto_assets.get(self.selection)
                if mark and mark['props'].get('auto_scaled'):ttk.Label(self.property_body,text=f'当前道面不足以容纳原字高{mark["props"].get("design_text_height",4):g}m标识，预览已适配。请加宽道面或专项复核尺寸；不计为规范通过。',wraplength=280,padding=8,foreground='#a05238').pack(fill='x')
                if a and a['kind'] in TAXIS and a['props'].get('rapid_exit'):
                    sec=self.section('快速脱离道接收端');self.property_field(sec,'join_reverse_visible','显示反向接入引导',a['props'].get('join_reverse_visible',True),'bool')
            finally:self._inspector_busy=False
        self.reveal_inspector11()
    def hide_field11(self,key):
        control=self._field_controls.pop(key,None)
        if control:
            info=control.grid_info()
            for widget in control.master.grid_slaves(row=info.get('row',-1)):widget.grid_remove()
        self.editor_vars.pop(key,None)
    def reveal_inspector11(self):
        if not hasattr(self,'property_canvas'):return
        if self._inspector_job11:
            try:self.after_cancel(self._inspector_job11)
            except tk.TclError:pass
        def show():
            self._inspector_job11=None
            if self._closed:return
            c=self.property_canvas
            for item in c.find_all():
                if c.type(item)=='window':c.itemconfigure(item,width=max(1,c.winfo_width()))
            c.configure(scrollregion=c.bbox('all'));c.yview_moveto(0)
        self._inspector_job11=self.after_idle(show)
    def road_tool11(self,key):
        side=self.lane10.get();self.set_mode('MARK:'+key);self.scene.data['meta'].setdefault('tool_defaults',{}).setdefault('MARK:'+key,{})['axis_side']=side;self.update_inspector()
    def apply_properties(self):
        if self._inspector_busy:return
        dirty=set(getattr(self,'_dirty_fields',set()))
        if self._draft11:
            try:
                values={}
                for key,(var,kind) in self.editor_vars.items():
                    if not key.startswith('_draft_'):continue
                    value=var.get();values[key[7:]]=int(value) if kind=='int' else float(value) if kind=='float' else value
                if any(isinstance(value,(float,int)) and not isinstance(value,bool) and not math.isfinite(value) for value in values.values()):raise ValueError('数值必须有限')
                if getattr(self,'_prefab19',None)=='GA_STAND':
                    from stand13 import ga_stand_props
                    values=dict(ga_stand_props(),**values)
                elif getattr(self,'_prefab19',None)=='HELI_STAND':
                    from stand13 import helicopter_stand_props
                    values.update(helicopter_stand_props())
                self._draft_values11=values;self.scene.data['meta'].setdefault('tool_defaults',{})[getattr(self,'_prefab19',None) or self._draft11]=dict(values)
                if 'lead_type' in values:self.lead10.set(values['lead_type']);self.bridge10.set(values.get('has_bridge',False))
                if 'route_type' in values:self.taxi_type10.set(values['route_type'])
                if 'axis_side' in values:self.lane10.set(values['axis_side'])
                self._dirty_fields.clear();self.property_error.configure(text='')
            except ValueError as exc:self.property_error.configure(text=str(exc))
            return
        if '_road_side11' in dirty:self.lane10.set(self.editor_vars['_road_side11'][0].get());self._dirty_fields.discard('_road_side11')
        if '_axis_side11' in dirty:
            try:self.change_side11(self.editor_vars['_axis_side11'][0].get());self._dirty_fields.discard('_axis_side11')
            except ValueError as exc:self.property_error.configure(text=str(exc));return
        return super().apply_properties()
    def change_side11(self,side):
        from marks11 import place_axis
        from roads11 import place
        a=self.scene.assets[self.selection];p=a['props'];pair=p.get('pair_group');old=[aid for aid,b in self.scene.assets.items() if aid==a['id'] or pair and b['props'].get('pair_group')==pair]
        if p.get('axis_path11'):
            from pavement_geometry import offset
            aid=p['label_asset'];parent=self.scene.assets[aid];pair=__import__('uuid').uuid4().hex[:10];made=[]
            with self.scene.transaction('改变路径标记显示侧'):
                for oid in old:self.scene.assets.pop(oid,None)
                for lane in ('A','B') if side=='BOTH' else (side,):
                    pts=g.subpath(parent['points'],p['path_station_a'],p['path_station_b'])
                    if lane!='CENTER':pts=offset(pts,(-1 if lane=='A' else 1)*parent['props']['width']/4)
                    if lane!='CENTER' and ((lane=='A')!=(self.scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT')):pts.reverse()
                    props=copy.deepcopy(p);props.update(axis_side=lane,pair_group=pair);props.pop('mark_type',None);made.append(self.scene.create_marking(p['mark_type'],pts,**props))
            self.selection=made[0];self.schedule_frame();self.redraw();return
        if p.get('road_id'):aid=p['road_id'];station=p['road_station'];fn=place
        else:aid=p['label_asset'];station=p['attached_station'];fn=place_axis
        q,_=g.at(self.scene.assets[aid]['points'],station)
        with self.scene.transaction('改变标记显示侧'):
            for oid in old:self.scene.assets.pop(oid,None)
            made=fn(self.scene,p['mark_type'],(0,aid,station,q),side)
            for oid in made:
                for key in ('text','black_outline','line_width','spacing','maxspan','category'):
                    if key in p:self.scene.assets[oid]['props'][key]=p[key]
        self.selection=made[0];self.schedule_frame();self.schedule_audit();self.redraw()
    def select(self,oid):
        if self.mode=='SELECT' and not self._editing_guide11:oid=tr.owner(self.scene,oid,self.auto_assets)
        self._draft11=None;super().select(oid);self.reveal_inspector11()
    def pick(self,p,paths_only=False):
        if not paths_only and hasattr(self,'canvas'):
            x,y=self.screen(p)
            from pavement_geometry import area
            candidates={}
            styles=self.scene.data['meta'].get('object_display',{})
            for item in reversed(self.canvas.find_overlapping(x-5,y-5,x+5,y+5)):
                for tag in self.canvas.gettags(item):
                    if not tag.startswith('owner:'):continue
                    oid=tag[6:]
                    if oid in candidates:continue
                    a=self.scene.assets.get(oid) or self.auto_assets.get(oid)
                    m=self.scene.movements.get(oid)
                    if not (a or m):continue
                    owner=(a or {}).get('owner') or oid
                    if any(styles.get(key,{}).get('hidden') or styles.get(key,{}).get('opacity')==0
                           for key in (oid,owner)):
                        continue
                    points=a['points'] if a else self.scene.movement_path(oid)
                    props=a['props'] if a else m
                    kind=a['kind'] if a else 'TAXIWAY'
                    if kind=='STAND':
                        from stand_profiles import safety_profile
                        footprint=abs(area(safety_profile(self.scene,a)))
                    elif kind=='MARKING' and CATALOG[props['mark_type']]['mode']=='AREA':
                        footprint=abs(area(points))
                    elif kind=='MARKING':
                        footprint=max(1,g.length(points))*props.get('line_width',.15)
                    elif kind in (*TAXIS,'RUNWAY','ROAD'):
                        footprint=g.length(points)*props.get('width',1)
                    else:
                        footprint=abs(area(points)) if len(points)>=3 else g.length(points)*props.get('width',1)
                    candidates[oid]=(footprint,points)
            if candidates:
                oid=min(candidates,key=lambda key:candidates[key][0])
                _,station,q=g.project(candidates[oid][1],p)
                return 0.,oid,station,q
        return super().pick(p,paths_only)
    def click(self,e):
        if self._space11 and self.scene.data['meta'].get('space_pan',True):
            self._pan11=dict(start=(e.x,e.y),origin=list(self.origin));return
        e=self.event10(e)
        if self.mode in ('BREAK','SPLIT7'):
            hit=self.taxi_hit11(self.world(e.x,e.y))
            if not hit:self.status.set('请点击需要切分的滑行道中线');return
            _,aid,station,q=hit
            if min(station,g.length(self.scene.assets[aid]['points'])-station)<.5:self.status.set('切分点应在滑行道内部，不能位于端点');return
            try:
                if self.mode=='SPLIT7':self.selection=__import__('editor7_model').split_route(self.scene,aid,station)
                else:self.selection=self.scene.split_asset(aid,station)
                self.set_mode('SELECT');self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        if self.mode=='SELECT' and not getattr(e,'state',0)&4 and self.begin_transform11(e):return
        if self.mode=='SELECT' and not self._editing_guide11:
            self.canvas.focus_set();p=self.world(e.x,e.y);hit=self.pick(p)
            if hit:
                oid=tr.owner(self.scene,hit[1],self.auto_assets)
                if getattr(e,'state',0)&4:
                    if oid in self.selected_ids:self.selected_ids.remove(oid)
                    else:self.selected_ids.add(oid)
                    self._preserve_set=True
                    try:self.select(oid)
                    finally:self._preserve_set=False
                else:self.select(oid)
            else:
                self._box=dict(start=(e.x,e.y),end=(e.x,e.y),add=bool(getattr(e,'state',0)&1));self.drag=None
            return
        if self.mode=='STAND':
            self.apply_properties();p=self.world(e.x,e.y)
            if not self.points:
                from editor7_model import snap_path
                hit=snap_path(self.scene,p,max(.25,12/self.zoom))
                if hit and self.scene.assets[hit[1]]['kind'] in TAXIS:p=hit[3]
                else:hit=None
                self._stand_start11=hit;self.points=[p];self.redraw();return
            if self._stand_exit_pending58:
                hit=self.stand_exit_candidate(p)
                point=hit[3] if hit else p
                vertices=self._stand_exit_vertices69
                previous=vertices[-1][0] if vertices else self.points[-1]
                if g.distance(previous,point)>.01:vertices.append((point,hit))
                self._stand_exit_hit58=hit
                self._stand_exit_cursor69=p
                self._stand_preview50=0
                self.pointer(e)
                self.status.set('左键继续放置引出线拐点，按 Enter 完成。')
                return
            if g.distance(self.points[-1],p)>.01:
                self.points.append(p)
                self.redraw()
                self._stand_preview50=0
                self.pointer(e)
            self.status.set('左键设置拐点或停止位置，按 Enter 确认。')
            return
        if self.mode.startswith('MARK:'):
            self.apply_properties();key=self.mode[5:];side=self._draft_values11.get('axis_side','CENTER')
            from roads10 import ROAD_MARKS,hit,place
            if key in ROAD_MARKS:
                h=hit(self.scene,self.world(e.x,e.y),max(.25,12/self.zoom))
                if not h:self.status.set('请点击服务车道');return
                try:self.selection=place(self.scene,key,h,side)[0];self.set_mode('SELECT');self.refresh()
                except ValueError as exc:self.status.set(str(exc))
                return
            from editor7_model import snap_path,AXIS_MARKS,CROSS_POINTS,CROSS_PATHS
            point=self.world(e.x,e.y)
            if key=='TWY_ENHANCED':
                from guidance20 import routes,snap
                from enhanced19 import between
                hit=snap(self.scene,point,max(.25,12/self.zoom))
                if not hit:
                    self.status.set('请点击可见的滑行道中线')
                    return
                if not self._axis_path11:
                    self._axis_path11=hit;self.points=[hit[3]];self.redraw();return
                try:
                    first=self._axis_path11
                    pts=between(self.scene,first,hit)
                    axis=routes(self.scene)[first[1]]
                    from pavement_geometry import offset
                    with self.scene.transaction('沿可见中线绘制增强标记'):
                        ids=[]
                        for lane in ('A','B') if side=='BOTH' else (side,):
                            points=pts if lane=='CENTER' else offset(pts,(-1 if lane=='A' else 1)*axis['props']['width']/4)
                            if lane!='CENTER' and ((lane=='A')!=(self.scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT')):
                                points=points[::-1]
                            ids.append(self.scene.create_marking(key,points,axis_side=lane,enhanced_two_point=True))
                    self.selection=ids[0];self.set_mode('SELECT');self.refresh()
                except ValueError as exc:self.status.set(str(exc))
                return
            if key=='HELI_SAFETY':
                if not self.points or g.distance(self.points[-1],point)>.01:
                    self.points.append(list(point))
                    self.redraw()
                return
            h=snap_path(self.scene,point,max(.25,12/self.zoom));spec=CATALOG[key]
            if h and key in AXIS_MARKS and (spec['mode']=='POINT' or key in CROSS_PATHS):
                from marks11 import place_axis
                self.selection=place_axis(self.scene,key,h,side)[0];self.set_mode('SELECT');self.refresh();return
            if h and key in ('TWY_CENTER','TWY_ENHANCED','ALIGNMENT','LEAD_IN','LEAD_OUT','AUX_LEAD'):
                if not self._axis_path11:self._axis_path11=h;self.points=[h[3]];self.redraw();return
                if h[1]==self._axis_path11[1]:
                    from pavement_geometry import offset
                    from marks11 import side_pose
                    a=self.scene.assets[h[1]];lo,hi=sorted((h[2],self._axis_path11[2]));pair=__import__('uuid').uuid4().hex[:10]
                    if hi-lo<.2:return
                    with self.scene.transaction('沿中线绘制引导标记'):
                        ids=[]
                        for lane in ('A','B') if side=='BOTH' else (side,):
                            pts=g.subpath(a['points'],lo,hi)
                            if lane!='CENTER':pts=offset(pts,(-1 if lane=='A' else 1)*a['props']['width']/4)
                            if lane!='CENTER' and ((lane=='A')!=(self.scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT')):pts.reverse()
                            ids.append(self.scene.create_marking(key,pts,label_asset=a['id'],axis_side=lane,pair_group=pair,path_station_a=lo,path_station_b=hi,axis_path11=True))
                    self.selection=ids[0];self.set_mode('SELECT');self.refresh();return
        if self.mode=='DEICE10':
            self.apply_properties();p=self.world(e.x,e.y);self.points.append(p)
            if len(self.points)==2:
                x0,x1=sorted(q[0] for q in self.points);y0,y1=sorted(q[1] for q in self.points)
                if min(x1-x0,y1-y0)<10:self.status.set('请绘制更大的除冰坪');self.points=[];return
                self.selection=self.scene.create_asset('APRON','除冰坪',[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],role='DEICING',**self._draft_values11);self.set_mode('SELECT');self.refresh()
            else:self.redraw()
            return
        return super().click(e)
    def stand_exit_candidate(self,point):
        from stand15 import remote_exit_hit
        hit=remote_exit_hit(self.scene,point,max(.25,12/self.zoom))
        stop=self.points[-1]
        direction=g.unit(self.points[-2],stop)
        if hit and sum((hit[3][k]-stop[k])*direction[k] for k in (0,1))>.5:
            return hit
        return None

    def prepare_remote_exit(self,points):
        if len(points)<2 or g.length(points)<15:
            self.status.set('引入线长度至少为 15 m。')
            return
        self.points=points
        self._stand_exit_pending58=True
        self._stand_exit_hit58=None
        self._stand_exit_cursor69=None
        self._stand_exit_vertices69=[]
        self.status.set('左键放置引出线拐点，可吸附出口滑行道。按 Enter 完成。')
        self.redraw()

    def commit_stand(self,points,exit_hit=None,exit_vertices=()):
        if len(points)<2 or g.length(points)<15:
            self.status.set('引入线长度至少为 15 m。')
            return
        p=points[-1]
        polyline=len(points)>2 or self._draft_values11.get('stand_polyline',False)
        values=dict(self._draft_values11)
        names={str(a['props'].get('stand_number') or a['name']) for a in self.scene.assets.values() if a['kind']=='STAND'}
        prefix='H' if values.get('helicopter_stand') else ''
        name=next(f'{prefix}{i}' for i in range(101,102+len(names)) if f'{prefix}{i}' not in names)
        props=dict(values,show_safety=values.get('show_safety',True),stand_number=name,outward=True)
        if polyline:props.update(lead_type='C',stand_polyline=True)
        if exit_vertices:
            from stand15 import drawn_remote_exit_props
            props.update(drawn_remote_exit_props(dict(points=points,props=props),exit_vertices,exit_hit))
        elif exit_hit:
            from stand15 import remote_stand_props
            props.update(remote_stand_props(exit_hit))
        if self._stand_start11:props.update(entry_asset=self._stand_start11[1],entry_station=self._stand_start11[2],entry_attached=True)
        try:
            with self.scene.transaction('绘制整套机位'):
                self.selection=self.scene.create_asset('STAND',name,points,**props)
                aprons=[(abs(__import__('pavement_geometry').area(a['points'])),aid) for aid,a in self.scene.assets.items() if a['kind']=='APRON' and not a['props'].get('turn_pad') and g.inside(p,a['points']) and g.inside(self.points[0],a['points'])]
                if aprons:self.scene.reparent(self.selection,min(aprons)[1])
                elif self._stand_start11:
                    parent=self.scene.assets.get(self._stand_start11[1],{}).get('container_id')
                    if parent:self.scene.reparent(self.selection,parent)
            self.set_mode('SELECT');self.refresh()
        except ValueError as exc:self.status.set(str(exc))

    def remote_exit_draft(self,preview=False):
        vertices=list(self._stand_exit_vertices69)
        hit=self._stand_exit_hit58
        if vertices and vertices[-1][1]:
            hit=vertices[-1][1]
        elif hit:
            if not vertices or g.distance(vertices[-1][0],hit[3])>.01:
                vertices.append((hit[3],hit))
            else:
                vertices[-1]=(hit[3],hit)
        elif (preview or not vertices) and self._stand_exit_cursor69 is not None:
            point=self._stand_exit_cursor69
            previous=vertices[-1][0] if vertices else self.points[-1]
            if g.distance(previous,point)>.01:vertices.append((point,None))
        if not vertices:return [],None
        hit=vertices[-1][1]
        if hit and len(vertices)==1:return [],hit
        return [point for point,_ in vertices],hit

    def finish_draw(self):
        if self.mode=='MARK:HELI_SAFETY':
            if len(self.points)<2:return
            self.apply_properties()
            oid=self.scene.create_marking('HELI_SAFETY',list(self.points),**self._draft_values11)
            self.set_mode('SELECT')
            self.select(oid)
            self.refresh()
            return
        if self.mode=='STAND':
            self.apply_properties()
            if self._stand_exit_pending58:
                vertices,hit=self.remote_exit_draft()
                if vertices or hit:
                    return self.commit_stand(list(self.points),hit,vertices)
                self.status.set('请设置引出线终点，再按 Enter 完成。')
                return
            points=list(self.points)
            if getattr(self,'_prefab19',None) in ('REMOTE_STAND','GA_STAND'):
                return self.prepare_remote_exit(points)
            return self.commit_stand(points)
        if self.mode in TAXIS+('ROAD',):
            if len(self.points)<2:return
            self.apply_properties();mode=self.mode;values=dict(self._draft_values11 or self.draft_defaults11(mode));vertices=copy.deepcopy(self.points)
            try:
                from curve_model import create_rounded,rounded_nodes,evaluate
                with self.scene.transaction('绘制预制路线'):
                    if mode=='ROAD':
                        radius=values.get('corner_radius',12);nodes,_=rounded_nodes(vertices,radius);aid=self.scene.create_asset('ROAD','S'+str(1+sum(a['kind']=='ROAD' for a in self.scene.assets.values())),evaluate(nodes),**values);self.scene.assets[aid].update(design_vertices=vertices,curve_nodes=nodes)
                    else:
                        kind=SUBTYPES.get(values.get('route_type'),mode);aid=create_rounded(self.scene,kind,'T'+str(1+sum(a['kind'] in TAXIS for a in self.scene.assets.values())),vertices,radius=values.get('corner_radius',25),tolerance=max(.25,12/self.zoom));self.scene.assets[aid]['props'].update(values)
                        if values.get('route_type')=='快速脱离道':
                            try:__import__('project10').rapid_option(self.scene,aid,True)
                            except ValueError as exc:self.scene.assets[aid]['props']['rapid_fit_note']=str(exc)
                self.selection=aid;self.set_mode('SELECT');self.refresh()
            except ValueError as exc:self.status.set(str(exc))
            return
        return super().finish_draw()
    def pointer(self,e):
        if self._object_drag11 or self._pan11:return
        e=self.event10(e)
        if self.mode=='STAND' and self.points:
            if self._stand_exit_pending58:
                self._stand_exit_cursor69=self.world(e.x,e.y)
                self._stand_exit_hit58=self.stand_exit_candidate(self._stand_exit_cursor69)
            import time
            stamp=time.monotonic()
            if stamp-self.__dict__.get('_stand_preview50',0)<1/30:return
            self._stand_preview50=stamp
        super().pointer(e);c=self.canvas;c.delete('cut_preview11');c.delete('stand_preview11');c.delete('angle_hint11')
        if self.mode=='MARK:TWY_ENHANCED' and self._axis_path11 and self.preview_enabled.get():
            import time
            now=time.monotonic()
            if now-self.__dict__.get('_enhanced_preview39',0)>=.065:
                self._enhanced_preview39=now
                c.delete('enhanced_two_point39')
                from guidance20 import snap
                from enhanced19 import between
                hit=snap(self.scene,self.world(e.x,e.y),max(.25,12/self.zoom))
                if hit:
                    try:
                        line=between(self.scene,self._axis_path11,hit)
                        c.create_line(*[v for p in line for v in self.screen(p)],
                                      fill='#d34f94',width=3,tags='enhanced_two_point39')
                    except ValueError:pass
        if getattr(e,'state',0)&1 and self.points:
            q=self.world(e.x,e.y);start=self.points[-1];angle=math.degrees(math.atan2(q[1]-start[1],q[0]-start[0]))%360;c.create_text(e.x+12,e.y+18,text=f'Shift · {angle:.1f}°',anchor='w',fill='#a52b54',tags='angle_hint11')
        if self.mode in ('BREAK','SPLIT7'):
            hit=self.taxi_hit11(self.world(e.x,e.y))
            if hit and self.scene.assets[hit[1]]['kind'] in TAXIS:
                a=self.scene.assets[hit[1]];q,u=g.at(a['points'],hit[2]);v=[-u[1],u[0]];width=a['props']['width']/2+a['props'].get('shoulder',0)+3
                c.create_line(*self.screen([q[k]-v[k]*width for k in (0,1)]),*self.screen([q[k]+v[k]*width for k in (0,1)]),fill='#d74187',width=2,dash=(5,3),tags='cut_preview11')
        if self.mode=='STAND' and self.points:
            p=self.world(e.x,e.y)
            from stand15 import design,draw_exit_snap,remote_exit_lines,remote_stand_props,drawn_remote_exit_props
            from stand13 import safety
            points=list(self.points)
            if not self._stand_exit_pending58 and g.distance(points[-1],p)>.01:
                points.append(p)
            if len(points)<2:return
            props=dict(self._draft_values11,stand_number='101')
            if len(points)>2 or props.get('stand_polyline'):
                props.update(lead_type='C',stand_polyline=True)
            if self._stand_start11:
                props.update(entry_asset=self._stand_start11[1],entry_station=self._stand_start11[2])
            if getattr(self,'_prefab19',None) in ('REMOTE_STAND','GA_STAND'):
                props.update(remote_stand=True,has_bridge=False)
            hit=None
            if self._stand_exit_pending58:
                vertices,hit=self.remote_exit_draft(preview=True)
                if vertices:
                    props.update(drawn_remote_exit_props(dict(points=points,props=props),vertices,hit))
                elif hit:
                    props.update(remote_stand_props(hit))
            a=dict(id='preview',name='101',kind='STAND',points=points,props=props)
            if props.get('helicopter_stand'):
                x,y=self.screen(points[-1])
                radius=props.get('aircraft_span',12)*self.zoom/2
                c.create_oval(x-radius,y-radius,x+radius,y+radius,outline='#f2ce54',width=2,tags='stand_preview11')
                c.create_text(x,y,text='H',fill='#f2ce54',tags='stand_preview11')
            paths=[dict(points=points)] if props.get('helicopter_stand') else design(a,self.scene)['paths']
            for part in paths:
                c.create_line(*[v for q in part['points'] for v in self.screen(q)],fill='#f2ce54',width=2,tags='stand_preview11')
            for path in remote_exit_lines(a,self.scene) if self._stand_exit_pending58 else ():
                c.create_line(*[v for q in path for v in self.screen(q)],
                              fill='#35bbd3' if hit else '#f2ce54',width=2,tags='stand_preview11')
            if hit:draw_exit_snap(self,hit,'stand_preview11')
            boundary=safety(self.scene,a)
            if props.get('helicopter_stand'):return
            if props.get('ga_stand'):boundary=boundary+[boundary[0]]
            c.create_line(*[v for q in boundary for v in self.screen(q)],fill='#d45070',width=2,dash=(4,3),tags='stand_preview11')
        if self.mode=='SELECT' and self._frame_box11:
            _,_,handles,box=self._frame_box11
            cursor='crosshair' if any(math.hypot(e.x-x,e.y-y)<10 for x,y in handles) else 'fleur' if self.border_hit11(e.x,e.y,box) else ''
            self.canvas.configure(cursor=cursor)
    def taxi_hit11(self,p):
        choices=[]
        for aid,a in self.scene.assets.items():
            if a['kind'] not in TAXIS:continue
            distance,station,q=g.project(a['points'],p)
            if distance<=max(.25,12/self.zoom,a['props']['width']/2):choices.append((distance,aid,station,q))
        return min(choices,key=lambda row:(row[0],row[1]!=self.selection)) if choices else None
    @staticmethod
    def border_hit11(x,y,box):
        x0,y0,x1,y1=box
        return x0-7<=x<=x1+7 and y0-7<=y<=y1+7 and (min(abs(x-x0),abs(x-x1))<7 or min(abs(y-y0),abs(y-y1))<7)
    def event10(self,e):
        if not (getattr(e,'state',0)&1) or not self.points:return e
        from project10 import constrain
        tangent=g.unit(self.points[-2],self.points[-1]) if len(self.points)>1 else self._start_tangent10
        q=constrain(self.points[-1],self.world(e.x,e.y),tangent);x,y=self.screen(q)
        return SimpleNamespace(x=x,y=y,state=e.state,widget=getattr(e,'widget',self.canvas))
    def selected_roots11(self):
        ids=set(self.selected_ids) if len(self.selected_ids)>1 else {self.selection} if self.selection else set()
        return {tr.owner(self.scene,oid,self.auto_assets) for oid in ids if oid}
    def frame11(self):
        roots=self.selected_roots11();items=tr.visual_items(self.scene,roots,self.render_items,self.auto_assets);box=tr.bounds(items)
        if box is None:
            points=[q for oid in roots if oid in self.scene.assets for q in self.scene.assets[oid]['points']]
            if points:box=(min(q[0] for q in points),min(q[1] for q in points),max(q[0] for q in points),max(q[1] for q in points))
        return roots,items,box
    def redraw(self):
        super().redraw()
        if not hasattr(self,'canvas'):return
        if self.mode=='SELECT' and not self._editing_guide11:
            self.canvas.delete('overlay');self.draw_frame11()
    def draw_frame11(self,box=None):
        c=self.canvas;c.delete('frame11')
        if box is None:
            roots,items,box=self.frame11()
        if box is None:self._frame_box11=None;return
        x0,y1=self.screen([box[0],box[1]]);x1,y0=self.screen([box[2],box[3]]);pad=8
        visual=[x0-pad,y0-pad,x1+pad,y1+pad];w,h=c.winfo_width(),c.winfo_height()
        visual=[max(12,min(w-12,visual[0])),max(12,min(h-12,visual[1])),max(12,min(w-12,visual[2])),max(12,min(h-12,visual[3]))];x0,y0,x1,y1=visual
        c.create_rectangle(x0,y0,x1,y1,outline='#1592aa',width=2,dash=(5,3),tags='frame11');handles=[]
        for x,y,dx,dy in [(x0,y0,-1,-1),(x1,y0,1,-1),(x0,y1,-1,1),(x1,y1,1,1)]:
            xx=max(5,min(w-5,x+dx*10));yy=max(5,min(h-5,y+dy*10));handles.append((xx,yy));c.create_oval(xx-4,yy-4,xx+4,yy+4,fill='#edfaff',outline='#1592aa',width=2,tags='frame11')
        self._frame_box11=(box,[(box[0]+box[2])/2,(box[1]+box[3])/2],handles,visual)
    def begin_transform11(self,e):
        if not self._frame_box11 or not self.selection:return False
        box,center,handles,visual=self._frame_box11;rotation=any(math.hypot(e.x-x,e.y-y)<10 for x,y in handles)
        if not rotation and not self.border_hit11(e.x,e.y,visual):return False
        self.apply_properties();roots,items,_=self.frame11();ids=tr.members(self.scene,roots)
        d=dict(roots=roots,items=items,ids=ids,center=center,box=box,start=self.world(e.x,e.y),pixel=(e.x,e.y),angle=0.,delta=[0.,0.],rotation=rotation,last_pixel=[0,0],base_items=self.render_items)
        self._object_drag11=d;self.drag=None;self._drag_data=None;self._anchor_drag=self._guide_drag=self._control_drag=self._vertex_drag=self._stop_drag=self._batch_drag=None
        for oid in ids:
            for item in self.canvas.find_withtag('owner:'+oid):self.canvas.addtag_withtag('drag11',item)
        for oid,a in self.auto_assets.items():
            if a.get('owner') in ids:
                for item in self.canvas.find_withtag('owner:'+oid):self.canvas.addtag_withtag('drag11',item)
        if rotation:self.canvas.itemconfigure('drag11',state='hidden')
        self.canvas.focus_set();return True
    def motion(self,e):
        if self._pan11:
            p=self._pan11;self.origin=[p['origin'][0]+e.x-p['start'][0],p['origin'][1]+e.y-p['start'][1]];self.redraw();return
        if not self._object_drag11:return super().motion(e)
        d=self._object_drag11;p=self.world(e.x,e.y)
        if d['rotation']:
            angle=math.atan2(p[1]-d['center'][1],p[0]-d['center'][0])-math.atan2(d['start'][1]-d['center'][1],d['start'][0]-d['center'][0])
            if getattr(e,'state',0)&1:angle=round(angle/(math.pi/4))*math.pi/4
            d['angle']=angle;self.canvas.delete('ghost11');points=[]
            for item in d['items']:
                if item.get('black_underlay') or item['type']=='text':continue
                transformed=[tr.point(q,d['center'],angle,[0,0]) for q in item['points']];points.extend(transformed)
                if len(transformed)<2:continue
                if item['type']=='polygon':transformed=transformed+[transformed[0]]
                if len(transformed)>120:transformed=g.simplify(transformed,.5/max(self.zoom,.001))
                self.canvas.create_line(*[v for q in transformed for v in self.screen(q)],fill='#26a7b5',width=1,tags='ghost11')
            if points:self.draw_frame11((min(q[0] for q in points),min(q[1] for q in points),max(q[0] for q in points),max(q[1] for q in points)))
        else:
            if getattr(e,'state',0)&1:p=__import__('project10').constrain(d['start'],p)
            dx,dy=p[0]-d['start'][0],p[1]-d['start'][1];d['delta']=[dx,dy];pixels=[dx*self.zoom,-dy*self.zoom]
            self.canvas.move('drag11',pixels[0]-d['last_pixel'][0],pixels[1]-d['last_pixel'][1]);d['last_pixel']=pixels
            box=d['box'];self.draw_frame11((box[0]+dx,box[1]+dy,box[2]+dx,box[3]+dy))
        self.status.set(f'旋转 {math.degrees(d["angle"]):.1f}°' if d['rotation'] else f'移动 X {d["delta"][0]:.2f}m / Y {d["delta"][1]:.2f}m')
    def release(self,e):
        if self._pan11:self._pan11=None;return
        if not self._object_drag11:return super().release(e)
        d=self._object_drag11;self._object_drag11=None;self.canvas.itemconfigure('drag11',state='normal');self.canvas.dtag('drag11','drag11');self.canvas.delete('ghost11')
        try:
            if tr.generated_signs_only(self.scene,d['roots'],self.auto_assets):
                ids = set(d['roots'])
                tr.move_generated_signs(self.scene,ids,self.auto_assets,d['center'],d['angle'],d['delta'],d['items'])
            else:
                ids=tr.apply(self.scene,d['roots'],d['center'],d['angle'],d['delta'])
            replacement=[]
            for item in d['base_items']:
                if tr.item_owner(item,self.auto_assets) in ids or item.get('oid') in ids:
                    changed=dict(item,points=[tr.point(q,d['center'],d['angle'],d['delta']) for q in item['points']])
                    if item['type']=='text':changed['rotation']=item.get('rotation',0)+math.degrees(d['angle'])
                    replacement.append(changed)
                else:replacement.append(item)
            self.render_items=replacement;self._renderer.items=None;self._nav_key=None;self.schedule_frame();self.schedule_audit();self.update_inspector();self.update_title();self.redraw()
        except ValueError as exc:self.status.set('未提交：'+str(exc));self._renderer.items=None;self.redraw()
    def cancel_action(self,e=None):
        if self._object_drag11:
            d=self._object_drag11;self._object_drag11=None;self.canvas.itemconfigure('drag11',state='normal');self.canvas.dtag('drag11','drag11');self.canvas.delete('ghost11');self._renderer.items=None;self.redraw();return 'break'
        self._pan11=None;return super().cancel_action(e)
    def gesture11(self):return self._object_drag11 or getattr(self,'_drag10',None) or getattr(self,'_vertex_drag',None) or getattr(self,'_control_drag',None) or getattr(self,'_anchor_drag',None) or getattr(self,'_guide_drag',None)
    def schedule_frame(self):
        if self.gesture11():self._pending_frame=True;return
        return super().schedule_frame()
    def start_frame(self):
        if self.gesture11():self._render_after=None;self._pending_frame=True;return
        return super().start_frame()
    def poll_frame(self):
        if self.gesture11():self._poll_after=self.after(25,self.poll_frame);return
        return super().poll_frame()
    def update_minimap(self):
        if self.gesture11():return
        return super().update_minimap()
    def space_press11(self,e):
        if isinstance(e.widget,(tk.Entry,ttk.Entry,ttk.Combobox,tk.Text)):return
        if self.scene.data['meta'].get('space_pan',True):self._space11=True;self.canvas.configure(cursor='fleur');return 'break'
    def space_release11(self,e):
        self._space11=False
        if hasattr(self,'canvas'):self.canvas.configure(cursor='')
    def place_nav11(self):
        if not hasattr(self,'nav_frame11') or not self.nav_visible11.get():return
        viewport = self.canvas.q.viewport()
        w, h = viewport.width(), viewport.height()
        if w<190 or h<158:return
        width, height = 190, 158
        position = self.scene.data['meta'].get('nav_position')
        x, y = position if position else (10, 10)
        x = max(0, min(w - width, x))
        y = max(0, min(h - height, y))
        widget=self.nav_frame11.q
        if widget.parentWidget() is not viewport:widget.setParent(viewport)
        widget.setGeometry(round(x),round(y),width,height)
        if widget.isHidden():widget.show()
        widget.raise_()
        self.nav_header11.show()
        self.nav_header11.raise_()
    def toggle_nav11(self):
        if not hasattr(self,'nav_frame11'):return
        self.scene.data['meta']['nav_visible']=self.nav_visible11.get()
        if self.nav_visible11.get():self.place_nav11()
        else:self.nav_frame11.place_forget()
    def nav_press11(self,e):self._nav_drag11=(e.x_root,e.y_root,self.nav_frame11.winfo_x(),self.nav_frame11.winfo_y())
    def nav_motion11(self,e):
        if not self._nav_drag11:return
        rx,ry,x,y=self._nav_drag11;self.scene.data['meta']['nav_position']=[x+e.x_root-rx,y+e.y_root-ry];self.place_nav11()
    def nav_release11(self,e):self._nav_drag11=None
    def preferences10(self):
        win=tk.Toplevel(self);win.title('项目首选项');body=ttk.Frame(win,padding=14);body.pack(fill='both',expand=True);m=self.scene.data['meta']
        traffic=tk.StringVar(value=m.get('traffic_side','RIGHT'));space=tk.BooleanVar(value=m.get('space_pan',True));nav=tk.BooleanVar(value=self.nav_visible11.get());grid=tk.BooleanVar(value=self.grid_visible.get());outline=tk.BooleanVar(value=m.get('guidance_black_outline',False));distance=tk.StringVar(value=str(m.get('jet_warning_distance',12)))
        win.q.setMinimumWidth(380)
        options=ttk.LabelFrame(body,text='显示与操作',padding=10)
        options.pack(fill='x',pady=4)
        parameters=ttk.LabelFrame(body,text='图面与标记牌',padding=10)
        parameters.pack(fill='x',pady=4)
        ttk.Label(options,text='车辆行驶方向').pack(anchor='w')
        for value,label in [('RIGHT','靠右行驶'),('LEFT','靠左行驶')]:ttk.Radiobutton(options,text=label,value=value,variable=traffic).pack(anchor='w')
        for label,var in [('按住空格＋左键拖动画面（PS习惯）',space),('显示可移动导航窗口',nav),('背景网格',grid),('标记黑底/描边',outline)]:ttk.Checkbutton(options,text=label,variable=var).pack(anchor='w',pady=3)
        ttk.Label(parameters,text='尾流警示距交叉道面边缘 m').pack(anchor='w');ttk.Entry(parameters,textvariable=distance).pack(fill='x')
        factor=tk.StringVar(value=str(m.get('board_enlarge_factor') or ''))
        ttk.Label(parameters,text='标记牌固定放大倍率（留空为自动）').pack(anchor='w',pady=4)
        ttk.Entry(parameters,textvariable=factor).pack(fill='x')
        autosave=getattr(self,'autosave_timer',None)
        if autosave:
            auto_enabled=tk.BooleanVar(value=self.autosave_enabled)
            auto_minutes=tk.StringVar(value=str(self.autosave_minutes))
            ttk.Checkbutton(options,text='自动保存工程副本',variable=auto_enabled).pack(anchor='w',pady=3)
            ttk.Label(parameters,text='自动保存间隔（分钟）').pack(anchor='w',pady=4)
            ttk.Entry(parameters,textvariable=auto_minutes).pack(fill='x')
        error=tk.StringVar(value='')
        def save():
            try:
                if autosave:
                    minutes=int(auto_minutes.get())
                    if not 1<=minutes<=120:raise ValueError('自动保存间隔应为 1 至 120 分钟。')
                d=float(distance.get())
                value=float(factor.get()) if factor.get().strip() else None
                if value is not None and (not math.isfinite(value) or value<1 or value>10):
                    raise ValueError('标记牌倍率请输入 1 至 10 或留空')
                if not math.isfinite(d) or d<3:raise ValueError('提示距离至少3m')
                with self.scene.transaction('项目首选项'):
                    m['board_enlarge_factor']=value
                    m.update(traffic_side=traffic.get(),space_pan=space.get(),nav_visible=nav.get(),grid_visible=grid.get(),guidance_black_outline=outline.get(),jet_warning_distance=d)
                    from marks11 import refresh_axis
                    from roads11 import refresh_attachments
                    for aid,a in list(self.scene.assets.items()):
                        if a['kind']=='ROAD':refresh_attachments(self.scene,aid)
                        if a['kind'] in TAXIS+('RUNWAY',):refresh_axis(self.scene,aid)
                if autosave:
                    self.autosave_enabled=auto_enabled.get()
                    self.autosave_minutes=minutes
                    self.configure_autosave()
                    from user_settings34 import path,save as save_preferences
                    try:save_preferences(self,path())
                    except OSError as exc:error.set(str(exc));return
                self.nav_visible11.set(nav.get());self.grid_visible.set(grid.get());self.toggle_nav11();win.destroy();self.refresh()
            except ValueError as exc:error.set(str(exc))
        ttk.Label(body,textvariable=error,wraplength=344).pack(fill='x')
        actions=ttk.Frame(body);actions.pack(fill='x',pady=4)
        save_button=ttk.Button(actions,text='保存到项目',command=save)
        save_button.q.setMinimumSize(108,32)
        save_button.pack(side='right',padx=4)
        cancel=ttk.Button(actions,text='取消',command=win.destroy)
        cancel.q.setMinimumSize(84,32)
        cancel.pack(side='right',padx=4)
    def merge_names11(self):
        from naming11 import suggestions,merge
        primary=self.selection
        if primary not in self.scene.assets or self.scene.assets[primary]['kind'] not in TAXIS:self.status.set('请先选中主滑行道，再使用智能合并命名');return
        candidates=suggestions(self.scene,primary);extra=[aid for aid in self.selected_ids if aid in self.scene.assets and self.scene.assets[aid]['kind'] in TAXIS and aid not in dict(candidates)];candidates += [(aid,'手动框选的路线') for aid in extra]
        win=tk.Toplevel(self);win.title('智能合并滑行道命名');win.geometry('540x500');frame=ttk.Frame(win,padding=12);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='只合并编号与位置标志，保留各段曲线及原层级。\n优先识别端点相接且切线连续的路线。').pack(anchor='w')
        name=tk.StringVar(value=self.scene.assets[primary]['props'].get('designation') or self.scene.assets[primary]['name']);ttk.Entry(frame,textvariable=name).pack(fill='x',pady=8);holder=ttk.Frame(frame);holder.pack(fill='both',expand=True);choices={}
        for aid,reason in candidates:
            var=tk.BooleanVar(value=True);choices[aid]=var;a=self.scene.assets[aid];ttk.Checkbutton(holder,text=f'{a["name"]}  {g.length(a["points"]):.1f}m · {reason}',variable=var).pack(anchor='w')
        def apply():
            try:ids=merge(self.scene,primary,[aid for aid,var in choices.items() if var.get()],name.get());win.destroy();self.refresh();self.status.set(f'已将{len(ids)}段并入编号 {name.get()}；道面几何保持原状')
            except ValueError as exc:self.status.set(str(exc))
        ttk.Button(frame,text='合并命名',command=apply).pack(fill='x',pady=8)
    def demo10(self):
        Editor11(AirportScene.load(Path(__file__).with_name('example_editor11.airport.json')))

def main():Editor11().mainloop()
if __name__=='__main__':main()
