import math

from node_interaction20_8 import edge_insertion
from node_preview import AltHover,paint_marker

from PySide6 import QtCore as C, QtGui as G, QtWidgets as W


def snap_45(point,anchor):
    dx,dy=point[0]-anchor[0],point[1]-anchor[1]
    angle=round(math.atan2(dy,dx)/(math.pi/4))*math.pi/4
    u,v=math.cos(angle),math.sin(angle)
    reach=dx*u+dy*v
    return anchor[0]+reach*u,anchor[1]+reach*v


class StandPreview(W.QWidget):
    """Render project markings with editable construction points."""
    selectionChanged=C.Signal()

    def __init__(self, caption, build, edit, insert_node=None, delete=None):
        super().__init__()
        self.caption=caption
        self.build=build
        self.edit=edit
        self.insert_node=insert_node
        self.delete=delete
        self.closed=set()
        self.key=None
        self.nodes={}
        self.plan={}
        self.zone_marks={}
        self.bounds=C.QRectF()
        self.canvas=W.QGraphicsScene(self)
        self.canvas.setBackgroundBrush(G.QColor('#687078'))
        self.view=PreviewView(self.canvas,self)
        self.objects=W.QTreeWidget()
        self.objects.setHeaderLabel(caption('\u5bf9\u8c61','Objects'))
        self.objects.setMinimumWidth(155)
        self.objects.currentItemChanged.connect(self.select)
        fit=W.QPushButton(caption('\u9002\u5e94\u753b\u677f','Fit to view'))
        fit.clicked.connect(self.fit)
        layout=W.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        split=W.QSplitter()
        split.addWidget(self.objects)
        split.addWidget(self.view)
        split.setSizes([165,520])
        layout.addWidget(split,1)
        hint=W.QHBoxLayout()
        hint.addWidget(W.QLabel(caption('Shift 吸附角度，Alt 单击边线添加节点','Shift: snap angle. Alt+click: insert node.')))
        hint.addStretch(1)
        remove=W.QPushButton(caption('删除对象','Delete object'))
        remove.clicked.connect(lambda:self.delete_selection(None))
        hint.addWidget(remove)
        shortcut=G.QShortcut(G.QKeySequence('Delete'),self.objects)
        shortcut.activated.connect(lambda:self.delete_selection(None))
        hint.addWidget(fit)
        layout.addLayout(hint)
        self.drawing_bar=W.QWidget()
        tools=W.QHBoxLayout(self.drawing_bar)
        tools.setContentsMargins(0,0,0,0)
        self.drawing_hint=W.QLabel()
        self.drawing_hint.setWordWrap(True)
        tools.addWidget(self.drawing_hint,1)
        for zh,en,callback in (
            ('完成','Finish',self.finish_drawing),('清空','Clear',self.clear_drawing),
            ('取消','Cancel',self.cancel_drawing)):
            button=W.QPushButton(caption(zh,en))
            button.clicked.connect(callback)
            tools.addWidget(button)
        layout.addWidget(self.drawing_bar)
        self.drawing_bar.hide()

    def delete_selection(self,index):
        if not self.delete or not self.key:return
        if self.delete(self.key,index):
            self.view.selected_node=None
            self.refresh()

    def start_drawing(self,label,points,closed,commit):
        self.view.draft=points
        self.view.draft_history=[[list(q) for q in points]]
        self.view.draft_index=0
        self.view.closed_draft=closed
        self.view.draft_pointer=None
        self.commit_drawing=commit
        self.drawing_hint.setText(label+' · '+self.caption(
            '单击添加顶点，Enter 完成，Esc 取消',
            'Click to add vertices. Enter finishes. Esc cancels.'))
        self.drawing_bar.show()
        self.view.setFocus()
        self.view.viewport().update()

    def clear_drawing(self):
        self.view.draft=[]
        self.view.record_drawing()

    def cancel_drawing(self):
        self.view.draft=None
        self.view.draft_pointer=None
        self.view.update_insertion(None)
        self.drawing_bar.hide()

    def finish_drawing(self):
        if self.view.draft is None:return
        try:self.commit_drawing(self.view.draft)
        except ValueError as exc:
            self.drawing_hint.setText(str(exc))
            return
        self.cancel_drawing()
        self.refresh()


    def fit(self):
        if not self.bounds.isEmpty():
            self.view.fitInView(self.bounds,C.Qt.AspectRatioMode.KeepAspectRatio)

    def refresh(self,fit=False):
        from automatic_markings import generated_markings
        from scene_render import display_list
        scene,self.plan=self.build()
        self.render_scene=scene
        marks=generated_markings(scene)
        self.zone_marks={k:m for k,m in marks.items() if m['props']['mark_type'] in ('WORK_WAIT','TEMP_WAIT')}
        self.nodes={}
        self.closed=set()
        self.canvas.clear()
        self.objects.clear()
        groups={}
        def insert(key,name,points,parent=None):
            item=W.QTreeWidgetItem([name])
            item.setData(0,C.Qt.ItemDataRole.UserRole,key)
            if parent is None:self.objects.addTopLevelItem(item)
            else:parent.addChild(item)
            self.nodes[key]=points
            if key==self.key:self.objects.setCurrentItem(item)
            return item
        for oid in self.plan:
            stand=scene.assets[oid]
            groups[oid]=insert(oid,stand['name'],stand['points'])
        for oid,mark in marks.items():
            if mark['owner'] in groups:
                insert(oid,mark['name'],mark['points'],groups[mark['owner']])
                from marking_catalog import CATALOG
                if CATALOG[mark['props']['mark_type']]['mode']=='AREA':self.closed.add(oid)
        for part in display_list(scene,generated=marks):
            points=part['points']
            if not points:continue
            fill=part.get('fill')
            stroke=part.get('stroke')
            if part['type']=='text':
                item=self.canvas.addSimpleText(part['text'])
                item.setBrush(G.QColor(fill or '#ffffff'))
                box=item.boundingRect()
                scale=part.get('size',3)/max(1,box.height())
                item.setScale(scale)
                item.setTransformOriginPoint(box.center())
                item.setRotation(-part.get('rotation',0))
                item.setPos(points[0][0]-box.width()/2,-points[0][1]-box.height()/2)
                item.setZValue(1)
                continue
            path=G.QPainterPath(C.QPointF(points[0][0],-points[0][1]))
            for x,y in points[1:]:path.lineTo(x,-y)
            if part['type']=='polygon':path.closeSubpath()
            pen=G.QPen(G.QColor(stroke),part.get('width',.15)) if stroke else G.QPen(C.Qt.PenStyle.NoPen)
            if stroke and part.get('dash'):
                dash=part['dash']
                pen.setDashPattern([v/max(.01,pen.widthF()) for v in dash*(1+len(dash)%2)])
            self.canvas.addPath(path,pen,G.QBrush(G.QColor(fill)) if fill else G.QBrush())
        points=[C.QPointF(x,-y) for path in self.nodes.values() for x,y in path]
        if points:
            self.bounds=G.QPolygonF(points).boundingRect().adjusted(-10,-10,10,10)
        else:
            self.bounds=C.QRectF()
        self.canvas.setSceneRect(self.bounds.adjusted(-1000,-1000,1000,1000))
        self.objects.expandToDepth(0)
        first=self.objects.topLevelItem(0)
        if self.objects.currentItem() is None and first:self.objects.setCurrentItem(first)
        self.selectionChanged.emit()
        if fit:self.fit()
        self.view.viewport().update()

    def select(self,item,previous):
        if item is not None:
            key=item.data(0,C.Qt.ItemDataRole.UserRole)
            if key!=self.key:self.view.selected_node=None
            self.key=key
        self.view.update_insertion(None)
        self.selectionChanged.emit()


class PreviewView(W.QGraphicsView):
    def __init__(self,scene,editor):
        super().__init__(scene)
        self.editor=editor
        self.pan=None
        self.grab=None
        self.selected_node=None
        self.last=None
        self.space=False
        self.draft=None
        self.draft_pointer=None
        self.insertion_pixel=None
        self.alt_hover=AltHover(self,self.update_insertion)
        self.setRenderHint(G.QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(W.QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def insertion_target(self,pixel):
        if self.draft is None:
            if not self.editor.insert_node or self.editor.key in self.editor.plan:return
            points=self.editor.nodes.get(self.editor.key,[])
            closed=self.editor.key in self.editor.closed
        else:
            points,closed=self.draft,self.closed_draft
        p=self.mapToScene(pixel)
        return edge_insertion(points,(p.x(),-p.y()),9/self.transform().m11(),closed)

    def update_insertion(self,pixel):
        hit=self.insertion_target(pixel) if pixel is not None else None
        self.insertion_pixel=self.mapFromScene(hit[1][0],-hit[1][1]) if hit else None
        self.viewport().update()

    def drawing_point(self,event):
        p=self.mapToScene(event.position().toPoint())
        point=(p.x(),-p.y())
        if self.draft and event.modifiers() & C.Qt.KeyboardModifier.ShiftModifier:
            point=snap_45(point,self.draft[-1])
        return list(point)

    def record_drawing(self):
        del self.draft_history[self.draft_index+1:]
        self.draft_history.append([list(q) for q in self.draft])
        self.draft_index+=1
        self.viewport().update()

    def travel_drawing(self,step):
        index=self.draft_index+step
        if 0<=index<len(self.draft_history):
            self.draft_index=index
            self.draft=[list(q) for q in self.draft_history[index]]
            self.update_insertion(None)

    def wheelEvent(self,event):
        factor=1.15**(event.angleDelta().y()/120)
        if .04<self.transform().m11()*factor<100:self.scale(factor,factor)
        event.accept()

    def keyPressEvent(self,event):
        if self.draft is not None:
            if event.key() in (C.Qt.Key.Key_Return,C.Qt.Key.Key_Enter):
                self.editor.finish_drawing()
                return
            if event.key()==C.Qt.Key.Key_Escape:
                self.editor.cancel_drawing()
                return
        if event.key()==C.Qt.Key.Key_Delete and self.draft is None:
            self.editor.delete_selection(self.selected_node)
            return
        if event.key()==C.Qt.Key.Key_Space:
            self.space=True
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==C.Qt.Key.Key_Space:
            self.space=False
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self,event):
        button=event.button()
        pos=event.position().toPoint()
        if button in (C.Qt.MouseButton.MiddleButton,C.Qt.MouseButton.RightButton) or (self.space and button==C.Qt.MouseButton.LeftButton):
            self.pan=(button,pos)
            self.setCursor(C.Qt.CursorShape.ClosedHandCursor)
            return
        if button==C.Qt.MouseButton.LeftButton:
            points=self.editor.nodes.get(self.editor.key,[])
            if event.modifiers() & C.Qt.KeyboardModifier.AltModifier:
                hit=self.insertion_target(pos)
                if hit:
                    if self.draft is not None:
                        self.draft.insert(*hit)
                        self.record_drawing()
                    elif self.editor.insert_node(self.editor.key,*hit):self.editor.refresh()
                return
            if self.draft is not None:
                self.draft.append(self.drawing_point(event))
                self.record_drawing()
                return
            hits=[((self.mapFromScene(x,-y)-pos).manhattanLength(),i) for i,(x,y) in enumerate(points)]
            if hits:
                distance,index=min(hits)
                if distance<=12:
                    self.grab=index
                    self.selected_node=index
                    self.last=pos
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        pos=event.position().toPoint()
        if self.pan:
            button,last=self.pan
            delta=pos-last
            for bar,d in ((self.horizontalScrollBar(),delta.x()),(self.verticalScrollBar(),delta.y())):
                bar.setValue(bar.value()-d)
            self.pan=(button,pos)
            return
        if self.grab is not None:
            x,y=self.drag_point(event)
            self.last=self.mapFromScene(x,-y)
            self.viewport().update()
            return
        if self.draft is not None:
            self.draft_pointer=self.drawing_point(event)
            self.viewport().update()
            return
        super().mouseMoveEvent(event)

    def drag_point(self,event):
        pos=self.mapToScene(event.position().toPoint())
        point=(pos.x(),-pos.y())
        points=self.editor.nodes[self.editor.key]
        if len(points)>1 and event.modifiers() & C.Qt.KeyboardModifier.ShiftModifier:
            anchor=points[self.grab-1 if self.grab else 1]
            point=snap_45(point,anchor)
        return point

    def mouseReleaseEvent(self,event):
        if self.pan and event.button()==self.pan[0]:
            self.pan=None
            self.unsetCursor()
            return
        if self.grab is not None and event.button()==C.Qt.MouseButton.LeftButton:
            index=self.grab
            point=self.drag_point(event)
            self.grab=None
            self.editor.edit(self.editor.key,index,point)
            self.editor.refresh()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self,event):
        super().paintEvent(event)
        if self.draft is not None:
            painter=G.QPainter(self.viewport())
            painter.setRenderHint(G.QPainter.RenderHint.Antialiasing)
            painter.setPen(G.QPen(G.QColor('#7af2ff'),2))
            pixels=[self.mapFromScene(x,-y) for x,y in self.draft]
            for pixel in pixels:painter.drawEllipse(pixel,4,4)
            if len(pixels)>1:painter.drawPolyline(G.QPolygon(pixels))
            if pixels and self.draft_pointer is not None and self.insertion_pixel is None:
                x,y=self.draft_pointer
                painter.setPen(G.QPen(G.QColor('#7af2ff'),1,C.Qt.PenStyle.DashLine))
                tip=self.mapFromScene(x,-y)
                painter.drawLine(pixels[-1],tip)
                if self.closed_draft and len(pixels)>1:painter.drawLine(tip,pixels[0])
            painter.end()
            paint_marker(self,self.insertion_pixel)
            return
        points=self.editor.nodes.get(self.editor.key,[])
        painter=G.QPainter(self.viewport())
        painter.setRenderHint(G.QPainter.RenderHint.Antialiasing)
        painter.setPen(G.QPen(G.QColor('#172830'),1.5))
        painter.setBrush(G.QColor('#69e7f2'))
        if self.grab is not None and self.grab<len(points):
            painter.setPen(G.QPen(G.QColor('#69e7f2'),1.5,C.Qt.PenStyle.DashLine))
            for index in (self.grab-1,self.grab+1):
                if 0<=index<len(points):
                    x,y=points[index]
                    painter.drawLine(self.last,self.mapFromScene(x,-y))
            painter.setPen(G.QPen(G.QColor('#172830'),1.5))
        for i,(x,y) in enumerate(points):
            p=self.last if self.grab==i else self.mapFromScene(x,-y)
            painter.setBrush(G.QColor('#ff9300' if i==self.selected_node else '#69e7f2'))
            painter.drawEllipse(p,5,5)
        painter.end()
        paint_marker(self,self.insertion_pixel)
