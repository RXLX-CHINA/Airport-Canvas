"""Display-only deicing routes and raw-pointer viewport readout."""
def status(app,event=None):
    state=app.__dict__;variable=state.get('view_status')
    if variable is None:return
    if event is not None:state['_status_pointer20_9']=(event.x,event.y)
    pixel=state.get('_status_pointer20_9')
    if pixel is None:
        canvas=state.get('canvas')
        if canvas is None:return
        pixel=(canvas.winfo_width()/2,canvas.winfo_height()/2)
    p=app.world(*pixel);text=f'X {p[0]:.1f} m   Y {p[1]:.1f} m   |   {app.zoom:.3f} px/m'
    getter=getattr(variable,'get',None)
    if text!=state.get('_status_text20_9') or callable(getter) and getter()!=text:variable.set(text);state['_status_text20_9']=text

def deice(app):
    c=app.canvas;c.delete('deice_axes20_9')
    if not app._color17:return
    key=(id(app.scene),app.scene.revision);cached=app.__dict__.get('_deice_axes20_9')
    if not cached or cached[0]!=key:
        import deice12
        rows=[]
        for aid,a in app.scene.assets.items():
            if not a['props'].get('deice_layout12') or a['props'].get('closed'):continue
            try:rows.append((aid,a['name'],deice12.layout(app.scene,a)['route']))
            except (ValueError,KeyError):continue
        cached=(key,rows);app.__dict__['_deice_axes20_9']=cached
    for aid,name,points in cached[1]:
        if len(points)<2:continue
        c.create_line(*[v for p in points for v in app.screen(p)],fill='#007e91',width=4 if app.selection==aid else 3,tags=('deice_axes20_9','owner:'+aid))

