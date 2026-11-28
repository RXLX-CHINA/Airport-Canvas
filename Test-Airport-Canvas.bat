@echo off
setlocal
set "repo=%~dp0"
if not exist "%repo%src\airport_canvas\qt_app21.py" (
    echo Airport Canvas source was not found. Run this script from the repository root.
    pause
    exit /b 1
)
pushd "%repo%" || exit /b 1
set "python=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "python_args="
if exist "%python%" goto run
set "python=py"
set "python_args=-3"
py -3 -c "import PySide6, shapely" >nul 2>&1
if not errorlevel 1 goto run
set "python=python"
set "python_args="
python -c "import PySide6, shapely" >nul 2>&1
if not errorlevel 1 goto run
echo No Python installation with PySide6 and Shapely was found.
popd
pause
exit /b 1

:run
if /i "%~1"=="--check" (
    "%python%" %python_args% -c "import runpy,sys; sys.path.insert(0,r'src\airport_canvas'); runpy.run_path(r'src\airport_canvas\qt_app21.py'); print('Airport Canvas source entry verified.')"
) else (
    "%python%" %python_args% "src\airport_canvas\qt_app21.py" %*
)
set "exit_code=%errorlevel%"
popd
if not "%exit_code%"=="0" pause
exit /b %exit_code%

