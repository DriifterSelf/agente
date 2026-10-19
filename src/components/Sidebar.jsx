import React, { useState } from 'react';
import { Folder, FolderPlus, FileText, ExternalLink, HardDrive, Plus, Check } from 'lucide-react';

export default function Sidebar({
  projects,
  activeProject,
  onSelectProject,
  onCreateProject,
  onOpenProjectFolder,
  projectFiles
}) {
  const [isCreating, setIsCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    if (newProjectName.trim()) {
      onCreateProject(newProjectName.trim());
      setNewProjectName('');
      setIsCreating(false);
    }
  };

  return (
    <aside className="w-64 bg-[#0D121F] border-r border-border flex flex-col h-full select-none">
      {/* Header */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <Folder size={14} className="text-blue-400" />
          <span>Proyectos</span>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="p-1 rounded hover:bg-surfaceHover text-slate-400 hover:text-blue-400 transition"
          title="Nuevo Proyecto"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* New Project Input */}
      {isCreating && (
        <form onSubmit={handleCreateSubmit} className="p-2 border-b border-border bg-surface/50">
          <input
            type="text"
            autoFocus
            placeholder="Nombre del proyecto..."
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            className="w-full text-xs bg-background border border-border rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
          />
          <div className="flex justify-end space-x-1.5 mt-2">
            <button
              type="button"
              onClick={() => setIsCreating(false)}
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
        </form>
      )}

      {/* Projects List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {projects.map((proj) => {
          const isActive = proj.name === activeProject;
          return (
            <button
              key={proj.name}
              onClick={() => onSelectProject(proj.name)}
              className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-xs transition group ${
                isActive
                  ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 font-medium'
                  : 'text-slate-300 hover:bg-surface hover:text-slate-100 border border-transparent'
              }`}
            >
              <div className="flex items-center space-x-2 truncate">
                <Folder size={14} className={isActive ? 'text-blue-400' : 'text-slate-400 group-hover:text-slate-300'} />
                <span className="truncate">{proj.name}</span>
              </div>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                isActive ? 'bg-blue-500/20 text-blue-300' : 'bg-surface text-slate-500'
              }`}>
                {proj.file_count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Project Folder Actions */}
      {activeProject && (
        <div className="p-3 border-t border-border bg-[#0B0F17]/60">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Carpeta de Trabajo</span>
            <button
              onClick={() => onOpenProjectFolder(activeProject)}
              className="flex items-center space-x-1 text-blue-400 hover:text-blue-300 transition text-[11px]"
              title="Abrir en el Explorador de Windows"
            >
              <span>Abrir</span>
              <ExternalLink size={11} />
            </button>
          </div>

          <div className="max-h-36 overflow-y-auto space-y-1 text-xs">
            {projectFiles && projectFiles.length > 0 ? (
              projectFiles.map((file) => (
                <div
                  key={file.name}
                  className="flex items-center space-x-2 text-slate-400 hover:text-slate-200 py-0.5 truncate"
                >
                  <FileText size={12} className="text-slate-500 flex-shrink-0" />
                  <span className="truncate text-[11px]">{file.name}</span>
                </div>
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
