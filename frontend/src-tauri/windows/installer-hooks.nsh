!macro NSIS_HOOK_PREINSTALL
  ; Keep application binaries separate from the runtime data stored under
  ; $LOCALAPPDATA\JLU Notice Monitor.
  ${If} $INSTDIR == "$LOCALAPPDATA\${PRODUCTNAME}"
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\${PRODUCTNAME}"
    SetOutPath $INSTDIR
  ${EndIf}
!macroend
