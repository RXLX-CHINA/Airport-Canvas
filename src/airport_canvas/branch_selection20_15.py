"""Selection aliases do not alter the physical taxiway graph."""
import uuid
import scene_geometry as g

def chain(scene,aid):
    import segments18 as seg
    routes=seg.routes(scene);a=routes.get(aid)
    if not a or a['props'].get('independent_branch20_15'):return {aid}
    key=a['props'].get('selection_chain20_15')
    if not key:
        # Only saved explicit merge membership is evidence of a legacy merge.
        groups=scene.data['meta'].get('naming_groups',{})
        members=next((set(ids) for ids in groups.values() if aid in ids),{aid})
        return {bid for bid in members if bid in routes and not routes[bid]['props'].get('independent_branch20_15')} or {aid}
    found={aid};changed=True
    while changed:
        changed=False
        for bid,b in routes.items():
            if bid in found or b['props'].get('selection_chain20_15')!=key or b['props'].get('independent_branch20_15'):continue
            found.add(bid);changed=True  # Explicit merge is a selection alias, independent of endpoint edits.
    return found

def merge_selection(scene,ids):
    import segments18 as seg
    routes=seg.routes(scene);pending=set(ids)&set(routes)
    # A disconnected item sharing a name is not a single selectable chain.
    # Freeze connected membership at merge time; later endpoint edits retain it.
    while pending:
        found={pending.pop()};changed=True
        while changed:
            changed=False
            for aid in list(pending):
                if any(g.distance(routes[aid]['points'][i],routes[bid]['points'][j])<=.05 for bid in found for i in (0,-1) for j in (0,-1)):
                    pending.remove(aid);found.add(aid);changed=True
        key=uuid.uuid4().hex
        for aid in found:routes[aid]['props'].update(selection_chain20_15=key,independent_branch20_15=False)

def independent(scene,aid,station,name):
    import segments18 as seg
    a=seg.route(scene,aid)
    if not name.strip():raise ValueError('请输入独立分支编号。')
    with scene.transaction('强制独立分支并改号'):
        seg.rename(scene,aid,station,name)
        a['props'].pop('selection_chain20_15',None);a['props']['independent_branch20_15']=True
        # Detach only the organizational container, never a welded endpoint.
        obj=scene.assets.get(aid) or scene.movements.get(aid)
        group=scene.data['groups'].get(obj.get('container_id'))
        if group and obj.get('container_id')==a['props'].get('network_group'):
            obj['container_id']=group.get('container_id');a['props'].pop('network_group',None)
        if len(seg.pieces(a))==1:
            obj['name']=name.strip();a['props']['designation']=name.strip()
    return aid
