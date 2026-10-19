import React from 'react';
import {
  FileSpreadsheet,
  FileText,
  Presentation,
  File,
  ExternalLink,
  Download,
  CheckCircle2,
  FolderOpen,
  Sparkles
} from 'lucide-react';

export default function ArtifactsPanel({ artifacts, onOpenFile, onOpenProjectFolder, activeProject }) {
  const getFileBadge = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    switch (ext) {
      case 'xlsx':
      case 'xls':
      case 'csv':
        return {
          icon: <FileSpreadsheet size={16} className="text-emerald-400" />,
          label: 'Excel',
          color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
          btnHover: 'hover:bg-emerald-600 hover:text-white'
        };
      case 'docx':
      case 'doc':
        return {
          icon: <FileText size={16} className="text-blue-400" />,
          label: 'Word',
          color: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
          btnHover: 'hover:bg-blue-600 hover:text-white'
        };
      case 'pptx':
      case 'ppt':
        return {
          icon: <Presentation size={16} className="text-amber-400" />,
          label: 'PowerPoint',
          color: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
          btnHover: 'hover:bg-amber-600 hover:text-white'
        };
      case 'pdf':
        return {
          icon: <FileText size={16} className="text-rose-400" />,
          label: 'PDF',
          color: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
          btnHover: 'hover:bg-rose-600 hover:text-white'
        };
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'webp':
      case 'bmp':
        return {
          icon: <File size={16} className="text-purple-400" />,
          label: 'Imagen',
          color: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
          btnHover: 'hover:bg-purple-600 hover:text-white'
        };
      case 'zip':
      case 'rar':
        return {
          icon: <FolderOpen size={16} className="text-yellow-400" />,
          label: 'ZIP',
          color: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
          btnHover: 'hover:bg-yellow-600 hover:text-white'
        };
      case 'json':
      case 'xml':
      case 'html':
      case 'sql':
      case 'md':
        return {
          icon: <File size={16} className="text-cyan-400" />,
          label: ext.toUpperCase(),
          color: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
          btnHover: 'hover:bg-cyan-600 hover:text-white'
        };
      default:
        return {
          icon: <File size={16} className="text-slate-400" />,
          label: ext.toUpperCase(),
          color: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
          btnHover: 'hover:bg-slate-600 hover:text-white'
        };
    }
  };

  const formatSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 KB';
    const k = 1024;
    if (bytes < k * 1024) return (bytes / k).toFixed(1) + ' KB';
    return (bytes / (k * k)).toFixed(1) + ' MB';
  };

  return (
    <aside className="w-80 bg-[#0D121F] border-l border-border flex flex-col h-full select-none">
      {/* Header */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <Sparkles size={14} className="text-blue-400" />
          <span>Artefactos y Entregables</span>
        </div>
        {activeProject && (
          <button
            onClick={() => onOpenProjectFolder(activeProject)}
            className="p-1 rounded hover:bg-surfaceHover text-slate-400 hover:text-blue-400 transition"
            title="Abrir carpeta del proyecto en Windows"
          >
            <FolderOpen size={16} />
          </button>
        )}
      </div>

      {/* Artifacts List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {artifacts && artifacts.length > 0 ? (
          artifacts.map((art, idx) => {
            const badge = getFileBadge(art.name);
            return (
              <div
                key={idx}
                className="bg-surface rounded-xl p-3 border border-border hover:border-slate-700 transition shadow-sm group"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <div className="p-2 rounded-lg bg-background border border-border">
                      {badge.icon}
                    </div>
                    <div>
                      <h4 className="text-xs font-medium text-slate-200 line-clamp-1 group-hover:text-blue-400 transition">
                        {art.name}
                      </h4>
                      <div className="flex items-center space-x-1.5 mt-0.5">
                        <span className={`text-[9px] px-1.5 py-0.2 rounded border font-semibold ${badge.color}`}>
                          {badge.label}
                        </span>
                        <span className="text-[10px] text-slate-500">
                          {formatSize(art.size_bytes || art.size)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Primary Action Button */}
                <button
                  onClick={() => onOpenFile(art.path)}
                  className={`w-full mt-2 py-1.5 px-3 rounded-lg text-xs font-medium bg-background hover:bg-surfaceHover text-slate-200 border border-border flex items-center justify-center space-x-1.5 transition ${badge.btnHover}`}
                >
                  <span>Abrir en {badge.label}</span>
                  <ExternalLink size={12} />
                </button>
              </div>
            );
          })
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
            <div className="w-12 h-12 rounded-full bg-surface flex items-center justify-center border border-border mb-3">
              <Sparkles size={20} className="text-slate-600" />
            </div>
            <p className="text-xs font-medium text-slate-400">Sin artefactos aún</p>
            <p className="text-[11px] text-slate-600 mt-1 max-w-[180px]">
              Los archivos Word, Excel o PowerPoint generados por el agente aparecerán aquí.
            </p>
          </div>
        )}
      </div>

      {/* Info footer */}
      <div className="p-3 border-t border-border bg-[#0B0F17]/60 text-[11px] text-slate-500 flex items-center justify-between">
        <span>Archivos guardados en disco</span>
        <span className="flex items-center space-x-1 text-emerald-400">
          <CheckCircle2 size={11} />
          <span>Sincronizado</span>
        </span>
      </div>
    </aside>
  );
}
