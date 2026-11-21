"""Stand designation mapping and the remote stand tool icon."""
import re
from PySide6.QtCore import Qt,QPointF,QSize
from PySide6.QtGui import QColor,QIcon,QPainter,QPen,QPixmap
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QHeaderView,QLabel,QTableWidget,QTableWidgetItem,QVBoxLayout,QPushButton,QInputDialog


def remote_stand_icon():
    pixmap=QPixmap(QSize(24,24))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#598caa'),1.7))
    for y,inner in ((5,9),(19,15)):
        painter.drawLine(QPointF(3,y),QPointF(13,y))
        painter.drawLine(QPointF(13,y),QPointF(18,inner))
    painter.setPen(QPen(QColor('#eab554'),1.8))
    painter.drawLine(QPointF(2,12),QPointF(22,12))
    painter.drawLine(QPointF(10,9),QPointF(10,15))
    painter.end()
    return QIcon(pixmap)


def stand_overlap_icon():
    from PySide6.QtCore import QRectF
    pixmap=QPixmap(QSize(24,24))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#598caa'),1.6))
    painter.drawRoundedRect(QRectF(3,4,11,12),2,2)
    painter.drawRoundedRect(QRectF(10,8,11,12),2,2)
    painter.fillRect(QRectF(10,8,4,8),QColor('#eab554'))
    painter.end()
    return QIcon(pixmap)


def stand_number_key(value):
    value=str(value).casefold()
    if value.isdecimal():return (0,int(value),len(value),value)
    letters=''.join(char for char in value if char.isalpha())
    first=letters[:1]
    parts=tuple((0,int(part)) if part.isdecimal() else (1,part)
                for part in re.findall(r'\d+|\D+',value))
    return (1,first,parts,value)


def show_stand_names(app):
    scene=app.scene
    previous=app.__dict__.get('_stand_names65')
    if previous:
        previous.close()
    dialog=QDialog(app.q)
    app._stand_names65=dialog
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.destroyed.connect(lambda:setattr(app,'_stand_names65',None) if app._stand_names65 is dialog else None)
    dialog.setWindowTitle('机位命名')
    dialog.resize(470,520)
    layout=QVBoxLayout(dialog)
    layout.addWidget(QLabel('双击当前编号可定位机位。新编号留空时保留原编号。'))
    stands=sorted((a for a in scene.assets.values() if a['kind']=='STAND'),
                  key=lambda a:stand_number_key(a['props'].get('stand_number') or a['name']))
    ids=[a['id'] for a in stands]
    table=QTableWidget(len(stands),2,dialog)
    table.setHorizontalHeaderLabels(['当前编号','新编号'])
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    for row,stand in enumerate(stands):
        item=QTableWidgetItem(str(stand['props'].get('stand_number') or stand['name']))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row,0,item)
        table.setItem(row,1,QTableWidgetItem())
    layout.addWidget(table)
    status=QLabel()
    status.setWordWrap(True)
    layout.addWidget(status)
    quick=QPushButton('快速编号',dialog)
    quick.setCheckable(True)
    quick.setEnabled(bool(ids))
    layout.addWidget(quick)
    start=None

    def quick_mode(active):
        nonlocal start
        start=None
        status.setText('请点击「新编号」列的起始格。' if active else '')

    def quick_cell(row,column):
        nonlocal start
        if not quick.isChecked() or column!=1:return
        if start is None:
            initial=table.item(row,1).text().strip()
            value,ok=QInputDialog.getText(dialog,'快速编号','起始编号（例如 1、D1 或 D009）',text=initial)
            if not ok:return
            match=re.fullmatch(r'([A-Za-z]*)([0-9]{1,64})',value.strip())
            if not match:
                status.setText('请输入数字或字母前缀加数字，例如 D1。')
                return
            prefix,digits=match.groups()
            start=(row,prefix,int(digits),len(digits))
            status.setText('请点击「新编号」列的末尾格。')
            return
        first,prefix,number,width=start
        step=1 if row>=first else -1
        for offset,target in enumerate(range(first,row+step,step)):
            table.item(target,1).setText(prefix+str(number+offset).zfill(width))
        quick.setChecked(False)
        status.setText(f'已填充 {abs(row-first)+1} 个编号，点击确定应用。')

    quick.toggled.connect(quick_mode)
    table.cellClicked.connect(quick_cell)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)

    def locate(row,column):
        if column==0 and app.scene is scene and ids[row] in scene.assets:
            app.selection=ids[row]
            app.focus_selected()
            app.update_inspector()

    def apply():
        if app.scene is not scene or set(ids)!={a['id'] for a in scene.assets.values() if a['kind']=='STAND'}:
            status.setText('工程或机位列表已变化。请重新打开机位命名。')
            return
        updates={oid:table.item(row,1).text().strip() for row,oid in enumerate(ids) if table.item(row,1).text().strip()}
        current={oid:str(scene.assets[oid]['props'].get('stand_number') or scene.assets[oid]['name']) for oid in ids}
        updates={oid:name for oid,name in updates.items() if current[oid]!=name}
        if not updates:
            dialog.accept()
            return
        from collections import Counter
        counts=Counter(updates.get(oid,name).casefold() for oid,name in current.items())
        duplicates=sorted({name for name in updates.values() if counts[name.casefold()]>1})
        if duplicates:
            status.setText('编号重复：'+ '、'.join(duplicates))
            return
        from editor7_model import sync_name
        try:
            with scene.transaction('统一更新机位编号'):
                for oid,name in updates.items():
                    sync_name(scene,oid,name)
        except ValueError as exc:
            status.setText(str(exc))
            return
        app.refresh()
        dialog.accept()

    table.cellDoubleClicked.connect(locate)
    buttons.accepted.connect(apply)
    buttons.rejected.connect(dialog.reject)
    dialog.show()
