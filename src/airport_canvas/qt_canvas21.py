"""Qt Graphics View overlay canvas and Pillow-to-Qt icon conversion."""
import io,math
from collections import defaultdict
from qt_core21 import *
from qt_widgets21 import Scrollable
import qt_core21 as core
import shiboken6

class PhotoImage:
    def __init__(self,image=None,master=None,file=None,**kw):
        from PIL import Image
        application();self.image=(image or Image.open(file)).convert('RGBA').copy();raw=self.image.tobytes();qimage=G.QImage(raw,self.image.width,self.image.height,G.QImage.Format.Format_RGBA8888).copy();self.pixmap=G.QPixmap.fromImage(qimage)
    def width(self):return self.image.width
    def height(self):return self.image.height
def getimage(photo):return photo.image.copy()
ImageTk=SimpleNamespace(PhotoImage=PhotoImage,getimage=getimage)

class Canvas(Scrollable,Widget):
    native=W.QGraphicsView;class_name='Canvas'
    def __init__(self,*args,**kw):self._items={};self._tags=defaultdict(set);self._item_id=0;self._z=0;self._embedded=[];self._map_visible21=None;self._map_visibility_dirty21=False;super().__init__(*args,**kw)
    def make_native(self,master):
        q=super().make_native(master);self.scene=W.QGraphicsScene(q);q.setScene(self.scene);q.setFrameShape(W.QFrame.Shape.NoFrame);q.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop);q.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);q.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);q.setRenderHints(G.QPainter.RenderHint.Antialiasing|G.QPainter.RenderHint.TextAntialiasing|G.QPainter.RenderHint.SmoothPixmapTransform);q.setViewportUpdateMode(W.QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate);q.setOptimizationFlag(W.QGraphicsView.OptimizationFlag.DontSavePainterState,False);q.setMouseTracking(True);q.viewport().setMouseTracking(True);q.viewport()._ac_wrapper=weakref.ref(self);q.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        q.verticalScrollBar().valueChanged.connect(lambda *_:self._scroll_changed());return q
    def enable_gpu49(self):
        """Switch the main scene viewport only when Qt can create a GL context."""
        if G.QGuiApplication.platformName() in ('offscreen','minimal','vnc'):return False
        try:from PySide6.QtOpenGLWidgets import QOpenGLWidget
        except ImportError:return False
        context=G.QOpenGLContext()
        if not context.create() or not context.isValid():return False
        surface=G.QOffscreenSurface();surface.setFormat(context.format());surface.create()
        if not surface.isValid() or not context.makeCurrent(surface):return False
        context.doneCurrent()
        viewport=QOpenGLWidget()
        viewport.setFormat(context.format())
        viewport._ac_wrapper=weakref.ref(self)
        self.q.setViewport(viewport)
        viewport.setMouseTracking(True)
        self.q.setViewportUpdateMode(W.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        return True

    def configure(self,cnf=None,**kw):
        super().configure(cnf,**kw)
        if 'bg' in kw or 'background' in kw:self.q.setBackgroundBrush(G.QColor(kw.get('bg',kw.get('background'))))
        if 'scrollregion' in kw and kw['scrollregion']:
            x0,y0,x1,y1=kw['scrollregion'];self.scene.setSceneRect(x0,y0,max(1,x1-x0),max(1,y1-y0));self._scroll_changed()
        if 'yscrollcommand' in kw:self._scroll_changed()
    def _scroll_changed(self):
        callback=self._options.get('yscrollcommand')
        if callable(callback):callback(*self.yview())
    def _resized(self):
        if not self._embedded and not self.__dict__.get('_world_mode21'):self.scene.setSceneRect(0,0,max(1,self.q.viewport().width()),max(1,self.q.viewport().height()))
    def enable_world21(self):
        if self.__dict__.get('_world_mode21'):return
        self._world_mode21=True;self._overlay_root21=W.QGraphicsRectItem();self._grid_root21=W.QGraphicsRectItem()
        for root,z in [(self._overlay_root21,1e9),(self._grid_root21,-1e9)]:root.setFlag(W.QGraphicsItem.GraphicsItemFlag.ItemHasNoContents,True);root.setZValue(z);self.scene.addItem(root)
    def camera21(self,origin,scale):
        self.enable_world21()
        w,h=max(1,self.q.viewport().width()),max(1,self.q.viewport().height())
        angle=getattr(self,'rotation21_2',0.)
        a,b=math.cos(angle)*scale,math.sin(angle)*scale
        transform=G.QTransform(a,b,b,-a,origin[0],origin[1])
        desired,_=transform.inverted()
        self.q.setSceneRect(desired.mapRect(C.QRectF(0,0,w,h)))
        self.q.setTransform(transform)
        self.q.horizontalScrollBar().setValue(0)
        self.q.verticalScrollBar().setValue(0)
        inverse,_=self.q.viewportTransform().inverted()
        self._overlay_root21.setTransform(inverse);self._grid_root21.setTransform(inverse);self.q.viewport().update()
    def _create(self,kind,coords,**options):
        if len(coords)==1 and isinstance(coords[0],(list,tuple)):coords=coords[0]
        coords=list(coords);self._item_id+=1;i=self._item_id;self._z+=1
        if kind=='line' or kind=='polygon':q=W.QGraphicsPathItem()
        elif kind=='rectangle':q=W.QGraphicsRectItem()
        elif kind=='oval':q=W.QGraphicsEllipseItem()
        elif kind=='text':q=W.QGraphicsPathItem()
        elif kind=='image':q=W.QGraphicsPixmapItem()
        elif kind=='window':
            child=options['window'];child.q.setParent(None);q=self.scene.addWidget(child.q);self._embedded.append(i)
        else:raise ValueError('Unknown Qt canvas primitive: '+kind)
        if q.scene() is None:self.scene.addItem(q)
        if self.__dict__.get('_world_mode21') and kind!='window':
            tags=options.get('tags',());tags=(tags,) if isinstance(tags,str) else tags;q.setParentItem(self._grid_root21 if 'grid' in tags else self._overlay_root21)
        q.setZValue(self._z);self._items[i]=dict(q=q,type=kind,coords=coords,options={})
        self.itemconfigure(i,**options);self._geometry(i);return i
    def register_world(self,q,tags,kind='world'):
        self._item_id+=1;i=self._item_id;self._items[i]=dict(q=q,type=kind,coords=[],options={});self.itemconfigure(i,tags=tags);q.setVisible('map' not in tags or self._map_visible21 is not False);return i
    def create_line(self,*coords,**kw):return self._create('line',coords,**kw)
    def create_polygon(self,*coords,**kw):return self._create('polygon',coords,**kw)
    def create_rectangle(self,*coords,**kw):return self._create('rectangle',coords,**kw)
    def create_oval(self,*coords,**kw):return self._create('oval',coords,**kw)
    def create_text(self,*coords,**kw):return self._create('text',coords,**kw)
    def create_image(self,*coords,**kw):return self._create('image',coords,**kw)
    def create_window(self,*coords,**kw):return self._create('window',coords,**kw)
    def _matching(self,target):
        if target=='all':return list(self._items)
        if isinstance(target,int):return [target] if target in self._items else []
        return list(self._tags.get(str(target),set()))
    def _geometry(self,i):
        record=self._items[i];q=record['q'];kind=record['type'];coords=record['coords'];p=record['options']
        if kind in ('world','world_group'):return
        if kind in ('line','polygon'):
            path=G.QPainterPath()
            if len(coords)>=2:
                path.moveTo(coords[0],coords[1])
                for x,y in zip(coords[2::2],coords[3::2]):path.lineTo(x,y)
                if kind=='polygon':path.closeSubpath()
                if p.get('arrow') in ('last','both') and len(coords)>=4:
                    x,y=coords[-2:];angle=math.atan2(y-coords[-3],x-coords[-4]);length=9;width=4;points=[C.QPointF(x,y),C.QPointF(x-length*math.cos(angle)+width*math.sin(angle),y-length*math.sin(angle)-width*math.cos(angle)),C.QPointF(x-length*math.cos(angle)-width*math.sin(angle),y-length*math.sin(angle)+width*math.cos(angle))];path.addPolygon(G.QPolygonF(points));path.closeSubpath()
            q.setPath(path)
        elif kind in ('rectangle','oval') and len(coords)>=4:
            x0,y0,x1,y1=coords[:4];q.setRect(C.QRectF(C.QPointF(x0,y0),C.QPointF(x1,y1)).normalized())
        elif kind in ('text','image') and len(coords)>=2:
            box=q.boundingRect();anchor=p.get('anchor','center');dx=0 if anchor in ('w','nw','sw') else box.width() if anchor in ('e','ne','se') else box.width()/2;dy=0 if anchor in ('n','nw','ne') else box.height() if anchor in ('s','sw','se') else box.height()/2;q.setTransformOriginPoint(box.center());q.setRotation(-float(p.get('angle',0)));q.setPos(coords[0]-dx-box.left(),coords[1]-dy-box.top())
        elif kind=='window':
            if len(coords)>=2:q.setPos(coords[0],coords[1])
            child=p['window'];width=float(p.get('width',max(1,child.q.sizeHint().width())));height=float(p.get('height',0)) or max(1,child.q.sizeHint().height());q.resize(width,height);child.q.show()
    def itemconfigure(self,target,cnf=None,**kw):
        if cnf:kw.update(cnf)
        if target=='map' and set(kw)=={'state'}:
            visible=kw['state']!='hidden'
            if self._map_visible21==visible and not self._map_visibility_dirty21:return
            self._map_visible21=visible;self._map_visibility_dirty21=False
        elif 'state' in kw:self._map_visibility_dirty21=True
        for i in self._matching(target):
            record=self._items[i];q=record['q'];old=record['options'];kind=record['type']
            if not shiboken6.isValid(q):continue
            if 'tags' in kw:
                for tag in old.get('tags',()):self._tags[tag].discard(i)
                tags=kw['tags'];tags=(tags,) if isinstance(tags,str) else tuple(tags)
                for tag in tags:self._tags[tag].add(i)
                kw=dict(kw,tags=tags)
            old.update(kw)
            if 'state' in kw:q.setVisible(kw['state']!='hidden')
            if kind in ('line','polygon','rectangle','oval'):
                color=old.get('fill') if kind=='line' else old.get('outline');color=color or ''
                pen=G.QPen(G.QColor(color),max(.01,float(old.get('width',1)))) if color else G.QPen(Qt.PenStyle.NoPen);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin if old.get('joinstyle','round')=='round' else Qt.PenJoinStyle.MiterJoin);pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                if old.get('dash'):
                    dash=old['dash'];dash=([4,3] if isinstance(dash,str) else list(dash));width=max(.01,pen.widthF());pen.setDashPattern([max(.01,float(x)/width) for x in dash]);pen.setDashOffset(float(old.get('dashoffset',0))/width)
                q.setPen(pen)
                fill=old.get('fill') if kind!='line' or old.get('arrow') else None
                if fill:
                    color=G.QColor(fill)
                    if 'fill_alpha' in old:color.setAlphaF(old['fill_alpha'])
                    q.setBrush(G.QBrush(color))
                else:q.setBrush(G.QBrush(Qt.BrushStyle.NoBrush))
            elif kind=='text':
                path=G.QPainterPath()
                path.addText(0,0,font(old.get('font')),str(old.get('text','')))
                box=path.boundingRect()
                if old.get('text_height_px') and not box.isEmpty():
                    scale=old['text_height_px']/box.height()
                    stretch=old.get('text_width_px',box.width()*scale)/box.width()
                    path=G.QTransform.fromScale(stretch,scale).map(path)
                q.setPath(path)
                pen=G.QPen(G.QColor(old['outline']),old.get('outline_width',1)) if old.get('outline') else G.QPen(Qt.PenStyle.NoPen)
                q.setPen(pen)
                q.setBrush(G.QBrush(G.QColor(old.get('fill','#263748'))))
            elif kind=='image' and old.get('image'):q.setPixmap(old['image'].pixmap)
            if kind not in ('world','world_group'):self._geometry(i)
    itemconfig=itemconfigure
    def itemcget(self,target,key):
        ids=self._matching(target);return self._items[ids[0]]['options'].get(key,'') if ids else ''
    def coords(self,target,*coords):
        ids=self._matching(target)
        if not ids:return []
        if not coords:return list(self._items[ids[0]]['coords'])
        coords=list(coords[0]) if len(coords)==1 and isinstance(coords[0],(list,tuple)) else list(coords)
        for i in ids:self._items[i]['coords']=coords;self._geometry(i)
    def move(self,target,dx,dy):
        for i in self._matching(target):
            r=self._items[i];r['coords']=[x+(dx if n%2==0 else dy) for n,x in enumerate(r['coords'])]
            if r['type']=='world' and self.__dict__.get('_world_mode21'):
                inverse,_=self.q.viewportTransform().inverted();delta=inverse.map(C.QPointF(dx,dy))-inverse.map(C.QPointF());r['q'].moveBy(delta.x(),delta.y())
            elif r['type'].startswith('world'):r['q'].moveBy(dx,dy)
            else:self._geometry(i)
    def delete(self,*targets):
        for target in targets:
            for i in self._matching(target):
                record=self._items.pop(i,None)
                if not record:continue
                for tag in record['options'].get('tags',()):self._tags[tag].discard(i)
                q=record['q']
                if shiboken6.isValid(q) and q.scene():self.scene.removeItem(q)
    def find_all(self):return tuple(self._items)
    def find_withtag(self,tag):return tuple(self._matching(tag))
    def find_overlapping(self,x0,y0,x1,y1):
        box=C.QRectF(x0,y0,x1-x0,y1-y0)
        if self.__dict__.get('_world_mode21'):inverse,_=self.q.viewportTransform().inverted();box=inverse.mapRect(box)
        hits=set(self.scene.items(box));return tuple(i for i,r in self._items.items() if r['q'] in hits)
    def gettags(self,target):
        ids=self._matching(target);return self._items[ids[0]]['options'].get('tags',()) if ids else ()
    def addtag_withtag(self,tag,target):
        for i in self._matching(target):self.itemconfigure(i,tags=self.gettags(i)+(tag,))
    def dtag(self,target,tag=None):
        for i in self._matching(target):self.itemconfigure(i,tags=tuple(t for t in self.gettags(i) if t!=(tag or target)))
    def type(self,target):
        ids=self._matching(target);return self._items[ids[0]]['type'] if ids else ''
    def bbox(self,*targets,visible_only=False):
        box=None
        for target in targets or ('all',):
            for i in self._matching(target):
                q=self._items[i]['q']
                if shiboken6.isValid(q) and (not visible_only or q.isVisible()):
                    bounds=(q.deviceTransform(self.q.viewportTransform()).mapRect(q.boundingRect())
                            if self.__dict__.get('_world_mode21') else q.sceneBoundingRect())
                    box=bounds if box is None else box.united(bounds)
        return (box.left(),box.top(),box.right(),box.bottom()) if box is not None else None
    def tag_raise(self,target,above=None):
        ids=sorted(self._matching(target),key=lambda i:self._items[i]['q'].zValue());others=self._matching(above) if above is not None else [];base=max((self._items[i]['q'].zValue() for i in others),default=self._z)+1
        for n,i in enumerate(ids):self._items[i]['q'].setZValue(base+n*.00001)
        self._z=max(self._z,base+1)
    def tag_lower(self,target,below=None):
        ids=sorted(self._matching(target),key=lambda i:self._items[i]['q'].zValue());others=self._matching(below) if below is not None else [];base=min((self._items[i]['q'].zValue() for i in others),default=-1000)-1
        for n,i in enumerate(ids):self._items[i]['q'].setZValue(base+n*.00001)
    def tag_bind(self,target,sequence,callback):self.bind(sequence,callback,add='+')
    def canvasx(self,x):return self.q.mapToScene(int(x),0).x()
    def canvasy(self,y):return self.q.mapToScene(0,int(y)).y()
