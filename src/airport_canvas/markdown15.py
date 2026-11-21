"""Offline Markdown viewer with headings, emphasis, code, links and figures."""
import re
from pathlib import Path
import qt_compat as tk
from qt_compat import ttk
def blocks(source):
    code=False;buffer=[]
    for line in source.splitlines():
        if line.startswith('```'):
            if code:yield 'code','\n'.join(buffer);buffer=[]
            code=not code;continue
        if code:buffer.append(line);continue
        m=re.match(r'^(#{1,6})\s+(.+)',line)
        if m:yield 'h'+str(len(m[1])),m[2];continue
        m=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line.strip())
        if m:yield 'image',(m[1],m[2]);continue
        if re.match(r'^\s*\|?[ :|-]+\|[ :|-]+\|?\s*$',line):continue
        if line.startswith('|'):yield 'table','  '.join(s.strip() for s in line.strip('|').split('|'));continue
        line=re.sub(r'^\s*[-*]\s+','• ',line);yield 'p',line
    if buffer:yield 'code','\n'.join(buffer)
def show(parent,path,title):
    return __import__('qt_manual21').show(parent,path,title)
