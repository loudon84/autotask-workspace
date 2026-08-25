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
!macroend
