@echo off
echo ======================================
echo PDF FormFill - Dependency Installer
echo ======================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b
)

echo Python found.
echo.

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

:: Install requirements
if not exist requirements.txt (
    echo ERROR: requirements.txt not found in this folder.
    pause
    exit /b
)

echo Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
echo.

echo ======================================
echo Installation complete!
echo You can now run PDF FormFill.
echo ======================================
pause
