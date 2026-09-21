!macro preInit
  SetRegView 64
  WriteRegExpandStr HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation "D:\Programs\SMC\AutoTask"
  WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation "D:\Programs\SMC\AutoTask"
  SetRegView 32
  WriteRegExpandStr HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation "D:\Programs\SMC\AutoTask"
  WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation "D:\Programs\SMC\AutoTask"
!macroend

!macro customInit
  StrCpy $INSTDIR "D:\Programs\SMC\AutoTask"
  ; 从 AutoTask 里拉起的安装包在同一作业对象里。点「确定关闭」会把安装程序一起杀掉。
  ; 先经 explorer 再启动一份，这份才能安全结束客户端。
  ${GetParameters} $R0
  ClearErrors
  ${GetOptions} $R0 "/autotask-detached" $R1
  ${If} ${Errors}
    StrCpy $R2 "$EXEDIR\autotask-relaunch.cmd"
    FileOpen $R3 "$R2" w
    ${If} $R3 != ""
      FileWrite $R3 "@echo off$\r$\n"
      FileWrite $R3 'start "" "$EXEPATH" /autotask-detached $R0$\r$\n'
      FileClose $R3
      Exec '"$WINDIR\explorer.exe" "$R2"'
      SetErrorLevel 0
      Quit
    ${EndIf}
  ${EndIf}
!macroend

; 安装包放在 D:\Programs\SMC\updates\AutoTask，不在 $INSTDIR 里。
!macro customInstall
  Delete "$EXEDIR\autotask-relaunch.cmd"
!macroend
