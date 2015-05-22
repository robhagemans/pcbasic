; PC-BASIC NSIS installer
; based on NSIS Modern User Interface example scripts written by Joost Verburg
; and NSIS advanced Uninstall Log examples

;..................................................................................................
;Following two definitions required. Uninstall log will use these definitions.
;You may use these definitions also, when you want to set up the InstallDirRagKey,
;store the language selection, store Start Menu folder etc.
;Enter the windows uninstall reg sub key to add uninstall information to Add/Remove Programs also.

!define INSTDIR_REG_ROOT "HKLM"
!define INSTDIR_REG_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\PC-BASIC"


; multiuser, modern UI

!define MULTIUSER_EXECUTIONLEVEL Highest
!define MULTIUSER_MUI
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MULTIUSER_INSTALLMODE_INSTDIR "PC-BASIC"
!include "MultiUser.nsh"
!include "MUI2.nsh"
!include "AdvUninstLog.nsh"
;
;--------------------------------
;General


;Name and file
Name "PC-BASIC"
OutFile "pcbasic-win32.exe"

!include LogicLib.nsh



;Start Menu Folder Page Configuration
!define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU" 
!define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\PC-BASIC" 
!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"

;--------------------------------
;Variables

Var StartMenuFolder
Var Shortcuts


;--------------------------------
;Interface Settings


!define MUI_ICON "pcbasic.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "pcbasic-bg.bmp"

!define MUI_ABORTWARNING

;--------------------------------
;Pages


!insertmacro MULTIUSER_PAGE_INSTALLMODE

!insertmacro UNATTENDED_UNINSTALL
;!insertmacro INTERACTIVE_UNINSTALL

;  !insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
  
;--------------------------------
;Languages
 
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section "PC-BASIC" SecDummy
    SetOutPath "$INSTDIR"

    !insertmacro UNINSTALL.LOG_OPEN_INSTALL

    File /r "dist\pcbasic\*"

    !insertmacro UNINSTALL.LOG_CLOSE_INSTALL

    ;Store installation folder
    WriteRegStr HKCU "Software\PC-BASIC" "" $INSTDIR

    !insertmacro MUI_STARTMENU_WRITE_BEGIN Application

    ;Create shortcuts
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Documentation.lnk" "$INSTDIR\doc\PC-BASIC_documentation.html"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    SetOutPath "$PROFILE"
    CreateShortCut "$SMPROGRAMS\$StartMenuFolder\PC-BASIC.lnk" "$INSTDIR\pcbasic.exe"

    ; workaround as multiuser doesn't seem to get the right location for shortcuts if an admin user installs 'just for me'
    WriteRegStr HKCU "Software\PC-BASIC" "Shortcuts" "$SMPROGRAMS\$StartMenuFolder"


    !insertmacro MUI_STARTMENU_WRITE_END
SectionEnd

;--------------------------------
;Uninstaller Section


Function .onInit
    !insertmacro MULTIUSER_INIT

    ;prepare log always within .onInit function
    !insertmacro UNINSTALL.LOG_PREPARE_INSTALL
FunctionEnd


Function .onInstSuccess
    ;create/update log always within .onInstSuccess function
    !insertmacro UNINSTALL.LOG_UPDATE_INSTALL
FunctionEnd


Section UnInstall
    ;uninstall from path, must be repeated for every install logged path individually
    !insertmacro UNINSTALL.LOG_UNINSTALL "$INSTDIR"
    ;end uninstall, after uninstall from all logged paths has been performed
    !insertmacro UNINSTALL.LOG_END_UNINSTALL

    !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder

    ; workaround as multiuser doesn't seem to get the right location for shortcuts if an admin user installs 'just for me'
    ReadRegStr $Shortcuts HKCU "Software\PC-BASIC" "Shortcuts"

    Delete "$Shortcuts\PC-BASIC.lnk"  
    Delete "$Shortcuts\Documentation.lnk"  
    Delete "$Shortcuts\Uninstall.lnk"
    RMDir "$Shortcuts"
    
    DeleteRegKey HKCU "Software\PC-BASIC"
;    DeleteRegKey /ifempty HKCU "Software\PC-BASIC"
SectionEnd


Function UN.onInit
    !insertmacro MULTIUSER_UNINIT

    ;begin uninstall, could be added on top of uninstall section instead
    !insertmacro UNINSTALL.LOG_BEGIN_UNINSTALL
FunctionEnd


