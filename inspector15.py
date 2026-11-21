"""Tabbed, independently scrollable property groups for every component."""
import qt_compat as tk
from qt_compat import ttk
from qt_widgets21 import PropertyScrollArea
CATEGORIES=('基本','几何','标记','外观','关联','操作')
def category(title):
    for result,keys in [('外观',('颜色','样式','底色','描边','显示','线型')),('关联',('组织','关联','组合','绑定','分组','所属')),('标记',('标志','标记','编号','停止','机型','入口','中心圆','引入')),('几何',('几何','尺寸','长度','位置','曲率','半径','坐标','圆角','顶点','截去','末端','转向'))]:
        if any(k in title for k in keys):return result
    return '基本'
class PropertyBook:
    def __init__(self,parent,selected='基本'):
        self.notebook=ttk.Notebook(parent);self.notebook.q.setProperty('acRole','inspectorTabs');self.notebook.pack(fill='both',expand=True,padx=4,pady=4);self.pages={};self.canvases={};self.fields={}
        for name in CATEGORIES:
            scroll = PropertyScrollArea(self.notebook)
            scroll.q.setProperty('acRole','inspectorPage')
            scroll.q.viewport().setProperty('acRole','inspectorViewport')
            body = ttk.Frame(scroll)
            body.q.setProperty('acRole','inspectorFields')
            scroll.set_body(body)
            self.notebook.add(scroll, text=name)
            self.pages[name] = body
            self.canvases[name] = scroll
        self.notebook.select(CATEGORIES.index(selected) if selected in CATEGORIES else 0)
    def section(self,title):
        frame=ttk.LabelFrame(self.pages[category(title)],text=title,padding=8);frame.pack(fill='x',padx=4,pady=5);frame.columnconfigure(1,weight=1);return frame
    def current(self):return CATEGORIES[self.notebook.index(self.notebook.select())]
    def field_parent(self,parent,key):
        key=key.removeprefix('_draft_')
        if key in ('_segment_name20_16','_segment_pick20_16'):name=CATEGORIES[0]
        elif key in ('name','group','configuration','source_note'):name='基本'
        elif key.startswith(('guide_','straight_')):name='标记'
        elif any(x in key for x in ('color','outline','visible','background','spacing','line_width')):name='外观'
        elif any(x in key for x in ('entry','attached','parent','asset','group','container','excludes','bind','_axis','_terminal')):name='关联'
        elif any(x in key for x in ('lead','stop','number','aircraft','suffix','circle','guidance','temporary','label')):name='标记'
        else:name='几何'
        try:title=parent.cget('text')
        except tk.TclError:title='参数'
        cache=(name,title)
        if cache not in self.fields:
            f=ttk.LabelFrame(self.pages[name],text=title,padding=8);f.pack(fill='x',padx=4,pady=5);f.columnconfigure(1,weight=1);self.fields[cache]=f
        return self.fields[cache]
    def tidy(self):
        for page in self.pages.values():
            for child in page.winfo_children():
                if isinstance(child,ttk.LabelFrame) and not child.winfo_children():child.destroy()
    def actions(self,parent):
        for widget in parent.winfo_children():
            if widget is self.notebook:continue
            try:widget.pack(in_=self.pages['操作'],fill='x',padx=6,pady=4)
            except tk.TclError:pass
