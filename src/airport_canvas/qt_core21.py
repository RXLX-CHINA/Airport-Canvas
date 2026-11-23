"""Native Qt widgets with the small command interface used by existing controllers.

No Tcl interpreter, Tk windows, webview, or embedded legacy UI is involved.
"""
import sys,math,re,traceback,itertools,weakref
from types import SimpleNamespace
from pathlib import Path
from PySide6 import QtCore as C,QtGui as G,QtWidgets as W
Qt=C.Qt
_app=None;_root=None;_serial=itertools.count(1);_registry={};_global={};_timers={};_event_errors=[]

def application():
    global _app
    if _app is None:
        _app=W.QApplication.instance() or W.QApplication(sys.argv[:1]);_app.setApplicationName('Airport Canvas');_app.setOrganizationName('Airport Canvas')
        for filename in ('segoeui.ttf','segoeuib.ttf','msyh.ttc','seguisym.ttf'):
            path=Path('C:/Windows/Fonts')/filename
            if path.is_file():G.QFontDatabase.addApplicationFont(str(path))
        _app.setStyle('Fusion');_app.setFont(G.QFont('Segoe UI',10));_app.installEventFilter(EventHub(_app))
    return _app

def report(exc):
    _event_errors.append(''.join(traceback.format_exception(type(exc),exc,exc.__traceback__)))
    root=_root
    if root and hasattr(root,'report_callback_exception'):root.report_callback_exception(type(exc),exc,exc.__traceback__)
    else:traceback.print_exception(exc)

def call(fn,*args):
    try:return fn(*args)
    except Exception as exc:report(exc)

def font(value):
    if isinstance(value,G.QFont):return value
    if not value:return application().font()
    if isinstance(value,str):return G.QFont(value,10)
    f=G.QFont(str(value[0]),abs(int(value[1])) if len(value)>1 else 10)
    if len(value)>2:f.setBold('bold' in str(value[2]));f.setItalic('italic' in str(value[2]))
    return f

def mods(event):
    flags=event.modifiers();state=(1 if flags&Qt.KeyboardModifier.ShiftModifier else 0)|(4 if flags&Qt.KeyboardModifier.ControlModifier else 0)|(8 if flags&Qt.KeyboardModifier.AltModifier else 0)
    if hasattr(event,'buttons'):
        state|=256 if event.buttons()&Qt.MouseButton.LeftButton else 0;state|=512 if event.buttons()&Qt.MouseButton.MiddleButton else 0;state|=1024 if event.buttons()&Qt.MouseButton.RightButton else 0
    return state

def canonical(sequence):
    sequence=sequence.replace('ButtonPress-','Button-').replace('KeyPress-','Key-').replace('<Control-Key-','<Control-')
    sequence=re.sub(r'<Double-(\d)>',r'<Double-Button-\1>',sequence)
    return re.sub(r'([->])([A-Z])>',lambda m:m[1]+m[2].lower()+'>',sequence) if 'Control-' in sequence else sequence

class EventHub(C.QObject):
    def eventFilter(self,obj,event):
        if event.type()==C.QEvent.Type.Wheel and isinstance(obj,W.QWidget):
            page=obj
            while page is not None:
                if isinstance(page,W.QScrollArea) and page.property('acRole')=='inspectorPage':
                    delta=event.pixelDelta().y() or event.angleDelta().y()/120*72
                    if delta:
                        bar=page.verticalScrollBar()
                        bar.setValue(bar.value()-round(delta))
                        return True
                    break
                page=page.parentWidget()
        ref=getattr(obj,'_ac_wrapper',None);widget=ref() if ref else None
        if widget is None or widget._destroyed:return False
        layout=getattr(widget,'viewport_layout11',None)
        if layout and obj is widget.q.viewport() and event.type() in (C.QEvent.Type.Show,C.QEvent.Type.Resize):
            C.QTimer.singleShot(0,layout)
        handler=getattr(widget,"viewport_input21_2",None)
        if handler and obj is widget.q.viewport() and handler(event):return True
        kind=event.type();sequences=[];pos=event.position() if hasattr(event,'position') else C.QPointF();rootpos=obj.mapToGlobal(pos.toPoint()) if isinstance(obj,W.QWidget) else C.QPoint()
        e=SimpleNamespace(widget=widget,x=int(pos.x()),y=int(pos.y()),x_root=rootpos.x(),y_root=rootpos.y(),width=widget.q.width(),height=widget.q.height(),state=mods(event) if hasattr(event,'modifiers') else 0,delta=0,num=0,keysym='',char='')
        mouse={Qt.MouseButton.LeftButton:1,Qt.MouseButton.MiddleButton:2,Qt.MouseButton.RightButton:3}
        if kind in (C.QEvent.Type.MouseButtonPress,C.QEvent.Type.MouseButtonRelease,C.QEvent.Type.MouseButtonDblClick):
            e.num=mouse.get(event.button(),0);sequences=[f'<Button-{e.num}>' if kind==C.QEvent.Type.MouseButtonPress else f'<ButtonRelease-{e.num}>' if kind==C.QEvent.Type.MouseButtonRelease else f'<Double-Button-{e.num}>']
            if kind==C.QEvent.Type.MouseButtonPress:sequences.append('<ButtonPress>')
            if kind==C.QEvent.Type.MouseButtonPress and widget.winfo_class()=='Canvas':widget.q.setFocus()
        elif kind==C.QEvent.Type.MouseMove:
            drag=[f'<B{i}-Motion>' for i,button in [(1,Qt.MouseButton.LeftButton),(2,Qt.MouseButton.MiddleButton),(3,Qt.MouseButton.RightButton)] if event.buttons()&button and f'<B{i}-Motion>' in widget._event_bindings21];sequences=drag or ['<Motion>']
        elif kind==C.QEvent.Type.Wheel:e.delta=event.angleDelta().y();sequences=['<MouseWheel>']
        elif kind==C.QEvent.Type.Resize:
            if hasattr(widget,'_resized'):widget._resized()
            sequences=['<Configure>']
        elif kind==C.QEvent.Type.Enter:sequences=['<Enter>']
        elif kind==C.QEvent.Type.Leave:sequences=['<Leave>']
        elif kind==C.QEvent.Type.FocusIn:sequences=['<FocusIn>']
        elif kind==C.QEvent.Type.FocusOut:sequences=['<FocusOut>']
        elif kind in (C.QEvent.Type.KeyPress,C.QEvent.Type.KeyRelease):
            key=event.key();special={Qt.Key.Key_Space:'space',Qt.Key.Key_Return:'Return',Qt.Key.Key_Enter:'Return',Qt.Key.Key_Escape:'Escape',Qt.Key.Key_Delete:'Delete',Qt.Key.Key_Backspace:'BackSpace',Qt.Key.Key_Tab:'Tab',Qt.Key.Key_Shift:'Shift_L',Qt.Key.Key_Control:'Control_L'}
            e.keysym=special.get(key,G.QKeySequence(key).toString());e.char=event.text();release=kind==C.QEvent.Type.KeyRelease;prefix='KeyRelease-' if release else ''
            top=widget.winfo_toplevel()
            shortcuts=top.__dict__.get('shortcuts21') if top is not None else None
            if not release and shortcuts and shortcuts.dispatch(event,widget,e):return True
            if event.isAutoRepeat() and e.keysym in ('space','Shift_L','Control_L'):return False
            modifiers=('Control-' if e.state&4 else '')+('Shift-' if e.state&1 and e.keysym not in ('Shift_L',) else '')+('Alt-' if e.state&8 else '')
            name=e.keysym if len(e.keysym)!=1 else e.keysym.lower()
            sequences=[f'<{prefix}{modifiers}{name}>',f'<KeyRelease-{name}>' if release else f'<Key-{name}>','<KeyRelease>' if release else '<Key>']
            if name=='space':sequences.append('<KeyRelease-space>' if release else '<Key-space>')
            if not release and not modifiers:sequences.append(f'<{name}>')
        consumed=False
        for seq in dict.fromkeys(canonical(s) for s in sequences):
            owners=[widget]
            keyboard=kind in (C.QEvent.Type.KeyPress,C.QEvent.Type.KeyRelease)
            editing=widget.winfo_class() in ('Entry','Combobox','Text','Spinbox')
            global_edit_key=(e.keysym in ('Escape','F5','F6','F7','F8') or e.keysym=='Return' and e.state&8 or e.state&4 and e.keysym.lower() in ('n','o','s','z','y'))
            if keyboard and widget.winfo_toplevel() is not widget and (not editing or global_edit_key):owners.append(widget.winfo_toplevel())
            for owner in owners:
                callbacks=list(owner._event_bindings21.get(seq,[]))
                for callback in callbacks:
                    if call(callback,e)=='break':consumed=True;break
                # A handled key must not propagate viewport -> view -> window
                # and invoke the same command repeatedly (undo/F6/Enter).
                if callbacks and keyboard:consumed=True
                if callbacks and widget.winfo_class() in ('Canvas','Frame','Label') and kind in (C.QEvent.Type.MouseButtonPress,C.QEvent.Type.MouseButtonRelease,C.QEvent.Type.MouseButtonDblClick,C.QEvent.Type.MouseMove,C.QEvent.Type.Wheel):consumed=True
                if consumed:break
            if consumed:break
            for callback in list(_global.get(seq,[])):
                if call(callback,e)=='break':consumed=True;break
        return consumed

class Variable:
    def __init__(self,master=None,value=None,name=None):self.value=value if value is not None else '';self._traces={};self._listeners=[]
    def get(self):return self.value
    def set(self,value):
        value=self.convert(value)
        if self.value==value:return
        self.value=value
        for listener in list(self._listeners):listener(value)
        for callback in list(self._traces.values()):call(callback,'','','write')
    def convert(self,value):return value
    def trace_add(self,mode,callback):key=str(next(_serial));self._traces[key]=callback;return key
    def trace_remove(self,mode,key):self._traces.pop(key,None)
    def trace(self,mode,callback):return self.trace_add(mode,callback)
class StringVar(Variable):
    def convert(self,value):return '' if value is None else str(value)
class BooleanVar(Variable):
    def __init__(self,master=None,value=False,**kw):super().__init__(master,bool(value),**kw)
    def convert(self,value):return value not in (False,0,'','0','false','False')
class IntVar(Variable):
    def get(self):return int(self.value)
class DoubleVar(Variable):
    def get(self):return float(self.value)
class TclError(RuntimeError):pass

class Widget:
    native=W.QWidget;class_name='Frame'
    def __init__(self,master=None,**kw):
        application();self.master=master;self._children=[];self._event_bindings21={};self._options={};self._layout_info={};self._manager='';self._destroyed=False;self._name='ac'+str(next(_serial));self._layout=None;self._trace_links=[]
        self.q=self.make_native(master);self.q._ac_wrapper=weakref.ref(self);_registry[self._name]=self
        self.q.hide()  # Unmanaged controller widgets must never overlay the window.
        if isinstance(self.q,W.QAbstractScrollArea):self.q.viewport()._ac_wrapper=weakref.ref(self);self.q.viewport().setMouseTracking(True)
        if master:master._children.append(self)
        self.q.setObjectName(self._name);self.q.setMouseTracking(True);self.configure(**kw)
    def make_native(self,master):return self.native(master.q if master and not isinstance(master,Window) else master._content if master else None)
    def __str__(self):return self._name
    def __getitem__(self,key):return self.cget(key)
    def __setitem__(self,key,value):self.configure(**{key:value})
    def root(self):
        own=self
        while own.master is not None:own=own.master
        return own
    def bind(self,sequence,callback=None,add=None):
        key=canonical(sequence)
        if callback is None:return self._event_bindings21.get(key,[])
        if add!='+':self._event_bindings21[key]=[]
        self._event_bindings21.setdefault(key,[]).append(callback);return key
    def unbind(self,sequence,funcid=None):self._event_bindings21.pop(canonical(sequence),None)
    def bind_all(self,sequence,callback,add=None):
        key=canonical(sequence)
        if add!='+':_global[key]=[]
        _global.setdefault(key,[]).append(callback)
    def unbind_all(self,sequence):_global.pop(canonical(sequence),None)
    def event_generate(self,sequence,**kw):
        event=SimpleNamespace(widget=self,x=kw.get('x',0),y=kw.get('y',0),state=kw.get('state',0),num=kw.get('num',1),delta=kw.get('delta',0),keysym=kw.get('keysym',''),width=self.q.width(),height=self.q.height(),x_root=self.winfo_rootx(),y_root=self.winfo_rooty())
        for callback in self._event_bindings21.get(canonical(sequence),[]):
            if call(callback,event)=='break':break
    def configure(self,cnf=None,**kw):
        if cnf:kw.update(cnf)
        self._options.update(kw)
        if 'font' in kw:self.q.setFont(font(kw['font']))
        if 'state' in kw:self.q.setEnabled(kw['state']!='disabled')
        if 'cursor' in kw:
            cursor={'arrow':Qt.CursorShape.ArrowCursor,'crosshair':Qt.CursorShape.CrossCursor,'fleur':Qt.CursorShape.SizeAllCursor,'hand2':Qt.CursorShape.PointingHandCursor,'hand1':Qt.CursorShape.PointingHandCursor,'watch':Qt.CursorShape.WaitCursor,'sb_h_double_arrow':Qt.CursorShape.SizeHorCursor,'sb_v_double_arrow':Qt.CursorShape.SizeVerCursor,'sizing':Qt.CursorShape.SizeAllCursor,'tcross':Qt.CursorShape.CrossCursor,'exchange':Qt.CursorShape.SizeAllCursor}
            self.q.setCursor(cursor.get(kw['cursor'],Qt.CursorShape.ArrowCursor))
        if 'text' in kw and hasattr(self.q,'setText'):
            from interface_language import tr
            self.q.setText(tr(str(kw['text']),enum=isinstance(self.q,W.QRadioButton)))
        if 'textvariable' in kw:self.link_variable(kw['textvariable'])
        if 'image' in kw and hasattr(self.q,'setIcon'):
            photo=kw['image'];self.q.setIcon(G.QIcon(photo.pixmap) if photo else G.QIcon())
            if photo:self.q.setIconSize(photo.pixmap.size())
        if 'style' in kw:self.q.setProperty('acStyle',kw['style']);self.q.style().unpolish(self.q);self.q.style().polish(self.q)
        if 'command' in kw and hasattr(self.q,'clicked') and not self.__dict__.get('_command_bound'):
            def invoke(*_):
                if self.class_name=='Radiobutton' and self._options.get('variable'):self._options['variable'].set(self._options['value'])
                return call(self._options['command']) if self._options.get('command') else None
            self._command_bound=True;self.q.clicked.connect(invoke)
        if isinstance(self.q,W.QLabel):
            if kw.get('wraplength'):
                self.q.setWordWrap(True)
                if int(kw['wraplength'])<=120:self.q.setMinimumWidth(int(kw['wraplength']))
        if self.class_name in ('Frame','Label') and any(key in kw for key in ('foreground','fg','background','bg')):
            style=[];color=self._options.get('foreground',self._options.get('fg'));background=self._options.get('background',self._options.get('bg'))
            if color:style.append('color:'+color)
            if background and self.class_name=='Frame':style.append('background-color:'+background)
            self.q.setStyleSheet(';'.join(style))
        if 'width' in kw and self.class_name not in ('Entry','Combobox','Button','Label','Spinbox','Treeview','Text'):
            self.q.setMinimumWidth(max(0,int(kw['width'])));self.q.resize(int(kw['width']),self.q.height())
        if 'height' in kw and self.class_name in ('Frame','Canvas'):self.q.resize(self.q.width(),int(kw['height']))
    config=configure
    def cget(self,key):
        if key=='text' and hasattr(self.q,'text'):return self._options.get(key,self.q.text())
        return self._options.get(key,'')
    def keys(self):return list(self._options)
    def link_variable(self,variable):
        if not hasattr(variable,'_listeners'):return
        def update(value):
            if self._destroyed:return
            blocker=C.QSignalBlocker(self.q)
            if isinstance(self.q,W.QComboBox):self.set(value)
            elif isinstance(self.q,W.QAbstractButton) and self.q.isCheckable():self.q.setChecked(value==self._options.get('value',True))
            elif hasattr(self.q,'setText'):
                from interface_language import tr
                self.q.setText(tr(str(value)) if isinstance(self.q,W.QLabel) else str(value))
        variable._listeners.append(update);self._trace_links.append((variable,update));update(variable.get())
        if isinstance(self.q,W.QLineEdit):self.q.textChanged.connect(variable.set)
        elif isinstance(self.q,W.QComboBox):self.q.currentTextChanged.connect(lambda *_:variable.set(self.get()))
    def _container(self):return self._content if isinstance(self,Window) else self.q
    def _ensure_layout(self,grid=False,side='top'):
        if self._layout is None:
            self._layout=W.QGridLayout(self._container()) if grid else W.QBoxLayout(W.QBoxLayout.Direction.LeftToRight if side in ('left','right') else W.QBoxLayout.Direction.TopToBottom,self._container())
            self._layout.setContentsMargins(10,22,10,10) if isinstance(self.q,W.QGroupBox) else self._layout.setContentsMargins(0,0,0,0);self._layout.setSpacing(4 if grid else 0)
            padding=self._options.get('padding')
            if isinstance(padding,(int,float)) and isinstance(self.q,W.QGroupBox):
                self._layout.setContentsMargins(int(padding),22,int(padding),int(padding))
        if grid and not isinstance(self._layout,W.QGridLayout):raise TclError('Cannot mix pack/grid in one container')
        return self._layout
    def pack(self,**kw):
        self._layout_info.update(kw);self._manager='pack';parent=kw.get('in_',self.master)
        if parent is None:return
        layout=parent._ensure_layout(side=kw.get('side','top'));self.q.setParent(parent._container())
        if layout.indexOf(self.q)>=0:layout.removeWidget(self.q)
        horizontal=isinstance(layout,W.QBoxLayout) and layout.direction()==W.QBoxLayout.Direction.LeftToRight
        if horizontal:
            spacer=parent.__dict__.get('_pack_spacer21')
            if kw.get('expand') and spacer:layout.removeItem(spacer);parent._pack_spacer21=None
            elif not kw.get('expand') and not spacer and not any(x._layout_info.get('expand') for x in parent.winfo_children() if x is not self and x._manager=='pack'):
                spacer=W.QSpacerItem(0,0,W.QSizePolicy.Policy.Expanding,W.QSizePolicy.Policy.Minimum);layout.addItem(spacer);parent._pack_spacer21=spacer
            layout.setSpacing(4)
        before=kw.get('before');after=kw.get('after');index=layout.indexOf(before.q) if before else layout.indexOf(after.q)+1 if after else layout.count()-(1 if parent.__dict__.get('_pack_spacer21') else 0)
        if isinstance(layout,W.QBoxLayout):layout.insertWidget(max(0,index),self.q,1 if kw.get('expand') else 0)
        else:layout.addWidget(self.q)
        if kw.get('fill') in ('both','x'):self.q.setSizePolicy(W.QSizePolicy.Policy.Expanding,W.QSizePolicy.Policy.Expanding if kw.get('expand') else W.QSizePolicy.Policy.Preferred)
        if isinstance(self.q,W.QPushButton) and kw.get('fill')=='x':self.q.setSizePolicy(W.QSizePolicy.Policy.Ignored,W.QSizePolicy.Policy.Preferred)
        self.q.show();parent._layout_changed()
    def grid(self,**kw):
        self._layout_info.update(kw);kw=self._layout_info;self._manager='grid';layout=self.master._ensure_layout(grid=True)
        row=int(kw.get('row',0));col=int(kw.get('column',0));layout.addWidget(self.q,row,col,int(kw.get('rowspan',1)),int(kw.get('columnspan',1)));self.q.show();self.master._layout_changed()
    def place(self,**kw):
        self._manager='place';self._layout_info.update(kw);parent=kw.get('in_',self.master);self.q.setParent(parent._container());width=kw.get('width',self.q.sizeHint().width());height=kw.get('height',self.q.sizeHint().height());x=float(kw.get('x',0))+float(kw.get('relx',0))*parent.q.width();y=float(kw.get('y',0))+float(kw.get('rely',0))*parent.q.height()
        anchor=kw.get('anchor','nw')
        if 'e' in anchor:x-=width
        if 's' in anchor:y-=height
        self.q.setGeometry(int(x),int(y),int(width),int(height));self.q.show();self.q.raise_()
    def _layout_changed(self):
        if self._layout:self._layout.activate()
    def pack_forget(self):
        self.q.hide();self._manager=''
        parent=self.q.parentWidget()
        if parent and parent.layout():parent.layout().removeWidget(self.q)
    grid_forget=pack_forget;grid_remove=pack_forget;place_forget=pack_forget
    def pack_info(self):return dict(self._layout_info)
    grid_info=pack_info;place_info=pack_info
    def pack_slaves(self):return [x for x in self.winfo_children() if x._manager=='pack']
    def grid_slaves(self,row=None,column=None):return [x for x in self.winfo_children() if x._manager=='grid' and (row is None or x._layout_info.get('row',0)==row) and (column is None or x._layout_info.get('column',0)==column)]
    def pack_propagate(self,*args):
        if args and not args[0] and self._options.get('height') and self.class_name=='Frame':self.q.setFixedHeight(int(self._options['height']))
    grid_propagate=pack_propagate
    def columnconfigure(self,index,weight=0,**kw):
        layout=self._ensure_layout(grid=True)
        for i in index if isinstance(index,(tuple,list)) else [index]:layout.setColumnStretch(int(i),weight)
    def rowconfigure(self,index,weight=0,**kw):
        layout=self._ensure_layout(grid=True)
        for i in index if isinstance(index,(tuple,list)) else [index]:layout.setRowStretch(int(i),weight)
    grid_columnconfigure=columnconfigure;grid_rowconfigure=rowconfigure
    def winfo_children(self):return [c for c in self._children if not c._destroyed]
    def winfo_width(self):return self.q.width()
    def winfo_height(self):return self.q.height()
    def winfo_reqwidth(self):return max(1,self.q.sizeHint().width())
    def winfo_reqheight(self):return max(1,self.q.sizeHint().height())
    def winfo_rootx(self):return self.q.mapToGlobal(C.QPoint()).x()
    def winfo_rooty(self):return self.q.mapToGlobal(C.QPoint()).y()
    def winfo_x(self):return self.q.x()
    def winfo_y(self):return self.q.y()
    def winfo_screenwidth(self):return self.q.screen().availableGeometry().width()
    def winfo_screenheight(self):return self.q.screen().availableGeometry().height()
    def winfo_exists(self):return not self._destroyed
    def winfo_viewable(self):return self.q.isVisible()
    def winfo_ismapped(self):return self.q.isVisible()
    def winfo_manager(self):return self._manager
    def winfo_class(self):return self.class_name
    def winfo_toplevel(self):
        own=self
        while own.master and not isinstance(own,Window):own=own.master
        return own
    def winfo_id(self):return id(self.q)
    def nametowidget(self,name):return name if isinstance(name,Widget) else _registry[str(name)]
    def focus_set(self):self.q.setFocus()
    focus_force=focus_set
    def focus_get(self):
        w=application().focusWidget()
        while w:
            ref=getattr(w,'_ac_wrapper',None)
            if ref:return ref()
            w=w.parentWidget()
        return None
    def after(self,ms,callback,*args):
        token='timer'+str(next(_serial));timer=C.QTimer(self.root().q);timer.setSingleShot(True);_timers[token]=timer
        def run():
            _timers.pop(token,None)
            if not self._destroyed:call(callback,*args)
            timer.deleteLater()
        timer.timeout.connect(run);timer.start(max(0,int(ms)));return token
    def after_idle(self,callback,*args):return self.after(0,callback,*args)
    def after_cancel(self,token):
        timer=_timers.pop(token,None)
        if timer:timer.stop();timer.deleteLater()
    def update(self):
        if isinstance(self,Window) and not self.__dict__.get('_withdrawn21',False):self.q.show()
        application().processEvents(C.QEventLoop.ProcessEventsFlag.AllEvents,8)
    def update_idletasks(self):
        C.QCoreApplication.sendPostedEvents(None,C.QEvent.Type.LayoutRequest)
        application().processEvents(C.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents,5)
    def destroy(self):
        if self._destroyed:return
        self.event_generate('<Destroy>');self._destroyed=True
        for variable,listener in self._trace_links:
            if listener in variable._listeners:variable._listeners.remove(listener)
        for child in list(self.winfo_children()):child.destroy()
        if isinstance(self,Window):
            if self.master is None:
                global _root
                for token,timer in list(_timers.items()):
                    if timer.parent() is self.q:self.after_cancel(token)
                if _root is self:_root=None
            for key,callbacks in list(_global.items()):_global[key]=[cb for cb in callbacks if getattr(cb,'__self__',None) is not self]
        if self.master and self in self.master._children:self.master._children.remove(self)
        self.q.hide();self.q.deleteLater();_registry.pop(self._name,None)
    def lift(self,aboveThis=None):self.q.raise_()
    def lower(self,belowThis=None):self.q.lower()
    def state(self,states=None):
        if states is None:return ('disabled',) if not self.q.isEnabled() else ()
        self.q.setEnabled('disabled' not in states)
    def instate(self,states):return self.state()==tuple(states)
    def clipboard_clear(self):application().clipboard().clear()
    def clipboard_append(self,value):application().clipboard().setText(application().clipboard().text()+str(value))
    def clipboard_get(self):return application().clipboard().text()

class _MainWindow(W.QMainWindow):
    def closeEvent(self,event):
        wrapper=self._ac_wrapper()
        if not wrapper._destroyed and wrapper._protocols.get('WM_DELETE_WINDOW'):
            event.ignore();call(wrapper._protocols['WM_DELETE_WINDOW'])
        else:event.accept()

class Window(Widget):
    class_name='Tk'
    def make_native(self,master):
        q=_MainWindow(master.q if master else None);self._content=W.QWidget(q);q.setCentralWidget(self._content);self._protocols={};q.resize(1280,800);return q
    def __init__(self,master=None,**kw):
        global _root
        super().__init__(master,**kw)
        if master is None:_root=self
    def configure(self,cnf=None,**kw):
        super().configure(cnf,**kw)
        if 'menu' in kw:
            menu=kw['menu'];menu._bar=self.q.menuBar()
            for action in menu.q.actions():menu._bar.addAction(action)
    config=configure
    def title(self,value=None):
        if value is None:return self.q.windowTitle()
        from interface_language import tr
        self.q.setWindowTitle(tr(str(value)))
    def geometry(self,value=None):
        if value is None:return f'{self.q.width()}x{self.q.height()}+{self.q.x()}+{self.q.y()}'
        match=re.match(r'(?:(\d+)x(\d+))?([+-]\d+)?([+-]\d+)?',value)
        if match:
            a,b,x,y=match.groups();area=self.q.screen().availableGeometry()
            if a:self._explicit_size21=True;self.q.resize(int(a),int(b))
            elif isinstance(self,Toplevel) and not self.__dict__.get('_explicit_size21'):self.q.adjustSize()
            if x is not None:self.q.move(int(x),int(y or 0))
    def minsize(self,w,h):
        area=self.q.screen().availableGeometry();self.q.setMinimumSize(min(w,area.width()),min(h,area.height()))
    def maxsize(self,w,h):self.q.setMaximumSize(w,h)
    def resizable(self,*args):pass
    def protocol(self,name,callback):self._protocols[name]=callback
    def mainloop(self):
        self._owns_mainloop=True
        self.q.show()
        try:return application().exec()
        finally:self._owns_mainloop=False
    def withdraw(self):self._withdrawn21=True;self.q.hide()
    def deiconify(self):self._withdrawn21=False;self.q.show()
    def transient(self,parent):self.q.setWindowModality(Qt.WindowModality.WindowModal)
    def grab_set(self):self.q.setWindowModality(Qt.WindowModality.ApplicationModal);self.q.show()
    def grab_release(self):self.q.setWindowModality(Qt.WindowModality.NonModal)
    def wait_visibility(self):self.q.show();application().processEvents()
    def wait_window(self,window=None):
        target=window or self;loop=C.QEventLoop();target.q.destroyed.connect(loop.quit);target.q.show();loop.exec()
    def wm_overrideredirect(self,value):self.q.setWindowFlag(Qt.WindowType.FramelessWindowHint,bool(value));self.q.setWindowFlag(Qt.WindowType.ToolTip,bool(value))
    def attributes(self,*args):
        if args and args[0]=='-topmost':self.q.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,bool(args[1]))
    def iconphoto(self,default,*photos):
        icon=G.QIcon()
        for photo in photos:icon.addPixmap(photo.pixmap)
        self.q.setWindowIcon(icon)
    def iconbitmap(self,path):self.q.setWindowIcon(G.QIcon(path))
    def report_callback_exception(self,kind,value,tb):
        message=''.join(traceback.format_exception(kind,value,tb));Path(__file__).with_name('gui_error.log').write_text(message,encoding='utf8');traceback.print_exception(kind,value,tb)
        if application().platformName()!='offscreen':W.QMessageBox.critical(self.q,'操作失败',str(value)+'\n详细信息见 gui_error.log')
class Tk(Window):pass
class Toplevel(Window):
    class_name='Toplevel'
    def __init__(self,*args,**kw):
        super().__init__(*args,**kw);self.after_idle(self.show21)
    def show21(self):
        if self.__dict__.get('_withdrawn21',False):return
        # Give legacy subwindows an outer gutter without changing the main editor.
        if self._layout is not None:
            self._layout.setContentsMargins(12,12,12,12)
        if not self.__dict__.get('_explicit_size21'):self.q.adjustSize()
        self.q.show()

class Frame(Widget):pass
class LabelFrame(Widget):
    native=W.QGroupBox;class_name='TLabelframe'
    def configure(self,cnf=None,**kw):
        super().configure(cnf,**kw)
        if 'text' in kw:self.q.setTitle(str(kw['text']))
class Label(Widget):native=W.QLabel;class_name='Label'
class Button(Widget):
    native=W.QPushButton;class_name='Button'
    def invoke(self):self.q.click()
class Entry(Widget):
    native=W.QLineEdit;class_name='Entry'
    def make_native(self,master):
        q=super().make_native(master);q.setSizePolicy(W.QSizePolicy.Policy.Ignored,W.QSizePolicy.Policy.Fixed);q.setMinimumWidth(0);return q
    def get(self):return self.q.text()
    def delete(self,first,last=None):
        if last=='end' or first==0 and last is None:self.q.clear()
        else:
            value=self.get();a=int(first);b=int(last)+1 if last is not None else a+1;self.q.setText(value[:a]+value[b:])
    def insert(self,index,text):self.q.setCursorPosition(len(self.get()) if index=='end' else int(index));self.q.insert(str(text))
    def selection_range(self,a,b):self.q.setSelection(int(a),len(self.get()) if b=='end' else int(b)-int(a))
    select_range=selection_range
    def icursor(self,index):self.q.setCursorPosition(len(self.get()) if index=='end' else int(index))
class Combobox(Widget):
    native=W.QComboBox;class_name='Combobox'
    def make_native(self,master):
        q=super().make_native(master);q.setEditable(True);q.setSizePolicy(W.QSizePolicy.Policy.Ignored,W.QSizePolicy.Policy.Fixed);q.setMinimumWidth(0);q.activated.connect(lambda *_:self.event_generate('<<ComboboxSelected>>'));return q
    def configure(self,cnf=None,**kw):
        if cnf:kw={**cnf,**kw}
        if 'values' in kw or 'state' in kw:
            desired=self.get()
            # Apply readonly first: Qt discards editable text when switching modes.
            with C.QSignalBlocker(self.q):
                if 'state' in kw:self.q.setEditable(kw['state']!='readonly')
                if 'values' in kw:
                    self.q.clear()
                    from interface_language import tr
                    values=kw['values']
                    for value in values:
                        raw=str(value)
                        label=values[value] if isinstance(values,dict) else raw
                        caption=raw if self.q.isEditable() else tr(label,enum=True)
                        self.q.addItem(caption,raw)
                self.set(desired)
        super().configure(**kw)
    def get(self):
        text=self.q.currentText()
        return text if self.q.isEditable() else self.q.currentData() or text
    def set(self,value):
        raw=str(value)
        if not self.q.isEditable():
            index=self.q.findData(raw)
            if index>=0:
                self.q.setCurrentIndex(index)
                return
        self.q.setCurrentText(raw)
    def current(self,index=None):
        if index is None:return self.q.currentIndex()
        self.q.setCurrentIndex(index)
class Checkbutton(Widget):
    native=W.QCheckBox;class_name='Checkbutton'
    def configure(self,cnf=None,**kw):
        variable=kw.get('variable')
        super().configure(cnf,**kw)
        if variable:
            self.link_variable(variable)
            if not self.__dict__.get('_check_bound'):
                self._check_bound=True;self.q.toggled.connect(lambda checked:self._options['variable'].set(self._options.get('onvalue',True) if checked else self._options.get('offvalue',False)))
    def invoke(self):self.q.click()
class Radiobutton(Checkbutton):
    native=W.QRadioButton;class_name='Radiobutton'
    def configure(self,cnf=None,**kw):
        Widget.configure(self,cnf,**kw)
        if 'variable' in kw:
            self.link_variable(kw['variable'])
            if not self.__dict__.get('_check_bound'):
                self._check_bound=True;self.q.setAutoExclusive(False);self.q.clicked.connect(lambda *_:self._options['variable'].set(self._options['value']))
class Spinbox(Entry):class_name='Spinbox'
class Separator(Widget):
    native=W.QFrame
    def make_native(self,master):q=super().make_native(master);q.setFrameShape(W.QFrame.Shape.HLine);return q
class Progressbar(Widget):
    native=W.QProgressBar
    def configure(self,cnf=None,**kw):
        super().configure(cnf,**kw);self.q.setTextVisible(False)
        if 'maximum' in kw:self.q.setMaximum(int(kw['maximum']))
        if 'value' in kw:self.q.setValue(round(kw['value']))
    def start(self,interval=50):self.q.setRange(0,0)
    def stop(self):self.q.setRange(0,int(self._options.get('maximum',100)))
class Style:
    def __init__(self,*args):self.values={}
    def theme_use(self,*args):return 'Fusion'
    def configure(self,name,**kw):self.values.setdefault(name,{}).update(kw)
    def map(self,*args,**kw):pass
    def lookup(self,name,key,default=None):return self.values.get(name,{}).get(key,default)

