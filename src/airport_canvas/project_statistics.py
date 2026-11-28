"""Project-wide object and fixture counts."""
from collections import Counter, defaultdict

from airport_scene import AirportScene
from automatic_markings import generated_markings
from interface_language import tr
import lighting_model
from marking_catalog import CATALOG
from qt_core21 import C, W, Qt


OBJECT_NAMES = {
    'RUNWAY': ('跑道', 'Runways'), 'TAXIWAY': ('滑行道', 'Taxiways'),
    'APRON_TAXIWAY': ('机坪滑行道', 'Apron taxiways'),
    'STAND_TAXILANE': ('机位滑行通道', 'Aircraft stand taxilanes'),
    'STAND': ('机位', 'Aircraft stands'), 'ROAD': ('服务车道', 'Service roads'),
    'APRON': ('机坪', 'Aprons'), 'PROTECTION': ('保护区', 'Protected areas'),
    'CLOSED_AREA': ('关闭区域', 'Closed areas'), 'EQUIPMENT': ('设施', 'Equipment'),
    'TERMINAL': ('航站楼', 'Terminals'), 'PIER': ('指廊', 'Piers'),
    'BRIDGE': ('廊桥', 'Passenger boarding bridges'),
    'REMOTE_STAND': ('远机位', 'Remote stands'), 'HELIPAD': ('直升机坪', 'Helipads'),
    'GA_STAND': ('通航机位', 'General aviation stands'), 'OTHER': ('其他建筑', 'Other buildings'),
}


def count_project(data, multicore):
    scene = AirportScene(data)
    scene.multicore_enabled = multicore
    generated = generated_markings(scene)
    objects, markings = Counter(), Counter()
    fixture_positions = defaultdict(set)
    for asset in scene.assets.values():
        kind, props = asset['kind'], asset['props']
        if kind == 'MARKING':
            markings[props['mark_type']] += 1
            continue
        if kind == 'STAND':
            if props.get('helicopter_stand'):
                kind = 'HELIPAD'
            elif props.get('ga_stand'):
                kind = 'GA_STAND'
            elif props.get('remote_stand'):
                kind = 'REMOTE_STAND'
        objects[props.get('building_role19') or kind] += 1
    markings.update(asset['props']['mark_type'] for asset in generated.values())
    connections = Counter(movement.get('role', 'UNKNOWN') for movement in scene.movements.values())
    symbols = Counter(item['kind'] for item in
                      scene.data['meta'].get('chart_f8', {}).get('symbols', {}).values())
    for row in lighting_model.plan_rows(scene, generated):
        kind, options = row[3], row[-1]
        if not options.get('enabled', True):
            continue
        for point, color, _, _ in lighting_model.fixtures(row):
            if kind == 'runway_hold' and color == lighting_model.YELLOW:
                fixture_kind = 'runway_guard'
            elif kind == 'guard':
                fixture_kind = 'runway_guard'
            elif kind == 'stop_bar' or options.get('configuration') == 'STOP':
                fixture_kind = 'runway_hold'
            else:
                fixture_kind = kind
            # Directional faces and repeated endpoints can share one fixture.
            fixture_positions[fixture_kind].add(tuple(round(value, 4) for value in point))
    fixtures = {kind: len(points) for kind, points in fixture_positions.items()}
    return objects, connections, markings, symbols, fixtures


class ProjectStatistics(W.QDockWidget):
    def __init__(self, app):
        super().__init__(tr('统计信息'), app.q)
        self.setObjectName('projectStatistics')
        self.app = app
        self.revision = None
        self.pending = None
        self.tree = W.QTreeWidget()
        self.tree.setHeaderLabels([tr('部件类型'), tr('数量')])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, W.QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, W.QHeaderView.ResizeMode.ResizeToContents)
        widget = W.QWidget()
        layout = W.QVBoxLayout(widget)
        self.status = W.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(self.tree)
        self.setWidget(widget)
        self.timer = C.QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.refresh)
        self.visibilityChanged.connect(self.visibility_changed)
        app.q.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self)
        self.hide()
        app.display_menu14.q.addAction(self.toggleViewAction())

    def visibility_changed(self, visible):
        if visible:
            self.timer.start()
            self.refresh()
        else:
            self.timer.stop()

    def refresh(self):
        import copy
        scene = self.app.scene
        key = (scene, scene.revision)
        if self.pending:
            pending_key, future = self.pending
            if not future.done():
                return
            self.pending = None
            if key == pending_key:
                self.revision = key
                try:
                    self.show_counts(future.result())
                except Exception as exc:
                    self.status.setText(f"{tr('统计计算失败')} · {exc}")
        if key != self.revision:
            self.tree.clear()
            self.status.setText(tr('正在统计工程部件和灯具…'))
            self.pending = (key, self.app._executor.submit(
                count_project, copy.deepcopy(scene.data), self.app.multicore_enabled))

    def show_counts(self, counts):
        from interface_language import language
        labels = {key: name[language != 'zh_CN'] for key, name in OBJECT_NAMES.items()}
        lights = {key: item[0] for key, item in lighting_model.CUSTOM.items()}
        lights.update(lighting_model.NAMES)
        groups = (
            ('机场部件', labels), ('连接关系', {}), ('标志与标记牌', {
                key: item['name'] for key, item in CATALOG.items()}),
            ('已布置航图符号', {}), ('灯具（盏）', lights),
        )
        self.tree.clear()
        for (title, names), group in zip(groups, counts):
            parent = W.QTreeWidgetItem(self.tree, [tr(title), str(sum(group.values()))])
            rows = sorted((tr(names.get(kind, kind)), count) for kind, count in group.items())
            for label, count in rows:
                W.QTreeWidgetItem(parent, [label, str(count)])
            parent.setExpanded(True)
        self.status.setText(tr('统计范围为整个工程。灯具按启用的布设方案计数，包含临时关闭区域。'))
