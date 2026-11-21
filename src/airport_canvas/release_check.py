"""Static release consistency check. Does not open a window or access network."""
from pathlib import Path
import json,ast

def check(root=None):
    root=Path(root or __file__).resolve().parent if root is None else Path(root)
    version=json.loads((root/'VERSION.json').read_text(encoding='utf8'));errors=[]
    for name in ('USER_GUIDE.md','SOFTWARE_OVERVIEW.md','CHANGELOG.md'):
        if version['version'] not in (root/name).read_text(encoding='utf8'):errors.append(name+' does not describe '+version['version'])
    for key in ('default_project','validation','manual','overview'):
        if not (root/version[key]).is_file():errors.append('Missing '+version[key])
    if not version['default_project'].endswith('.ACP'):errors.append('Default project must use ACP')
    if version['entry_module'] not in (root/'gui.py').read_text(encoding='utf8'):errors.append('GUI entry does not match version')
    for path in root.glob('*.py'):
        try:ast.parse(path.read_text(encoding='utf8'),filename=str(path))
        except SyntaxError as exc:errors.append(str(exc))
    if version['validation']=='VALIDATION_QT21_6_F8_CHART.md':
        for name in ('chart_f8.py','chart_layout_f8.py','chart_view_f8.py'):
            if not (root/name).is_file():errors.append('Missing '+name)
        for name in ('USER_GUIDE.md','SOFTWARE_OVERVIEW.md','CHANGELOG.md'):
            if 'F8' not in (root/name).read_text(encoding='utf8'):errors.append(name+' does not describe F8')
    if errors:raise ValueError('\n'.join(errors))
    return version

if __name__=='__main__':print('Release consistency passed:',check()['release'])
