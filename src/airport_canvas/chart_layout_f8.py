"""Interactive F8 page preview, navigation and print layout."""
import chart_f8 as chart
from interface_language import tr
from qt_core21 import C, G, W
from map_painter import draw_items, text_sprite


class Preview(W.QWidget):
    def __init__(self, callback=None, move=None, camera_changed=None, jump=None):
        super().__init__()
        self.callback=callback
        self.move=move
        self.camera_changed=camera_changed
        self.jump=jump
        self.setMinimumSize(200,170)
        self.setFocusPolicy(C.Qt.FocusPolicy.StrongFocus)
        self.image=G.QImage()
        self.selection=None
        self.start=None
        self.pan=None
        self.element=None
        self.zoom=1.
        self.offset=C.QPointF()
        self.space=False
        self.groups={}
        self.ratio=None

    def load(self,items,box,page=False):
        box=tuple(box)
        previous=getattr(self,'box',None)
        if previous is None or any(abs((box[i+2]-box[i])-(previous[i+2]-previous[i]))>1e-6 for i in (0,1)):
            self.zoom=1.
            self.offset=C.QPointF()
        self.box=box
        x0,y0,x1,y1=box
        scale=min(1800/(x1-x0),1900/(y1-y0))
        size=(max(1,round((x1-x0)*scale)),max(1,round((y1-y0)*scale)))
        rows=list(chart.pixel_items(items,scale,size[0]/1000 if page else .72))
        raster=draw_items(rows,size,[-x0*scale,y1*scale],scale,'#ffffff')
        self.image=G.QImage(raster.tobytes(),*size,size[0]*3,G.QImage.Format.Format_RGB888).copy()
        raster.close()
        groups={}
        if self.move:
            for row in rows:
                oid=row['oid']
                if not oid.startswith('F8_PAGE:') or oid[8:] not in chart.PAGE_MOVABLE:continue
                points=row['points']
                if row['type']=='text':
                    x,y=points[0]
                    sprite=text_sprite(row['text'],row['fill'],max(1,round(row['size']*scale)),row.get('rotation',0))
                    w,h=sprite.width/scale/2,sprite.height/scale/2
                    points=[(x-w,y-h),(x+w,y+h)]
                groups.setdefault(oid[8:],[]).extend(points)
        self.groups={key:chart.chart_extent([{'points':points}]) for key,points in groups.items()}
        self.changed()

    def changed(self):
        self.update()
        if self.camera_changed:self.camera_changed()

    def reset_camera(self):
        self.zoom=1.
        self.offset=C.QPointF()
        self.changed()

    def center_on(self,point):
        self.offset+=C.QRectF(self.rect()).center()-self.pixel(point)
        self.changed()

    def target(self):
        r=C.QRectF(self.rect()).adjusted(8,8,-8,-8)
        scale=self.zoom*min(r.width()/max(1,self.image.width()),r.height()/max(1,self.image.height()))
        width=self.image.width()*scale
        height=self.image.height()*scale
        return C.QRectF(r.center().x()+self.offset.x()-width/2,r.center().y()+self.offset.y()-height/2,width,height)

    def pixel(self,p):
        r=self.target()
        x0,y0,x1,y1=self.box
        return C.QPointF(r.left()+r.width()*(p[0]-x0)/(x1-x0),r.bottom()-r.height()*(p[1]-y0)/(y1-y0))

    def world(self,p,clamp=False):
        r=self.target()
        x0,y0,x1,y1=self.box
        u=(p.x()-r.left())/max(1,r.width())
        v=(r.bottom()-p.y())/max(1,r.height())
        if clamp:u,v=min(1,max(0,u)),min(1,max(0,v))
        return x0+(x1-x0)*u,y0+(y1-y0)*v

    def rect_for(self,box):
        x0,y0,x1,y1=box
        return C.QRectF(self.pixel((x0,y0)),self.pixel((x1,y1))).normalized()

    def paintEvent(self,event):
        painter=G.QPainter(self)
        painter.fillRect(self.rect(),G.QColor('#dfe5eb'))
        if self.image.isNull():return
        painter.setRenderHint(G.QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self.target(),self.image)
        painter.setPen(G.QPen(G.QColor('#08758f'),1.5))
        painter.setBrush(G.QColor(8,117,143,35))
        if self.selection:painter.drawRect(self.rect_for(self.selection))
        if self.element:
            name,start,pos=self.element
            rect=self.rect_for(self.groups[name]).adjusted(-3,-3,3,3)
            painter.drawRect(rect.translated(pos-start))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.camera_changed:self.camera_changed()

    def wheelEvent(self,event):
        if self.image.isNull() or self.jump:return
        pos=event.position()
        point=self.world(pos)
        self.zoom=max(.5,min(16.,self.zoom*1.2**(event.angleDelta().y()/120)))
        self.offset+=pos-self.pixel(point)
        self.changed()
        event.accept()

    def keyPressEvent(self,event):
        if event.key()==C.Qt.Key.Key_Space:self.space=True
        else:super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==C.Qt.Key.Key_Space:self.space=False
        else:super().keyReleaseEvent(event)

    def focusOutEvent(self,event):
        self.space=False
        super().focusOutEvent(event)

    def mousePressEvent(self,event):
        if self.image.isNull():return
        pos=event.position()
        button=event.button()
        left=C.Qt.MouseButton.LeftButton
        if button in (C.Qt.MouseButton.MiddleButton,C.Qt.MouseButton.RightButton) or (button==left and self.space):
            self.pan=pos
            self.setCursor(C.Qt.CursorShape.ClosedHandCursor)
        elif button==left and self.target().contains(pos):
            if self.jump:
                self.jump(self.world(pos,True))
            elif self.callback:
                self.start=pos
                self.saved_selection=self.selection
                self.reposition=bool(self.selection and self.rect_for(self.selection).contains(pos)
                                     and event.modifiers()&C.Qt.KeyboardModifier.ShiftModifier)
            elif self.move:
                hits=[(rect.width()*rect.height(),name) for name,box in self.groups.items()
                      if (rect:=self.rect_for(box).adjusted(-5,-5,5,5)).contains(pos)]
                if hits:self.element=(min(hits)[1],pos,pos)

    def region(self,pos):
        if self.reposition:
            a,b=self.world(self.start)
            c,d=self.world(pos)
            x,y,X,Y=self.saved_selection
            return x+c-a,y+d-b,X+c-a,Y+d-b
        x,y=self.world(self.start,True)
        a,b=self.world(pos,True)
        if self.ratio and abs(a-x)>0 and abs(b-y)>0:
            width=min(abs(a-x),abs(b-y)*self.ratio)
            a=x+width*(1 if a>x else -1)
            b=y+width/self.ratio*(1 if b>y else -1)
        return min(x,a),min(y,b),max(x,a),max(y,b)

    def mouseMoveEvent(self,event):
        pos=event.position()
        if self.pan is not None:
            self.offset+=pos-self.pan
            self.pan=pos
            self.changed()
        elif self.start is not None:
            self.selection=self.region(pos)
            self.update()
        elif self.element:
            self.element=(*self.element[:2],pos)
            self.update()

    def mouseReleaseEvent(self,event):
        if self.pan is not None:
            self.pan=None
            self.unsetCursor()
            return
        if self.start is not None:
            region=self.region(event.position())
            moved=(event.position()-self.start).manhattanLength()>5
            self.start=None
            if moved and region[2]>region[0] and region[3]>region[1]:
                self.callback(region)
            else:
                self.selection=self.saved_selection
                self.update()
        elif self.element:
            key,start,_=self.element
            self.element=None
            a,b=self.world(start)
            x,y=self.world(event.position())
            self.move(key,x-a,y-b)
            self.update()


class LayoutDialog(W.QDialog):
    def __init__(self,view):
        super().__init__(view.app.q)
        self.view=view
        self.setWindowTitle('航图排版 · F8')
        view.ensure()
        self.items,self.kinds=view.items,view.kinds
        self.full=chart.fit_extent(self.items)
        self.region=chart.saved_region(view.scene,self.items)
        self.base_region=self.region
        config=view.config().get('page',{})
        self.positions=dict(config.get('positions',{}))
        self.history=[]
        self.history_index=-1
        self.replaying=False
        layout=W.QVBoxLayout(self)
        splitter=W.QSplitter()
        layout.addWidget(splitter,1)

        page=W.QWidget()
        left=W.QVBoxLayout(page)
        left.addWidget(W.QLabel('排版页面 · 滚轮缩放，中键或右键平移，左键拖动版面元素'))
        self.preview=Preview(move=self.move_element,camera_changed=self.sync_overview)
        left.addWidget(self.preview,1)
        tools=W.QHBoxLayout()
        for caption,callback in [('页面适合窗口',self.preview.reset_camera),('重置版面元素位置',self.reset_elements)]:
            button=W.QPushButton(caption)
            button.clicked.connect(callback)
            tools.addWidget(button)
        tools.addStretch()
        self.overview=Preview(jump=self.preview.center_on)
        self.overview.setFixedSize(145,94)
        self.overview.setToolTip('页面浏览导航 · 点击定位')
        tools.addWidget(self.overview)
        left.addLayout(tools)
        splitter.addWidget(page)

        panel=W.QWidget()
        right=W.QVBoxLayout(panel)
        right.addWidget(W.QLabel('航图导航 · 左键框选，Shift 拖动裁切框'))
        self.navigation=Preview(self.set_region)
        self.navigation.load(self.items,self.full)
        self.navigation.setMinimumHeight(112)
        self.navigation.setMaximumHeight(174)
        right.addWidget(self.navigation)
        fit=W.QPushButton('适合窗口')
        fit.clicked.connect(self.fit_navigation)
        right.addWidget(fit)
        scroll=W.QScrollArea()
        self.parameter_scroll=scroll
        scroll.setWidgetResizable(True)
        form_widget=W.QWidget()
        form=W.QFormLayout(form_widget)
        self.controls={}
        self.selectors={}
        for key,caption,choices,default in (
            ('paper','纸张',[(x,x) if x!='auto' else ('原始比例','auto') for x in chart.PAPERS],'auto'),
            ('orientation','纸张方向',[('纵向','portrait'),('横向','landscape')],'portrait'),
            ('fit','画面适配',[('缩放以容纳选区','fit'),('按纸张比例裁切','crop')],'fit'),
            ('legend_direction','图例排列',[('横向按行','horizontal'),('纵向按列','vertical')],'horizontal'),
            ('scale_style','比例尺样式',[('线段','line'),('数字比例','numeric'),('黑白铁道线','rail')],'line'),
            ('scale_unit','比例尺单位',[(x,x) for x in chart.SCALE_UNITS],'m')):
            control=W.QComboBox()
            for title,value in choices:control.addItem(tr(title),value)
            control.setCurrentIndex(max(0,control.findData(config.get(key,default))))
            control.currentIndexChanged.connect(self.render_page)
            self.selectors[key]=control
            form.addRow(caption,control)
        self.legend_count=W.QSpinBox()
        self.legend_count.setRange(1,6)
        self.legend_count.setValue(int(config.get('legend_count',2)))
        self.legend_count.valueChanged.connect(self.render_page)
        form.addRow('行数或列数',self.legend_count)
        self.frequencies={}
        self.timer=C.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.render_page)
        for key,caption in chart.FIELDS:
            if key=='changes':
                changes=W.QComboBox()
                for label,value in [('无',''),('机位','Stands'),('滑行道','Taxiways'),
                                    ('机坪','Apron'),('建筑','Buildings'),('航图信息','Chart information')]:
                    changes.addItem(tr(label),value)
                changes.setCurrentIndex(max(0,changes.findData(config.get(key,''))))
                changes.currentIndexChanged.connect(self.render_page)
                self.changes=changes
                form.addRow(caption,changes)
                continue
            if key in ('atis','tower','ground','delivery'):
                edit=W.QPlainTextEdit(config.get(key,''))
                edit.setMaximumHeight(76)
                edit.setPlaceholderText('可输入多行频率和字母')
                edit.textChanged.connect(lambda:self.timer.start(240))
                form.addRow(caption,edit)
                self.frequencies[key]=edit
                continue
            edit=W.QLineEdit(config.get(key,''))
            edit.setMaxLength(4 if key=='ident' else 26 if key=='airport' else 24)
            if key=='ident':edit.setValidator(G.QRegularExpressionValidator(C.QRegularExpression('[A-Za-z]{0,4}'),edit))
            if key=='date':edit.setInputMask('0000-00-00; ')
            edit.editingFinished.connect(self.render_page)
            form.addRow(caption,edit)
            self.controls[key]=edit
        note=W.QPlainTextEdit(config.get('note',''))
        note.setMaximumHeight(78)
        note.setPlaceholderText('图框内注记，可输入多行')
        self.note=note
        form.addRow('Note（图框内）',note)
        author=W.QLineEdit(config.get('author',''))
        author.setMaxLength(80)
        author.editingFinished.connect(self.render_page)
        self.controls['author']=author
        form.addRow('署名／制图单位',author)
        self.options={}
        for key,caption in [('true_north','真北指针及标注'),('magnetic_north','磁北指针及标注'),('scale','比例尺'),('legend','图例')]:
            toggle=W.QCheckBox(caption)
            toggle.setChecked(config.get(key,True))
            toggle.toggled.connect(self.render_page)
            self.options[key]=toggle
            form.addRow(toggle)
        scroll.setWidget(form_widget)
        right.addWidget(scroll,1)
        splitter.addWidget(panel)
        splitter.setSizes([670,390])
        commit=W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Save|W.QDialogButtonBox.StandardButton.Cancel)
        commit.accepted.connect(self.save)
        commit.rejected.connect(self.reject)
        layout.addWidget(commit)
        note.textChanged.connect(lambda:self.timer.start(250))
        self.resize(1120,780)
        self.set_region(self.region)
        for widget in [self,*self.findChildren(W.QWidget)]:
            widget.installEventFilter(self)

    def page_config(self):
        values={key:edit.text().strip() for key,edit in self.controls.items()}
        values.update({key:edit.toPlainText().strip() for key,edit in self.frequencies.items()})
        values.update({key:control.currentData() for key,control in self.selectors.items()})
        values.update(legend_count=self.legend_count.value(),positions=self.positions.copy())
        values['changes']=self.changes.currentData()
        values['ident']=values['ident'].upper()
        if values['date']=='--':values['date']=''
        values['note']=self.note.toPlainText().strip()
        values.update({key:toggle.isChecked() for key,toggle in self.options.items()})
        return values

    def eventFilter(self,watched,event):
        kind=event.type()
        if kind in (C.QEvent.Type.ShortcutOverride,C.QEvent.Type.KeyPress):
            if event.modifiers()==C.Qt.KeyboardModifier.ControlModifier and event.key() in (C.Qt.Key.Key_Z,C.Qt.Key.Key_Y):
                event.accept()
                if kind==C.QEvent.Type.KeyPress:self.step_history(-1 if event.key()==C.Qt.Key.Key_Z else 1)
                return True
        if kind==C.QEvent.Type.Wheel and self.parameter_scroll.isAncestorOf(watched):
            bar=self.parameter_scroll.verticalScrollBar()
            pixels=event.pixelDelta().y()
            amount=pixels or round(event.angleDelta().y()/120*bar.singleStep()*3)
            bar.setValue(bar.value()-amount)
            event.accept()
            return True
        return super().eventFilter(watched,event)

    def remember(self,info):
        if self.replaying:return
        state=(self.base_region,info)
        if self.history_index>=0 and self.history[self.history_index]==state:return
        del self.history[self.history_index+1:]
        self.history.append(state)
        self.history_index=len(self.history)-1

    def step_history(self,step):
        self.timer.stop()
        info=self.page_config()
        self.remember(info)
        index=self.history_index+step
        if not 0<=index<len(self.history):return
        self.history_index=index
        self.base_region,info=self.history[index]
        self.replaying=True
        controls=[*self.controls.values(),*self.frequencies.values(),*self.selectors.values(),
                  *self.options.values(),self.note,self.changes,self.legend_count]
        blockers=[C.QSignalBlocker(widget) for widget in controls]
        try:
            self.positions=info['positions'].copy()
            for key,widget in self.controls.items():widget.setText(info[key])
            for key,widget in self.frequencies.items():widget.setPlainText(info[key])
            for key,widget in self.selectors.items():widget.setCurrentIndex(widget.findData(info[key]))
            for key,widget in self.options.items():widget.setChecked(info[key])
            self.note.setPlainText(info['note'])
            self.changes.setCurrentIndex(self.changes.findData(info['changes']))
            self.legend_count.setValue(info['legend_count'])
            self.render_page()
        finally:
            for blocker in blockers:blocker.unblock()
            self.replaying=False

    def set_region(self,region):
        self.base_region=tuple(region)
        self.render_page()

    def fit_navigation(self):
        self.navigation.reset_camera()
        self.set_region(self.full)

    def sync_overview(self):
        if not hasattr(self,'overview') or self.preview.image.isNull():return
        x0,y1=self.preview.world(C.QPointF(0,0),True)
        x1,y0=self.preview.world(C.QPointF(self.preview.width(),self.preview.height()),True)
        self.overview.selection=(x0,y0,x1,y1)
        self.overview.update()

    def move_element(self,key,dx,dy):
        x0,y0,x1,y1=self.preview.box
        a,b=self.positions.get(key,(0.,0.))
        left,bottom,right,top=self.preview.groups[key]
        dx=min(max(dx,x0-left),x1-right) if right-left<x1-x0 else 0.
        dy=min(max(dy,y0-bottom),y1-top) if top-bottom<y1-y0 else 0.
        self.positions[key]=[a+dx/(x1-x0),b+dy/(y1-y0)]
        self.render_page()

    def reset_elements(self):
        self.positions.clear()
        self.render_page()

    def render_page(self):
        info=self.page_config()
        self.remember(info)
        self.region=chart.adjust_region(self.base_region,info)
        self.navigation.ratio=chart.frame_aspect(info) if info['fit']=='crop' else None
        self.navigation.selection=self.region
        self.navigation.update()
        page=chart.page_box(self.region,info)
        items=chart.page_items(self.view.scene,self.items,self.kinds,self.region,page,info=info)
        self.preview.load(items,chart.center_page_vertically(page,items),page=True)
        self.overview.image=self.preview.image
        self.overview.box=self.preview.box
        self.sync_overview()

    def save(self):
        self.render_page()
        with self.view.scene.transaction('保存航图排版'):
            config=self.view.scene.data['meta'].setdefault('chart_f8',{})
            config.update(region=list(self.region),page=self.page_config())
        self.view.app.redraw()
        self.accept()
