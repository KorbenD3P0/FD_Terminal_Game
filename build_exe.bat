@echo off
echo Checking for PyInstaller...
pip show pyinstaller > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

echo Building FD Terminal Game executable...

REM Create a directory structure placeholder for PyInstaller
mkdir fd_terminal\data 2>nul
mkdir fd_terminal\assets\fonts 2>nul
mkdir assets\fonts 2>nul
mkdir data 2>nul
echo. > fd_terminal\data\placeholder
echo. > fd_terminal\assets\placeholder
echo. > assets\placeholder
echo. > data\placeholder

REM Install necessary Kivy dependencies for PyInstaller
pip install kivy_deps.sdl2 kivy_deps.glew

REM Build using the spec file
pyinstaller --clean fd_terminal.spec

if %ERRORLEVEL% == 0 (
    echo PyInstaller build complete! Executable created in dist\FD_Terminal_Game.exe
    
    REM Copy fonts directly to the distribution directory
    echo Creating assets folder structure in dist...
    mkdir dist\assets\fonts 2>nul
    mkdir dist\fd_terminal\assets\fonts 2>nul
    
    REM Only copy fonts if they exist
    if exist fd_terminal\assets\fonts\*.ttf (
        xcopy /y fd_terminal\assets\fonts\*.ttf dist\fd_terminal\assets\fonts\
    )
    if exist assets\fonts\*.ttf (
        xcopy /y assets\fonts\*.ttf dist\assets\fonts\
    )
    
    echo Build process complete! Run dist\FD_Terminal_Game.exe to start the game.
) else (
    echo Error during PyInstaller build. Error code: %ERRORLEVEL%
)

pause