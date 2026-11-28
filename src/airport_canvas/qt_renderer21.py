"""Retained metre-space Qt paths: pan/zoom changes one parent transform.

Qt's scene index clips individual vector records; dashes remain in world units.
No Pillow viewport uploads or per-segment Python redraws on camera movement.
"""
import math,time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from PySide6 import QtCore as C,QtGui as G,QtWidgets as W
Qt=C.Qt
_fonts={}
def batches(items):
    """Merge only adjacent, identical paint from the SAME editable owner."""
    rows=[];last=None
    for index,e in enumerate(items):
        signature=(e['oid'],e['type'],e.get('stroke'),e.get('fill'),e.get('width',.15),tuple(e.get('dash') or ()),e.get('dash_offset',0),e.get('opacity',1.),e.get('cosmetic_pen',False),e.get('round_caps',False),e.get('screen_weight',1.5)) if e['type']!='text' else None
        if signature is not None and rows and signature==last:rows[-1][0].append(index);rows[-1][1].append(e)
        else:rows.append(([index],[e]));last=signature
    return rows
class Camera:
    def __init__(self,canvas):self.canvas=canvas
    def transform(self):return self.canvas.q.viewportTransform()

@lru_cache(maxsize=512)
def base_glyph(family,text):
    font=G.QFont(family)
    font.setPixelSize(100)
    font.setStyleStrategy(G.QFont.StyleStrategy.PreferAntialias)
    path=G.QPainterPath()
    path.addText(0,0,font,text)
    return path,path.boundingRect()


def glyph_path(e):
    from font_paths import font_path
    family='Microsoft YaHei UI';path=font_path(e.get('font','normal'))
    if path not in _fonts:
        identifier=G.QFontDatabase.addApplicationFont(str(path));families=G.QFontDatabase.applicationFontFamilies(identifier);_fonts[path]=families[0] if families else family
    path,box=base_glyph(_fonts[path],e.get('text',''))
    if box.isEmpty():return path
    height=max(.001,e.get('size',4));sy=height/box.height();sx=(e['text_width']/box.width()) if e.get('text_width') else sy;origin=e['points'][0];transform=G.QTransform();transform.translate(*origin);transform.rotate(float(e.get('rotation',0)));transform.scale(sx,-sy);transform.translate(-box.center().x(),-box.center().y());return transform.map(path)

class CanvasRenderer:
    def __init__(self,canvas,tag='map'):
        self.tag=tag
        self.canvas=canvas;self.items=None;self.origin=None;self.scale=None;self.root=None;self._ids=[];self._record_cache={};self.metrics=dict(rebuilds=0,reuses=0,pans=0,culled=0,last_build_ms=0,camera_ms=0,path_reuses=0,path_updates=0);self.photos=[];self.records=[];self.draw_records={};self.text_items={};self.large_dash_items={};self._pavement_underlays=[]
    def render(self,items,origin,scale):
        start=time.perf_counter();c=self.canvas
        if self.items is not items:
            if self.root is None:
                c.enable_world21();self.root=Camera(c)
            for identifier in self._pavement_underlays:c.delete(identifier)
            self._pavement_underlays=[]
            from itertools import groupby
            for (continuous,fill),run in groupby(enumerate(items),
                    key=lambda entry:(entry[1].get('continuous_pavement') and entry[1].get('opacity',1.)==1.,entry[1].get('fill'))):
                if not continuous or not fill:continue
                polygons=list(run)
                if len(polygons)<2:continue
                path=G.QPainterPath()
                path.setFillRule(Qt.FillRule.WindingFill)
                for _,piece in polygons:
                    points=piece['points']
                    if len(points)<3:continue
                    if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))<0:
                        points=list(reversed(points))
                    path.moveTo(*points[0])
                    for point in points[1:]:path.lineTo(*point)
                    path.closeSubpath()
                # Draw the continuous fill once and preserve the original paths for hit testing.
                q=W.QGraphicsPathItem(path)
                q.setPen(G.QPen(Qt.PenStyle.NoPen))
                q.setBrush(G.QColor(fill))
                q.setZValue(polygons[0][0]-.25)
                c.scene.addItem(q)
                self._pavement_underlays.append(c.register_world(q,('map','pavement_underlay')))
            self.draw_records={};counts=defaultdict(int);keep=set()
            for indices,data in batches(items):
                index=indices[0];e=data[0]
                key=(e['oid'],counts[e['oid']]);counts[e['oid']]+=1;keep.add(key);old=self._record_cache.get(key)
                if old and old['data']==data:
                    old['q'].setZValue(index)
                    for original_index in indices:self.draw_records[original_index]=old['q']
                    self.metrics['path_reuses']+=1;continue
                path=G.QPainterPath();points=e['points']
                if e['type']=='text':path=glyph_path(e)
                else:
                    path.setFillRule(Qt.FillRule.WindingFill)
                    for part in data:
                        points=part['points']
                        if not points:continue
                        if part['type']=='polygon' and sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))<0:points=list(reversed(points))
                        path.moveTo(*points[0])
                        for p in points[1:]:path.lineTo(*p)
                        if part['type']=='polygon':path.closeSubpath()
                q=old['q'] if old else W.QGraphicsPathItem()
                q.setPath(path);q.setZValue(index);stroke=e.get('stroke');fill=e.get('fill');width=max(.001,float(e.get('width',.15)))
                if e['type']=='text':stroke=fill if e.get('black_outline') else None;fill=e.get('fill');width=max(.08,e.get('size',4)*.055)
                pen=G.QPen(G.QColor('#151a20' if e.get('black_outline') and e['type']=='text' else stroke),width) if stroke else G.QPen(Qt.PenStyle.NoPen);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin);pen.setCapStyle(Qt.PenCapStyle.RoundCap if e.get('round_caps') else Qt.PenCapStyle.FlatCap)
                if e.get('cosmetic_pen'):pen.setCosmetic(True);pen.setWidthF(e.get('screen_weight',1.5))
                if e.get('dash'):
                    pattern=list(e['dash']);pattern=pattern*2 if len(pattern)%2 else pattern;pen.setDashPattern([max(.001,x/width) for x in pattern]);pen.setDashOffset(e.get('dash_offset',0)/width)
                q.setPen(pen);q.setBrush(G.QBrush(G.QColor(fill)) if fill else G.QBrush(Qt.BrushStyle.NoBrush))
                if q.scene() is None:c.scene.addItem(q)
                identifier=old['id'] if old else c.register_world(q,(self.tag,'owner:'+e['oid']));c.update_layer_opacity(identifier,e.get('opacity',1.));self._record_cache[key]=dict(q=q,id=identifier,data=data);self.metrics['path_updates']+=1
                for original_index in indices:self.draw_records[original_index]=q
            for key in set(self._record_cache)-keep:c.delete(self._record_cache.pop(key)['id'])
            self.items=items;self.metrics['rebuilds']+=1;self.metrics['last_build_ms']=(time.perf_counter()-start)*1000
        else:self.metrics['reuses']+=1
        if self.origin!=list(origin):self.metrics['pans']+=1
        c.camera21(origin,scale);self.origin=list(origin);self.scale=scale;self.metrics['camera_ms']=(time.perf_counter()-start)*1000
