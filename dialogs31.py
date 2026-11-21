"""Native Qt views for project review and airport-wide marking configuration."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,QDialog,QFrame,QHeaderView,QHBoxLayout,QLabel,
    QPushButton,QRadioButton,QTabWidget,QTreeWidget,QTreeWidgetItem,QVBoxLayout,
)


def heading(text,description,layout):
    title=QLabel(text)
    title.setProperty('acRole','dialogHeading')
    layout.addWidget(title)
    label=QLabel(description)
    label.setWordWrap(True)
    layout.addWidget(label)


def footer(layout,*buttons):
    row=QHBoxLayout()
    row.setSpacing(8)
    row.addStretch()
    for button in buttons:
        button.setMinimumWidth(94)
        row.addWidget(button)
    buttons[-1].setProperty('acRole','primaryAction')
    layout.addLayout(row)


def button(text,callback):
    item=QPushButton(text)
    item.clicked.connect(callback)
    return item


def review(editor):
    from scene_rules import validate_scene
    window=getattr(editor,'_review31',None)
    if window is None:
        window=editor._review31=QDialog(editor.q)
        window.setWindowTitle('机场工程审阅')
        window.resize(1030,640)
        layout=QVBoxLayout(window)
        layout.setContentsMargins(20,18,20,16)
        layout.setSpacing(12)
        heading('机场工程审阅','双击条目定位到图上的对象。',layout)
        tabs=QTabWidget()
        layout.addWidget(tabs,1)
        trees=[]
        for name in ('问题','待核'):
            tree=QTreeWidget()
            tree.setHeaderLabels(['状态','对象','规则','说明'])
            tree.setRootIsDecorated(False)
            tree.setUniformRowHeights(True)
            tree.setAlternatingRowColors(True)
            header=tree.header()
            header.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            header.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            header.setStretchLastSection(False)
            for col,width in enumerate((112,135,180,570)):
                tree.setColumnWidth(col,width)
            tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            tree.setHorizontalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)
            tree.itemDoubleClicked.connect(lambda item,column:locate(item))
            tabs.addTab(tree,name)
            trees.append(tree)
        def locate(item):
            oid=item.data(0,Qt.ItemDataRole.UserRole)
            if oid:
                editor.select(oid)
                editor.focus_selected()
                editor.q.raise_()
        def refresh():
            with editor.processing('正在审查机场工程'):
                editor.report=validate_scene(editor.scene)
                for tree in trees:tree.clear()
                for issue in editor.report['issues']:
                    status=issue['status']
                    if status in ('PASS','NOT_APPLICABLE'):continue
                    oid=issue['object_id']
                    a=editor.scene.assets.get(oid) or editor.scene.movements.get(oid) or {}
                    labels={'FAIL':'问题','REVIEW_REQUIRED':'需复核','UNKNOWN':'资料不足','UNVERIFIED':'待验证'}
                    row=QTreeWidgetItem([labels.get(status,status),a.get('name',''),issue['rule'],issue['message']])
                    row.setData(0,Qt.ItemDataRole.UserRole,oid)
                    row.setToolTip(3,issue['message'])
                    trees[0 if status=='FAIL' else 1].addTopLevelItem(row)
                for i,name in enumerate(('问题','待核')):tabs.setTabText(i,f'{name} · {trees[i].topLevelItemCount()}')
        window.refresh_report=refresh
        footer(layout,button('关闭',window.close),button('刷新审阅',refresh),button('导出报告',editor.export_report))
    window.refresh_report()
    window.show()
    from qt_theme21 import native_caption
    native_caption(window,getattr(editor,'_dark_mode24',False))
    window.raise_()


def no_entry_settings(editor):
    import model20
    import styles19
    try:
        with editor.processing('正在检查 NO ENTRY 可用宽度'):
            rows=model20.no_entry_limits(editor.scene)
    except ValueError as exc:
        editor.status.set(str(exc))
        return
    standard=styles19.standard_no_entry_height(editor.scene)
    maximum=min((row['maximum'] for row in rows),default=standard)
    names='、'.join(sorted({row['name'] for row in rows if abs(row['maximum']-maximum)<.001}))
    window=QDialog(editor.q)
    window.setWindowTitle('全机场 NO ENTRY 字高')
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    window.setMinimumWidth(510)
    layout=QVBoxLayout(window)
    layout.setContentsMargins(22,20,22,16)
    layout.setSpacing(12)
    heading('统一 NO ENTRY 字高','为工程中的禁止驶入地面标记统一字高。',layout)
    details=QFrame()
    details.setProperty('acRole','dialogSummary')
    fields=QVBoxLayout(details)
    fields.setContentsMargins(13,9,13,9)
    for text in (f'{len(rows)} 处标记    ·    指标字高 {standard:g} m    ·    最窄处 {maximum:.2f} m',
                 '限制位置 '+(names or '无')):
        label=QLabel(text)
        label.setWordWrap(True)
        fields.addWidget(label)
    layout.addWidget(details)
    group=QButtonGroup(window)
    for index,(key,text) in enumerate((
        ('STANDARD','按指标字高统一，保留空间不足的位置供审阅'),
        ('FIT','按最窄处统一，低于指标字高时列入审阅'),
    )):
        choice=QRadioButton(text)
        group.addButton(choice,index)
        choice.setChecked(editor.scene.data['meta'].get('no_entry_mode20','STANDARD')==key)
        layout.addWidget(choice)
    error=QLabel()
    error.setWordWrap(True)
    error.hide()
    layout.addWidget(error)
    def apply():
        try:
            with editor.processing('正在统一禁止驶入标记字高'):
                report=model20.uniform_no_entry(editor.scene,'FIT' if group.checkedId()==1 else 'STANDARD')
                editor.refresh()
            editor.status.set(f'已统一 {report["count"]} 处 NO ENTRY，字高 {report["height"]:.2f} m')
            window.accept()
        except ValueError as exc:
            error.setText(str(exc))
            error.show()
    footer(layout,button('取消',window.reject),button('应用字高',apply))
    window.open()
    from qt_theme21 import native_caption
    native_caption(window,getattr(editor,'_dark_mode24',False))
