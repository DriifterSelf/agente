import React, { useState, useEffect } from 'react';
import { Minus, Square, Copy, X, Cpu, Sparkles, RefreshCw, DownloadCloud, Check, Brain, ChevronDown, Terminal } from 'lucide-react';
import { API_BASE } from '../config';
import DiagnosticModal from './DiagnosticModal';

export default function TitleBar({ activeProject, systemStatus, isBackendConnected, onRefreshStatus, usedTokens = 0 }) {
  const [updateStatus, setUpdateStatus] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [isMaximized, setIsMaximized] = useState(false);
  const [isContextOpen, setIsContextOpen] = useState(false);
  const [isDiagOpen, setIsDiagOpen] = useState(false);
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
        const res = await fetch(`${API_BASE}/api/settings/context-presets`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setServerPresets(data);
          }
        }
      } catch (e) {}
    };
    if (isBackendConnected) {
      fetchPresets();
    }
  }, [isBackendConnected, systemStatus?.active_model]);

  const activePresets = serverPresets.length > 0 ? serverPresets : FALLBACK_PRESETS;

  const shortGpuName = (name) => {
    if (!name) return '';
    return name
      .replace(/NVIDIA GeForce /i, '')
      .replace(/AMD Radeon /i, '')
      .replace(/ Laptop GPU/i, '')
      .trim();
  };

  const handleSelectMode = async (mode) => {
    try {
      const currentTokens = systemStatus?.n_ctx || 32768;
      const res = await fetch(`${API_BASE}/api/settings/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ n_ctx: currentTokens, kv_mode: mode })
      });
      if (res.ok && onRefreshStatus) onRefreshStatus();
    } catch (err) {
      console.error('Error changing mode:', err);
    }
  };

  const handleSelectContext = async (tokens) => {
    try {
      const currentMode = systemStatus?.kv_mode || 'auto';
      const res = await fetch(`${API_BASE}/api/settings/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ n_ctx: tokens, kv_mode: currentMode })
      });
      if (res.ok && onRefreshStatus) onRefreshStatus();
    } catch (err) {
      console.error('Error changing context:', err);
    }
    setIsContextOpen(false);
  };

  useEffect(() => {
    if (window.electronAPI) {
      if (window.electronAPI.onUpdateStatus) {
        window.electronAPI.onUpdateStatus((data) => setUpdateStatus(data));
      }
      if (window.electronAPI.onMaximizedChange) {
        window.electronAPI.onMaximizedChange((maximized) => setIsMaximized(maximized));
      }
      if (window.electronAPI.isMaximized) {
        window.electronAPI.isMaximized().then((maximized) => setIsMaximized(maximized));
      }
    }
  }, []);

  const handleMinimize = (e) => {
    e?.preventDefault();
    e?.stopPropagation();
    if (window.electronAPI?.minimize) {
      window.electronAPI.minimize();
    }
  };

  const handleMaximize = (e) => {
    e?.preventDefault();
    e?.stopPropagation();
    if (window.electronAPI?.maximize) {
      window.electronAPI.maximize();
    }
  };

  const handleClose = (e) => {
    e?.preventDefault();
    e?.stopPropagation();
    if (window.electronAPI?.close) {
      window.electronAPI.close();
    }
  };

  const handleCheckUpdates = async () => {
    setIsSyncing(true);
    setSyncMessage('Buscando...');
    if (window.electronAPI && window.electronAPI.checkForUpdates) {
      window.electronAPI.checkForUpdates();
    }
    try {
      const res = await fetch(`${API_BASE}/api/system/git-pull`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success' && data.rebuilt) {
        setSyncMessage('¡Actualizado!');
        setTimeout(() => window.location.reload(), 1500);
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

  return (
    <div className="h-10 bg-[#070A0F] border-b border-border flex items-center justify-between select-none drag-region px-2.5 z-50 gap-2">
      {/* Brand & Project */}
      <div className="flex items-center space-x-2 min-w-0 flex-shrink">
        <div className="flex items-center space-x-1.5 text-blue-400 font-semibold text-xs sm:text-sm flex-shrink-0">
          <div className="w-5 h-5 rounded bg-blue-600/20 flex items-center justify-center border border-blue-500/30">
            <Sparkles size={12} className="text-blue-400" />
          </div>
          <span className="tracking-wide text-slate-100 whitespace-nowrap">Agente Studio</span>
        </div>

        <div className="h-4 w-[1px] bg-border flex-shrink-0 hidden sm:block" />

        <div
          className="hidden sm:flex items-center space-x-1.5 text-[11px] text-textMuted bg-surface px-2 py-0.5 rounded-full border border-border truncate max-w-[160px] lg:max-w-[220px]"
          title={`Proyecto activo: ${activeProject || 'Sin selección'}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
            isBackendConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500 animate-ping'
          }`} />
          <span className="truncate text-slate-200 font-medium">
            {activeProject || 'Sin proyecto'}
          </span>
        </div>
      </div>

      {/* HUD Central: Monitor de Contexto Restante */}
      <div className="hidden md:flex items-center justify-center flex-1 max-w-sm mx-2 no-drag">
        {(() => {
          const maxTokens = systemStatus?.n_ctx || 40960;
          const used = Math.min(usedTokens, maxTokens);
          const percentUsed = Math.min(100, Math.round((used / maxTokens) * 100));
          const percentFree = 100 - percentUsed;
          const usedK = (used / 1024).toFixed(1);
          const maxK = Math.round(maxTokens / 1024);
          const remainingTokens = Math.max(0, maxTokens - used);

          const barColor =
            percentUsed > 85 ? 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]' :
            percentUsed > 65 ? 'bg-amber-400' :
            'bg-emerald-400';

          const textColor =
            percentUsed > 85 ? 'text-rose-400 font-bold' :
            percentUsed > 65 ? 'text-amber-300' :
            'text-emerald-300';

          return (
            <div
              className="flex items-center space-x-2.5 bg-surface/70 hover:bg-surface border border-border/80 px-3 py-1 rounded-full text-[11px] transition cursor-default shadow-inner"
              title={`Contexto consumido: ~${used.toLocaleString()} tokens\nRestante disponible: ~${remainingTokens.toLocaleString()} tokens\nLímite máximo: ${maxTokens.toLocaleString()} tokens`}
            >
              <div className="flex items-center space-x-1.5 font-mono">
                <span className="text-slate-400 text-[10px]">CTX</span>
                <span className="font-semibold text-slate-200">{usedK}K</span>
                <span className="text-slate-500">/</span>
                <span className="text-slate-400">{maxK}K</span>
              </div>

              {/* Barra de progreso */}
              <div className="w-20 lg:w-28 h-1.5 bg-slate-800/90 rounded-full overflow-hidden border border-slate-700/50">
                <div
                  className={`h-full ${barColor} transition-all duration-300 rounded-full`}
                  style={{ width: `${Math.max(percentUsed, 3)}%` }}
                />
              </div>

              {/* Porcentaje libre */}
              <span className={`font-mono text-[10px] font-semibold ${textColor}`}>
                {percentFree}% libre
              </span>
            </div>
          );
        })()}
      </div>

      {/* Hardware & OTA Updates */}
      <div className="flex items-center space-x-1.5 text-[11px] text-slate-400 no-drag whitespace-nowrap flex-shrink-0">
        {/* Active Model Status Badge */}
        {systemStatus?.active_model ? (
          <div
            className="flex items-center space-x-1 bg-emerald-500/10 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30"
            title={systemStatus.engine_message || 'Motor local listo'}
          >
            <Sparkles size={11} className="text-emerald-400 flex-shrink-0" />
            <span className="font-medium truncate max-w-[140px] xl:max-w-none">
              {systemStatus.active_model.replace(/\.gguf$/i, '').replace(/[-_]/g, ' ')}
            </span>
          </div>
        ) : systemStatus?.engine_state === 'loading' ? (
          <div className="flex items-center space-x-1 bg-amber-500/10 text-amber-300 px-2 py-0.5 rounded border border-amber-500/30">
            <RefreshCw size={11} className="animate-spin text-amber-400" />
            <span>Cargando modelo...</span>
          </div>
        ) : null}

        {/* Hardware Status */}
        <div className="hidden lg:flex items-center space-x-1 bg-surface/80 px-2 py-0.5 rounded border border-border/80">
          <Cpu size={11} className="text-blue-400 flex-shrink-0" />
          <span>
            {systemStatus?.gpu_name 
              ? `${shortGpuName(systemStatus.gpu_name)} • ${systemStatus.gpu_backend}`
              : isBackendConnected ? 'Detectando GPU...' : 'Conectando...'}
          </span>
        </div>

        {/* Context RAM Allocation Badge & Dropdown */}
        <div className="relative">
          <button
            onClick={() => setIsContextOpen(!isContextOpen)}
            className="flex items-center space-x-1 bg-surface/80 hover:bg-surfaceHover text-slate-300 hover:text-white px-2 py-0.5 rounded border border-border/80 transition"
            title="Configurar memoria para el contexto"
          >
            <Brain size={11} className="text-purple-400 flex-shrink-0" />
            <span>
              <strong className="text-purple-300">{systemStatus?.n_ctx_k || 32}K</strong>
              <span className="hidden xl:inline text-slate-500 ml-1">
                ({systemStatus?.context_ram_gb || 1.6} GB · {systemStatus?.kv_location === 'ram' ? 'RAM' : 'VRAM'})
              </span>
            </span>
            <ChevronDown size={10} className={`text-slate-400 transition-transform ${isContextOpen ? 'rotate-180' : ''}`} />
          </button>

          {isContextOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsContextOpen(false)} />
              <div className="absolute right-0 top-full mt-1.5 w-80 sm:w-96 max-w-[92vw] bg-[#0F141C] border border-border rounded-xl shadow-2xl p-3.5 z-50 text-left whitespace-normal">
                <div className="flex items-center justify-between pb-2 mb-2.5 border-b border-border/80">
                  <div className="flex items-center space-x-1.5 text-slate-200 font-medium text-xs">
                    <Brain size={13} className="text-purple-400" />
                    <span>Ubicación y Memoria del Contexto</span>
                  </div>
                  <span className="text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 px-1.5 py-0.5 rounded font-mono">
                    KV en {systemStatus?.kv_location === 'ram' ? 'DDR5' : 'VRAM'}
                  </span>
                </div>

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
                  En <strong>Automático</strong>, el motor evalúa tu GPU en tiempo real y combina tu VRAM con tus <strong>{systemStatus?.ram_total_gb || 64} GB DDR5</strong>.
                </p>

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
                  <span>RAM: <strong className="text-slate-200">{systemStatus?.ram_total_gb || 64} GB</strong> (Libre: <strong className="text-emerald-400">{systemStatus?.ram_available_gb || 41} GB</strong>)</span>
                  <span>VRAM: <strong className="text-blue-300">{systemStatus?.gpu_vram || '8.0 GB'}</strong></span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* OTA Update Button */}
        {updateStatus?.status === 'downloaded' ? (
          <button
            onClick={() => window.electronAPI?.restartForUpdate()}
            className="flex items-center space-x-1 bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 px-2 py-0.5 rounded font-medium hover:bg-emerald-600/30 transition animate-bounce"
          >
            <DownloadCloud size={11} />
            <span>Aplicar v{updateStatus.version}</span>
          </button>
        ) : updateStatus?.status === 'downloading' ? (
          <div className="flex items-center space-x-1 bg-blue-600/20 border border-blue-500/30 text-blue-300 px-2 py-0.5 rounded">
            <RefreshCw size={10} className="animate-spin text-blue-400" />
            <span>OTA ({updateStatus.percent}%)</span>
          </div>
        ) : (
          <button
            onClick={handleCheckUpdates}
            disabled={isSyncing}
            className="flex items-center space-x-1 bg-surface/80 hover:bg-surfaceHover text-slate-300 hover:text-white px-2 py-0.5 rounded border border-border/80 transition"
            title="Buscar actualizaciones OTA"
          >
            <RefreshCw size={10} className={isSyncing ? "animate-spin text-blue-400" : "text-slate-400"} />
            <span className="hidden md:inline">{syncMessage || "Actualizar"}</span>
          </button>
        )}

        {/* DevTools & Diagnostics Button */}
        <button
          onClick={() => {
            if (window.electronAPI?.openDevTools) {
              window.electronAPI.openDevTools('detach');
            }
            setIsDiagOpen(true);
          }}
          className="flex items-center space-x-1 bg-surface/80 hover:bg-surfaceHover text-slate-300 hover:text-white px-2 py-0.5 rounded border border-border/80 transition"
          title="Consola de Desarrollador (F12) - Inspeccionar errores y llamadas"
        >
          <Terminal size={11} className="text-blue-400 flex-shrink-0" />
          <span className="hidden sm:inline font-mono text-[10px]">DevTools</span>
        </button>
      </div>

      {/* Window Controls */}
      <div
        className="flex items-center space-x-0.5 flex-shrink-0"
        style={{ WebkitAppRegion: 'no-drag', appRegion: 'no-drag' }}
      >
        <button
          type="button"
          title="Minimizar"
          onClick={handleMinimize}
          onMouseDown={(e) => e.stopPropagation()}
          className="no-drag w-7 h-7 flex items-center justify-center rounded hover:bg-surfaceHover text-slate-400 hover:text-slate-200 transition cursor-pointer"
          style={{ WebkitAppRegion: 'no-drag', appRegion: 'no-drag' }}
        >
          <Minus size={14} className="pointer-events-none" />
        </button>
        <button
          type="button"
          title={isMaximized ? "Restaurar" : "Maximizar"}
          onClick={handleMaximize}
          onMouseDown={(e) => e.stopPropagation()}
          className="no-drag w-7 h-7 flex items-center justify-center rounded hover:bg-surfaceHover text-slate-400 hover:text-slate-200 transition cursor-pointer"
          style={{ WebkitAppRegion: 'no-drag', appRegion: 'no-drag' }}
        >
          {isMaximized ? (
            <Copy size={11} className="rotate-180 pointer-events-none" />
          ) : (
            <Square size={12} className="pointer-events-none" />
          )}
        </button>
        <button
          type="button"
          title="Cerrar ventana"
          onClick={handleClose}
          onMouseDown={(e) => e.stopPropagation()}
          className="no-drag w-7 h-7 flex items-center justify-center rounded hover:bg-rose-600 text-slate-400 hover:text-white transition cursor-pointer"
          style={{ WebkitAppRegion: 'no-drag', appRegion: 'no-drag' }}
        >
          <X size={14} className="pointer-events-none" />
        </button>
      </div>

      {/* Diagnostic & DevTools Modal */}
      <DiagnosticModal
        isOpen={isDiagOpen}
        onClose={() => setIsDiagOpen(false)}
        systemStatus={systemStatus}
        isBackendConnected={isBackendConnected}
      />
    </div>
  );
}