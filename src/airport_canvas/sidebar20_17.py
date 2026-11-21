"""Fit notebook to the sidebar viewport; scroll only the current tab."""
def fit(app):
    state=app.__dict__;c=state.get('property_canvas')
    if c is None:return
    book=state.get('_book15');tabbed=bool(book and book.notebook.winfo_exists())
    bars=state.get('_outer_bars20_17')
    if bars is None:
        bars=[w for w in c.master.winfo_children() if w is not c and w.winfo_class() in ('TScrollbar','Scrollbar')];state['_outer_bars20_17']=bars
    for bar in bars:
        if tabbed:bar.pack_forget()
        elif not bar.winfo_manager():bar.pack(side='right',fill='y',before=c)
    if not state.get('_sidebar_fit_bound20_17'):
        c.bind('<Configure>',lambda e:fit(app));state['_sidebar_fit_bound20_17']=True
    width=max(1,c.winfo_width());height=max(1,c.winfo_height()) if tabbed else 0
    for item in c.find_all():
        if c.type(item)=='window':c.itemconfigure(item,width=width,height=height)
    if tabbed:c.yview_moveto(0);c.configure(yscrollcommand='')
    elif bars:c.configure(yscrollcommand=bars[0].set)
