"""Pointer and Alt-key tracking for edge insertion previews."""
from PySide6 import QtCore as C, QtGui as G, QtWidgets as W


class AltHover(C.QObject):
    def __init__(self,view,update):
        super().__init__(view)
        self.viewport=view.viewport()
        self.update=update
        self.viewport.setMouseTracking(True)
        W.QApplication.instance().installEventFilter(self)

    def eventFilter(self,obj,event):
        kind=event.type()
        if obj is self.viewport:
            if kind==C.QEvent.Type.MouseMove:
                alt=event.modifiers() & C.Qt.KeyboardModifier.AltModifier
                self.update(event.position().toPoint() if alt and not event.buttons() else None)
            elif kind in (C.QEvent.Type.Leave,C.QEvent.Type.MouseButtonPress,C.QEvent.Type.Wheel):
                self.update(None)
        if kind in (C.QEvent.Type.KeyPress,C.QEvent.Type.KeyRelease) and event.key()==C.Qt.Key.Key_Alt:
            pos=self.viewport.mapFromGlobal(G.QCursor.pos())
            if kind==C.QEvent.Type.KeyRelease:
                self.update(None)
            elif self.viewport.isVisible() and self.viewport.underMouse():
                self.update(pos)
        return False


def paint_marker(view,pixel):
    if pixel is None:return
    painter=G.QPainter(view.viewport())
    painter.setRenderHint(G.QPainter.RenderHint.Antialiasing)
    painter.setPen(G.QPen(G.QColor('#183a49'),2))
    painter.setBrush(G.QColor('#7af2ff'))
    painter.drawEllipse(pixel,6,6)
    x,y=pixel.x(),pixel.y()
    painter.drawLine(x-3,y,x+3,y)
    painter.drawLine(x,y-3,x,y+3)
    painter.end()
