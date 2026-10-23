import React, { useState, useEffect } from 'react';
import { Terminal, Bug, RefreshCw, X, Copy, Check, ExternalLink, AlertTriangle, ShieldCheck, HardDrive } from 'lucide-react';
import { API_BASE, isElectron } from '../config';

export default function DiagnosticModal({ isOpen, onClose, systemStatus, isBackendConnected }) {
  const [logs, setLogs] = useState([]);
  const [copied, setCopied] = useState(false);
  const [backendInfo, setBackendInfo] = useState(null);
  const [isRestarting, setIsRestarting] = useState(false);
  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'errors' | 'backend'

  // Capture frontend console errors
  useEffect(() => {
    const handleWindowError = (event) => {
      setLogs((prev) => [
        ...prev,
        {
          type: 'stderr',
          source: 'frontend',
          text: `[Frontend Uncaught] ${event.message} at ${event.filename || ''}:${event.lineno || 0}`,
          time: new Date().toLocaleTimeString()
        }
      ]);
    };

    const handleUnhandledRejection = (event) => {
      setLogs((prev) => [
        ...prev,
        {
          type: 'stderr',
          source: 'frontend',
          text: `[Frontend Promise Error] ${event.reason?.message || event.reason}`,
          time: new Date().toLocaleTimeString()
        }
      ]);
    };

    window.addEventListener('error', handleWindowError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    // Initial logs from electron backend manager
    if (window.electronAPI?.getBackendLogs) {
      window.electronAPI.getBackendLogs().then((backendLogs) => {
        if (Array.isArray(backendLogs)) {
          setLogs((prev) => [
            ...backendLogs.map((l) => ({ ...l, source: 'backend' })),
            ...prev
          ]);
        }
      });
    }

    if (window.electronAPI?.getBackendStatus) {
      window.electronAPI.getBackendStatus().then(setBackendInfo);
    }

    // Subscribe to live backend logs
    let unsubscribe;
    if (window.electronAPI?.onBackendLog) {
      unsubscribe = window.electronAPI.onBackendLog((log) => {
        setLogs((prev) => [...prev.slice(-300), { ...log, source: 'backend' }]);
      });
    }

    return () => {
      window.removeEventListener('error', handleWindowError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      if (unsubscribe) unsubscribe();
    };
  }, []);

  if (!isOpen) return null;

  const handleOpenDevTools = () => {
    if (window.electronAPI?.openDevTools) {
      window.electronAPI.openDevTools('detach');
    }
  };

  const handleReload = () => {
    if (window.electronAPI?.reloadWindow) {
      window.electronAPI.reloadWindow();
    } else {
      window.location.reload();
    }
  };

  const handleRestartBackend = async () => {
    setIsRestarting(true);
    try {
      if (window.electronAPI?.restartBackend) {
        await window.electronAPI.restartBackend();
      }
      setTimeout(() => {
        setIsRestarting(false);
        if (window.electronAPI?.getBackendStatus) {
          window.electronAPI.getBackendStatus().then(setBackendInfo);
        }
      }, 2000);
    } catch (e) {
      setIsRestarting(false);
    }
  };

  const handleCopyLogs = () => {
    const text = logs.map((l) => `[${l.time}] [${l.type.toUpperCase()}] ${l.text}`).join('\n');
    const fullReport = `=== AGENTE DIAGNOSTIC REPORT ===
Hora: ${new Date().toISOString()}
Plataforma: ${window.electronAPI?.platform || navigator.platform}
isElectron: ${isElectron}
API_BASE: ${API_BASE}
Backend Conectado: ${isBackendConnected}
GPU: ${systemStatus?.gpu_name || 'N/A'} (${systemStatus?.gpu_backend || 'N/A'})
VRAM: ${systemStatus?.gpu_vram || 'N/A'}
RAM: ${systemStatus?.ram_total_gb || 'N/A'} GB
Modelo Activo: ${systemStatus?.active_model || 'None'}

=== LOGS ===
${text}`;
    navigator.clipboard.writeText(fullReport);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filteredLogs = logs.filter((l) => {
    if (activeTab === 'errors') return l.type === 'stderr';
    if (activeTab === 'backend') return l.source === 'backend';
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-4xl bg-[#090D14] border border-border/80 rounded-2xl shadow-2xl flex flex-col overflow-hidden max-h-[88vh]">
        {/* Header */}
        <div className="px-5 py-3.5 bg-[#0C111B] border-b border-border/80 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Terminal size={17} />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-semibold text-slate-100">Consola de Diagnóstico & DevTools</h3>
                <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/30 px-1.5 py-0.5 rounded font-mono">
                  Atajo: F12 o Ctrl+Shift+I
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Inspección de procesos de backend (Python FastAPI), consola webkit y llamadas IPC.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleOpenDevTools}
              className="flex items-center space-x-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1.5 rounded-lg font-medium transition shadow-sm"
              title="Abre la ventana completa de Google Chrome / WebKit Developer Tools"
            >
              <Bug size={13} />
              <span>Abrir Chrome DevTools (F12)</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surfaceHover transition"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Status Strip */}
        <div className="bg-[#0A0F18] border-b border-border/60 px-5 py-2.5 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div className="flex items-center space-x-2">
            <div className={`w-2.5 h-2.5 rounded-full ${isBackendConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-rose-500'}`} />
            <div>
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Backend 8765</div>
              <div className="font-mono text-slate-200">
                {isBackendConnected ? 'Online (200 OK)' : 'Desconectado'}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <HardDrive size={14} className="text-purple-400" />
            <div>
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Aceleración</div>
              <div className="font-mono text-slate-200 truncate">
                {systemStatus?.gpu_backend || 'CUDA / Vulkan'}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <ShieldCheck size={14} className="text-emerald-400" />
            <div>
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Entorno</div>
              <div className="font-mono text-slate-200">
                {isElectron ? 'Desktop Electron' : 'Web Studio'}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <AlertTriangle size={14} className="text-amber-400" />
            <div>
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Errores detectados</div>
              <div className="font-mono text-slate-200">
                {logs.filter((l) => l.type === 'stderr').length} alertas
              </div>
            </div>
          </div>
        </div>

        {/* Tabs and Actions Bar */}
        <div className="px-5 py-2 bg-[#0C111C]/60 border-b border-border/60 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-1.5">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-2.5 py-1 rounded text-xs transition ${
                activeTab === 'all' ? 'bg-slate-800 text-white font-medium' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Todos ({logs.length})
            </button>
            <button
              onClick={() => setActiveTab('errors')}
              className={`px-2.5 py-1 rounded text-xs transition ${
                activeTab === 'errors' ? 'bg-rose-950/60 border border-rose-500/40 text-rose-300 font-medium' : 'text-slate-400 hover:text-rose-400'
              }`}
            >
              Errores & Alertas ({logs.filter((l) => l.type === 'stderr').length})
            </button>
            <button
              onClick={() => setActiveTab('backend')}
              className={`px-2.5 py-1 rounded text-xs transition ${
                activeTab === 'backend' ? 'bg-slate-800 text-white font-medium' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Logs de Backend
            </button>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleRestartBackend}
              disabled={isRestarting}
              className="flex items-center space-x-1 px-2.5 py-1 rounded bg-surface hover:bg-surfaceHover text-slate-300 text-xs transition border border-border/60"
            >
              <RefreshCw size={11} className={isRestarting ? 'animate-spin text-blue-400' : ''} />
              <span>{isRestarting ? 'Reiniciando...' : 'Reconectar Python'}</span>
            </button>

            <button
              onClick={handleReload}
              className="flex items-center space-x-1 px-2.5 py-1 rounded bg-surface hover:bg-surfaceHover text-slate-300 text-xs transition border border-border/60"
            >
              <RefreshCw size={11} />
              <span>Recargar (Ctrl+R)</span>
            </button>

            <button
              onClick={handleCopyLogs}
              className="flex items-center space-x-1 px-2.5 py-1 rounded bg-surface hover:bg-surfaceHover text-slate-300 text-xs transition border border-border/60"
            >
              {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
              <span>{copied ? 'Copiado' : 'Copiar todo'}</span>
            </button>
          </div>
        </div>

        {/* Console Log Output */}
        <div className="p-4 bg-[#05080E] font-mono text-[11px] overflow-y-auto flex-1 space-y-1.5 select-text leading-relaxed">
          {filteredLogs.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Bug size={24} className="mx-auto mb-2 opacity-40" />
              <p>No hay eventos registrados en este canal.</p>
              <p className="text-[10px] text-slate-600 mt-1">Haz clic en "Abrir Chrome DevTools" para inspeccionar la red y los scripts en vivo.</p>
            </div>
          ) : (
            filteredLogs.map((log, idx) => {
              const isError = log.type === 'stderr';
              const isSystem = log.type === 'system';
              return (
                <div
                  key={idx}
                  className={`flex items-start space-x-2 py-0.5 px-2 rounded ${
                    isError
                      ? 'bg-rose-950/20 text-rose-300 border-l-2 border-rose-500'
                      : isSystem
                      ? 'bg-blue-950/20 text-blue-300 border-l-2 border-blue-500'
                      : 'text-slate-300 hover:bg-slate-900/40'
                  }`}
                >
                  <span className="text-slate-600 select-none flex-shrink-0 text-[10px]">{log.time}</span>
                  <span
                    className={`text-[9px] uppercase px-1 rounded flex-shrink-0 font-bold ${
                      isError
                        ? 'bg-rose-500/20 text-rose-400'
                        : isSystem
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {log.type}
                  </span>
                  <span className="break-all whitespace-pre-wrap">{log.text}</span>
                </div>
              );
            })
          )}
        </div>

        {/* Footer advice */}
        <div className="px-5 py-2.5 bg-[#0C111B] border-t border-border/80 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center space-x-2">
            <span>💡 <strong>Consejo:</strong> Haz clic derecho en cualquier parte de la ventana para "Inspeccionar elemento" o pulsa <strong>F12</strong>.</span>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition text-xs font-medium"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
