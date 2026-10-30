import React, { useState, useEffect } from 'react';
import {
  Minus,
  Square,
  Copy,
  X,
  Cpu,
  Sparkles,
  RefreshCw,
  DownloadCloud,
  Check,
  Brain,
  ChevronDown,
  Terminal,
  FolderOpen,
  HardDrive
} from 'lucide-react';
import { API_BASE } from '../config';
import DiagnosticModal from './DiagnosticModal';

const DEFAULT_MODELS = [
  {
    filename: 'Qwen3-30B-A3B-Q4_K_M.gguf',
    size_gb: 17.3,
    installed: true,
    badge: 'MoE • 64GB DDR5 + GPU',
    desc: 'Arquitectura Mixture-of-Experts (30B totales, 3B activos) • Máximo razonamiento'
  },
  {
    filename: 'Qwen3-8B-Q4_K_M.gguf',
    size_gb: 4.68,
    installed: true,
    badge: '100% VRAM • Ultrarrápido',
    desc: '100% en los 8GB VRAM de tu RTX 4070 • Respuesta instantánea'
  }
];

export default function TitleBar({
  activeProject,
  systemStatus,
  isBackendConnected,
  onRefreshStatus,
  usedTokens = 0
}) {
  const [updateStatus, setUpdateStatus] = useState(null);
  const [appVersion, setAppVersion] = useState('1.0.1');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [isMaximized, setIsMaximized] = useState(false);
  const [isContextOpen, setIsContextOpen] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  const [isDiagOpen, setIsDiagOpen] = useState(false);
  const [serverPresets, setServerPresets] = useState([]);
  const [modelsList, setModelsList] = useState(DEFAULT_MODELS);
  const [switchingModel, setSwitchingModel] = useState(null);
  const [downloadingModel, setDownloadingModel] = useState(null);

  const FALLBACK_PRESETS = [
    { tokens: 8192, kv_gb: 0.6, location: 'gpu', desc: '8K • Consultas puntuales y código rápido' },
    { tokens: 16384, kv_gb: 1.2, location: 'gpu', desc: '16K • Ensayos medianos y resúmenes ejecutivos' },
    { tokens: 32768, kv_gb: 2.4, location: 'gpu', desc: '32K • Estándar para PDFs de 50+ págs y Excel' },
    { tokens: 65536, kv_gb: 4.8, location: 'ram', desc: '64K • Podcasts 45 min, guiones de radio y transcripciones' },
    { tokens: 131072, kv_gb: 9.6, location: 'ram', desc: '128K Ultra • Libros completos y maratones en 64GB DDR5' }
  ];

  const fetchModels = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/models`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setModelsList(data);
        }
      }
    } catch (e) {}
  };

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
      fetchModels();
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

  const handleSelectModel = async (filename) => {
    if (!filename || switchingModel) return;
    setSwitchingModel(filename);
    try {
      const res = await fetch(`${API_BASE}/api/models/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename,
          n_ctx: systemStatus?.n_ctx || 32768
        })
      });
      if (res.ok) {
        await fetchModels();
        if (onRefreshStatus) await onRefreshStatus();
      }
    } catch (err) {
      console.error('Error al cambiar de modelo:', err);
    } finally {
      setSwitchingModel(null);
      setIsModelMenuOpen(false);
    }
  };

  const handleDownloadModel = async (e, filename) => {
    e.stopPropagation();
    setDownloadingModel(filename);
    try {
      await fetch(`${API_BASE}/api/models/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename })
      });
      setTimeout(() => {
        setDownloadingModel(null);
        fetchModels();
      }, 2500);
    } catch (err) {
      setDownloadingModel(null);
    }
  };

  const handleOpenModelsFolder = async (e) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/api/models/open-folder`, { method: 'POST' });
    } catch (err) {}
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

  const compareSemverClient = (vA, vB) => {
    const parse = (s) => {
      const m = String(s || '').match(/(\d+)\.(\d+)\.(\d+)/);
      return m ? [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)] : [0, 0, 0];
    };
    const [a1, a2, a3] = parse(vA);
    const [b1, b2, b3] = parse(vB);
    if (a1 !== b1) return a1 - b1;
    if (a2 !== b2) return a2 - b2;
    return a3 - b3;
  };

  useEffect(() => {
    let unsubUpdate = null;
    let unsubMax = null;
    if (window.electronAPI) {
      if (window.electronAPI.getAppVersion) {
        window.electronAPI.getAppVersion().then((ver) => {
          if (ver) setAppVersion(ver);
        });
      }
      if (window.electronAPI.onUpdateStatus) {
        unsubUpdate = window.electronAPI.onUpdateStatus((data) => {
          setUpdateStatus(data);
          if (data?.status === 'checking') {
            setIsSyncing(true);
            setSyncMessage('Buscando tags...');
          } else if (data?.status === 'available') {
            setIsSyncing(true);
            setSyncMessage(`Descargando v${data.version}...`);
          } else if (data?.status === 'downloading') {
            setIsSyncing(false);
            setSyncMessage('');
          } else if (data?.status === 'downloaded') {
            setIsSyncing(false);
            setSyncMessage(`¡v${data.version} lista!`);
          } else if (data?.status === 'tag-only') {
            setIsSyncing(false);
            setSyncMessage(`Nuevo tag v${data.version}`);
          } else if (data?.status === 'not-available') {
            setIsSyncing(false);
            setSyncMessage('Al día');
            setTimeout(() => setSyncMessage(''), 3000);
          } else if (data?.status === 'error') {
            setIsSyncing(false);
          }
        });
      }
      if (window.electronAPI.onMaximizedChange) {
        unsubMax = window.electronAPI.onMaximizedChange((maximized) => setIsMaximized(maximized));
      }
      if (window.electronAPI.isMaximized) {
        window.electronAPI.isMaximized().then((maximized) => setIsMaximized(maximized));
      }
    }
    return () => {
      if (typeof unsubUpdate === 'function') unsubUpdate();
      if (typeof unsubMax === 'function') unsubMax();
    };
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
    setSyncMessage('Buscando tags...');
    if (window.electronAPI && window.electronAPI.checkForUpdates) {
      window.electronAPI.checkForUpdates();
    }
    try {
      const res = await fetch(`${API_BASE}/api/system/git-pull`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success' && data.rebuilt) {
        setSyncMessage('¡Actualizado!');
        setTimeout(() => window.location.reload(), 1500);
        return;
      }
      if (data.latest_version && compareSemverClient(data.latest_version, appVersion) > 0) {
        if (!window.electronAPI) {
          setUpdateStatus({
            status: 'tag-only',
            version: data.latest_version,
            rawTag: data.latest_tag || `v${data.latest_version}`
          });
          setSyncMessage(`Nuevo tag v${data.latest_version}`);
        }
        return;
      }
      if (!window.electronAPI) {
        setSyncMessage('Al día');
        setTimeout(() => setSyncMessage(''), 3000);
      }
    } catch (e) {
      if (!window.electronAPI) {
        setSyncMessage('Al día');
        setTimeout(() => setSyncMessage(''), 2500);
      }
    } finally {
      if (!window.electronAPI) {
        setIsSyncing(false);
      }
    }
  };

  const currentModelName = systemStatus?.active_model || 'Qwen3-30B-A3B-Q4_K_M.gguf';
  const isEngineLoading = Boolean(switchingModel) || systemStatus?.engine_state === 'loading';

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
          <span
            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
              isBackendConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500 animate-ping'
            }`}
          />
          <span className="truncate text-slate-200 font-medium">{activeProject || 'Sin proyecto'}</span>
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
            percentUsed > 85
              ? 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'
              : percentUsed > 65
              ? 'bg-amber-400'
              : 'bg-emerald-400';

          const textColor =
            percentUsed > 85 ? 'text-rose-400 font-bold' : percentUsed > 65 ? 'text-amber-300' : 'text-emerald-300';

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

              <div className="w-20 lg:w-28 h-1.5 bg-slate-800/90 rounded-full overflow-hidden border border-slate-700/50">
                <div
                  className={`h-full ${barColor} transition-all duration-300 rounded-full`}
                  style={{ width: `${Math.max(percentUsed, 3)}%` }}
                />
              </div>

              <span className={`font-mono text-[10px] font-semibold ${textColor}`}>{percentFree}% libre</span>
            </div>
          );
        })()}
      </div>

      {/* Hardware, Model Selector & OTA Updates */}
      <div className="flex items-center space-x-1.5 text-[11px] text-slate-400 no-drag whitespace-nowrap flex-shrink-0">
        {/* Interactive Model Selector Badge & Dropdown */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              if (!isModelMenuOpen) fetchModels();
              setIsModelMenuOpen(!isModelMenuOpen);
              setIsContextOpen(false);
            }}
            className={`flex items-center space-x-1.5 px-2.5 py-0.5 rounded border transition cursor-pointer ${
              isEngineLoading
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/40 hover:bg-amber-500/25'
                : 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
            }`}
            title="Haz clic para cambiar entre modelos locales (.GGUF)"
          >
            {isEngineLoading ? (
              <RefreshCw size={11} className="animate-spin text-amber-400 flex-shrink-0" />
            ) : (
              <Sparkles size={11} className="text-emerald-400 flex-shrink-0" />
            )}
            <span className="font-medium truncate max-w-[145px] xl:max-w-[210px]">
              {switchingModel
                ? `Cargando ${switchingModel.replace(/\.gguf$/i, '')}...`
                : currentModelName.replace(/\.gguf$/i, '').replace(/[-_]/g, ' ')}
            </span>
            <ChevronDown
              size={10}
              className={`text-emerald-400/80 transition-transform ${isModelMenuOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {isModelMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsModelMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1.5 w-80 sm:w-96 max-w-[94vw] bg-[#0F141C] border border-border rounded-xl shadow-2xl p-3.5 z-50 text-left whitespace-normal">
                <div className="flex items-center justify-between pb-2 mb-2.5 border-b border-border/80">
                  <div className="flex items-center space-x-1.5 text-slate-200 font-medium text-xs">
                    <Sparkles size={13} className="text-emerald-400" />
                    <span>Selector de Modelo GGUF</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <button
                      type="button"
                      onClick={handleOpenModelsFolder}
                      className="flex items-center space-x-1 text-[10px] bg-surface hover:bg-surfaceHover text-slate-300 px-2 py-0.5 rounded border border-border transition"
                      title="Abrir carpeta ~/AgenteStudio/models en Windows"
                    >
                      <FolderOpen size={10} className="text-blue-400" />
                      <span>Carpeta</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => fetchModels()}
                      className="p-1 bg-surface hover:bg-surfaceHover text-slate-300 rounded border border-border transition"
                      title="Escanear carpeta de modelos"
                    >
                      <RefreshCw size={10} />
                    </button>
                  </div>
                </div>

                <div className="space-y-2 mb-2.5 max-h-72 overflow-y-auto pr-0.5">
                  {modelsList.map((model) => {
                    const isSelected =
                      currentModelName.toLowerCase() === model.filename.toLowerCase();
                    const isSwitchingThis = switchingModel === model.filename;
                    const isDownloadingThis = downloadingModel === model.filename;
                    const isInstalled = model.installed !== false;

                    return (
                      <div
                        key={model.filename}
                        onClick={() => handleSelectModel(model.filename)}
                        className={`w-full text-left p-2.5 rounded-lg border transition cursor-pointer flex items-start justify-between gap-2 ${
                          isSelected
                            ? 'bg-emerald-950/40 border-emerald-500/60 text-white shadow-sm'
                            : 'bg-surface/50 border-border/60 hover:bg-surface text-slate-300 hover:text-white'
                        }`}
                      >
                        <div className="space-y-1 min-w-0 flex-1">
                          <div className="flex items-center flex-wrap gap-1.5">
                            <span className="font-semibold text-xs text-slate-100 truncate">
                              {model.filename.replace(/\.gguf$/i, '')}
                            </span>
                            <span className="text-[10px] bg-blue-500/15 text-blue-300 border border-blue-500/30 px-1.5 py-0.2 rounded font-mono">
                              {model.size_gb} GB
                            </span>
                            {model.badge && (
                              <span className="text-[10px] bg-purple-500/15 text-purple-300 border border-purple-500/30 px-1.5 py-0.2 rounded font-mono">
                                {model.badge}
                              </span>
                            )}
                          </div>

                          <div className="text-[10px] text-slate-400 leading-snug">
                            {model.desc || 'Modelo cuantizado GGUF para inferencia local'}
                          </div>

                          <div className="flex items-center space-x-2 pt-0.5">
                            {isInstalled ? (
                              <span className="inline-flex items-center space-x-1 text-[10px] text-emerald-400 font-medium">
                                <HardDrive size={10} />
                                <span>En disco (Verificado GGUF)</span>
                              </span>
                            ) : (
                              <div className="flex items-center space-x-2">
                                <span className="text-[10px] text-amber-400">
                                  {model.partial_gb > 0
                                    ? `Descarga parcial (${model.partial_gb} GB)`
                                    : 'No detectado en ~/AgenteStudio/models'}
                                </span>
                                <button
                                  type="button"
                                  onClick={(e) => handleDownloadModel(e, model.filename)}
                                  className="text-[10px] bg-blue-600 hover:bg-blue-500 text-white px-2 py-0.5 rounded font-medium transition flex items-center space-x-1"
                                >
                                  <DownloadCloud size={10} />
                                  <span>
                                    {isDownloadingThis
                                      ? 'Abriendo curl.exe...'
                                      : model.partial_gb > 0
                                      ? 'Reanudar'
                                      : 'Descargar'}
                                  </span>
                                </button>
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="flex-shrink-0 mt-1">
                          {isSwitchingThis ? (
                            <RefreshCw size={14} className="animate-spin text-amber-400" />
                          ) : isSelected ? (
                            <div className="w-4 h-4 rounded-full bg-emerald-600 flex items-center justify-center">
                              <Check size={10} className="text-white" />
                            </div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="pt-2 border-t border-border/80 flex items-center justify-between text-[10px] text-slate-400">
                  <span className="truncate">
                    Estado: <strong className="text-slate-200">{systemStatus?.engine_message || 'Listo'}</strong>
                  </span>
                  <span className="font-mono text-emerald-400 flex-shrink-0 ml-2">
                    {systemStatus?.gpu_backend || 'CUDA 12.x'}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Hardware Status */}
        <div className="hidden lg:flex items-center space-x-1 bg-surface/80 px-2 py-0.5 rounded border border-border/80">
          <Cpu size={11} className="text-blue-400 flex-shrink-0" />
          <span>
            {systemStatus?.gpu_name
              ? `${shortGpuName(systemStatus.gpu_name)} • ${systemStatus.gpu_backend}`
              : isBackendConnected
              ? 'Detectando GPU...'
              : 'Conectando...'}
          </span>
        </div>

        {/* Context RAM Allocation Badge & Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setIsContextOpen(!isContextOpen);
              setIsModelMenuOpen(false);
            }}
            className="flex items-center space-x-1 bg-surface/80 hover:bg-surfaceHover text-slate-300 hover:text-white px-2 py-0.5 rounded border border-border/80 transition"
            title="Configurar memoria para el contexto"
          >
            <Brain size={11} className="text-purple-400 flex-shrink-0" />
            <span>
              <strong className="text-purple-300">{systemStatus?.n_ctx_k || 32}K</strong>
              <span className="hidden xl:inline text-slate-500 ml-1">
                ({systemStatus?.context_ram_gb || 2.4} GB · {systemStatus?.kv_location === 'ram' ? 'RAM' : 'VRAM'})
              </span>
            </span>
            <ChevronDown
              size={10}
              className={`text-slate-400 transition-transform ${isContextOpen ? 'rotate-180' : ''}`}
            />
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
                  <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                    Modo de Ubicación KV
                  </div>
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
                  En <strong>Automático</strong>, el motor evalúa tu GPU en tiempo real y combina tu VRAM con tus{' '}
                  <strong>{systemStatus?.ram_total_gb || 64} GB DDR5</strong>.
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
                  <span>
                    RAM: <strong className="text-slate-200">{systemStatus?.ram_total_gb || 64} GB</strong> (Libre:{' '}
                    <strong className="text-emerald-400">{systemStatus?.ram_available_gb || 41} GB</strong>)
                  </span>
                  <span>
                    VRAM: <strong className="text-blue-300">{systemStatus?.gpu_vram || '8.0 GB'}</strong>
                  </span>
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
            title={`Instalar actualización v${updateStatus.version} ahora`}
          >
            <DownloadCloud size={11} />
            <span>Aplicar v{updateStatus.version}</span>
          </button>
        ) : updateStatus?.status === 'downloading' ? (
          <div className="flex items-center space-x-1 bg-blue-600/20 border border-blue-500/30 text-blue-300 px-2 py-0.5 rounded">
            <RefreshCw size={10} className="animate-spin text-blue-400" />
            <span>
              OTA {updateStatus.version ? `v${updateStatus.version} ` : ''}({updateStatus.percent}%)
            </span>
          </div>
        ) : updateStatus?.status === 'tag-only' ? (
          <button
            onClick={() => {
              const url = `https://github.com/DriifterSelf/agente/releases`;
              if (window.electronAPI?.openExternal) {
                window.electronAPI.openExternal(url);
              } else {
                handleCheckUpdates();
              }
            }}
            className="flex items-center space-x-1 bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/25 px-2 py-0.5 rounded font-medium transition"
            title={`Tag v${updateStatus.version} detectado en GitHub (Haz clic para ver el estado del Release en GitHub)`}
          >
            <DownloadCloud size={11} className="text-amber-400" />
            <span>Nuevo Tag v{updateStatus.version}</span>
          </button>
        ) : (
          <button
            onClick={handleCheckUpdates}
            disabled={isSyncing}
            className="flex items-center space-x-1 bg-surface/80 hover:bg-surfaceHover text-slate-300 hover:text-white px-2 py-0.5 rounded border border-border/80 transition"
            title={`Versión actual: v${appVersion} • Haz clic para buscar nuevos tags (v1.2.0, v1.3.0, v2.0.0...)`}
          >
            <RefreshCw size={10} className={isSyncing ? 'animate-spin text-blue-400' : 'text-slate-400'} />
            <span className="hidden md:inline">{syncMessage || `Actualizar (v${appVersion})`}</span>
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
          title={isMaximized ? 'Restaurar' : 'Maximizar'}
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