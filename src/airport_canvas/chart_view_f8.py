"""F8 parking chart workspace and page layout controls."""
import math
from uuid import uuid4

from qt_core21 import C, G, W
from qt_renderer21 import CanvasRenderer
import chart_f8 as chart
from interface_language import tr
import scene_geometry as g


class ChartView:
    def __init__(self, app):
        self.app=app
        self.active=False
        self.selected=None
        self.tool=None
        self.key=None
        self.kinds_by_owner={}
        self.renderer=CanvasRenderer(app.canvas,'chart_f8_surface')
        self.right=W.QScrollArea()
        self.right.setWidgetResizable(True)
        app.property_title.q.parentWidget().layout().addWidget(self.right,1)
        self.right.hide()
        self.tabs=app.lighting_view.tabs
        self.palette=W.QWidget()
        layout=W.QVBoxLayout(self.palette)
        self.draft=[]
        self.hover=None
        self.symbol_drag=None
        self.vertex_drag=None
        self.buttons={}
        for kind in chart.SYMBOLS:
            button=W.QPushButton(tr(chart.TYPES[kind][0]))
            button.setIcon(chart_icon(kind))
            button.setCheckable(True)
            button.setStyleSheet('QPushButton { text-align:left } QPushButton:checked { background:#d1edf6; color:#12576b; border-color:#76afc3 }')
            button.clicked.connect(lambda checked=False, kind=kind:self.choose(None if self.tool==kind else kind))
            layout.addWidget(button)
            self.buttons[kind]=button
        self.shape=W.QComboBox()
        self.shape.setToolTip('热点形状')
        for key,label in chart.HOTSPOTS.items():self.shape.addItem(chart_icon(key),tr(label),key)
        self.shape.currentIndexChanged.connect(lambda _:self.choose(self.tool) if self.tool in chart.AREA_TOOLS else None)
        toolbar=app.tool_buttons['SELECT'].master.q
        self.toolbar=W.QWidget(toolbar)
        row=W.QHBoxLayout(self.toolbar)
        row.setContentsMargins(5,0,1,0)
        for key,caption,callback in [('palette','航图配色',self.palette_dialog),('layout','航图排版',self.layout_dialog)]:
            button=W.QToolButton()
            button.setText(caption)
            button.setToolTip(caption)
            button.setIcon(chart_icon(key))
            button.setToolButtonStyle(C.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.clicked.connect(callback)
            row.addWidget(button)
        toolbar.layout().addWidget(self.toolbar)
        self.toolbar.hide()
        layout.addStretch()
        self.index=self.tabs.addTab(self.palette,'航图工具')
        self.tabs.setTabVisible(self.index,False)
        self.action=app.display_menu14.q.addAction('航图模式 · F8',self.toggle)
        self.action.setCheckable(True)
        app.bind('<F8>',lambda event:self.toggle())
        app.bind('<Escape>',lambda event:app.cancel_action(event) if self.active else app.set_mode('SELECT'))

    @property
    def scene(self):
        return self.app.scene

    def toggle(self):
        if self.active:
            self.leave()
            return 'break'
        app=self.app
        app.prepare_display_mode()
        app.select(None)
        self.active=True
        self.selection_scene=self.scene
        self.action.setChecked(True)
        self.previous=self.tabs.currentWidget()
        self.tabs.setTabVisible(self.index,True)
        self.tabs.setCurrentIndex(self.index)
        parent=self.right.parentWidget()
        option=C.Qt.FindChildOption.FindDirectChildrenOnly
        self.hidden=[w for w in parent.findChildren(W.QWidget,options=option) if w is not self.right and not w.isHidden()]
        for widget in self.hidden:widget.hide()
        self.right.show()
        self.toolbar.show()
        for tag in ('color17','movement_names20','view_mode18','frame11','north23','sign_display23',
                    'stand_context20_18','stand_text_f6','grid','grid7','scale14','selection','overlay','sign_anchor21_2'):
            if tag=='stand_context20_18':app.canvas.itemconfigure(tag,state='hidden')
            else:app.canvas.delete(tag)
        self.properties()
        app.status.set('航图模式 · 点击对象编辑配色，F8 返回')
        app.canvas.focus_set()
        app.redraw()
        return 'break'

    def leave(self,redraw=True):
        if not self.active:return
        self.active=False
        self.selected=None
        self.choose(None,focus=False)
        self.action.setChecked(False)
        self.toolbar.hide()
        self.right.hide()
        for widget in self.hidden:widget.show()
        for tab in self.app.lighting_view.original_tabs:
            self.tabs.setTabVisible(self.tabs.indexOf(tab),True)
        if self.previous in self.app.lighting_view.original_tabs:self.tabs.setCurrentWidget(self.previous)
        self.tabs.setTabVisible(self.index,False)
        c=self.app.canvas
        for tag in ('chart_f8_labels','chart_f8_badge','chart_f8_preview','chart_f8_selected_vertex','frame11'):c.delete(tag)
        c.itemconfigure('chart_f8_surface',state='hidden')
        c.itemconfigure('map',state='normal')
        c.camera21(self.app.origin,self.app.zoom)
        c.q.setBackgroundBrush(G.QColor('#131d27' if self.app.dark_mode_enabled() else '#e9eef2'))
        from bitmap_layers46 import draw
        draw(self.app)
        if redraw:self.app.redraw()

    def choose(self,kind,focus=True):
        self.cancel_symbol_drag()
        if focus:self.app.use_display_tools()
        self.tool=kind
        self.rvr_draft=None
        with C.QSignalBlocker(self.shape):
            if kind in chart.BOUNDARIES:
                if self.shape.findData('open_curve')<0:
                    self.shape.addItem(tr('开放折线'),'open_line')
                    self.shape.addItem(tr('开放曲线'),'open_curve')
                    self.shape.setCurrentIndex(self.shape.findData('open_curve'))
            else:
                for shape in chart.OPEN_SHAPES:
                    index=self.shape.findData(shape)
                    if index>=0:self.shape.removeItem(index)
        self.draft=[]
        self.hover=None
        for key,button in self.buttons.items():button.setChecked(key==kind)
        viewport=self.app.canvas.q.viewport()
        if kind:viewport.setCursor(C.Qt.CursorShape.CrossCursor)
        else:viewport.unsetCursor()
        self.draw_preview()
        if self.active:self.properties()
        if focus:
            if kind=='RVR':hint=tr('RVR：点击确认跑道中线上的位置。')
            elif kind=='HS' or kind in chart.BOUNDARIES:
                hint='点击顶点，按 Enter 完成' if self.shape.currentData() in ('polygon','rounded_polygon',*chart.OPEN_SHAPES) else '点击起点和终点'
            else:hint='点击放置，可吸附跑道中点' if kind=='ARP' else '点击放置' if kind else '选择航图对象'
            self.app.status.set(hint)
            self.app.canvas.focus_set()

    def pointer(self,event):
        self.hover=(event.x,event.y)
        self.draw_preview()
        return 'break'

    def snap(self,x,y):
        point=self.app.world(x,y)
        if self.tool!='ARP':return point,None
        options=[]
        for aid,asset in self.scene.assets.items():
            if asset['kind']!='RUNWAY' or not self.app.can_edit_object(aid):continue
            midpoint=g.at(asset['points'],g.length(asset['points'])/2)[0]
            options.append((math.dist((x,y),self.app.screen(midpoint)),aid,midpoint))
        if options:
            distance,aid,midpoint=min(options)
            if distance<=18:return midpoint,aid
        return point,None

    def rvr_screen_direction(self,point,direction):
        if direction is None:return
        x,y=self.app.screen(point)
        a,b=self.app.screen([p+100*d for p,d in zip(point,direction)])
        length=math.hypot(a-x,b-y)
        if length:return (a-x)/length,(b-y)/length

    def rvr_candidate(self,point):
        if self.rvr_draft is None:
            return chart.snap_rvr(self.scene,point,18/max(.001,self.app.zoom),self.app.can_edit_object)
        return chart.rvr_placement(self.scene,self.rvr_draft,point,face='rvr_gap' in self.rvr_draft)

    def place_rvr_step(self,point):
        candidate=self.rvr_candidate(point)
        if not candidate:return 'break'
        if self.rvr_draft is None:
            self.rvr_draft=candidate
            self.app.status.set(tr('RVR：横向移动选择跑道侧和距离，然后点击确认。'))
        elif 'rvr_gap' not in self.rvr_draft:
            self.rvr_draft=candidate
            self.app.status.set(tr('RVR：朝跑道任一端移动选择扇形朝向，然后点击完成。'))
        else:
            anchor,_=chart.rvr_pose(self.scene,dict(candidate,point=point))
            self.place_symbol('RVR',anchor,**candidate)
        self.draw_preview()
        return 'break'

    def draw_preview(self):
        c=self.app.canvas
        tag='chart_f8_preview'
        c.delete(tag)
        if not self.tool or self.hover is None:return
        point,runway=self.snap(*self.hover)
        direction=None
        if self.tool=='RVR':
            binding=self.rvr_candidate(point)
            if not binding:return
            asset=self.scene.assets[binding['runway']]
            center,_=g.at(asset['points'],g.length(asset['points'])*binding['rvr_station'])
            cx,cy=self.app.screen(center)
            c.create_oval(cx-4,cy-4,cx+4,cy+4,outline='#086e86',width=2,tags=tag)
            if self.rvr_draft is None:return
            point,u=chart.rvr_pose(self.scene,dict(binding,point=point))
            direction=self.rvr_screen_direction(point,u)
            px,py=self.app.screen(point)
            c.create_line(cx,cy,px,py,fill='#086e86',dash=(4,3),tags=tag)
            c.create_text((cx+px)/2,(cy+py)/2-9,text=f'{binding["rvr_gap"]:.1f} m',
                          fill='#086e86',tags=tag)
        x,y=self.app.screen(point)
        ink='#086e86'
        if self.tool in chart.ANNOTATIONS or self.tool=='HS':
            c.create_line(x-8,y,x+8,y,fill=ink,width=1,tags=tag)
            c.create_line(x,y-8,x,y+8,fill=ink,width=1,tags=tag)
            if self.tool=='RUNWAY_GUARD':
                geometry=chart.snap_guard(self.scene,point,self.app.can_edit_object)
                if geometry:
                    for path in chart.guard_paths(*geometry):
                        c.create_line(*[v for p in path for v in self.app.screen(p)],fill=ink,width=2,tags=tag)
            if not self.draft:return
            mode=self.shape.currentData()
            vertices=[*self.draft,point]
            path=chart.hotspot_path(mode,vertices)
            if len(path)>1:c.create_line(*[v for p in path for v in self.app.screen(p)],fill='#e6780a',width=2,dash=(5,3),tags=tag)
            for px,py in map(self.app.screen,self.draft):
                c.create_oval(px-3,py-3,px+3,py+3,outline='#e6780a',fill='white',width=2,tags=tag)
        else:
            asset=chart.arp_runway(self.scene,point,runway) if self.tool=='ARP' else None
            if self.tool=='ARP':
                ink=chart.colors(self.config(),'ARP')[0] if asset else '#000000'
            symbol={'chart_symbol_max':chart.arp_diameter(asset,point)} if asset else {}
            factor=chart.symbol_scale(symbol,self.app.zoom)
            for typ,pts in chart.symbol_parts(self.tool) if factor>0 else ():
                coords=[v for dx,dy in (chart.rvr_screen_offset(*q,direction) for q in pts)
                        for v in (x+dx*factor,y+dy*factor)]
                if typ=='polygon':c.create_polygon(*coords,outline=ink,fill='',width=2,tags=tag)
                else:c.create_line(*coords,fill=ink,width=2,tags=tag)
        if runway:
            c.create_oval(x-14,y-14,x+14,y+14,outline='#087f60',width=2,dash=(4,2),tags=tag)
            c.create_text(x+18,y-12,text=tr('吸附 · 跑道中点'),anchor='sw',fill='#087f60',
                          font=('Microsoft YaHei UI',10,'bold'),tags=tag)

    def finish(self):
        if self.tool not in chart.AREA_TOOLS:return 'break'
        from shapely.geometry import LineString,Polygon
        mode=self.shape.currentData()
        if len(self.draft)<(3 if mode.endswith('polygon') else 2):return 'break'
        path=chart.hotspot_path(mode,self.draft)
        shape=LineString(path) if mode in chart.OPEN_SHAPES else Polygon(path)
        if not shape.is_valid or not shape.is_simple or shape.length<.01 or (mode not in chart.OPEN_SHAPES and shape.area<.01):
            self.app.status.set(tr('请绘制有效且不自交的边界。'))
            if mode not in ('polygon','rounded_polygon',*chart.OPEN_SHAPES):self.draft=self.draft[:1]
            return 'break'
        center=shape.centroid
        self.place_symbol(self.tool,[center.x,center.y],shape=mode,vertices=self.draft.copy())
        return 'break'

    def place_symbol(self,kind,point,**extra):
        symbols=self.config().get('symbols',{})
        number=next(n for n in range(1,len(symbols)+2)
                    if all(item.get('label')!=f'HS{n}' for item in symbols.values()))
        oid='chart:'+uuid4().hex[:12]
        caption=f'HS{number}' if kind=='HS' else 'TWR' if kind=='TOWER' else kind
        caption={'HELIPAD':'H','ANEMOMETER':'ANEM'}.get(kind,caption)
        if kind=='RVR':
            taken={item.get('label') for item in symbols.values() if item['kind']=='RVR'}
            caption=next((letter for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if letter not in taken),'A')
        value=dict(kind=kind,point=list(point),label=caption,**extra)
        self.selected=oid
        self.choose(None,focus=False)
        self.change('symbols',oid,value)
        self.properties()

    def auto_locate_arp(self):
        point=chart.runway_end_center(self.scene)
        if point is None:
            self.app.status.set('请先绘制跑道')
            return
        symbols=self.config().get('symbols',{})
        current=symbols.get(self.selected,{})
        oid=self.selected if current.get('kind')=='ARP' else next(
            (key for key,item in symbols.items() if item['kind']=='ARP'),None)
        if oid is None:
            self.place_symbol('ARP',point,auto_runway_center=True)
        else:
            value=dict(symbols[oid],point=point,auto_runway_center=True)
            value.pop('runway',None)
            self.selected=oid
            self.choose(None,focus=False)
            self.change('symbols',oid,value)
            self.properties()
        self.app.status.set('ARP 已定位于所有跑道端点的几何中心')

    def config(self):
        return chart.settings(self.scene)

    def change(self,section,key,value):
        with self.scene.transaction('编辑航图'):
            data=self.scene.data['meta'].setdefault('chart_f8',{}).setdefault(section,{})
            if value is None:data.pop(key,None)
            else:data[key]=value
        self.app.update_title()
        self.app.redraw()

    def ensure(self):
        key=(self.scene,self.scene.data,self.scene.revision,id(self.app.render_items))
        if self.key and self.key[0] is key[0] and self.key[1] is key[1] and self.key[2:]==key[2:]:
            return
        from shapely.strtree import STRtree
        from shapely.geometry import LineString
        from geometry11 import polygon
        self.key=key
        self.items,self.kinds=chart.chart_items(self.scene,self.app.render_items)
        self.visible_owners={item['oid'] for item in self.items}
        self.shapes=[item for item in self.items if item['type']!='text']
        self.kinds_by_owner={item['oid']:item['chart_kind'] for item in self.items if 'chart_kind' in item}
        shapes=[]
        owners=[]
        for item in self.shapes:
            pts=item['points']
            shape=polygon(pts) if item['type']=='polygon' and len(pts)>=3 else LineString(pts) if len(pts)>=2 else None
            if shape is not None and not shape.is_empty:
                shapes.append(shape)
                owners.append(item['oid'])
        self.hit_tree=STRtree(shapes)
        self.hit_owners=owners

    def redraw(self,editing=False):
        if self.selection_scene is not self.scene:
            self.selection_scene=self.scene
            self.selected=None
            self.choose(None,focus=False)
            self.properties()
        self.ensure()
        app=self.app
        c=app.canvas
        self.renderer.render(self.shapes,app.origin,app.zoom)
        c.itemconfigure('map',state='hidden')
        for bitmap,_ in app.__dict__.get('_bitmap_items',{}).values():
            if bitmap.isVisible():bitmap.hide()
        c.itemconfigure('chart_f8_surface',state='normal')
        c.q.setBackgroundBrush(G.QColor('#ffffff'))
        c.delete('chart_f8_labels')
        c.delete('chart_f8_badge')
        self.labels=[]
        self.elevation_labels={}
        for item in self.items:
            if item['type']!='text':continue
            x,y=app.screen(item['points'][0])
            direction=self.rvr_screen_direction(item['points'][0],item.get('rvr_direction'))
            dx,dy=chart.rvr_screen_offset(*item.get('chart_offset',(0,0)),direction)
            angle=0
            if 'axis_angle' in item:
                rotation=getattr(c,'rotation21_2',0.)
                theta=item['axis_angle']-rotation
                angle=(math.degrees(theta)+item.get('angle_delta',0)+90)%180-90
                nx,ny=item['normal']
                offset=item.get('chart_normal_px',12)
                dx=offset*(nx*math.cos(rotation)+ny*math.sin(rotation))
                dy=offset*(nx*math.sin(rotation)-ny*math.cos(rotation))
            if not (-40<=x<=c.winfo_width()+40 and -40<=y<=c.winfo_height()+40):continue
            oid=item['oid']
            if 'chart_symbol' in item:
                factor=chart.symbol_scale(item,app.zoom)
                for typ,pts in chart.symbol_parts(item['chart_symbol'],item.get('symbol_variant')) if factor>0 else ():
                    coords=[v for px,py in (chart.rvr_screen_offset(*q,direction) for q in pts)
                            for v in (x+px*factor,y+py*factor)]
                    if typ=='polygon':
                        tag=c.create_polygon(*coords,outline=item['fill'],fill=item['symbol_fill'],width=1,tags='chart_f8_labels')
                    else:
                        tag=c.create_line(*coords,fill=item['fill'],width=1,tags='chart_f8_labels')
                    self.labels.append((tag,oid))
                continue
            font=('Microsoft YaHei UI',item.get('chart_px',10))
            size={}
            if 'chart_world_size' in item:
                font=('Microsoft YaHei UI',100)
                size['text_height_px']=item['chart_world_size']*app.zoom
            tag=c.create_text(x+dx,y+dy,text=item['text'],fill=item['fill'],font=font,angle=angle,
                              tags='chart_f8_labels',**size)
            self.labels.append((tag,oid))
            if 'elevation_end' in item:self.elevation_labels[tag]=(oid,item['elevation_end'])
            if 'chart_box' in item:
                left,top,right,bottom=c.bbox(tag)
                hw,hh=(right-left)/2+3,(bottom-top)/2+2
                zoom=max(.001,app.zoom)
                center,source=chart.hotspot_label_pose(item,hw/zoom,hh/zoom,9/zoom)
                px,py=app.screen(center)
                c.coords(tag,px,py)
                left,top,right,bottom=c.bbox(tag)
                target=app.screen(source)
                end=chart.box_edge((px,py),target,hw,hh)
                leader=c.create_line(*target,*end,fill=item['chart_box'],width=1,tags='chart_f8_labels')
                self.labels.append((leader,oid))
                frame=c.create_rectangle(left-3,top-2,right+3,bottom+2,outline=item['chart_box'],width=1,
                                         tags='chart_f8_labels')
                self.labels.append((frame,oid))
        c.create_text(c.winfo_width()-16,16,text=tr('航图模式 · F8'),anchor='ne',fill='#262626',
                      font=('Microsoft YaHei UI',11,'bold'),tags='chart_f8_badge')
        if not editing:self.selection_frame()
        self.draw_preview()

    def selection_frame(self):
        c=self.app.canvas
        c.delete('chart_f8_selected_vertex')
        c.delete('frame11')
        if not self.selected:
            self.app._frame_box11=None
            self.app._handles14=[]
            return
        ids=[tag for tag,oid in self.labels if oid==self.selected]
        ids.extend(c.find_withtag('owner:'+self.selected))
        box=c.bbox(*ids,visible_only=True) if ids else None
        if box:self.app.draw_frame11(screen_box=box)
        target=getattr(self,'selected_vertex',None)
        if self.app.mode=='NODES':
            symbol=self.config().get('symbols',{}).get(self.selected)
            if symbol:
                vertices=symbol.get('vertices') or [chart.symbol_point(self.scene,symbol)]
                for index,point in enumerate(vertices):
                    x,y=self.app.screen(point)
                    fill='#ff9300' if target==(self.selected,index) else '#ffffff'
                    c.create_oval(x-5,y-5,x+5,y+5,fill=fill,outline='#087f60',
                                  width=2,tags='chart_f8_selected_vertex')

    def edge_node_target(self,x,y):
        from node_interaction20_8 import edge_insertion
        if self.tool or self.app.mode!='NODES':return
        point=self.app.world(x,y)
        oid=self.selected or self.pick(point,x,y)
        item=self.config().get('symbols',{}).get(oid,{})
        shape=item.get('shape')
        if shape in ('polygon','rounded_polygon',*chart.OPEN_SHAPES):
            vertices=list(item['vertices'])
            hit=edge_insertion(vertices,point,10/max(.001,self.app.zoom),shape not in chart.OPEN_SHAPES)
            if hit:return hit[1],oid,item,vertices,hit[0]

    def click(self,event):
        x,y=event.x,event.y
        point=self.app.world(x,y)
        if not self.tool and self.app.mode=='NODES' and getattr(event,'state',0)&8:
            hit=self.edge_node_target(x,y)
            if hit:
                q,oid,item,vertices,index=hit
                vertices.insert(index,q)
                self.selected=oid
                self.change('symbols',oid,dict(item,vertices=vertices))
                self.properties()
            return 'break'
        if self.tool:
            point,runway=self.snap(x,y)
            if self.tool in chart.AREA_TOOLS:
                if not self.draft or math.dist(point,self.draft[-1])>.01:self.draft.append(list(point))
                if self.shape.currentData() not in ('polygon','rounded_polygon',*chart.OPEN_SHAPES) and len(self.draft)>=2:return self.finish()
                self.draw_preview()
                return 'break'
            if self.tool=='RUNWAY_GUARD':
                geometry=chart.snap_guard(self.scene,point,self.app.can_edit_object)
                if geometry is None:
                    self.app.status.set(tr('请点击滑行道放置跑道警戒灯。'))
                    return 'break'
                center,transverse,width=geometry
                self.place_symbol(self.tool,center,transverse=transverse,width=width)
                return 'break'
            attachment={'runway':runway} if runway else {}
            if self.tool=='RVR':return self.place_rvr_step(point)
            self.place_symbol(self.tool,point,**attachment)
            return 'break'
        self.selected_vertex=None
        selected=self.config().get('symbols',{}).get(self.selected,{})
        if self.app.mode=='NODES' and selected.get('vertices'):
            candidates=[(math.dist((x,y),self.app.screen(vertex)),i)
                        for i,vertex in enumerate(selected['vertices'])]
            if candidates:
                distance,index=min(candidates)
                if distance<=9:
                    self.selected_vertex=(self.selected,index)
                    self.vertex_drag=(self.scene,self.selected,index,(x,y))
                    self.selection_frame()
                    return 'break'
        elevation_end=None
        self.selected=self.pick(point,x,y)
        for tag,(oid,end) in reversed(list(self.elevation_labels.items())):
            bounds=self.app.canvas.bbox(tag)
            if bounds and bounds[0]<=x<=bounds[2] and bounds[1]<=y<=bounds[3]:
                self.selected=oid
                elevation_end=end
                break
        symbol=self.config().get('symbols',{}).get(self.selected)
        if symbol:
            # Use the displayed anchor, which may differ from the saved point
            # for navigation symbols with automatic placement.
            anchor=next((item['points'][0] for item in self.items
                         if item['oid']==self.selected and 'chart_symbol' in item),
                        chart.symbol_point(self.scene,symbol))
            self.symbol_drag=(self.scene,self.selected,(x,y),point,anchor)
        self.properties(elevation_end)
        self.selection_frame()
        return 'break'

    def cancel_symbol_drag(self):
        self.symbol_drag=self.vertex_drag=None
        self.app.canvas.delete('chart_f8_drag')

    def drag_symbol(self,event):
        if self.vertex_drag:
            canvas=self.app.canvas
            canvas.delete('chart_f8_drag')
            x,y=event.x,event.y
            canvas.create_oval(x-6,y-6,x+6,y+6,outline='#087f60',width=2,tags='chart_f8_drag')
            return 'break'
        drag=self.symbol_drag
        if drag and math.dist(drag[2],(event.x,event.y))>=4:
            mouse=self.app.world(event.x,event.y)
            point=[anchor+end-start for anchor,end,start in zip(drag[4],mouse,drag[3])]
            canvas=self.app.canvas
            canvas.delete('chart_f8_drag')
            symbol=self.config().get('symbols',{}).get(drag[1],{})
            if symbol.get('kind')=='RVR':
                binding=chart.snap_rvr(self.scene,point,max(symbol.get('rvr_gap',12),18/max(.001,self.app.zoom)),self.app.can_edit_object)
                if not binding:return 'break'
                point,_=chart.rvr_pose(self.scene,{**symbol,**binding,'point':point})
            x,y=self.app.screen(point)
            canvas.create_oval(x-8,y-8,x+8,y+8,outline='#087f60',width=2,tags='chart_f8_drag')
        return 'break'

    def release_symbol(self,event):
        vertex=self.vertex_drag
        if vertex:
            self.cancel_symbol_drag()
            scene,oid,index,press=vertex
            symbol=self.config().get('symbols',{}).get(oid)
            if scene is self.scene and symbol and math.dist(press,(event.x,event.y))>=3:
                vertices=list(symbol['vertices'])
                vertices[index]=self.app.world(event.x,event.y)
                if symbol['shape'] not in chart.OPEN_SHAPES:
                    try:__import__('polygon_edit20_7').checked(vertices)
                    except ValueError as exc:
                        self.app.status.set(str(exc))
                        return 'break'
                self.change('symbols',oid,dict(symbol,vertices=vertices))
            return 'break'
        drag=self.symbol_drag
        self.cancel_symbol_drag()
        if not drag:return 'break'
        scene,oid,press,start,anchor=drag
        symbol=self.config().get('symbols',{}).get(oid)
        if scene is not self.scene or symbol is None or math.dist(press,(event.x,event.y))<4:
            return 'break'
        mouse=self.app.world(event.x,event.y)
        delta=[end-begin for end,begin in zip(mouse,start)]
        value=dict(symbol,point=[p+d for p,d in zip(anchor,delta)])
        if symbol['kind']=='RUNWAY_GUARD':
            snapped=chart.snap_guard(self.scene,value['point'],self.app.can_edit_object)
            if snapped is None:
                self.app.status.set(tr('请点击滑行道放置跑道警戒灯。'))
                return 'break'
            value['point'],value['transverse'],value['width']=snapped
        if symbol['kind']=='RVR':
            binding=chart.snap_rvr(self.scene,value['point'],max(symbol.get('rvr_gap',12),18/max(.001,self.app.zoom)),self.app.can_edit_object)
            if not binding:return 'break'
            value.update(binding)
            value['point'],_=chart.rvr_pose(self.scene,value)
        if symbol['kind'] in chart.NAV_SYMBOLS:value['manual_position']=True
        if symbol['kind']=='ARP':
            value.pop('runway',None)
            value.pop('auto_runway_center',None)
        if symbol.get('vertices'):
            value['vertices']=[[p+d for p,d in zip(vertex,delta)] for vertex in symbol['vertices']]
        self.change('symbols',oid,value)
        return 'break'

    def pick(self,point,x,y):
        from shapely.geometry import Point
        symbols=self.config().get('symbols',{})
        ordinary_label=None
        for tag,oid in reversed(self.labels):
            if self.app.canvas.type(tag)=='line' and oid in symbols and symbols[oid]['kind']=='HS':continue
            box=self.app.canvas.bbox(tag)
            if box and box[0]-2<=x<=box[2]+2 and box[1]-2<=y<=box[3]+2:
                if oid in symbols:return oid
                if ordinary_label is None:ordinary_label=oid
        target=Point(point)
        tolerance=5/max(.001,self.app.zoom)
        hits=[]
        for i in self.hit_tree.query(target.buffer(tolerance)):
            shape=self.hit_tree.geometries[i]
            distance=shape.distance(target)
            if distance<=tolerance:hits.append((distance,shape.area,self.hit_owners[i]))
        symbol_hits=[(distance,oid) for distance,_,oid in hits if oid in symbols or oid.startswith('chart:guard:')]
        if symbol_hits:return min(symbol_hits)[1]
        if ordinary_label is not None:return ordinary_label
        return min(hits,key=lambda row:(row[0]>0,row[1],row[0]))[2] if hits else None

    def delete_selected(self):
        oid=self.selected
        if not oid:return 'break'
        self.cancel_symbol_drag()
        target=getattr(self,'selected_vertex',None)
        if target and target[0]==oid:
            symbol=self.config().get('symbols',{}).get(oid,{})
            vertices=list(symbol.get('vertices',()))
            closed=symbol.get('shape') not in chart.OPEN_SHAPES
            if len(vertices)<=(3 if closed else 2):
                self.app.status.set(tr('已达到此对象的最少节点数。'))
                return 'break'
            vertices.pop(target[1])
            if closed:
                try:__import__('polygon_edit20_7').checked(vertices)
                except ValueError as exc:
                    self.app.status.set(str(exc))
                    return 'break'
            self.selected_vertex=None
            self.change('symbols',oid,dict(symbol,vertices=vertices))
            return 'break'
        self.selected=None
        if oid in self.config().get('symbols',{}):
            self.change('symbols',oid,None)
        elif oid.startswith('chart:guard:'):
            hidden=self.config().get('annotations',{}).get('hidden_guards',[])
            self.change('annotations','hidden_guards',[*hidden,oid])
        self.properties()
        return 'break'

    def color_button(self,kind,key,oid=None):
        button=W.QPushButton()
        index=0 if key=='stroke' else 1
        def refresh():
            color=chart.colors(self.config(),kind,oid)[index]
            swatch=G.QPixmap(20,14)
            swatch.fill(G.QColor(color))
            button.setIcon(G.QIcon(swatch))
            button.setText(color.upper())
        def choose():
            color=W.QColorDialog.getColor(G.QColor(chart.colors(self.config(),kind,oid)[index]),button)
            if color.isValid():
                section='objects' if oid else 'palette'
                name=oid or kind
                values=dict(self.config().get(section,{}).get(name,{}))
                values[key]=color.name()
                self.change(section,name,values)
                refresh()
        button.clicked.connect(choose)
        refresh()
        return button

    def properties(self,elevation_end=None):
        from model20 import axis
        holder=W.QWidget()
        form=W.QFormLayout(holder)
        oid=self.selected
        config=self.config()
        symbol=config.get('symbols',{}).get(oid)
        asset=self.scene.assets.get(oid) or (axis(self.scene,oid) if oid else None)
        kind=symbol['kind'] if symbol else self.kinds_by_owner.get(oid) or (chart.category(asset) if asset else 'STOPWAY' if oid and ':stopway:' in oid else None)
        if asset and asset['kind']=='RUNWAY':kind='RUNWAY'
        focus=None
        if self.tool in chart.AREA_TOOLS:
            self.shape.setParent(None)
            form.addRow('热点工具 / 形状',self.shape)
        elif self.tool=='ARP':
            auto_arp=W.QPushButton('自动定位 ARP')
            auto_arp.setIcon(chart_icon('ARP'))
            auto_arp.clicked.connect(self.auto_locate_arp)
            form.addRow('机场基准点 / 定位',auto_arp)
        elif kind in chart.TYPES:
            form.addRow(W.QLabel(asset['name'] if asset else chart.TYPES[kind][0]))
            form.addRow('线条颜色',self.color_button(kind,'stroke',oid))
            if chart.TYPES[kind][2] is not None and kind!='HS':form.addRow('道面颜色',self.color_button(kind,'fill',oid))
            reset=W.QPushButton('恢复类型配色')
            def reset_color():
                self.change('objects',oid,None)
                self.properties()
            reset.clicked.connect(reset_color)
            form.addRow(reset)
            if kind=='RUNWAY':
                for end in ('a','b'):
                    field='elevation_'+end
                    value=asset['props'].get(field)
                    control=W.QLineEdit('' if value is None else str(value))
                    control.setPlaceholderText(tr('机场海拔 (m)'))
                    control.editingFinished.connect(lambda field=field,control=control:
                                                    self.save_elevation(oid,field,control))
                    form.addRow(tr('跑道端海拔 (m，可空)')+' '+end.upper(),control)
                    if end==elevation_end:focus=control
                unit=W.QComboBox()
                unit.addItems(chart.UNITS)
                unit.setCurrentText(config.get('units',{}).get(oid,'m'))
                unit.currentTextChanged.connect(lambda value:self.change('units',oid,value))
                form.addRow('跑道尺寸单位',unit)
                material=W.QComboBox()
                for code,caption in chart.SURFACES.items():
                    material.addItem(f'{code} · {tr(caption)}' if code else tr(caption),code)
                material.setCurrentIndex(max(0,material.findData(config.get('surfaces',{}).get(oid,''))))
                material.currentIndexChanged.connect(lambda _:self.change('surfaces',oid,material.currentData()))
                form.addRow('跑道道面材质',material)
            if symbol:
                if kind=='TOWER':
                    variant=W.QComboBox()
                    for code,caption in [('star','五角星'),('tower','塔状符号')]:
                        variant.addItem(tr(caption),code)
                    variant.setCurrentIndex(int(symbol.get('variant')=='tower'))
                    variant.currentIndexChanged.connect(lambda _:self.change(
                        'symbols',oid,dict(self.config()['symbols'][oid],variant=variant.currentData())))
                    form.addRow(tr('控制塔符号'),variant)
                name=W.QLineEdit(symbol['label'])
                name.setMaxLength(2 if kind=='RVR' else 12)
                name.editingFinished.connect(lambda:self.change('symbols',oid,dict(self.config()['symbols'][oid],label=name.text().strip() or ('A' if kind=='RVR' else kind))))
                if kind not in chart.ANNOTATIONS:form.addRow('标号',name)
                remove=W.QPushButton('删除标识')
                def delete():
                    self.selected=None
                    self.change('symbols',oid,None)
                    self.properties()
                remove.clicked.connect(delete)
                form.addRow(remove)
        else:
            form.addRow(W.QLabel('航图可见对象'))
            closure=W.QComboBox()
            for mode,caption in [('red','红色中线'),('cross','道面同色 ×')]:
                closure.addItem(tr(caption),mode)
            closure.setCurrentIndex(max(0,closure.findData(chart.closure_style(config))))
            closure.currentIndexChanged.connect(lambda _:self.change('closure','style',closure.currentData()))
            form.addRow(tr('关闭道面标注'),closure)
            auto_guard=W.QCheckBox(tr('自动生成跑道警戒灯'))
            auto_guard.setChecked(config.get('annotations',{}).get('auto_runway_guard',False))
            auto_guard.toggled.connect(lambda value:self.change('annotations','auto_runway_guard',value))
            form.addRow(auto_guard)
            runway_badges=W.QCheckBox(tr('合并跑道编号和航向'))
            runway_badges.setChecked(config.get('annotations',{}).get('runway_end_badge',False))
            runway_badges.toggled.connect(lambda enabled:self.change('annotations','runway_end_badge',enabled))
            form.addRow(runway_badges)
            present=chart.present_types(self.scene) | {'AIM','DISPLACED','ELEV','APPROACH_LIGHTS',*chart.ANNOTATIONS}
            for kind,(caption,_,_) in chart.TYPES.items():
                if kind not in present:continue
                box=W.QCheckBox(caption)
                box.setChecked(chart.is_visible(config,kind))
                box.toggled.connect(lambda enabled,kind=kind:self.change('visible',kind,enabled))
                form.addRow(box)
        if self.tool not in chart.AREA_TOOLS and self.shape.parentWidget() is not None:
            self.shape.setParent(None)
        self.right.setWidget(holder)
        if focus:
            focus.setFocus()
            focus.selectAll()
        if self.tool in chart.AREA_TOOLS:self.shape.show()

    def save_elevation(self,oid,field,control):
        runway=self.scene.assets.get(oid)
        if not runway:return
        previous=runway['props'].get(field)
        text=control.text().strip()
        try:
            value=float(text) if text else None
            if value is not None and not math.isfinite(value):raise ValueError
        except ValueError:
            control.setText('' if previous is None else str(previous))
            self.app.status.set(tr('请输入有效的海拔数值'))
            return
        if value!=previous:
            self.scene.update_asset(oid,props={field:value})
            self.app.redraw()

    def palette_dialog(self):
        dialog=W.QDialog(self.app.q)
        dialog.setWindowTitle('航图配色')
        outer=W.QVBoxLayout(dialog)
        area=W.QScrollArea()
        area.setWidgetResizable(True)
        content=W.QWidget()
        layout=W.QGridLayout(content)
        layout.addWidget(W.QLabel('对象类型'),0,0)
        layout.addWidget(W.QLabel('线条'),0,1)
        layout.addWidget(W.QLabel('道面'),0,2)
        for row,(kind,(caption,_,_)) in enumerate(chart.TYPES.items(),1):
            layout.addWidget(W.QLabel(caption),row,0)
            layout.addWidget(self.color_button(kind,'stroke'),row,1)
            if chart.TYPES[kind][2] is not None and kind!='HS':layout.addWidget(self.color_button(kind,'fill'),row,2)
        area.setWidget(content)
        outer.addWidget(area)
        close=W.QPushButton('完成')
        close.clicked.connect(dialog.accept)
        outer.addWidget(close)
        dialog.resize(500,640)
        dialog.exec()

    def layout_dialog(self):
        from chart_layout_f8 import LayoutDialog
        LayoutDialog(self).exec()


def chart_icon(kind):
    pix=G.QPixmap(24,24)
    pix.fill(C.Qt.GlobalColor.transparent)
    p=G.QPainter(pix)
    p.setRenderHint(G.QPainter.RenderHint.Antialiasing)
    p.setPen(G.QPen(G.QColor('#08758f'),1.7))
    if kind=='RUNWAY_GUARD':
        p.drawRect(2,9,5,5)
        p.drawRect(17,9,5,5)
        p.drawLine(7,11,17,11)
    elif kind in chart.BOUNDARIES:
        for path in chart.boundary_motifs([(1,12),(23,12)],.65):
            p.drawPolyline(G.QPolygonF([C.QPointF(*q) for q in path]))
    elif kind in chart.ANNOTATIONS:
        if kind in ('CONSTRUCTION','ILS_SENSITIVE'):
            pen=p.pen()
            pen.setStyle(C.Qt.PenStyle.DotLine if kind=='ILS_SENSITIVE' else C.Qt.PenStyle.DashLine)
            p.setPen(pen)
        p.drawPolygon(G.QPolygonF([C.QPointF(4,18),C.QPointF(8,5),C.QPointF(19,7),C.QPointF(20,17)]))
    elif kind in chart.SYMBOLS:
        if kind=='HS':p.setPen(G.QPen(G.QColor('#e6780a'),1.7))
        for typ,points in chart.symbol_parts(kind):
            path=G.QPolygonF([C.QPointF(x+12,y+12) for x,y in points])
            if typ=='polygon':p.drawPolygon(path)
            else:p.drawPolyline(path)
    elif kind=='palette':
        for i,color in enumerate(('#4d4d4d','#cccccc','#e6780a')):
            p.fillRect(3+i*6,4,5,16,G.QColor(color))
    elif kind=='layout':
        p.drawRect(5,3,14,18)
        p.drawRect(8,8,8,9)
        p.drawLine(8,6,16,6)
    else:
        rect=C.QRectF(4,5,16,14)
        if kind=='circle':p.drawEllipse(rect)
        elif kind=='rectangle':p.drawRect(rect)
        elif kind=='rounded_rectangle':p.drawRoundedRect(rect,4,4)
        elif kind=='rounded_polygon':
            p.drawPolygon(G.QPolygonF([C.QPointF(*q) for q in chart.hotspot_path(kind,[(4,18),(8,5),(19,7),(20,17)])]))
        else:p.drawPolygon(G.QPolygonF([C.QPointF(4,18),C.QPointF(8,5),C.QPointF(19,7),C.QPointF(20,17)]))
    p.end()
    return G.QIcon(pix)
