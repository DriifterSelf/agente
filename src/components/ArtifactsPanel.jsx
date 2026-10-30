import React, { useState } from 'react';
import {
  FileSpreadsheet,
  FileText,
  Presentation,
  File,
  ExternalLink,
  FolderOpen,
  Sparkles,
  Copy,
  Check,
  Search,
  Video,
  Music
} from 'lucide-react';

export default function ArtifactsPanel({ artifacts, onOpenFile, onOpenProjectFolder, activeProject }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [copiedPath, setCopiedPath] = useState(null);
  const [openingFile, setOpeningFile] = useState(null);

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
      case 'mp4':
      case 'mkv':
      case 'mov':
      case 'avi':
      case 'webm':
        return {
          icon: <Video size={16} className="text-indigo-400" />,
          label: 'Video',
          color: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
          btnHover: 'hover:bg-indigo-600 hover:text-white'
        };
      case 'mp3':
      case 'wav':
      case 'm4a':
      case 'ogg':
      case 'flac':
        return {
          icon: <Music size={16} className="text-pink-400" />,
          label: 'Audio',
          color: 'bg-pink-500/10 text-pink-400 border-pink-500/30',
          btnHover: 'hover:bg-pink-600 hover:text-white'
        };
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'webp':
      case 'bmp':
      case 'svg':
        return {
          icon: <File size={16} className="text-purple-400" />,
          label: filename.toLowerCase().startsWith('poster_') ? 'Póster HD' : 'Imagen',
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
      case 'html':
        if (filename.toLowerCase().startsWith('poster_')) {
          return {
            icon: <Presentation size={16} className="text-cyan-400" />,
            label: 'Póster A0/PDF',
            color: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/40',
            btnHover: 'hover:bg-cyan-600 hover:text-white'
          };
        }
        return {
          icon: <File size={16} className="text-cyan-400" />,
          label: 'HTML',
          color: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
          btnHover: 'hover:bg-cyan-600 hover:text-white'
        };
      case 'json':
      case 'xml':
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

  const copyPath = (path, name) => {
    navigator.clipboard.writeText(path);
    setCopiedPath(name);
    setTimeout(() => setCopiedPath(null), 2000);
  };

  const handleOpen = async (path, name) => {
    setOpeningFile(name);
    await onOpenFile(path);
    setTimeout(() => setOpeningFile(null), 1000);
  };

  const filteredArtifacts = (artifacts || []).filter(art => 
    art.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside className="w-80 bg-[#0D121F] border-l border-border flex flex-col h-full select-none">
      {/* Header */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <Sparkles size={14} className="text-blue-400" />
          <span>Artefactos ({artifacts ? artifacts.length : 0})</span>
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

      {/* Search Input if more than 3 artifacts */}
      {artifacts && artifacts.length > 3 && (
        <div className="p-2 border-b border-border bg-[#0B0F17]/40">
          <div className="relative flex items-center">
            <Search size={12} className="absolute left-2.5 text-slate-500 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar entregables..."
              className="w-full text-[11px] bg-background border border-border rounded-lg pl-7 pr-3 py-1 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
      )}

      {/* Artifacts List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {filteredArtifacts.length > 0 ? (
          filteredArtifacts.map((art, idx) => {
            const badge = getFileBadge(art.name);
            const isCopied = copiedPath === art.name;
            const isOpening = openingFile === art.name;
            return (
              <div
                key={idx}
                className="bg-surface rounded-xl p-3 border border-border hover:border-slate-700 transition shadow-sm group"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2 truncate mr-1">
                    <div className="p-2 rounded-lg bg-background border border-border flex-shrink-0">
                      {badge.icon}
                    </div>
                    <div className="truncate">
                      <h4
                        className="text-xs font-medium text-slate-200 truncate group-hover:text-blue-400 transition"
                        title={art.name}
                      >
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

                  {/* Copy Path Button */}
                  <button
                    onClick={() => copyPath(art.path, art.name)}
                    className="p-1 rounded hover:bg-surfaceHover text-slate-500 hover:text-slate-300 transition flex-shrink-0"
                    title="Copiar ruta de archivo"
                  >
                    {isCopied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                  </button>
                </div>

                {/* Primary Action Button */}
                <button
                  onClick={() => handleOpen(art.path, art.name)}
                  className={`w-full mt-2 py-1.5 px-3 rounded-lg text-xs font-medium bg-background hover:bg-surfaceHover text-slate-200 border border-border flex items-center justify-center space-x-1.5 transition ${badge.btnHover}`}
                >
                  <span>{isOpening ? 'Abriendo...' : `Abrir en ${badge.label}`}</span>
                  <ExternalLink size={12} />
                </button>
              </div>
            );
          })
        ) : artifacts && artifacts.length > 0 ? (
          <div className="p-6 text-center text-slate-500 text-xs">
            <p>No se encontraron archivos con "{searchTerm}"</p>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
            <div className="w-12 h-12 rounded-full bg-surface flex items-center justify-center border border-border mb-3 shadow-inner">
              <Sparkles size={20} className="text-slate-600" />
            </div>
            <p className="text-xs font-medium text-slate-400">Sin entregables aún</p>
            <p className="text-[11px] text-slate-600 mt-1 max-w-[180px]">
              Los archivos Word, Excel, PowerPoint, imágenes o audio generados aparecerán aquí.
            </p>
          </div>
        )}
      </div>

      {/* Info footer */}
      <div className="p-3 border-t border-border bg-[#0B0F17]/60 text-[11px] text-slate-500 flex items-center justify-between">
        <span className="truncate">Sincronizado con disco</span>
        <button
          onClick={() => activeProject && onOpenProjectFolder(activeProject)}
          className="text-blue-400 hover:text-blue-300 text-[10px] font-medium"
        >
          Explorar
        </button>
      </div>
    </aside>
  );
}
