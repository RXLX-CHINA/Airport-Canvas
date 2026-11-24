@echo off
setlocal
set "repo=%~dp0"
if not exist "%repo%src\airport_canvas\qt_app21.py" set "repo=C:\Users\ASUS\Documents\Codex\2026-11-19\https-chatgpt-com-share-6afe70e5-b470-2\work\ac-gh-repo\"
if not exist "%repo%src\airport_canvas\qt_app21.py" (
    echo Airport Canvas source was not found. Run this script from the repository root.
    pause
    exit /b 1
)
pushd "%repo%" || exit /b 1
set "python=C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe"
if /i "%~1"=="--check" (
    "%python%" -c "import runpy,sys; sys.path.insert(0,r'src\airport_canvas'); runpy.run_path(r'src\airport_canvas\qt_app21.py'); print('Airport Canvas source entry verified.')"
) else (
    "%python%" "src\airport_canvas\qt_app21.py" %*
)
set "exit_code=%errorlevel%"
popd
if not "%exit_code%"=="0" pause
exit /b %exit_code%
