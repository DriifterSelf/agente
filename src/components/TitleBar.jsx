import React, { useState, useEffect } from 'react';
import { Minus, Square, Copy, X, Cpu, Sparkles, RefreshCw, DownloadCloud, Check, Brain, ChevronDown } from 'lucide-react';

export default function TitleBar({ activeProject, systemStatus, isBackendConnected, onRefreshStatus }) {
  const [updateStatus, setUpdateStatus] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [isMaximized, setIsMaximized] = useState(false);
  const [isContextOpen, setIsContextOpen] = useState(false);
  const [serverPresets, setServerPresets] = useState([]);

  const FALLBACK_PRESETS = [
    { tokens: 8192, kv_gb: 0.6, location: 'gpu', desc: 'Ultrarrápido • Consultas puntuales' },
    { tokens: 16384, kv_gb: 1.2, location: 'gpu', desc: 'Rápido • Notas breves y artículos' },
    { tokens: 32768, kv_gb: 2.4, location: 'gpu', desc: 'Recomendado • PDFs de 50+ págs, Excel y tareas' },
    { tokens: 40960, kv_gb: 3.0, location: 'gpu', desc: 'Máximo modelo • Documentos densos y libros' },
  ];

  useEffect(() => {
    const fetchPresets = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8765/api/settings/context-presets');
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setServerPresets(data);
          }
        }
      } catch (e) {
        // fallback presets will be used
      }
    };
    if (isBackendConnected) {
      fetchPresets();
    }
  }, [isBackendConnected, systemStatus?.active_model]);

  const activePresets = serverPresets.length > 0 ? serverPresets : FALLBACK_PRESETS;

  const handleSelectMode = async (mode) => {
    try {
      const currentTokens = systemStatus?.n_ctx || 32768;
      const res = await fetch('http://127.0.0.1:8765/api/settings/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ n_ctx: currentTokens, kv_mode: mode })
      });
      if (res.ok && onRefreshStatus) {
        onRefreshStatus();
      }
    } catch (err) {
      console.error('Error changing mode:', err);
    }
  };

  const handleSelectContext = async (tokens) => {
    try {
      const currentMode = systemStatus?.kv_mode || 'auto';
      const res = await fetch('http://127.0.0.1:8765/api/settings/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ n_ctx: tokens, kv_mode: currentMode })
      });
      if (res.ok && onRefreshStatus) {
        onRefreshStatus();
      }
    } catch (err) {
      console.error('Error changing context:', err);
    }
    setIsContextOpen(false);
  };

  useEffect(() => {
    // Listen to Electron window state
    if (window.electronAPI) {
      if (window.electronAPI.onUpdateStatus) {
        window.electronAPI.onUpdateStatus((data) => {
          setUpdateStatus(data);
        });
      }
      if (window.electronAPI.onMaximizedChange) {
        window.electronAPI.onMaximizedChange((maximized) => {
          setIsMaximized(maximized);
        });
      }
      if (window.electronAPI.isMaximized) {
        window.electronAPI.isMaximized().then((maximized) => {
          setIsMaximized(maximized);
        });
      }
    }
  }, []);

  const handleMinimize = () => {
    if (window.electronAPI) window.electronAPI.minimize();
  };

  const handleMaximize = () => {
    if (window.electronAPI) window.electronAPI.maximize();
  };

  const handleClose = () => {
    if (window.electronAPI) window.electronAPI.close();
  };

  const handleCheckUpdates = async () => {
    setIsSyncing(true);
    setSyncMessage('Buscando...');
    
    // 1. Try Electron autoUpdater
    if (window.electronAPI && window.electronAPI.checkForUpdates) {
      window.electronAPI.checkForUpdates();
    }

    // 2. Also check Git sync
    try {
      const res = await fetch('http://127.0.0.1:8765/api/system/git-pull', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        if (data.rebuilt) {
          setSyncMessage('¡Actualizado!');
          setTimeout(() => window.location.reload(), 1500);
        } else {
          setSyncMessage('Al día');
          setTimeout(() => setSyncMessage(''), 3000);
        }
      } else {
        setSyncMessage('Al día');
        setTimeout(() => setSyncMessage(''), 3000);
      }
    } catch (e) {
      setSyncMessage('Al día');
      setTimeout(() => setSyncMessage(''), 2500);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleRestartForUpdate = () => {
    if (window.electronAPI && window.electronAPI.restartForUpdate) {
      window.electronAPI.restartForUpdate();
    }
  };

  return (
    <div className="h-10 bg-[#070A0F] border-b border-border flex items-center justify-between select-none drag-region px-3 z-50">
      {/* Brand & Project with safe truncation */}
      <div className="flex items-center space-x-3 overflow-hidden">
        <div className="flex items-center space-x-2 text-blue-400 font-semibold text-sm flex-shrink-0">
          <div className="w-5 h-5 rounded bg-blue-600/20 flex items-center justify-center border border-blue-500/30">
            <Sparkles size={12} className="text-blue-400" />
          </div>
          <span className="tracking-wide text-slate-100">Agente Studio</span>
        </div>

        <div className="h-4 w-[1px] bg-border flex-shrink-0" />

        <div
          className="flex items-center space-x-1.5 text-xs text-textMuted bg-surface px-2.5 py-0.5 rounded-full border border-border truncate max-w-[240px]"
          title={`Proyecto activo: ${activeProject || 'Sin selección'}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
            isBackendConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500 animate-ping'
          }`} />
          <span className="truncate">
            {activeProject ? (
              <span>Proyecto: <strong className="text-slate-200">{activeProject}</strong></span>
            ) : (
              <span className="text-slate-400">Sin proyecto</span>
            )}
          </span>
        </div>
      </div>

      {/* Hardware & OTA Updates */}
      <div className="hidden md:flex items-center space-x-2 text-xs text-slate-400 no-drag">
        {/* Active Model Status Badge */}
        {systemStatus?.active_model ? (
          <div
            className="flex items-center space-x-1.5 bg-emerald-500/10 text-emerald-300 px-2.5 py-0.5 rounded border border-emerald-500/30"
            title={systemStatus.engine_message || 'Motor local listo'}
          >
            <Sparkles size={11} className="text-emerald-400" />
            <span className="font-medium">
              {systemStatus.active_model.replace(/\.gguf$/i, '').replace(/[-_]/g, ' ')} · {systemStatus.kv_location === 'ram' ? 'RAM DDR5' : 'VRAM'}
            </span>
          </div>
        ) : systemStatus?.engine_state === 'loading' ? (
          <div className="flex items-center space-x-1.5 bg-amber-500/10 text-amber-300 px-2.5 py-0.5 rounded border border-amber-500/30">
            <RefreshCw size={11} className="animate-spin text-amber-400" />
            <span>Cargando modelo...</span>
          </div>
        ) : null}

        {/* Hardware Status */}
        <div className="flex items-center space-x-1.5 bg-surface/80 px-2.5 py-0.5 rounded border border-border/80">
          <Cpu size={12} className="text-blue-400" />
          <span>
            {systemStatus?.gpu_name 
              ? `${systemStatus.gpu_name} • ${systemStatus.gpu_backend}`
              : isBackendConnected ? 'Cargando hardware...' : 'Conectando con motor local...'}
          </span>
        </div>

        {/* Context RAM Allocation Badge & Dropdown */}
        <div className="relative">
          <button
            onClick={() => setIsContextOpen(!isContextOpen)}
            className="flex items-center space-x-1.5 bg-surface/80 hover:bg-surfaceHover text-slate-300 hover:text-white px-2.5 py-0.5 rounded border border-border/80 transition"
            title="Configurar asignación de memoria RAM para el contexto"
          >
            <Brain size={12} className="text-purple-400" />
            <span>
              Contexto: <strong className="text-purple-300">{systemStatus?.n_ctx_k || 32}K</strong>
              <span className="text-slate-500 ml-1">
                ({systemStatus?.context_ram_gb || 2.4} GB · {systemStatus?.kv_location === 'ram' ? 'RAM' : 'VRAM'})
              </span>
            </span>
            <ChevronDown size={11} className={`text-slate-400 transition-transform ${isContextOpen ? 'rotate-180' : ''}`} />
          </button>

          {isContextOpen && (
            <>
              {/* Backdrop */}
              <div 
                className="fixed inset-0 z-40" 
                onClick={() => setIsContextOpen(false)} 
              />
              {/* Popover */}
              <div className="absolute right-0 top-full mt-1.5 w-88 bg-[#0F141C] border border-border rounded-lg shadow-2xl p-3 z-50 text-left">
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-border/80">
                  <div className="flex items-center space-x-1.5 text-slate-200 font-medium text-xs">
                    <Brain size={13} className="text-purple-400" />
                    <span>Ubicación y Memoria del Contexto</span>
                  </div>
                  <span className="text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 px-1.5 py-0.5 rounded font-mono">
                    KV en {systemStatus?.kv_location === 'ram' ? 'DDR5' : 'VRAM'}
                  </span>
                </div>

                {/* Mode Selector */}
                <div className="mb-3">
                  <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Modo de Ubicación KV</div>
                  <div className="grid grid-cols-3 gap-1 bg-surface/60 p-1 rounded border border-border/60">
                    {[
                      { id: 'auto', label: 'Automático' },
                      { id: 'gpu', label: 'Forzar VRAM' },
                      { id: 'ram', label: 'RAM (DDR5)' }
                    ].map((m) => {
                      const active = (systemStatus?.kv_mode || 'auto') === m.id;
                      return (
                        <button
                          key={m.id}
                          onClick={() => handleSelectMode(m.id)}
                          className={`text-[11px] py-1 px-1.5 rounded transition text-center font-medium ${
                            active
                              ? 'bg-purple-600 text-white shadow-sm'
                              : 'text-slate-400 hover:text-slate-200 hover:bg-surface'
                          }`}
                        >
                          {m.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <p className="text-[11px] text-slate-400 mb-2.5 leading-relaxed">
                  En <strong>Automático</strong>, el motor evalúa tu GPU en tiempo real. Si el contexto cabe en VRAM lo ejecuta a máxima velocidad; si es colosal, traslada el caché a tus <strong>64 GB DDR5</strong> sin saturar la VRAM.
                </p>

                {/* Preset List */}
                <div className="space-y-1.5 mb-2.5">
                  {activePresets.map((preset) => {
                    const isSelected = (systemStatus?.n_ctx || 32768) === preset.tokens;
                    const tokensK = Math.round(preset.tokens / 1024);
                    const gbLabel = preset.kv_gb ? `~${preset.kv_gb} GB` : '';
                    const locLabel = preset.location === 'ram' ? 'RAM DDR5' : 'VRAM';
                    return (
                      <button
                        key={preset.tokens}
                        onClick={() => handleSelectContext(preset.tokens)}
                        className={`w-full text-left p-2 rounded border transition flex items-start justify-between ${
                          isSelected
                            ? 'bg-purple-950/40 border-purple-500/60 text-white'
                            : 'bg-surface/50 border-border/60 hover:bg-surface text-slate-300 hover:text-white'
                        }`}
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center space-x-1.5">
                            <span className="font-semibold text-xs text-purple-200">{tokensK}K Tokens</span>
                            {gbLabel && (
                              <span className="text-[10px] text-purple-400/90 font-mono">
                                ({gbLabel} · {locLabel})
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-slate-400">{preset.desc || 'Optimizado'}</div>
                        </div>
                        {isSelected && (
                          <div className="w-4 h-4 rounded-full bg-purple-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <Check size={10} className="text-white" />
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>

                <div className="pt-2 border-t border-border/80 flex items-center justify-between text-[10px] text-slate-400">
                  <span>RAM Total: <strong className="text-slate-200">{systemStatus?.ram_total_gb || 64} GB</strong> (Libre: <strong className="text-emerald-400">{systemStatus?.ram_available_gb || 45} GB</strong>)</span>
                  <span>VRAM: <strong className="text-blue-300">{systemStatus?.gpu_vram || '16 GB'}</strong></span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* OTA Update Status & Sync Button */}
        {updateStatus?.status === 'downloaded' ? (
          <button
            onClick={handleRestartForUpdate}
            className="flex items-center space-x-1.5 bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 px-2 py-0.5 rounded font-medium hover:bg-emerald-600/30 transition animate-bounce"
          >
            <DownloadCloud size={12} />
            <span>Reiniciar para aplicar v{updateStatus.version}</span>
          </button>
        ) : updateStatus?.status === 'downloading' ? (
          <div className="flex items-center space-x-1 bg-blue-600/20 border border-blue-500/30 text-blue-300 px-2 py-0.5 rounded">
            <RefreshCw size={11} className="animate-spin text-blue-400" />
            <span>Descargando OTA ({updateStatus.percent}%)</span>
          </div>
        ) : (
          <button
            onClick={handleCheckUpdates}
            disabled={isSyncing}
            className="flex items-center space-x-1.5 bg-surface/80 hover:bg-surfaceHover text-slate-300 hover:text-white px-2 py-0.5 rounded border border-border/80 transition"
            title="Buscar actualizaciones y sincronizar con el repositorio"
          >
            <RefreshCw size={11} className={isSyncing ? "animate-spin text-blue-400" : "text-slate-400"} />
            <span>{syncMessage || "Buscar Actualizaciones"}</span>
          </button>
        )}
      </div>

      {/* Window Controls */}
      <div className="flex items-center no-drag space-x-1 flex-shrink-0">
        <button
          onClick={handleMinimize}
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-surfaceHover text-slate-400 hover:text-slate-200 transition"
          title="Minimizar"
        >
          <Minus size={14} />
        </button>
        <button
          onClick={handleMaximize}
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-surfaceHover text-slate-400 hover:text-slate-200 transition"
          title={isMaximized ? "Restaurar" : "Maximizar"}
        >
          {isMaximized ? <Copy size={11} className="rotate-180" /> : <Square size={12} />}
        </button>
        <button
          onClick={handleClose}
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-rose-600 text-slate-400 hover:text-white transition"
          title="Cerrar"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
