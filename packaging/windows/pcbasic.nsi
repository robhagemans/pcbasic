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

;--------------------------------
;Include Modern UI

!include "MUI2.nsh"
!include "AdvUninstLog.nsh"
;
;--------------------------------
;General


;Name and file
Name "PC-BASIC 3.23"
OutFile "pcbasic-win32.exe"






;Default installation folder
InstallDir "$programfiles\PC-BASIC"
;Get installation folder from registry if available
InstallDirRegKey ${INSTDIR_REG_ROOT} "${INSTDIR_REG_KEY}" "InstallDir"

;Request application privileges for Windows Vista
;RequestExecutionLevel user

RequestExecutionLevel admin ;Require admin rights on NT6+ (When UAC is turned on)

!include LogicLib.nsh



;Start Menu Folder Page Configuration
!define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU" 
!define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\PC-BASIC" 
!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"

;--------------------------------
;Variables

Var StartMenuFolder

;--------------------------------
;Interface Settings


!define MUI_ICON "pcbasic.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "pcbasic-bg.bmp"

!define MUI_ABORTWARNING

;--------------------------------
;Pages

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


    !insertmacro MUI_STARTMENU_WRITE_END
SectionEnd

;--------------------------------
;Descriptions

  ;Language strings
;  LangString DESC_SecDummy ${LANG_ENGLISH} "Main section."

  ;Assign language strings to sections
;  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
;  !insertmacro MUI_DESCRIPTION_TEXT ${SecDummy} $(DESC_SecDummy)
;  !insertmacro MUI_FUNCTION_DESCRIPTION_END


;--------------------------------
;Uninstaller Section


Function .onInit
    ;prepare log always within .onInit function

    UserInfo::GetAccountType
    pop $0
    ${If} $0 != "admin" ;Require admin rights on NT4+
        MessageBox mb_iconstop "Administrator rights required!"
        SetErrorLevel 740 ;ERROR_ELEVATION_REQUIRED
        Quit
    ${EndIf}

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
    Delete "$SMPROGRAMS\$StartMenuFolder\PC-BASIC.lnk"  
    Delete "$SMPROGRAMS\$StartMenuFolder\Documentation.lnk"  
    Delete "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk"
    RMDir "$SMPROGRAMS\$StartMenuFolder"
    
    DeleteRegKey /ifempty HKCU "Software\PC-BASIC"
SectionEnd


Function UN.onInit
    ;begin uninstall, could be added on top of uninstall section instead
    !insertmacro UNINSTALL.LOG_BEGIN_UNINSTALL
FunctionEnd


