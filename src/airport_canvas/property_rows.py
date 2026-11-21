"""Layout helpers for controls redirected into notebook property pages."""
def next_row(container):
    return max((int(widget.grid_info()['row']) for widget in container.grid_slaves() if 'row' in widget.grid_info()),default=-1)+1

def field_container(original,control):
    return control.master if control is not None else original
