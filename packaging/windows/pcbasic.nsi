; PC-BASIC NSIS installer
; based on NSIS Modern User Interface example scripts written by Joost Verburg
; and http://nsis.sourceforge.net/Uninstall_only_installed_files


;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"
  !include "UninstallLog.nsh"
;
;--------------------------------
; UnInstallLog preparation

  ;Set the name of the uninstall log
  !define UninstLog "uninstall.log"
  Var UninstLog
  ;The root registry to write to
  !define REG_ROOT "HKLM"
  ;The registry path to write to
  !define REG_APP_PATH "SOFTWARE\appname"
 
  ;Uninstall log file missing.
  LangString UninstLogMissing ${LANG_ENGLISH} "${UninstLog} not found!$\r$\nUninstallation cannot proceed!"
 
  ;macros
  !define AddItem "!insertmacro AddItem"
  !define BackupFile "!insertmacro BackupFile" 
  !define BackupFiles "!insertmacro BackupFiles" 
  !define CopyFiles "!insertmacro CopyFiles"
  !define CreateDirectory "!insertmacro CreateDirectory"
  !define CreateShortcut "!insertmacro CreateShortcut"
  !define File "!insertmacro File"
  !define Rename "!insertmacro Rename"
  !define RestoreFile "!insertmacro RestoreFile"    
  !define RestoreFiles "!insertmacro RestoreFiles"
  !define SetOutPath "!insertmacro SetOutPath"
  !define WriteRegDWORD "!insertmacro WriteRegDWORD" 
  !define WriteRegStr "!insertmacro WriteRegStr"
  !define WriteUninstaller "!insertmacro WriteUninstaller"
 
  Section -openlogfile
    CreateDirectory "$INSTDIR"
    IfFileExists "$INSTDIR\${UninstLog}" +3
      FileOpen $UninstLog "$INSTDIR\${UninstLog}" w
    Goto +4
      SetFileAttributes "$INSTDIR\${UninstLog}" NORMAL
      FileOpen $UninstLog "$INSTDIR\${UninstLog}" a
      FileSeek $UninstLog 0 END
  SectionEnd


--------------------------------
;General

  ;Name and file
  Name "PC-BASIC 3.23"
  OutFile "pc-basic-win32.exe"

  ;Default installation folder
  InstallDir "$programfiles\PC-BASIC"
  
  ;Get installation folder from registry if available
  InstallDirRegKey HKCU "Software\PC-BASIC" ""

  ;Request application privileges for Windows Vista
  RequestExecutionLevel user

;--------------------------------
;Variables

  Var StartMenuFolder

;--------------------------------
;Interface Settings

  !define MUI_ICON "pcbasic.ico"
  !define MUI_HEADERIMAGE
  !define MUI_HEADERIMAGE_BITMAP "pcbasic-bg.bmp"
;  !define MUI_HEADERIMAGE_RIGHT

  !define MUI_ABORTWARNING

;--------------------------------
;Pages

;  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY

  ;Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU" 
  !define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\PC-BASIC" 
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
  
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

  ${SetOutPath} "$INSTDIR"
  
  ${File} /r "dist\pcbasic\*"
  
  ;Store installation folder
  ${WriteRegStr} HKCU "Software\PC-BASIC" "" $INSTDIR
  
  ;Create uninstaller
  ${WriteUninstaller} "$INSTDIR\Uninstall.exe"

  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    
    ;Create shortcuts
    ${CreateDirectory} "$SMPROGRAMS\$StartMenuFolder"
    ${CreateShortCut} "$SMPROGRAMS\$StartMenuFolder\PC-BASIC.lnk" "$INSTDIR\pcbasic.exe"
    ${CreateShortCut} "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  
  !insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

;--------------------------------
;Descriptions

  ;Language strings
  LangString DESC_SecDummy ${LANG_ENGLISH} "Main section."

  ;Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDummy} $(DESC_SecDummy)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section


Section Uninstall
  ;Can't uninstall if uninstall log is missing!
  IfFileExists "$INSTDIR\${UninstLog}" +3
    MessageBox MB_OK|MB_ICONSTOP "$(UninstLogMissing)"
      Abort
 
  Push $R0
  Push $R1
  Push $R2
  SetFileAttributes "$INSTDIR\${UninstLog}" NORMAL
  FileOpen $UninstLog "$INSTDIR\${UninstLog}" r
  StrCpy $R1 -1
 
  GetLineCount:
    ClearErrors
    FileRead $UninstLog $R0
    IntOp $R1 $R1 + 1
    StrCpy $R0 $R0 -2
    Push $R0   
    IfErrors 0 GetLineCount
 
  Pop $R0
 
  LoopRead:
    StrCmp $R1 0 LoopDone
    Pop $R0
 
    IfFileExists "$R0\*.*" 0 +3
      RMDir $R0  #is dir
    Goto +9
    IfFileExists $R0 0 +3
      Delete $R0 #is file
    Goto +6
    StrCmp $R0 "${REG_ROOT} ${REG_APP_PATH}" 0 +3
      DeleteRegKey ${REG_ROOT} "${REG_APP_PATH}" #is Reg Element
    Goto +3
    StrCmp $R0 "${REG_ROOT} ${UNINSTALL_PATH}" 0 +2
      DeleteRegKey ${REG_ROOT} "${UNINSTALL_PATH}" #is Reg Element
 
    IntOp $R1 $R1 - 1
    Goto LoopRead
  LoopDone:
  FileClose $UninstLog
  Delete "$INSTDIR\${UninstLog}"
  RMDir "$INSTDIR"
  Pop $R2
  Pop $R1
  Pop $R0
 
  ;Remove registry keys
    ;DeleteRegKey ${REG_ROOT} "${REG_APP_PATH}"
    ;DeleteRegKey ${REG_ROOT} "${UNINSTALL_PATH}"
SectionEnd


;Section "Uninstall"
  
  ;!insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder
  ;
  ;Delete "$SMPROGRAMS\$StartMenuFolder\pcbasic.lnk"  
  ;Delete "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk"
  ;RMDir "$SMPROGRAMS\$StartMenuFolder"
  ;  
  ;DeleteRegKey /ifempty HKCU "Software\PC-BASIC"

;SectionEnd
