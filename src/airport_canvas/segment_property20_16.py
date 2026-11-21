"""A child number editor targets an immutable segment ID, not its parent name."""
import segments18 as seg

def target(app):
    aid=app.__dict__.get('selection');a=seg.routes(app.scene).get(aid)
    if not a:return None
    active=app.__dict__.get('_active_piece18')
    part=next((p for p in seg.pieces(a) if active and active[0]==aid and p['id']==active[1]),None)
    part=part or seg.piece_at(a,app.__dict__.get('_logical_station18',0))
    return aid,part

def rename(scene,aid,pid,name):
    a=seg.route(scene,aid);part=next((p for p in seg.pieces(a) if p['id']==pid),None)
    if not part:raise ValueError('该子段已改变，请重新点选后改号。')
    L=__import__('scene_geometry').length(a['points'])
    with scene.transaction('修改路线编号'):
        seg.rename(scene,aid,L*(part['lo']+part['hi'])/2,name)
        if len(seg.pieces(a))==1:
            obj=scene.assets.get(aid) or scene.movements.get(aid);obj['name']=name.strip();a['props']['designation']=name.strip()
    return aid

def refresh_form(app):
    current=target(app)
    if current and app.__dict__.get('_segment_form20_16')!=(current[0],current[1]['id']):app.update_inspector()
