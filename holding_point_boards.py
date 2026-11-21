"""Project HP signs and pavement legends attached to intermediate holds."""
SIDES = {'BOTH':'两侧', 'LEFT':'左侧', 'RIGHT':'右侧', 'OFF':'关闭'}
HOLD_TYPES = {'INTERMEDIATE','INTERMEDIATE_POINT'}


def hp_boards(scene,generated):
    from automatic_markings import synthetic
    from lighting_closures import pavement_closures
    from lighting_model import holding_frame
    from signs21_2 import sign_props

    side = scene.data['meta'].get('hp_sign_side','BOTH')
    if side=='OFF':
        return {}
    closed = pavement_closures(scene)
    result = {}
    holdings = [mark for mark in (*scene.assets.values(),*generated.values())
                if mark['props'].get('mark_type') in HOLD_TYPES]
    existing = [mark for mark in scene.assets.values()
                if mark['props'].get('sign_role23') in ('FREQUENCY','FREQUENCY_PAVEMENT')]
    used = {str(mark['props'].get('text','')).replace(' ','').upper() for mark in existing}
    count = 0
    for mark in holdings:
        count += 1
        while f'HP{count}' in used:
            count += 1
        if mark.get('owner',mark['id']) in closed or closed.intersection(mark['id'].split(':')):
            continue
        point,_,facing,width = holding_frame(mark,scene)
        travel = tuple(-x for x in facing)
        left = (-travel[1],travel[0])
        for name,sign in (('LEFT',1),('RIGHT',-1)):
            if side not in ('BOTH',name):
                continue
            # Reserve a longitudinal offset from the runway-number boards.
            anchor = [point[i]+left[i]*sign*(width/2+3)+facing[i]*5 for i in (0,1)]
            label = f'HP{count}'
            props = sign_props(label,[],True,name,width,location=False)
            props.update(sign_role23='FREQUENCY',standard_clause20_18='8.3')
            board = synthetic(mark.get('owner',mark['id']),'DIRECTION',
                              [anchor,[anchor[i]+travel[i]*10 for i in (0,1)]],
                              f"HP_BOARD:{mark['id']}:{name}",**props)
            result[board['id']] = board
            paint = sign_props(label,[],False,name,width,location=False)
            if paint is None:
                continue
            half = len(label)*.6*paint['text_height']/2
            offset = min(width/2-half-.45,half+.55)
            anchor = [point[i]+left[i]*sign*offset+facing[i]*5 for i in (0,1)]
            paint.update(sign_role23='FREQUENCY_PAVEMENT')
            legend = synthetic(mark.get('owner',mark['id']),'DIRECTION',
                               [anchor,[anchor[i]+travel[i]*10 for i in (0,1)]],
                               f"HP_PAINT:{mark['id']}:{name}",**paint)
            result[legend['id']] = legend
    return result


def install(app):
    from qt_core21 import G
    from interface_language import tr
    menu = next((action.menu() for action in app.q.menuBar().actions()
                 if action.text().replace('&','') in ('信息引导',tr('信息引导'))),None)
    if menu is None:
        menu = app.q.menuBar().addMenu('信息引导')
    submenu = menu.addMenu('自动 HP 标记牌与道面标识')
    group = G.QActionGroup(submenu)
    for side,label in SIDES.items():
        action = submenu.addAction(label)
        action.setCheckable(True)
        action.setData(side)
        group.addAction(action)
    def sync():
        side = app.scene.data['meta'].get('hp_sign_side','BOTH')
        for action in group.actions():
            action.setChecked(action.data()==side)
    def change(action):
        with app.scene.transaction('设置 HP 等待点标记牌'):
            app.scene.data['meta']['hp_sign_side'] = action.data()
        app.refresh()
    submenu.aboutToShow.connect(sync)
    group.triggered.connect(change)
