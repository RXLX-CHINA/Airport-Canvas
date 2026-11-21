"""Qt menus, splitters, property tabs, trees, text and native dialogs."""
from qt_core21 import *
import qt_core21 as core
from interface_language import tr

class Menu(Widget):
    native=W.QMenu;class_name='Menu'
    def __init__(self,*args,**kw):self._entries=[];self._bar=None;super().__init__(*args,**kw)
    def add_cascade(self,**kw):
        child=kw['menu'];child.q.setTitle(tr(kw.get('label','')));action=self.q.addMenu(child.q);self._record(action,kw,'cascade')
    def _record(self,action,options,kind):
        self._entries.append(dict(action=action,kind=kind,**options))
        if self._bar:self._bar.addAction(action)
    def add_command(self,**kw):
        action=self.q.addAction(tr(kw.get('label','')));self._record(action,kw,'command');entry=self._entries[-1];action.triggered.connect(lambda *_:core.call(entry['command']) if entry.get('command') else None)
    def add_separator(self):self._record(self.q.addSeparator(),{},'separator')
    def add_checkbutton(self,**kw):
        action=self.q.addAction(tr(kw.get('label','')));action.setCheckable(True);var=kw['variable'];action.setChecked(bool(var.get()))
        def changed(checked):var.set(checked);core.call(kw['command']) if kw.get('command') else None
        action.triggered.connect(changed);var._listeners.append(lambda value,a=action:a.setChecked(bool(value)));self._record(action,kw,'checkbutton')
    def add_radiobutton(self,**kw):
        action=self.q.addAction(tr(kw.get('label','')));action.setCheckable(True);var=kw['variable'];action.setChecked(var.get()==kw['value'])
        def changed(checked):var.set(kw['value']);core.call(kw['command']) if kw.get('command') else None
        action.triggered.connect(changed);var._listeners.append(lambda value,a=action,k=kw['value']:a.setChecked(value==k));self._record(action,kw,'radiobutton')
    def index(self,index):
        if index=='end':return len(self._entries)-1 if self._entries else None
        if isinstance(index,str) and not index.isdigit():return next(i for i,x in enumerate(self._entries) if x.get('label')==index)
        return int(index)
    def type(self,index):return self._entries[self.index(index)]['kind']
    def entrycget(self,index,key):return self._entries[self.index(index)].get(key,'')
    def entryconfigure(self,index,**kw):
        data=self._entries[self.index(index)];data.update(kw);action=data['action']
        if 'label' in kw:action.setText(tr(kw['label']))
        if 'state' in kw:action.setEnabled(kw['state']!='disabled')
        if kw.get('image'):action.setIcon(G.QIcon(kw['image'].pixmap))
    entryconfig=entryconfigure
    def delete(self,first,last=None):
        lo=self.index(first);hi=self.index(last) if last is not None else lo
        for data in self._entries[lo:hi+1]:
            self.q.removeAction(data['action'])
            if self._bar:self._bar.removeAction(data['action'])
        del self._entries[lo:hi+1]
    def invoke(self,index):self._entries[self.index(index)]['action'].trigger()
    def tk_popup(self,x,y):self.q.popup(C.QPoint(x,y))

class Panedwindow(Widget):
    native=W.QSplitter;class_name='TPanedwindow'
    def configure(self,cnf=None,**kw):
        super().configure(cnf,**kw)
        if 'orient' in kw:self.q.setOrientation(Qt.Orientation.Horizontal if kw['orient']=='horizontal' else Qt.Orientation.Vertical)
        self.q.setChildrenCollapsible(False);self.q.setHandleWidth(5)
    def add(self,child,**kw):
        self.q.addWidget(child.q);self.q.setStretchFactor(self.q.indexOf(child.q),int(kw.get('weight',0)));child.q.show()
    def panes(self):return tuple(child._name for child in self.winfo_children() if self.q.indexOf(child.q)>=0)
    def sashpos(self,index,value=None):
        sizes=self.q.sizes()
        if value is None:return sum(sizes[:index+1])
        if len(sizes)<index+2:return
        total=sum(sizes);previous=sum(sizes[:index]);sizes[index]=max(100,int(value)-previous);sizes[index+1]=max(100,total-sum(sizes[:index+1])-sum(sizes[index+2:]));self.q.setSizes(sizes)
    def forget(self,child):child.q.setParent(None)

class Notebook(Widget):
    native=W.QTabWidget;class_name='TNotebook'
    def make_native(self,master):q=super().make_native(master);q.currentChanged.connect(lambda *_:self.event_generate('<<NotebookTabChanged>>'));return q
    def add(self,child,**kw):self.q.addTab(child.q,tr(kw.get('text','')))
    def select(self,index=None):
        if index is None:
            q=self.q.currentWidget();return next((w._name for w in self._children if w.q is q),'')
        i=self.index(index);self.q.setCurrentIndex(i)
    def index(self,index):
        if isinstance(index,int):return index
        if index=='current':return self.q.currentIndex()
        widget=self.nametowidget(index);return self.q.indexOf(widget.q)
    def tabs(self):return tuple(w._name for w in self._children if self.q.indexOf(w.q)>=0)
    def tab(self,index,option=None,**kw):
        i=self.index(index)
        if 'text' in kw:self.q.setTabText(i,tr(kw['text']))
        if 'state' in kw:self.q.setTabEnabled(i,kw['state']!='disabled')
        if option=='text':return self.q.tabText(i)
    def forget(self,index):self.q.removeTab(self.index(index))

class Scrollable:
    def yview(self,*args):return self._scroll(True,*args)
    def xview(self,*args):return self._scroll(False,*args)
    def _scroll(self,vertical,*args):
        bar=self.q.verticalScrollBar() if vertical else self.q.horizontalScrollBar()
        if not args:return (bar.value()/max(1,bar.maximum()+bar.pageStep()),(bar.value()+bar.pageStep())/max(1,bar.maximum()+bar.pageStep()))
        if args[0]=='moveto':bar.setValue(round(float(args[1])*max(1,bar.maximum()+bar.pageStep())))
        elif args[0]=='scroll':bar.setValue(bar.value()+int(args[1])*(bar.pageStep() if len(args)>2 and args[2]=='pages' else 24))
    def yview_moveto(self,value):self.yview('moveto',value)
    def yview_scroll(self,n,what):self.yview('scroll',n,what)
    def xview_moveto(self,value):self.xview('moveto',value)

class PropertyScrollArea(Scrollable, Widget):
    native = W.QScrollArea

    def make_native(self, master):
        area = super().make_native(master)
        area.setWidgetResizable(True)
        area.setFrameShape(W.QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return area

    def set_body(self, body):
        self.q.setWidget(body.q)
        body._ensure_layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        body.q.show()


class Scrollbar(Widget):
    native=W.QScrollBar;class_name='TScrollbar'
    def make_native(self,master):
        q=super().make_native(master);q.setOrientation(Qt.Orientation.Vertical);q.setRange(0,1000);q.valueChanged.connect(lambda value:core.call(self._options['command'],'moveto',value/1000) if self._options.get('command') else None);return q
    def configure(self,cnf=None,**kw):
        Widget.configure(self,cnf,**kw)
        if 'orient' in kw:self.q.setOrientation(Qt.Orientation.Horizontal if kw['orient']=='horizontal' else Qt.Orientation.Vertical)
    def set(self,first,last):
        blocker=C.QSignalBlocker(self.q);self.q.setPageStep(max(1,round((float(last)-float(first))*1000)));self.q.setRange(0,max(0,1000-self.q.pageStep()));self.q.setValue(round(float(first)*1000))

class Treeview(Scrollable,Widget):
    native=W.QTreeWidget;class_name='Treeview'
    def __init__(self,*args,**kw):self._items={};self._columns=[];self._tags={};super().__init__(*args,**kw)
    def make_native(self,master):
        q=super().make_native(master);q.setRootIsDecorated(True);q.setUniformRowHeights(True);q.setAlternatingRowColors(False);q.itemSelectionChanged.connect(lambda:self.event_generate('<<TreeviewSelect>>'));return q
    def configure(self,cnf=None,**kw):
        super().configure(cnf,**kw)
        if 'columns' in kw:self._columns=list(kw['columns']);self.q.setColumnCount(1+len(self._columns))
        if 'show' in kw:self.q.setColumnHidden(0,'tree' not in kw['show'])
        if 'selectmode' in kw:self.q.setSelectionMode(W.QAbstractItemView.SelectionMode.ExtendedSelection if kw['selectmode'] in ('extended','multiple') else W.QAbstractItemView.SelectionMode.SingleSelection)
        if 'height' in kw:self.q.setMinimumHeight(min(300,int(kw['height'])*24))
    def _col(self,column):return 0 if column=='#0' else int(column[1:]) if str(column).startswith('#') else self._columns.index(column)+1
    def heading(self,column,**kw):self.q.headerItem().setText(self._col(column),tr(kw.get('text','')))
    def column(self,column,**kw):
        if 'width' in kw:self.q.setColumnWidth(self._col(column),int(kw['width']))
    def insert(self,parent,index,iid=None,**kw):
        iid=iid or 'item'+str(next(core._serial));item=W.QTreeWidgetItem();item.setData(0,Qt.ItemDataRole.UserRole,iid);self._items[iid]=item
        if parent:self._items[parent].addChild(item)
        else:self.q.addTopLevelItem(item)
        self.item(iid,**kw);return iid
    def item(self,iid,option=None,**kw):
        item=self._items[iid]
        if 'text' in kw:item.setText(0,str(kw['text']))
        if 'values' in kw:
            for i,value in enumerate(kw['values'],1):
                raw=str(value)
                item.setData(i,Qt.ItemDataRole.UserRole,raw)
                item.setText(i,tr(raw))
        if 'open' in kw:item.setExpanded(bool(kw['open']))
        if 'tags' in kw:
            tags=kw['tags'];tags=(tags,) if isinstance(tags,str) else tuple(tags);item.setData(0,Qt.ItemDataRole.UserRole+1,tags)
            for tag in tags:
                spec=self._tags.get(tag,{})
                for column in range(self.q.columnCount()):
                    if spec.get('foreground'):item.setForeground(column,G.QBrush(G.QColor(spec['foreground'])))
                    if spec.get('background'):item.setBackground(column,G.QBrush(G.QColor(spec['background'])))
        data=dict(text=item.text(0),values=tuple(item.data(i,Qt.ItemDataRole.UserRole) or item.text(i) for i in range(1,self.q.columnCount())),open=item.isExpanded(),tags=item.data(0,Qt.ItemDataRole.UserRole+1) or ())
        return data.get(option) if option else data
    def set(self,iid,column=None,value=None):
        if value is not None:
            item=self._items[iid]
            col=self._col(column)
            raw=str(value)
            if col:item.setData(col,Qt.ItemDataRole.UserRole,raw)
            item.setText(col,tr(raw) if col else raw)
        elif column is not None:
            item=self._items[iid]
            col=self._col(column)
            return (item.data(col,Qt.ItemDataRole.UserRole) if col else None) or item.text(col)
        else:return dict(zip(self._columns,self.item(iid,'values')))
    def exists(self,iid):return iid in self._items
    def get_children(self,parent=None):
        p=self._items.get(parent);return tuple((p.child(i) if p else self.q.topLevelItem(i)).data(0,Qt.ItemDataRole.UserRole) for i in range(p.childCount() if p else self.q.topLevelItemCount()))
    def delete(self,*ids):
        for iid in ids:
            if isinstance(iid,(tuple,list)):self.delete(*iid);continue
            if iid not in self._items:continue
            self.delete(*self.get_children(iid));item=self._items.pop(iid);p=item.parent()
            if p:p.takeChild(p.indexOfChild(item))
            else:self.q.takeTopLevelItem(self.q.indexOfTopLevelItem(item))
    def move(self,iid,parent,index):
        item=self._items[iid];p=item.parent()
        if p:p.takeChild(p.indexOfChild(item))
        else:self.q.takeTopLevelItem(self.q.indexOfTopLevelItem(item))
        target=self._items.get(parent)
        if target:target.insertChild(target.childCount() if index=='end' else int(index),item)
        else:self.q.insertTopLevelItem(self.q.topLevelItemCount() if index=='end' else int(index),item)
    def set_hidden(self,iid,hidden):
        self._items[iid].setHidden(hidden)

    def detach(self,iid):
        item=self._items[iid];p=item.parent()
        if p:p.takeChild(p.indexOfChild(item))
        else:self.q.takeTopLevelItem(self.q.indexOfTopLevelItem(item))
    def parent(self,iid):
        p=self._items[iid].parent();return p.data(0,Qt.ItemDataRole.UserRole) if p else ''
    def index(self,iid):
        item=self._items[iid];parent=item.parent();return parent.indexOfChild(item) if parent else self.q.indexOfTopLevelItem(item)
    def selection(self):return tuple(item.data(0,Qt.ItemDataRole.UserRole) for item in self.q.selectedItems())
    def selection_set(self,*ids):
        ids=ids[0] if len(ids)==1 and isinstance(ids[0],(tuple,list,set)) else ids;blocker=C.QSignalBlocker(self.q);self.q.clearSelection()
        for iid in ids:
            if iid in self._items:self._items[iid].setSelected(True)
    def selection_remove(self,*ids):
        for iid in ids:
            if iid in self._items:self._items[iid].setSelected(False)
    def selection_add(self,*ids):
        for iid in ids:
            if iid in self._items:self._items[iid].setSelected(True)
    def focus(self,iid=None):
        if iid is not None:self.q.setCurrentItem(self._items[iid])
        elif self.q.currentItem():return self.q.currentItem().data(0,Qt.ItemDataRole.UserRole)
        else:return ''
    def see(self,iid):self.q.scrollToItem(self._items[iid])
    def identify_row(self,y):
        item=self.q.itemAt(8,int(y));return item.data(0,Qt.ItemDataRole.UserRole) if item else ''
    def identify_column(self,x):return '#'+str(self.q.columnAt(int(x)))
    def identify_region(self,x,y):return 'tree' if self.q.itemAt(int(x),int(y)) else 'nothing'
    def bbox(self,iid,column=None):
        r=self.q.visualItemRect(self._items[iid]);return (r.x(),r.y(),r.width(),r.height())
    def tag_configure(self,tag,**kw):
        self._tags[tag]=kw
        for iid,item in self._items.items():
            tags=item.data(0,Qt.ItemDataRole.UserRole+1) or ()
            if tag in tags:self.item(iid,tags=tags)
    tag_config=tag_configure

class Listbox(Scrollable,Widget):
    native=W.QListWidget;class_name='Listbox'
    def configure(self,cnf=None,**kw):
        super().configure(cnf,**kw);self.q.setSelectionMode(W.QAbstractItemView.SelectionMode.MultiSelection)
    def insert(self,index,text):self.q.insertItem(self.q.count() if index=='end' else int(index),str(text))
    def curselection(self):return tuple(self.q.row(item) for item in self.q.selectedItems())
    def selection_set(self,first,last=None):
        for i in range(int(first),int(last)+1 if last not in (None,'end') else self.q.count() if last=='end' else int(first)+1):self.q.item(i).setSelected(True)
    def get(self,index):return self.q.item(int(index)).text()

class Text(Scrollable,Widget):
    native=W.QTextEdit;class_name='Text'
    def __init__(self,*args,**kw):self._tags={};self._links={};super().__init__(*args,**kw)
    def configure(self,cnf=None,**kw):
        super().configure(cnf,**kw)
        if 'state' in kw:self.q.setEnabled(True);self.q.setReadOnly(kw['state']=='disabled')
    def insert(self,index,value,tags=None):
        cursor=self.q.textCursor();cursor.movePosition(G.QTextCursor.MoveOperation.End);fmt=G.QTextCharFormat()
        for tag in (tags,) if isinstance(tags,str) else tags or ():
            spec=self._tags.get(tag,{})
            if spec.get('font'):fmt.setFont(font(spec['font']))
            if spec.get('foreground'):fmt.setForeground(G.QColor(spec['foreground']))
            if spec.get('background'):fmt.setBackground(G.QColor(spec['background']))
            if spec.get('underline'):fmt.setFontUnderline(True)
        cursor.insertText(str(value),fmt);self.q.setTextCursor(cursor)
    def delete(self,first,last=None):self.q.clear()
    def get(self,first='1.0',last='end'):return self.q.toPlainText()
    def index(self,index):return str(self.q.document().characterCount())
    def tag_configure(self,tag,**kw):self._tags[tag]=kw
    tag_config=tag_configure
    def tag_bind(self,tag,event,callback):self._links[tag]=callback
    def image_create(self,index,**kw):
        photo=kw['image'];cursor=self.q.textCursor();cursor.movePosition(G.QTextCursor.MoveOperation.End);name='img'+str(next(core._serial));self.q.document().addResource(G.QTextDocument.ResourceType.ImageResource,C.QUrl(name),photo.pixmap.toImage());cursor.insertImage(name)
    def see(self,index):self.q.ensureCursorVisible()

def parent_q(kwargs):
    value=kwargs.pop('parent',None);return value.q if value else core._root.q if core._root else None
class Dialogs:
    def askopenfilename(self,**kw):
        parent=parent_q(kw);return W.QFileDialog.getOpenFileName(parent,tr(kw.get('title','打开工程')),kw.get('initialdir',''),filters(kw.get('filetypes',[])))[0]
    def asksaveasfilename(self,**kw):
        parent=parent_q(kw);path=W.QFileDialog.getSaveFileName(parent,tr(kw.get('title','保存文件')),str(Path(kw.get('initialdir',''))/kw.get('initialfile','')),filters(kw.get('filetypes',[])))[0];extension=kw.get('defaultextension','')
        return path+extension if path and extension and not Path(path).suffix else path
    def askdirectory(self,**kw):return W.QFileDialog.getExistingDirectory(parent_q(kw),tr(kw.get('title','选择文件夹')),kw.get('initialdir',''))
def filters(values):return ';;'.join(tr(str(name))+' ('+(' '.join(pattern) if isinstance(pattern,(list,tuple)) else str(pattern))+')' for name,pattern in values)
class Messages:
    def showerror(self,title,message,**kw):return W.QMessageBox.critical(parent_q(kw),tr(title),tr(str(message)))
    def showwarning(self,title,message,**kw):return W.QMessageBox.warning(parent_q(kw),tr(title),tr(str(message)))
    def showinfo(self,title,message,**kw):return W.QMessageBox.information(parent_q(kw),tr(title),tr(str(message)))
    def askyesno(self,title,message,**kw):return W.QMessageBox.question(parent_q(kw),tr(title),tr(str(message)),W.QMessageBox.StandardButton.Yes|W.QMessageBox.StandardButton.No)==W.QMessageBox.StandardButton.Yes
    def askokcancel(self,title,message,**kw):return W.QMessageBox.question(parent_q(kw),tr(title),tr(str(message)),W.QMessageBox.StandardButton.Ok|W.QMessageBox.StandardButton.Cancel)==W.QMessageBox.StandardButton.Ok
    def askyesnocancel(self,title,message,**kw):
        answer=W.QMessageBox.question(parent_q(kw),tr(title),tr(str(message)),W.QMessageBox.StandardButton.Yes|W.QMessageBox.StandardButton.No|W.QMessageBox.StandardButton.Cancel);return None if answer==W.QMessageBox.StandardButton.Cancel else answer==W.QMessageBox.StandardButton.Yes
class SimpleDialogs:
    def askstring(self,title,prompt,**kw):
        text,ok=W.QInputDialog.getText(parent_q(kw),tr(title),tr(prompt),text=str(kw.get('initialvalue','')));return text if ok else None
    def askinteger(self,title,prompt,**kw):
        value,ok=W.QInputDialog.getInt(parent_q(kw),tr(title),tr(prompt),int(kw.get('initialvalue',0)),kw.get('minvalue',-2147483647),kw.get('maxvalue',2147483647));return value if ok else None
    def askfloat(self,title,prompt,**kw):
        value,ok=W.QInputDialog.getDouble(parent_q(kw),tr(title),tr(prompt),float(kw.get('initialvalue',0)));return value if ok else None
class Colors:
    def askcolor(self,color=None,**kw):
        value=W.QColorDialog.getColor(G.QColor(color or '#ffffff'),parent_q(kw),tr(kw.get('title','选择颜色')));return ((value.red(),value.green(),value.blue()),value.name()) if value.isValid() else (None,None)
filedialog=Dialogs();messagebox=Messages();simpledialog=SimpleDialogs();colorchooser=Colors()
