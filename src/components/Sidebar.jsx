import React, { useState } from 'react';
import { Folder, FileText, ExternalLink, Plus, Trash2, AlertCircle, Check, X } from 'lucide-react';
import { FolderGit } from 'lucide-react';

export default function Sidebar({
  projects,
  activeProject,
  onSelectProject,
  onCreateProject,
  onDeleteProject,
  onOpenProjectFolder,
  onOpenFile,
  projectFiles
}) {
  const [isCreating, setIsCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    const trimmed = newProjectName.trim();
    if (!trimmed) return;

    if (/[\\/:*?"<>|]/.test(trimmed) || /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i.test(trimmed)) {
      setErrorMsg('Nombre no permitido por Windows.');
      return;
    }

    if (projects.some(p => p.name.toLowerCase() === trimmed.toLowerCase())) {
      setErrorMsg('Ya existe un proyecto con ese nombre.');
      return;
    }

    onCreateProject(trimmed);
    setNewProjectName('');
    setErrorMsg('');
    setIsCreating(false);
  };
// Dentro del componente Sidebar:
const handleOpenLocalRepo = async () => {
  if (window.electronAPI && window.electronAPI.selectFolder) {
    const selectedPath = await window.electronAPI.selectFolder();
    if (selectedPath) {
      // Conectar el repo con el backend
      const res = await fetch('http://127.0.0.1:8765/api/workspace/open-repo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: selectedPath })
      });
      if (res.ok) {
        const data = await res.json();
        onSelectProject(data.name);
      }
    }
  }
};
  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setIsCreating(false);
      setNewProjectName('');
      setErrorMsg('');
    }
  };

  return (
    
    <aside className="w-64 bg-[#0D121F] border-r border-border flex flex-col h-full select-none flex-shrink-0">
      {/* Header */}
<div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <Folder size={14} className="text-blue-400" />
          <span>Workspace</span>
        </div>
        <div className="flex items-center space-x-1">
          {/* Botón para abrir repo existente de tu PC */}
          <button
            onClick={handleOpenLocalRepo}
            className="p-1 rounded hover:bg-surfaceHover text-slate-400 hover:text-emerald-400 transition"
            title="Abrir Repositorio Local"
          >
            <FolderGit size={16} />
          </button>
          {/* Botón de nuevo proyecto */}
          <button
            onClick={() => setIsCreating(true)}
            className="p-1 rounded hover:bg-surfaceHover text-slate-400 hover:text-blue-400 transition"
            title="Nuevo Proyecto"
          >
            <Plus size={16} />
          </button>
        </div>
      </div>

      {/* New Project Input */}
      {isCreating && (
        <form onSubmit={handleCreateSubmit} className="p-2 border-b border-border bg-surface/50">
          <input
            type="text"
            autoFocus
            maxLength={80}
            placeholder="Nombre del proyecto..."
            value={newProjectName}
            onKeyDown={handleKeyDown}
            onChange={(e) => {
              setNewProjectName(e.target.value);
              setErrorMsg('');
            }}
            className="w-full text-xs bg-background border border-border rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
          />
          {errorMsg && (
            <div className="flex items-center space-x-1 text-[10px] text-rose-400 mt-1">
              <AlertCircle size={10} />
              <span>{errorMsg}</span>
            </div>
          )}
          <div className="flex justify-between items-center mt-2">
            <span className="text-[10px] text-slate-500">Esc para cancelar</span>
            <div className="flex space-x-1.5">
              <button
                type="button"
                onClick={() => {
                  setIsCreating(false);
                  setErrorMsg('');
                }}
                className="text-xs px-2 py-0.5 rounded text-slate-400 hover:bg-surfaceHover"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="text-xs px-2.5 py-0.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium"
              >
                Crear
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Projects List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {projects.length === 0 ? (
          <div className="p-4 text-center text-slate-500 text-xs">
            <p className="font-medium text-slate-400">Sin proyectos</p>
            <p className="text-[11px] mt-1 text-slate-600">Haz clic en + para crear tu primer proyecto.</p>
          </div>
        ) : (
          projects.map((proj) => {
            const isActive = proj.name === activeProject;
            const isConfirming = confirmDelete === proj.name;
            return (
              <div
                key={proj.name}
                onClick={() => !isConfirming && onSelectProject(proj.name)}
                className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-xs transition cursor-pointer group ${
                  isActive
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 font-medium'
                    : 'text-slate-300 hover:bg-surface hover:text-slate-100 border border-transparent'
                }`}
                title={proj.name}
              >
                <div className="flex items-center space-x-2 truncate min-w-0 mr-2">
                  <Folder size={14} className={isActive ? 'text-blue-400 flex-shrink-0' : 'text-slate-400 group-hover:text-slate-300 flex-shrink-0'} />
                  <span className="truncate">{proj.name}</span>
                </div>
                <div className="flex items-center space-x-1 flex-shrink-0">
                  {isConfirming ? (
                    <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => {
                          onDeleteProject(proj.name);
                          setConfirmDelete(null);
                        }}
                        className="p-1 bg-rose-600 text-white rounded hover:bg-rose-500"
                        title="Confirmar eliminación"
                      >
                        <Check size={11} />
                      </button>
                      <button
                        onClick={() => setConfirmDelete(null)}
                        className="p-1 bg-surfaceHover text-slate-300 rounded hover:text-white"
                        title="Cancelar"
                      >
                        <X size={11} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        isActive ? 'bg-blue-500/20 text-blue-300' : 'bg-surface text-slate-500'
                      }`}>
                        {proj.file_count}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDelete(proj.name);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 text-slate-500 rounded transition"
                        title={`Eliminar ${proj.name}`}
                      >
                        <Trash2 size={12} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Project Folder Actions */}
      {activeProject && (
        <div className="p-3 border-t border-border bg-[#0B0F17]/60">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Carpeta de Trabajo</span>
            <button
              onClick={() => onOpenProjectFolder(activeProject)}
              className="flex items-center space-x-1 text-blue-400 hover:text-blue-300 transition text-[11px] px-1.5 py-0.5 rounded hover:bg-surfaceHover"
              title="Abrir en el Explorador de Windows"
            >
              <span>Abrir</span>
              <ExternalLink size={11} />
            </button>
          </div>

          <div className="max-h-36 overflow-y-auto space-y-1 text-xs">
            {projectFiles && projectFiles.length > 0 ? (
              projectFiles.map((file) => (
                <button
                  key={file.name}
                  onClick={() => onOpenFile && onOpenFile(file.path)}
                  className="w-full flex items-center space-x-2 text-slate-400 hover:text-blue-400 hover:bg-surface/60 px-1.5 py-1 rounded truncate text-left transition"
                  title={`Abrir ${file.name}`}
                >
                  <FileText size={12} className="text-slate-500 flex-shrink-0" />
                  <span className="truncate text-[11px]">{file.name}</span>
                </button>
              ))
            ) : (
              <p className="text-[11px] text-slate-500 italic">Sin archivos todavía</p>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}