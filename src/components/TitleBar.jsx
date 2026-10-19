import React, { useState, useEffect } from 'react';
import { Minus, Square, X, Cpu, Sparkles, RefreshCw, DownloadCloud, Check } from 'lucide-react';

export default function TitleBar({ activeProject, systemStatus }) {
  const [updateStatus, setUpdateStatus] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');

  useEffect(() => {
    // Listen to Electron OTA auto-updater events if running inside Electron
    if (window.electronAPI && window.electronAPI.onUpdateStatus) {
      window.electronAPI.onUpdateStatus((data) => {
        setUpdateStatus(data);
      });
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
      {/* Brand & Project */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2 text-blue-400 font-semibold text-sm">
          <div className="w-5 h-5 rounded bg-blue-600/20 flex items-center justify-center border border-blue-500/30">
            <Sparkles size={12} className="text-blue-400" />
          </div>
          <span className="tracking-wide text-slate-100">Agente Studio</span>
        </div>

        <div className="h-4 w-[1px] bg-border" />

        <div className="flex items-center space-x-1.5 text-xs text-textMuted bg-surface px-2.5 py-0.5 rounded-full border border-border">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>Proyecto: <strong className="text-slate-200">{activeProject || 'Sin selección'}</strong></span>
        </div>
      </div>

      {/* Hardware & OTA Updates */}
      <div className="hidden md:flex items-center space-x-2 text-xs text-slate-400 no-drag">
        {/* Hardware Status */}
        <div className="flex items-center space-x-1.5 bg-surface/80 px-2.5 py-0.5 rounded border border-border/80">
          <Cpu size={12} className="text-blue-400" />
          <span>
            {systemStatus?.gpu_name 
              ? `${systemStatus.gpu_name} • ${systemStatus.gpu_backend}`
              : 'Detectando aceleración GPU...'}
          </span>
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
      <div className="flex items-center no-drag space-x-1">
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
          title="Maximizar"
        >
          <Square size={12} />
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
