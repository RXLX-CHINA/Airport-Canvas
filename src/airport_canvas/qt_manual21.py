"""Native offline Markdown document viewer, with search and external links."""
from pathlib import Path
from interface_language import tr
from qt_core21 import W,G,C,Qt

def show(parent,path,title):
    path=Path(path);window=W.QMainWindow(parent.q);window.setWindowTitle(title);window.resize(940,740);body=W.QWidget(window);layout=W.QVBoxLayout(body);layout.setContentsMargins(16,12,16,16)
    search=W.QLineEdit(body);search.setPlaceholderText(tr('搜索本页，按 Enter 查找下一处'));search.setClearButtonEnabled(True);browser=W.QTextBrowser(body);browser.setOpenExternalLinks(True);browser.setSearchPaths([str(path.parent)]);browser.setStyleSheet('QTextBrowser { padding: 20px; }');browser.document().setDefaultFont(G.QFont('Microsoft YaHei UI',11));browser.setMarkdown(path.read_text(encoding='utf8'));layout.addWidget(search);layout.addWidget(browser,1);window.setCentralWidget(body)
    def find():
        if not browser.find(search.text()):cursor=browser.textCursor();cursor.movePosition(G.QTextCursor.MoveOperation.Start);browser.setTextCursor(cursor);browser.find(search.text())
    search.returnPressed.connect(find);parent.__dict__.setdefault('_manual_windows21',[]).append(window);window.show();return window
