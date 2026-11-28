"""Persistent reference images and the native Qt calibration tools."""
import base64
import math
from pathlib import Path
import uuid

from interface_language import tr

UNITS={'米 (m)':1.,'厘米 (cm)':.01,'毫米 (mm)':.001,'千米 (km)':1000.,
       '英尺 (ft)':.3048,'英寸 (in)':.0254}
MAX_PIXELS=100_000_000
MAX_ENCODED=96_000_000
PREVIEW_PIXELS=4_000_000


def preview_size(size):
    from PySide6.QtCore import QSize
    pixels=size.width()*size.height()
    if pixels<=PREVIEW_PIXELS:return size
    ratio=math.sqrt(PREVIEW_PIXELS/pixels)
    return QSize(max(1,int(size.width()*ratio)),max(1,int(size.height()*ratio)))


def read_image(reader):
    # Qt's default allocation cap can reject a valid large image after the header check.
    from PySide6.QtGui import QImageReader
    limit=QImageReader.allocationLimit()
    try:
        if 0<limit<768:QImageReader.setAllocationLimit(768)
        return reader.read()
    finally:
        if QImageReader.allocationLimit()!=limit:QImageReader.setAllocationLimit(limit)

def layers(scene):
    return scene.data.get('bitmap_layers',{})

def validate(data):
    records=data.get('bitmap_layers',{})
    if not isinstance(records,dict):raise ValueError('位图底图记录无效')
    total=0
    for row in records.values():
        if not isinstance(row,dict) or not isinstance(row.get('png'),str):
            raise ValueError('位图底图记录无效')
        total+=len(row['png'])
        if not isinstance(row.get('name'),str) or type(row.get('locked')) is not bool:
            raise ValueError('位图名称或锁定状态无效')
        for key in ('x','y','rotation','scale','opacity'):
            value=row.get(key)
            if type(value) not in (int,float) or not math.isfinite(value):
                raise ValueError('位图坐标、比例或透明度无效')
        w,h=row.get('width'),row.get('height')
        if type(w) is not int or type(h) is not int or min(w,h)<=0 or w*h>MAX_PIXELS:
            raise ValueError('位图尺寸无效')
        if not 0<=row['opacity']<=1 or row['scale']<=0 or not math.isfinite(max(w,h)*row['scale']):
            raise ValueError('位图比例或透明度超出范围')
    if total>MAX_ENCODED:raise ValueError('工程内嵌位图超过容量上限，请减少底图或缩小分辨率。')

def add(scene,name,image,scale,center,rotation=0.):
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
    if image.isNull() or image.width()*image.height()>MAX_PIXELS:
        raise ValueError('位图尺寸无效')
    remaining=MAX_ENCODED-sum(len(row['png']) for row in layers(scene).values())
    def encode(format,quality=-1):
        encoded=QByteArray()
        buffer=QBuffer(encoded)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer,format,quality):raise ValueError('无法编码位图')
        return encoded
    encoded=encode('PNG')
    if (len(encoded)+2)//3*4>remaining and not image.hasAlphaChannel():
        encoded=encode('JPEG',95)
    if (len(encoded)+2)//3*4>remaining:
        raise ValueError('工程内嵌位图已超过上限，请减少底图或缩小分辨率。')
    oid='bitmap-'+uuid.uuid4().hex
    row=dict(name=name,png=base64.b64encode(bytes(encoded)).decode('ascii'),
             width=image.width(),height=image.height(),scale=scale,
             x=center[0],y=center[1],rotation=rotation,opacity=1.,locked=False)
    with scene.transaction('导入位图底图'):
        scene.data.setdefault('bitmap_layers',{})[oid]=row
    return oid

def update(scene,oid,**changes):
    row=layers(scene)[oid]
    if row['locked'] and changes!={'locked':False}:return
    if all(row.get(key)==value for key,value in changes.items()):return
    with scene.transaction('修改位图底图'):row.update(changes)

def corners(row):
    angle=math.radians(row['rotation'])
    cos,sin=math.cos(angle),math.sin(angle)
    w,h=row['width']*row['scale']/2,row['height']*row['scale']/2
    return [(row['x']+x*cos-y*sin,row['y']+x*sin+y*cos)
            for x,y in ((-w,-h),(w,-h),(w,h),(-w,h))]

def contains(row,point):
    angle=math.radians(row['rotation'])
    x,y=point[0]-row['x'],point[1]-row['y']
    cos,sin=math.cos(angle),math.sin(angle)
    return (abs(x*cos+y*sin)<=row['width']*row['scale']/2 and
            abs(-x*sin+y*cos)<=row['height']*row['scale']/2)

def pixmap(row,preview=False):
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
    from PySide6.QtGui import QImageReader,QPixmap
    try:content=QByteArray(base64.b64decode(row['png'],validate=True))
    except ValueError:return QPixmap()
    buffer=QBuffer(content)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader=QImageReader(buffer)
    size=reader.size()
    if size.width()!=row['width'] or size.height()!=row['height']:return QPixmap()
    if preview:reader.setScaledSize(preview_size(size))
    return QPixmap.fromImage(read_image(reader))

def draw(editor):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTransform
    from PySide6.QtWidgets import QGraphicsPixmapItem
    cache=editor.__dict__.setdefault('_bitmap_items',{})
    records=layers(editor.scene)
    for oid in cache.keys()-records.keys():
        editor.canvas.scene.removeItem(cache.pop(oid)[0])
    order=editor.scene.data['meta'].get('draw_order',{}).get('bitmap',())
    ids=dict.fromkeys([*order,*records])
    for index,oid in enumerate(key for key in ids if key in records):
        row=records[oid]
        pixels=row['width']*row['height']
        use_preview=pixels>PREVIEW_PIXELS and editor.zoom*row['scale']<=math.sqrt(PREVIEW_PIXELS/pixels)
        signature=(row['png'],row['width'],row['height'],use_preview)
        if oid not in cache:
            item=QGraphicsPixmapItem()
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            editor.canvas.scene.addItem(item)
            cache[oid]=(item,None)
        item,previous=cache[oid]
        if previous!=signature:
            picture=pixmap(row,preview=use_preview)
            item.setPixmap(picture)
            item.setOffset(-picture.width()/2,-picture.height()/2)
            cache[oid]=(item,signature)
        picture=item.pixmap()
        sx=row['width']/max(1,picture.width())*row['scale']
        sy=row['height']/max(1,picture.height())*row['scale']
        item.setPos(row['x'],row['y'])
        item.setTransform(QTransform().rotate(row['rotation']).scale(sx,-sy))
        item.setOpacity(row['opacity'])
        item.setVisible(not editor.scene.data['meta'].get('object_display',{}).get(oid,{}).get('hidden'))
        item.setZValue(-9e8+index)

def settings(parent,image,existing=None,rotation=0.,original_size=None,true_north=0.):
    from PySide6 import QtGui,QtCore,QtWidgets as W
    Qt=QtCore.Qt
    if image.isNull():return None
    original_size=original_size or image.size()
    scale_x=original_size.width()/image.width()
    scale_y=original_size.height()/image.height()

    class MeasureView(W.QGraphicsView):
        def __init__(self):
            super().__init__()
            self.setScene(W.QGraphicsScene(self))
            self.bitmap=self.scene().addPixmap(image)
            self.bitmap.setTransformOriginPoint(self.bitmap.boundingRect().center())
            self.bitmap.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            self.line=W.QGraphicsLineItem(self.bitmap)
            self.line.setPen(QtGui.QPen(QtGui.QColor('#00aeef'),2))
            pen=self.line.pen()
            pen.setCosmetic(True)
            self.line.setPen(pen)
            self.north_arrow=W.QGraphicsPathItem(self.bitmap)
            arrow_pen=QtGui.QPen(QtGui.QColor('#c6381f'),2)
            arrow_pen.setCosmetic(True)
            self.north_arrow.setPen(arrow_pen)
            self.north_points=()
            self.points=()
            self.setMouseTracking(True)
            self.enabled=False
            self.pan=None
            self.pan_button=None
            self.space_pan=False
            self.user_camera=False
            self.setTransformationAnchor(W.QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        def point(self,event):
            point=self.bitmap.mapFromScene(self.mapToScene(event.position().toPoint()))
            return QtCore.QPointF(min(max(0,point.x()),image.width()),
                                  min(max(0,point.y()),image.height()))

        def frame_bitmap(self):
            bounds=self.bitmap.sceneBoundingRect()
            self.setSceneRect(bounds)
            if not self.user_camera:self.fitInView(bounds,Qt.AspectRatioMode.KeepAspectRatio)

        def resizeEvent(self,event):
            super().resizeEvent(event)
            self.frame_bitmap()

        def show_measurement(self,preview=None):
            if len(self.points)==2:
                self.line.setLine(QtCore.QLineF(*self.points))
            elif self.points:
                self.line.setLine(QtCore.QLineF(self.points[0],preview or self.points[0]))
            self.line.setVisible(self.enabled and bool(self.points))

        def show_north(self,preview=None):
            path=QtGui.QPainterPath()
            if self.north_points:
                tail=self.north_points[0]
                tip=self.north_points[1] if len(self.north_points)==2 else preview or tail
                path.moveTo(tail)
                path.lineTo(tip)
                dx,dy=tip.x()-tail.x(),tip.y()-tail.y()
                length=math.hypot(dx,dy)
                if length:
                    size=min(length*.24,max(image.width(),image.height())*.035)
                    ux,uy=dx/length,dy/length
                    for side in (-1,1):
                        path.moveTo(tip)
                        path.lineTo(tip.x()-size*(ux+side*.52*uy),
                                    tip.y()-size*(uy-side*.52*ux))
            self.north_arrow.setPath(path)

        def wheelEvent(self,event):
            factor=1.15**(event.angleDelta().y()/120)
            current=self.transform().m11()
            if .001<=current*factor<=100:
                self.user_camera=True
                self.scale(factor,factor)
            event.accept()

        def keyPressEvent(self,event):
            if event.key()==Qt.Key.Key_Space:
                self.space_pan=True
                event.accept()
                return
            super().keyPressEvent(event)

        def keyReleaseEvent(self,event):
            if event.key()==Qt.Key.Key_Space:
                self.space_pan=False
                event.accept()
                return
            super().keyReleaseEvent(event)

        def mousePressEvent(self,event):
            if (event.button() in (Qt.MouseButton.MiddleButton,Qt.MouseButton.RightButton)
                    or self.space_pan and event.button()==Qt.MouseButton.LeftButton):
                self.pan_button=event.button()
                self.pan=event.position().toPoint()
                self.user_camera=True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
            if north.isChecked() and event.button()==Qt.MouseButton.LeftButton:
                self.setFocus()
                point=self.point(event)
                if len(self.north_points)==1:
                    tail=self.north_points[0]
                    if point==tail:return
                    bearing=math.degrees(math.atan2((point.x()-tail.x())*scale_x,
                                                     (tail.y()-point.y())*scale_y))
                    rotation=(bearing-true_north+180)%360-180
                    points=(tail,point)
                else:
                    rotation=angle.value()
                    points=(point,)
                history.push(CalibrationChange((self.north_points,angle.value()),
                                               (points,rotation),apply_north))
                event.accept()
                return
            if self.enabled and event.button()==Qt.MouseButton.LeftButton:
                self.setFocus()
                point=self.point(event)
                if len(self.points)==1:
                    if point==self.points[0]:return
                    points=(*self.points,point)
                else:
                    points=(point,)
                history.push(CalibrationChange(self.points,points,apply_points))
                event.accept()
            else:super().mousePressEvent(event)

        def mouseMoveEvent(self,event):
            if self.pan is not None:
                point=event.position().toPoint()
                delta=point-self.pan
                self.pan=point
                for bar,amount in ((self.horizontalScrollBar(),delta.x()),
                                   (self.verticalScrollBar(),delta.y())):
                    bar.setValue(bar.value()-amount)
                event.accept()
                return
            if north.isChecked() and len(self.north_points)==1:
                self.show_north(self.point(event))
                event.accept()
                return
            if self.enabled and not north.isChecked() and len(self.points)==1:
                self.show_measurement(self.point(event))
                event.accept()
            else:super().mouseMoveEvent(event)

        def mouseReleaseEvent(self,event):
            if self.pan is not None and event.button()==self.pan_button:
                self.pan=None
                self.unsetCursor()
                event.accept()
                return
            super().mouseReleaseEvent(event)

    class CalibrationChange(QtGui.QUndoCommand):
        def __init__(self,before,after,apply):
            super().__init__()
            self.before=before
            self.after=after
            self.apply=apply

        def undo(self):
            self.apply(self.before)

        def redo(self):
            self.apply(self.after)

    dialog=W.QDialog(parent)
    history=QtGui.QUndoStack(dialog)
    for key,action in (('Ctrl+Z',history.undo),('Ctrl+Y',history.redo)):
        shortcut=QtGui.QShortcut(QtGui.QKeySequence(key),dialog)
        shortcut.activated.connect(action)
    dialog.setWindowTitle('重设底图比例' if existing else '导入位图设置')
    dialog.resize(770,570)
    layout=W.QVBoxLayout(dialog)
    view=MeasureView();layout.addWidget(view,1)
    row=W.QFormLayout();layout.addLayout(row)
    mode=W.QComboBox();mode.addItems([tr('按每像素的实际长度'),tr('在位图上点击两点标定长度')])
    row.addRow('比例方式',mode)
    amount=W.QDoubleSpinBox();amount.setDecimals(8);amount.setRange(.00000001,100000000.)
    amount.setValue(existing or 1.)
    row.addRow('实际长度',amount)
    unit=W.QComboBox()
    for label,factor in UNITS.items():unit.addItem(tr(label),factor)
    row.addRow('单位',unit)
    angle=W.QDoubleSpinBox()
    angle.setRange(-360.,360.)
    angle.setDecimals(3)
    angle.setSuffix(' °')
    angle.setValue(rotation)
    row.addRow(tr('旋转角度'),angle)
    north=W.QCheckBox(tr('绘制真北箭头（先点箭尾，再点箭头）'))
    row.addRow(north)
    committed_angle=rotation

    def preview_rotation(value):
        view.bitmap.setRotation(-value)
        view.frame_bitmap()

    def apply_angle(value):
        nonlocal committed_angle
        angle.setValue(value)
        committed_angle=angle.value()

    def commit_angle():
        if angle.value()!=committed_angle:
            history.push(CalibrationChange(committed_angle,angle.value(),apply_angle))

    def apply_north(state):
        points,value=state
        view.north_points=points
        apply_angle(value)
        view.show_north()
        if len(points)==2 and north.isChecked():north.setChecked(False)
        sync()

    angle.valueChanged.connect(preview_rotation)
    angle.editingFinished.connect(commit_angle)
    preview_rotation(angle.value())
    feedback=W.QLabel();layout.addWidget(feedback)
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Ok|W.QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)

    def measured_length():
        if not view.enabled:return 1.
        if len(view.points)!=2:return 0.
        a,b=view.points
        return math.hypot((b.x()-a.x())*scale_x,(b.y()-a.y())*scale_y)

    def apply_points(points):
        view.points=points
        sync()

    def sync(*_):
        view.enabled=mode.currentIndex()==1
        view.setCursor(Qt.CursorShape.CrossCursor if view.enabled or north.isChecked() else Qt.CursorShape.ArrowCursor)
        view.show_measurement()
        length=measured_length()
        buttons.button(W.QDialogButtonBox.StandardButton.Ok).setEnabled(length>0)
        text=(tr('比例 {scale:.8g} 米/像素').format(scale=amount.value()*unit.currentData()/length)
              if length else tr('在位图上点击终点。' if view.points else '在位图上点击起点。'))
        if north.isChecked():
            text=tr('在位图上点真北箭头的顶端。' if len(view.north_points)==1 else '在位图上点真北箭头的起点。')
        feedback.setText(text)

    north.toggled.connect(sync)
    mode.currentIndexChanged.connect(sync);amount.valueChanged.connect(sync);unit.currentIndexChanged.connect(sync)
    sync()
    if dialog.exec()!=W.QDialog.DialogCode.Accepted:return None
    length=measured_length()
    if not length:return None
    return amount.value()*unit.currentData()/length,angle.value()

def import_image(editor,filename=None):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImageReader,QPixmap
    from PySide6.QtWidgets import QFileDialog,QMessageBox
    if filename is None:filename,_=QFileDialog.getOpenFileName(editor.q,tr('导入位图'),'',tr('位图 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)'))
    if not filename:return
    reader=QImageReader(filename);reader.setAutoTransform(True)
    size=reader.size()
    if not size.isValid() or size.width()*size.height()>MAX_PIXELS:
        QMessageBox.warning(editor.q,tr('导入位图'),tr('无法识别该图片，或图片超过 1 亿像素。'));return
    image=read_image(reader)
    if image.isNull():
        QMessageBox.warning(editor.q,tr('导入位图'),reader.errorString());return
    del reader
    preview=image.scaled(preview_size(image.size()),mode=Qt.TransformationMode.SmoothTransformation)
    true_north=-float(editor.scene.data['meta'].get('grid_north_true_heading',0) or 0)
    calibration=settings(editor.q,QPixmap.fromImage(preview),original_size=image.size(),true_north=true_north)
    if calibration is None:return
    scale,rotation=calibration
    viewport=editor.canvas.q.viewport()
    center=editor.world(viewport.width()/2,viewport.height()/2)
    try:oid=add(editor.scene,Path(filename).name,image,scale,center,rotation)
    except ValueError as error:QMessageBox.warning(editor.q,tr('导入位图'),tr(str(error)));return
    editor.select_bitmap46(oid)
    editor.fit()
    editor.update_title()

def inspector(editor,oid):
    from qt_compat import ttk
    from PySide6.QtWidgets import QCheckBox,QDoubleSpinBox,QPushButton
    row=layers(editor.scene)[oid]
    panel=editor.section('位图底图')
    layout=panel._ensure_layout(grid=True)
    editor.property_title.configure(text=row['name'])

    def change(**values):
        update(editor.scene,oid,**values)
        editor.redraw()
        editor.update_title()

    controls=[]
    for index,(key,label,low,high,factor) in enumerate((
            ('opacity','透明度（%）',0,100, -100),('rotation','旋转（°）',-360,360,1),
            ('x','中心 X（m）',-1e9,1e9,1),('y','中心 Y（m）',-1e9,1e9,1))):
        field=QDoubleSpinBox(panel.q);field.setRange(low,high);field.setDecimals(3)
        field.setValue((1-row[key])*100 if factor<0 else row[key])
        field.editingFinished.connect(lambda k=key,f=field,m=factor:change(**{
            k:1-f.value()/100 if m<0 else f.value()}))
        ttk.Label(panel,text=label).grid(row=index,column=0)
        layout.addWidget(field,index,1)
        controls.append(field)
    locked=QCheckBox('锁定底图',panel.q)
    locked.setChecked(row['locked'])
    def lock(checked):
        change(locked=checked)
        for control in controls:control.setEnabled(not checked)
        editor.sync_tree()
    locked.toggled.connect(lock)
    layout.addWidget(locked,4,0,1,2)
    resize=QPushButton('重设比例…',panel.q)
    def rescale():
        current=layers(editor.scene).get(oid)
        if not current or current['locked']:return
        from PySide6.QtCore import QSize
        calibration=settings(editor.q,pixmap(current,preview=True),current['scale'],current['rotation'],
                             QSize(current['width'],current['height']),
                             -float(editor.scene.data['meta'].get('grid_north_true_heading',0) or 0))
        if calibration is not None:
            scale,rotation=calibration
            change(scale=scale,rotation=rotation)
    resize.clicked.connect(rescale)
    layout.addWidget(resize,5,0,1,2)
    remove=QPushButton('删除底图',panel.q)
    def delete():
        if layers(editor.scene)[oid]['locked']:return
        with editor.scene.transaction('删除位图底图'):del layers(editor.scene)[oid]
        editor.select_bitmap46(None)
        editor.update_title()
    remove.clicked.connect(delete)
    layout.addWidget(remove,6,0,1,2)
    controls.extend((resize,remove))
    for control in controls:control.setEnabled(not row['locked'])
    editor._book15.notebook.select(list(editor._book15.pages).index('基本'))

def manage(editor):
    from PySide6.QtWidgets import QInputDialog,QMessageBox
    records=layers(editor.scene)
    if not records:
        QMessageBox.information(editor.q,tr('位图底图管理'),tr('当前工程没有位图底图。'));return
    choices={f'{index}. {row["name"]}'+(tr('（已锁定）') if row['locked'] else ''):oid
             for index,(oid,row) in enumerate(records.items(),1)}
    selected,ok=QInputDialog.getItem(editor.q,tr('位图底图管理'),tr('选择底图'),list(choices),editable=False)
    if not ok:return
    oid=choices[selected]
    row=records[oid]
    if row['locked']:
        if QMessageBox.question(editor.q,tr('解锁底图'),tr('解锁这张位图底图？'))!=QMessageBox.StandardButton.Yes:return
        update(editor.scene,oid,locked=False)
        editor.update_title()
    editor.select_bitmap46(oid)


def install_drop_filter(editor):
    from PySide6.QtCore import QEvent,QObject,QTimer
    extensions={'.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp','.acp'}

    class FileDrop(QObject):
        def eventFilter(self,target,event):
            if event.type() not in (QEvent.Type.DragEnter,QEvent.Type.DragMove,QEvent.Type.Drop):
                return False
            paths=[url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            if not paths or any(Path(path).suffix.lower() not in extensions for path in paths):
                return False
            event.acceptProposedAction()
            if event.type()==QEvent.Type.Drop:
                QTimer.singleShot(0,editor.q,lambda:self.load(paths))
            return True

        def load(self,paths):
            for path in paths:
                if Path(path).suffix.lower()=='.acp':
                    editor.open(path)
                else:
                    import_image(editor,path)

    handler=FileDrop(editor.q)
    for target in (editor.q,editor.canvas.q.viewport()):
        target.setAcceptDrops(True)
        target.installEventFilter(handler)
    return handler
