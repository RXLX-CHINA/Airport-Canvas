"""Persistent reference images and the native Qt calibration tools."""
import base64
import math
from pathlib import Path
import uuid

UNITS={'米 (m)':1.,'厘米 (cm)':.01,'毫米 (mm)':.001,'千米 (km)':1000.,
       '英尺 (ft)':.3048,'英寸 (in)':.0254}
MAX_PIXELS=24_000_000
MAX_ENCODED=12_000_000

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

def add(scene,name,image,scale,center):
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
    encoded=QByteArray()
    buffer=QBuffer(encoded)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer,'PNG'):raise ValueError('无法编码位图')
    oid='bitmap-'+uuid.uuid4().hex
    row=dict(name=name,png=base64.b64encode(bytes(encoded)).decode('ascii'),
             width=image.width(),height=image.height(),scale=scale,
             x=center[0],y=center[1],rotation=0.,opacity=1.,locked=False)
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

def pixmap(row):
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
    from PySide6.QtGui import QImageReader,QPixmap
    try:content=QByteArray(base64.b64decode(row['png'],validate=True))
    except ValueError:return QPixmap()
    buffer=QBuffer(content)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader=QImageReader(buffer,b'PNG')
    size=reader.size()
    if size.width()!=row['width'] or size.height()!=row['height']:return QPixmap()
    return QPixmap.fromImage(reader.read())

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
        signature=(row['png'],row['width'],row['height'])
        if oid not in cache:
            item=QGraphicsPixmapItem()
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            editor.canvas.scene.addItem(item)
            cache[oid]=(item,None)
        item,previous=cache[oid]
        if previous!=signature:
            item.setPixmap(pixmap(row))
            item.setOffset(-row['width']/2,-row['height']/2)
            cache[oid]=(item,signature)
        item.setPos(row['x'],row['y'])
        item.setTransform(QTransform().rotate(row['rotation']).scale(row['scale'],-row['scale']))
        item.setOpacity(row['opacity'])
        item.setVisible(not editor.scene.data['meta'].get('object_display',{}).get(oid,{}).get('hidden'))
        item.setZValue(-9e8+index)

def settings(parent,image,existing=None):
    from PySide6 import QtGui,QtCore,QtWidgets as W
    Qt=QtCore.Qt

    class MeasureView(W.QGraphicsView):
        def __init__(self):
            super().__init__()
            self.setScene(W.QGraphicsScene(self))
            self.scene().addPixmap(image)
            self.image_bounds=QtCore.QRectF(image.rect())
            self.line=self.scene().addLine(QtCore.QLineF(),QtGui.QPen(QtGui.QColor('#00aeef'),0))
            self.anchor=None
            self.enabled=False

        def point(self,event):
            point=self.mapToScene(event.position().toPoint())
            return QtCore.QPointF(min(max(0,point.x()),image.width()),
                                  min(max(0,point.y()),image.height()))

        def resizeEvent(self,event):
            super().resizeEvent(event)
            self.fitInView(self.image_bounds,Qt.AspectRatioMode.KeepAspectRatio)

        def mousePressEvent(self,event):
            if self.enabled and event.button()==Qt.MouseButton.LeftButton:
                self.anchor=self.point(event)
                self.line.setLine(QtCore.QLineF(self.anchor,self.anchor))
                sync()
            else:super().mousePressEvent(event)

        def mouseMoveEvent(self,event):
            if self.anchor is not None:
                self.line.setLine(QtCore.QLineF(self.anchor,self.point(event)))
                sync()
            else:super().mouseMoveEvent(event)

        def mouseReleaseEvent(self,event):
            if self.anchor is not None and event.button()==Qt.MouseButton.LeftButton:
                self.mouseMoveEvent(event)
                self.anchor=None
            else:super().mouseReleaseEvent(event)

    dialog=W.QDialog(parent)
    dialog.setWindowTitle('重设底图比例' if existing else '导入位图设置')
    dialog.resize(770,570)
    layout=W.QVBoxLayout(dialog)
    view=MeasureView();layout.addWidget(view,1)
    row=W.QFormLayout();layout.addLayout(row)
    mode=W.QComboBox();mode.addItems(['按每像素的实际长度','在位图上拉出已知长度'])
    row.addRow('比例方式',mode)
    amount=W.QDoubleSpinBox();amount.setDecimals(8);amount.setRange(.00000001,100000000.)
    amount.setValue(existing or 1.)
    row.addRow('实际长度',amount)
    unit=W.QComboBox();unit.addItems(list(UNITS));row.addRow('单位',unit)
    feedback=W.QLabel();layout.addWidget(feedback)
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Ok|W.QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)

    def sync(*_):
        view.enabled=mode.currentIndex()==1
        view.setCursor(Qt.CursorShape.CrossCursor if view.enabled else Qt.CursorShape.ArrowCursor)
        view.line.setVisible(view.enabled)
        length=view.line.line().length() if view.enabled else 1.
        buttons.button(W.QDialogButtonBox.StandardButton.Ok).setEnabled(length>0)
        text=f'比例 {amount.value()*UNITS[unit.currentText()]/length:.8g} 米/像素' if length else '在位图上按住鼠标左键拉出已知长度'
        feedback.setText(text)

    mode.currentIndexChanged.connect(sync);amount.valueChanged.connect(sync);unit.currentIndexChanged.connect(sync)
    sync()
    if dialog.exec()!=W.QDialog.DialogCode.Accepted:return None
    length=view.line.line().length() if view.enabled else 1.
    return amount.value()*UNITS[unit.currentText()]/length

def import_image(editor,filename=None):
    from PySide6.QtGui import QImageReader,QPixmap
    from PySide6.QtWidgets import QFileDialog,QMessageBox
    if filename is None:filename,_=QFileDialog.getOpenFileName(editor.q,'导入位图','','位图 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)')
    if not filename:return
    reader=QImageReader(filename);reader.setAutoTransform(True)
    size=reader.size()
    if not size.isValid() or size.width()*size.height()>MAX_PIXELS:
        QMessageBox.warning(editor.q,'导入位图','无法识别该图片，或图片超过 2400 万像素。');return
    image=reader.read()
    if image.isNull():
        QMessageBox.warning(editor.q,'导入位图',reader.errorString());return
    scale=settings(editor.q,QPixmap.fromImage(image))
    if scale is None:return
    viewport=editor.canvas.q.viewport()
    center=editor.world(viewport.width()/2,viewport.height()/2)
    try:oid=add(editor.scene,Path(filename).name,image,scale,center)
    except ValueError as error:QMessageBox.warning(editor.q,'导入位图',str(error));return
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
        scale=settings(editor.q,pixmap(current),current['scale'])
        if scale is not None:change(scale=scale)
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
        QMessageBox.information(editor.q,'位图底图管理','当前工程没有位图底图。');return
    choices={f'{index}. {row["name"]}'+('（已锁定）' if row['locked'] else ''):oid
             for index,(oid,row) in enumerate(records.items(),1)}
    selected,ok=QInputDialog.getItem(editor.q,'位图底图管理','选择底图',list(choices),editable=False)
    if not ok:return
    oid=choices[selected]
    row=records[oid]
    if row['locked']:
        if QMessageBox.question(editor.q,'解锁底图','解锁这张位图底图？')!=QMessageBox.StandardButton.Yes:return
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
