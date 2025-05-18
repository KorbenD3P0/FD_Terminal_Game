!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "FD Terminal Game"
OutFile "FD_Terminal_Simple_Setup.exe"

# Default installation directory
InstallDir "$PROGRAMFILES\FD Terminal Game"

# Use built-in NSIS icons
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

# Check if dist directory exists
!define DIST_DIR "dist\FD_Terminal_Game"
!define DIST_CHECK "$%TEMP%\fd_terminal_dist_check.txt"

# Interface Settings
!define MUI_ABORTWARNING

Function .onInit
  # Check if dist directory exists before continuing
  IfFileExists "${DIST_DIR}\*.*" ContinueInstall
    MessageBox MB_ICONSTOP "PyInstaller output not found in ${DIST_DIR}.$\n$\nPlease run build_exe.bat first to create the executable before building the installer."
    Abort "Build files not found"
  ContinueInstall:
FunctionEnd

# Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

# Language
!insertmacro MUI_LANGUAGE "English"

Section "Install"
    # Set output path to the installation directory
    SetOutPath $INSTDIR
    
    # Add all files from the dist directory (PyInstaller output)
    File /r "${DIST_DIR}\*.*"
    
    # Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    # Create desktop shortcut
    CreateShortcut "$DESKTOP\FD Terminal Game.lnk" "$INSTDIR\FD_Terminal_Game.exe"
SectionEnd

Section "Uninstall"
    # Remove all the files and folders
    RMDir /r "$INSTDIR"
    
    # Remove desktop shortcut
    Delete "$DESKTOP\FD Terminal Game.lnk"
SectionEnd