"""Restrained light workstation theme, native focus, contrast and DPI scaling."""
from qt_core21 import application
STYLE='''
QMainWindow, QWidget { background:#f4f6f9; color:#253649; font-family:"Segoe UI","Microsoft YaHei UI"; font-size:13px; }
QMenuBar { background:#ffffff; border-bottom:1px solid #dce3eb; padding:5px 8px; }
QMenuBar::item { padding:6px 10px; background:transparent; border-radius:4px; }
QMenuBar::item:selected,QMenu::item:selected { background:#e3f2f7; color:#075d78; }
QMenu { background:#ffffff; padding:6px; border:1px solid #d9e2ec; }
QMenu::item { padding:7px 25px 7px 18px; border-radius:4px; }
QPushButton { background:#ffffff; border:1px solid #d4dee8; border-radius:6px; padding:6px 9px; min-height:19px; }
QPushButton:hover { background:#edf8fc; border-color:#81b9ce; }
QPushButton:pressed { background:#dceff6; }
QPushButton[acStyle="Selected.Tool.TButton"] { background:#d9f0f6; border:1px solid #279ab7; color:#086b87; }
QPushButton[acStyle="Category11.TButton"] { background:#e8eef5; color:#334b65; text-align:left; font-weight:600; border:none; }
QPushButton[acStyle="Item11.TButton"] { background:transparent; text-align:left; border:1px solid transparent; }
QPushButton[acStyle="Item11.TButton"]:hover { background:#e0f0f7; border-color:#d0e4ef; }
QPushButton[acRole="paletteTool"], QPushButton[acRole="paletteHeading"] { text-align:left; border-color:transparent; background:transparent; border-radius:5px; padding:6px 8px; }
QPushButton[acRole="paletteTool"]:hover { background:#e0eff7; }
QPushButton[acRole="paletteTool"][acStyle="Selected.Tool.TButton"] { background:#d5edf5; border-color:#93c8d9; color:#076b85; }
QPushButton[acRole="paletteHeading"] { background:#e5edf5; font-weight:600; color:#526c83; }
QLabel { background:transparent; }
QLabel[acRole="dialogHeading"] { font-size:20px; font-weight:650; }
QFrame[acRole="dialogSummary"] { background:#e8eef5; border:1px solid #dce3eb; border-radius:7px; }
QPushButton[acRole="primaryAction"] { background:#086b87; color:#ffffff; border:1px solid transparent; }
QPushButton[acRole="primaryAction"]:hover { background:#08758f; }
QTreeWidget[alternatingRowColors="true"] { alternate-background-color:#f5f7fa; }
QWidget[acRole="banner"] { background:#1b3048; }
QWidget[acRole="navHeader"] { background:#d7e6ef; border-bottom:1px solid #a9bdcd; }
QLabel[acRole="navTitle"] { background:transparent; color:#25485d; font-weight:600; }
QPushButton[acRole="navClose"] { background:transparent; color:#355668; border:0; padding:0; min-height:0; font-size:18px; }
QPushButton[acRole="navClose"]:hover { background:#c5dce9; }
QLabel[acRole="inspectorTitle"] { font-size:15px; font-weight:600; padding:10px 8px; }
QLineEdit,QComboBox,QTextEdit { background:#ffffff; border:1px solid #d5dfe9; border-radius:5px; padding:5px 7px; selection-background-color:#c8eaf5; selection-color:#15374d; }
QLineEdit:focus,QComboBox:focus,QTextEdit:focus { border-color:#218dab; }
QComboBox::drop-down { border:none; width:22px; }
QComboBox QAbstractItemView { background:white; selection-background-color:#e1f1f7; padding:4px; }
QGroupBox { background:#ffffff; border:1px solid #e0e6ee; border-radius:7px; margin-top:18px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; color:#536b81; }
QTabWidget::pane { border:1px solid #dce4ee; background:#f5f7fa; border-radius:5px; }
QTabBar::tab { padding:8px 10px; background:#e8edf3; color:#637488; border-bottom:2px solid transparent; }
QTabBar::tab:selected { background:#ffffff; color:#08758f; border-bottom-color:#1596b5; }
QTreeWidget,QListWidget { background:#ffffff; border:1px solid #dce4ec; border-radius:5px; outline:none; }
QTreeWidget::item { min-height:27px; padding:2px; }
QTreeWidget::item:selected { background:#dceff6; color:#0c627e; }
QHeaderView::section { background:#edf2f7; padding:7px; color:#65778b; border:none; border-bottom:1px solid #dce4ec; }
QScrollBar:vertical { background:transparent; width:10px; margin:2px; }
QScrollBar::handle:vertical { background:#bac7d5; border-radius:4px; min-height:28px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QSplitter::handle { background:#e0e6ee; }
QProgressBar { background:#e1e9f0; border:none; border-radius:3px; max-height:7px; }
QProgressBar::chunk { background:#148fad; border-radius:3px; }
QToolTip { background:#21374c; color:#ffffff; border:1px solid #34536c; padding:3px 6px; font-size:12px; }
QWidget:disabled { color:#98a6b3; }
'''
def apply():application().setStyleSheet(STYLE)

DARK = {
    '#f4f6f9':'#15202a', '#253649':'#e1ebf2', '#ffffff':'#1d2b37',
    '#dce3eb':'#3d4d5b', '#e3f2f7':'#2c4759', '#075d78':'#9bdcef',
    '#d9e2ec':'#3e5060', '#d4dee8':'#465a69', '#edf8fc':'#2a4354',
    '#81b9ce':'#6093ab', '#dceff6':'#2b4557', '#d9f0f6':'#204b5a',
    '#086b87':'#a7e1f0', '#e8eef5':'#273744', '#334b65':'#c0d2e2',
    '#e0f0f7':'#2b4557', '#d0e4ef':'#455d6c', '#e0eff7':'#2a4557',
    '#d5edf5':'#234a5a', '#93c8d9':'#679bae', '#076b85':'#ace4f0',
    '#e5edf5':'#293c4d', '#526c83':'#c9d7e4', '#d5dfe9':'#435968',
    '#c8eaf5':'#3d626f', '#15374d':'#eff9fd', '#e1f1f7':'#38586a', '#dce4ec':'#3b4d5e',
    '#e0e6ee':'#405564', '#536b81':'#b9cedd', '#dce4ee':'#3a4c5c',
    '#f5f7fa':'#192733', '#e8edf3':'#293b47', '#637488':'#b3c6d7',
    '#08758f':'#a9e6f1', '#0c627e':'#b3e6f1',
    '#edf2f7':'#283b49', '#65778b':'#bdcddd',
    '#bac7d5':'#607787', '#98a6b3':'#96a7b5',
}


def window_theme(editor,dark):
    import re
    from qt_core21 import G
    dark=bool(dark)
    if getattr(editor,'_dark_mode24',None)==dark:return
    editor._dark_mode24=dark
    if not dark:
        editor.q.setStyleSheet('')
    else:
        style=re.sub(r'#[a-f0-9]{6}',lambda m:DARK.get(m[0],m[0]),STYLE)
        style=style.replace('background:white','background:#1d2b37')
        style += '''
        QWidget[acRole="banner"] { background:#17202b; }
        QWidget[acRole="navHeader"] { background:#202e3f; border-bottom:1px solid #526c82; }
        QLabel[acRole="navTitle"], QPushButton[acRole="navClose"] { color:#e1ebf2; }
        QPushButton[acRole="navClose"]:hover { background:#394e62; }
        QWidget[acRole="palette"], QScrollArea { background:#19232f; }
        QTabWidget[acRole="inspectorTabs"], QScrollArea[acRole="inspectorPage"],
        QWidget[acRole="inspectorViewport"], QWidget[acRole="inspectorFields"] { background:#19232f; }
        QTabWidget[acRole="inspectorTabs"]::pane { background:#19232f; border-color:#344658; }
        QPushButton[acRole="primaryAction"] { background:#267083; color:#eff9fd; }
        QPushButton[acRole="primaryAction"]:hover { background:#33869b; }
        QComboBox QAbstractItemView { color:#e1ebf2; background:#1d2b37; selection-background-color:#38586a; selection-color:#eef7ff; }
        QComboBox QLineEdit { background:#1d2b37; color:#e1ebf2; border:0; }
        QComboBox::drop-down { background:#263949; border-top-right-radius:5px; border-bottom-right-radius:5px; }
        QTabBar::tab:selected { background:#243746; color:#a9e6f1; border-bottom:2px solid #54b9cd; }
        QCheckBox::indicator, QRadioButton::indicator { background:#192734; border:1px solid #607585; }
        QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#5dbace; border:2px solid #192734; }
        QRadioButton::indicator { border-radius:6px; }
        QToolTip { color:#eef6fc; background:#28394a; border-color:#3f566c; }
        '''
        editor.q.setStyleSheet(style)
    native_caption(editor.q,dark)
    editor.canvas.q.setBackgroundBrush(G.QColor('#131d27' if dark else '#e9eef2'))
    if getattr(editor,'property_canvas',None):
        from qt_core21 import W
        canvas=editor.property_canvas.q
        body=editor.property_body.q
        base='#19232f' if dark else '#f0f3f6'
        canvas.setBackgroundBrush(G.QColor(base))
        # The inspector is hosted inside a graphics proxy and owns its styling boundary.
        body.setStyleSheet(style if dark else STYLE)
        for widget in (canvas.viewport(),body,*body.findChildren(W.QScrollArea)):
            target=widget.viewport() if isinstance(widget,W.QScrollArea) else widget
            palette=target.palette()
            for role in (G.QPalette.ColorRole.Window,G.QPalette.ColorRole.Base):
                palette.setColor(role,G.QColor(base))
            target.setPalette(palette)
            target.setAutoFillBackground(True)
    if getattr(editor,'minimap',None):
        editor.minimap.q.setBackgroundBrush(G.QColor('#253442' if dark else '#eef4f7'))
        editor._nav_key=None



def native_caption(window,dark):
    import sys
    if sys.platform!='win32':return
    import ctypes as ct
    from ctypes import wintypes
    from qt_core21 import application
    if application().platformName()!='windows':return
    def colorref(rgb):
        red,green,blue=rgb
        return red | green<<8 | blue<<16
    setter=ct.windll.dwmapi.DwmSetWindowAttribute
    setter.argtypes=(wintypes.HWND,wintypes.DWORD,ct.c_void_p,wintypes.DWORD)
    setter.restype=ct.c_long
    hwnd=int(window.winId())
    def apply(attribute,value):
        setting=ct.c_uint(value)
        return setter(hwnd,attribute,ct.byref(setting),ct.sizeof(setting))
    if apply(20,int(dark))!=0:apply(19,int(dark))
    apply(35,colorref((23,32,43) if dark else (232,238,245)))
    apply(36,colorref((225,235,242) if dark else (37,54,73)))
