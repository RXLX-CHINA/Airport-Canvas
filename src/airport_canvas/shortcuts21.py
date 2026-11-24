"""Main-window shortcut definitions and per-user overrides."""
import json

from PySide6 import QtCore as C, QtGui as G, QtWidgets as W

from interface_language import tr
from qt_core21 import call

PORTABLE=G.QKeySequence.SequenceFormat.PortableText

# Identifier, legacy binding, default value, display name.
COMMANDS=(
    ('new','<Control-n>','Ctrl+N','新建工程'),
    ('open','<Control-o>','Ctrl+O','打开工程'),
    ('save','<Control-s>','Ctrl+S','保存工程'),
    ('undo','<Control-z>','Ctrl+Z','撤销'),
    ('redo','<Control-y>','Ctrl+Y','重做'),
    ('cut','<Control-x>','Ctrl+X','剪切对象'),
    ('copy','<Control-c>','Ctrl+C','复制对象'),
    ('paste','<Control-v>','Ctrl+V','粘贴对象'),
    ('duplicate','<Control-d>','Ctrl+D','制作对象副本'),
    ('merge_names','<Control-m>','Ctrl+M','合并路线编号'),
    ('delete','<Delete>','Delete','删除选中对象'),
    ('signs','<F5>','F5','标识与标记牌模式'),
    ('segments','<F6>','F6','彩色分段模式'),
    ('lighting','<F7>','F7','灯光模式'),
    ('chart','<F8>','F8','航图模式'),
    ('true_north',None,'Alt+N','真北朝上'),
    ('grid_north',None,'Alt+Return','工程网格朝上'),
    ('layer_transparency',None,'T','切换临时图层透明度'),
)
GLOBAL_COMMANDS={'new','open','save','undo','redo','signs','segments','lighting','chart','true_north','grid_north'}
FIXED=(
    ('Esc','取消工具或返回选择'),
    ('Enter','完成绘制或确认当前操作'),
    ('Space','按住后可用鼠标拖动画布'),
    ('Ctrl+Z / Ctrl+Y','航图排版窗口内撤销与重做'),
    ('Scroll wheel','缩放画布'),
    ('Middle / Right drag','平移画布'),
    ('Alt + Right drag','旋转画布'),
    ('Ctrl + click','增减选中对象'),
    ('Shift + drag','在支持的绘制或变换工具中约束方向或比例'),
)


def key_name(sequence):
    if sequence.count()!=1:return ''
    value=sequence.toString(PORTABLE)
    if value.endswith('Enter'):value=value[:-5]+'Return'
    return value


def normalize(values):
    result={}
    used={}
    for action,_,default,label in COMMANDS:
        raw=values.get(action,default)
        if not isinstance(raw,str):raise ValueError(tr('快捷键格式无效。'))
        if not raw.strip():
            result[action]=''
            continue
        sequence=G.QKeySequence.fromString(raw,PORTABLE)
        name=key_name(sequence)
        if not name or sequence[0].key() in (C.Qt.Key.Key_unknown,C.Qt.Key.Key_Shift,C.Qt.Key.Key_Control,C.Qt.Key.Key_Alt,C.Qt.Key.Key_Meta):
            raise ValueError(tr('快捷键必须是单个有效按键组合。'))
        if name in ('Esc','Return','Space','Tab','Backtab','Alt+F4','Alt+Space'):
            raise ValueError(tr('此按键由系统或其他编辑操作保留。')+' '+name)
        if name in used:
            raise ValueError(tr('快捷键冲突。')+f' {name}: {tr(used[name])} / {tr(label)}')
        used[name]=label
        result[action]=name
    return result


class Shortcuts:
    def __init__(self,app):
        self.app=app
        self.callbacks={}
        self.captions=[]
        for action,binding,_,_ in COMMANDS:
            if binding:
                self.callbacks[action]=tuple(app.bind(binding))
                app.unbind(binding)
        view=app.view_tools21_2
        for action,native in [('true_north',view.north_action),('grid_north',view.grid_action)]:
            native.setShortcuts([])
            self.callbacks[action]=(lambda event,native=native:native.trigger(),)
        self.callbacks['layer_transparency']=(lambda event:app.toggle_layer_transparency(),)
        from user_settings34 import read
        config=read(app._preferences34)
        try:
            values=json.loads(config.get('shortcuts','bindings',fallback='{}'))
            self.apply(values if isinstance(values,dict) else {})
        except ValueError:
            self.apply({})

    def apply(self,values):
        self.values=normalize(values)
        self.by_key={key:action for action,key in self.values.items() if key}
        for action,set_caption,caption in self.captions:
            key=self.values[action].replace('Return','Enter')
            set_caption(f'{caption}  {key}' if key else caption)

    def sync_captions(self):
        defaults={default.replace('Return','Enter'):action for action,_,default,_ in COMMANDS}
        for item in self.app.q.findChildren(G.QAction):
            self.capture_caption(item.text(),item.setText,defaults)
        for item in self.app.q.findChildren(W.QAbstractButton):
            self.capture_caption(item.toolTip(),item.setToolTip,defaults)
        self.apply(self.values)

    def capture_caption(self,caption,set_caption,defaults):
        for key,action in defaults.items():
            for separator in (' ', '\t', ' · '):
                if caption.endswith(separator+key):
                    self.captions.append((action,set_caption,caption[:-len(separator+key)].rstrip(' ·')))
                    return

    def dispatch(self,event,wrapper,context):
        combo=event.keyCombination()
        modifiers=combo.keyboardModifiers() & ~C.Qt.KeyboardModifier.KeypadModifier
        name=key_name(G.QKeySequence(C.QKeyCombination(modifiers,combo.key())))
        action=self.by_key.get(name)
        if action is None:return False
        editing=wrapper.winfo_class() in ('Entry','Combobox','Text','Spinbox')
        if editing and (action not in GLOBAL_COMMANDS or (event.text() and event.text().isprintable())):return False
        if editing and name in ('Ctrl+C','Ctrl+X','Ctrl+V','Delete','Backspace'):return False
        if action=='delete' and wrapper not in (self.app.canvas,self.app.tree):return False
        if not event.isAutoRepeat():
            for callback in self.callbacks[action]:
                if call(callback,context)=='break':break
        return True

    def dialog(self):
        dialog=W.QDialog(self.app.q)
        dialog.setWindowTitle(tr('自定义快捷键'))
        dialog.resize(680,600)
        layout=W.QVBoxLayout(dialog)
        layout.addWidget(W.QLabel(tr('点击按键栏并按下新组合。清空后可禁用该命令快捷键。保存后立即生效。')))
        table=W.QTableWidget(len(COMMANDS),3)
        table.setHorizontalHeaderLabels([tr('命令'),tr('默认快捷键'),tr('当前快捷键')])
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(0,W.QHeaderView.ResizeMode.Stretch)
        editors={}
        for row,(action,_,default,label) in enumerate(COMMANDS):
            for col,value in enumerate((tr(label),default)):
                item=W.QTableWidgetItem(value)
                item.setFlags(C.Qt.ItemFlag.ItemIsEnabled|C.Qt.ItemFlag.ItemIsSelectable)
                table.setItem(row,col,item)
            editor=editors[action]=W.QKeySequenceEdit(G.QKeySequence.fromString(self.values[action],PORTABLE))
            editor.setMaximumSequenceLength(1)
            editor.setClearButtonEnabled(True)
            table.setCellWidget(row,2,editor)
        layout.addWidget(table)
        fixed=W.QLabel('\n'.join(f'{tr(key)}  ·  {tr(label)}' for key,label in FIXED))
        fixed.setWordWrap(True)
        layout.addWidget(fixed)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Save|W.QDialogButtonBox.StandardButton.Cancel|W.QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.button(W.QDialogButtonBox.StandardButton.Save).setText(tr('保存'))
        buttons.button(W.QDialogButtonBox.StandardButton.Cancel).setText(tr('取消'))
        reset=buttons.button(W.QDialogButtonBox.StandardButton.RestoreDefaults)
        reset.setText(tr('恢复默认'))
        layout.addWidget(buttons)

        def defaults():
            for action,_,default,_ in COMMANDS:
                editors[action].setKeySequence(G.QKeySequence.fromString(default,PORTABLE))

        def save():
            from user_settings34 import read,write
            try:
                keys=normalize({key:edit.keySequence().toString(PORTABLE) for key,edit in editors.items()})
                config=read(self.app._preferences34)
                if 'shortcuts' not in config:config.add_section('shortcuts')
                config['shortcuts']['bindings']=json.dumps(keys)
                write(config,self.app._preferences34)
            except (ValueError,OSError) as exc:
                W.QMessageBox.warning(dialog,tr('无法保存快捷键'),str(exc))
                return
            self.apply(keys)
            dialog.accept()

        reset.clicked.connect(defaults)
        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()
