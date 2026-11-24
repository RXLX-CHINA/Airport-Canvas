"""Application preferences stored separately from airport projects."""
import configparser
import json
import os
from pathlib import Path

FLAGS=('dark_mode24','grid_visible','nav_visible')
def path():
    return Path(__file__).resolve().parent/'config'/'preferences.aci'


def migrate(filename):
    if filename.exists():return
    root=Path(os.environ.get('APPDATA') or Path.home()/'.config')
    legacy=root/'Airport Canvas'/'preferences.aci'
    if legacy.is_file():
        try:write(read(legacy),filename)
        except OSError:pass


def save_language(filename,language):
    config=read(filename)
    if 'interface' not in config:config.add_section('interface')
    config['interface']['language']=language
    write(config,filename)

def read(filename):
    config=configparser.ConfigParser(interpolation=None)
    try:config.read(filename,encoding='utf8')
    except (OSError,configparser.Error,UnicodeError):return configparser.ConfigParser(interpolation=None)
    return config

def apply_scene(scene,config):
    meta=scene.data['meta']
    for key in FLAGS:
        try:
            value=config.getboolean('display',key,fallback=None)
        except ValueError:continue
        if value is not None:meta[key]=value
    try:
        xy=[int(x) for x in config.get('display','nav_position',fallback='').split(',')]
    except ValueError:xy=[]
    if len(xy)==2:meta['nav_position']=xy

def apply_window(app,config):
    try:
        app.repeat.set(config.getboolean('editing','continuous_drawing',fallback=False))
        width=config.getint('window','width',fallback=0)
        height=config.getint('window','height',fallback=0)
        if width>0 and height>0:
            screen=app.q.screen().availableGeometry()
            app.q.resize(min(width,screen.width()),min(height,screen.height()))
        if config.getboolean('window','maximized',fallback=False):
            from PySide6.QtCore import Qt
            app.q.setWindowState(app.q.windowState()|Qt.WindowState.WindowMaximized)
    except ValueError:pass

def save(app,filename):
    config=read(filename)
    for group in ('display','editing','window'):
        if group not in config:config.add_section(group)
    meta=app.scene.data['meta']
    config['display'].setdefault('dark_mode24',str(bool(meta.get('dark_mode24'))))
    config['display'].update(grid_visible=str(bool(app.grid_visible.get())),
                             nav_visible=str(bool(app.nav_visible11.get())))
    if hasattr(app,'preview_transparency'):config['display']['preview_transparency']=str(app.preview_transparency)
    if hasattr(app,'gpu_requested'):config['display']['gpu_viewport']=str(app.gpu_requested)
    config['display'].pop('nav_position',None)
    if meta.get('nav_position') is not None:
        config['display']['nav_position']=','.join(str(round(x)) for x in meta['nav_position'])
    config['editing']['continuous_drawing']=str(bool(app.repeat.get()))
    if hasattr(app,'autosave_timer'):
        config['editing'].update(autosave=str(app.autosave_enabled),autosave_minutes=str(app.autosave_minutes))
    if hasattr(app,'drawing_presets'):
        import json
        config['editing']['drawing_presets']=json.dumps(app.drawing_presets,ensure_ascii=False)
    normal=app.q.normalGeometry()
    if not normal.isValid():normal=app.q.geometry()
    config['window'].update(width=str(normal.width()),height=str(normal.height()),
                            maximized=str(app.q.isMaximized()))
    write(config,filename)

def batch_stand_preferences(filename):
    try:
        value=json.loads(read(filename).get('editing','batch_stands',fallback='{}'))
    except ValueError:
        return {}
    return value if isinstance(value,dict) else {}


def save_batch_stand_preferences(filename,values):
    config=read(filename)
    if 'editing' not in config:config.add_section('editing')
    config['editing']['batch_stands']=json.dumps(values,ensure_ascii=False)
    write(config,filename)


def recent_projects(filename):
    config=read(filename)
    try:entries=json.loads(config.get('files','recent',fallback='[]'))
    except ValueError:return []
    return [entry for entry in entries if isinstance(entry,str) and entry] if isinstance(entries,list) else []


def remember_project(filename,project):
    project=str(Path(project).resolve())
    key=os.path.normcase(project)
    history=[project]+[entry for entry in recent_projects(filename) if os.path.normcase(entry)!=key]
    config=read(filename)
    if 'files' not in config:config.add_section('files')
    config['files']['recent']=json.dumps(history[:10],ensure_ascii=False)
    write(config,filename)


def save_theme(filename,enabled):
    config=read(filename)
    if 'display' not in config:config.add_section('display')
    config['display']['dark_mode24']=str(bool(enabled))
    write(config,filename)

def write(config,filename):
    filename.parent.mkdir(parents=True,exist_ok=True)
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile(mode='w',encoding='utf8',dir=filename.parent,delete=False) as scratch:
        temporary=Path(scratch.name)
        config.write(scratch)
    try:temporary.replace(filename)
    finally:temporary.unlink(missing_ok=True)


def last_directory(filename,operation):
    directory=read(filename).get('files',operation+'_directory',fallback='')
    return directory if directory and Path(directory).is_dir() else ''


def remember_directory(filename,operation,destination):
    config=read(filename)
    if 'files' not in config:config.add_section('files')
    config['files'][operation+'_directory']=str(Path(destination).resolve().parent)
    write(config,filename)
