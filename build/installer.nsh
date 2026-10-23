; ==============================================================================
; Script NSIS personalizado para Agente Studio (electron-builder)
; Garantiza la desinstalación limpia, completa y self-aware (directorio personalizado)
; ==============================================================================

!macro customInit
  ; Self-aware: si $INSTDIR está vacío o no se resolvió, buscar en el registro o usar la carpeta del ejecutable
  ${if} $INSTDIR == ""
    ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\com.agente.studio" "InstallLocation"
    ${if} $0 != ""
      StrCpy $INSTDIR $0
    ${else}
      StrCpy $INSTDIR $EXEDIR
    ${endif}
  ${endif}
!macroend

!macro customRemoveFiles
  ; 1. Limpiar archivos y carpetas generados en tiempo de ejecución en el directorio de instalación real ($INSTDIR)
  ; (Especialmente bytecode de Python __pycache__, .pyc, logs y temporales)
  ${if} $INSTDIR != ""
    RMDir /r /REBOOTOK "$INSTDIR\resources\backend\__pycache__"
    RMDir /r /REBOOTOK "$INSTDIR\backend\__pycache__"
    RMDir /r /REBOOTOK "$INSTDIR\resources"
    RMDir /r /REBOOTOK "$INSTDIR"
  ${endif}

  ; 2. Limpiar datos de usuario en Roaming (IndexedDB, LocalStorage, cookies, sesiones, configuración)
  RMDir /r /REBOOTOK "$APPDATA\Agente Studio"
  RMDir /r /REBOOTOK "$APPDATA\agente-studio"
  RMDir /r /REBOOTOK "$APPDATA\com.agente.studio"

  ; 3. Limpiar caché de electron-updater (instaladores OTA descargados) y logs de Chromium
  RMDir /r /REBOOTOK "$LOCALAPPDATA\agente-studio-updater"
  RMDir /r /REBOOTOK "$LOCALAPPDATA\Agente Studio"
  RMDir /r /REBOOTOK "$LOCALAPPDATA\agente-studio"
  RMDir /r /REBOOTOK "$LOCALAPPDATA\com.agente.studio"

  ; 4. Limpiar carpeta de proyectos y modelos generados por el backend en el perfil de usuario
  RMDir /r /REBOOTOK "$PROFILE\AgenteStudio"
  RMDir /r /REBOOTOK "$PROFILE\Agente Studio"
!macroend

!macro customUnInstall
  ; 1. Forzar cierre de cualquier instancia residual de la app o backend
  nsExec::Exec 'taskkill /F /IM "Agente Studio.exe" /T'

  ; 2. Limpieza exhaustiva de Roaming AppData
  RMDir /r /REBOOTOK "$APPDATA\Agente Studio"
  RMDir /r /REBOOTOK "$APPDATA\agente-studio"
  RMDir /r /REBOOTOK "$APPDATA\com.agente.studio"

  ; 3. Limpieza exhaustiva de Local AppData y el caché de updates
  RMDir /r /REBOOTOK "$LOCALAPPDATA\agente-studio-updater"
  RMDir /r /REBOOTOK "$LOCALAPPDATA\Agente Studio"
  RMDir /r /REBOOTOK "$LOCALAPPDATA\agente-studio"
  RMDir /r /REBOOTOK "$LOCALAPPDATA\com.agente.studio"

  ; 4. Limpieza del directorio de instalación real (self-aware: donde sea que el usuario lo haya instalado)
  ${if} $INSTDIR != ""
    RMDir /r /REBOOTOK "$INSTDIR"
  ${endif}

  ; Limpieza adicional por si hubo alguna instalación previa en la ruta por defecto
  RMDir /r /REBOOTOK "$LOCALAPPDATA\Programs\Agente Studio"

  ; 5. Limpieza de datos en el perfil de usuario
  RMDir /r /REBOOTOK "$PROFILE\AgenteStudio"
  RMDir /r /REBOOTOK "$PROFILE\Agente Studio"

  ; 6. Eliminar accesos directos de escritorio y menú inicio
  Delete "$DESKTOP\Agente Studio.lnk"
  Delete "$SMPROGRAMS\Agente Studio.lnk"
  Delete "$SMPROGRAMS\Agente Studio\*.lnk"
  RMDir /r "$SMPROGRAMS\Agente Studio"

  ; 7. Limpiar registros de Windows
  DeleteRegKey HKCU "Software\Agente Studio"
  DeleteRegKey HKCU "Software\agente-studio"
  DeleteRegKey HKCU "Software\com.agente.studio"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\com.agente.studio"
!macroend
