@echo off
echo Activating Conda environment... 
call D:\Documents\miniconda\Scripts\activate.bat star_emg

echo Cleaning previous build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo.
echo Building application...
pyinstaller app.spec

if errorlevel 1 (
    echo.
    echo ============================
    echo BUILD FAILED!
    echo ============================
    echo.
    pause
    exit /b 1
)

echo.
echo ============================
echo BUILD COMPLETE!
echo ============================
echo.
echo Output:
echo dist\star-emg.exe\
echo.

pause
