import React, { useState } from 'react';
import {
  Folder,
  FileText,
  ExternalLink,
  Plus,
  Trash2,
  AlertCircle,
  Check,
  X,
  FolderGit,
  MessageSquare,
  Edit2
} from 'lucide-react';
import { API_BASE } from '../config';

export default function Sidebar({
  projects,
  activeProject,
  onSelectProject,
  onCreateProject,
  onDeleteProject,
  onOpenProjectFolder,
  onOpenFile,
  projectFiles,
  conversations = [],
  activeConversationId = '',
  onSelectConversation,
  onCreateConversation,
  onRenameConversation,
  onDeleteConversation,
  isStreaming = false
}) {
  const [isCreating, setIsCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);

  // Conversation rename & delete state
  const [editingConvId, setEditingConvId] = useState(null);
  const [editingConvTitle, setEditingConvTitle] = useState('');
  const [confirmDeleteConv, setConfirmDeleteConv] = useState(null);

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    const trimmed = newProjectName.trim();
    if (!trimmed) return;

    if (/[\\/:*?"<>|]/.test(trimmed) || /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i.test(trimmed)) {
      setErrorMsg('Nombre no permitido por Windows.');
      return;
    }

    if (projects.some((p) => p.name.toLowerCase() === trimmed.toLowerCase())) {
      setErrorMsg('Ya existe un proyecto con ese nombre.');
      return;
    }

    onCreateProject(trimmed);
    setNewProjectName('');
    setErrorMsg('');
    setIsCreating(false);
  };

  const handleOpenLocalRepo = async () => {
    let selectedPath = null;
    if (window.electronAPI && window.electronAPI.selectFolder) {
      selectedPath = await window.electronAPI.selectFolder();
    } else {
      selectedPath = window.prompt('Introduce el nombre o ruta del repositorio local:', 'Mi Repositorio');
    }
    if (selectedPath) {
      const res = await fetch(`${API_BASE}/api/workspace/open-repo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: selectedPath })
      });
      if (res.ok) {
        const data = await res.json();
        onSelectProject(data.name);
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

  const startRenameConv = (e, conv) => {
    e.stopPropagation();
    setEditingConvId(conv.id);
    setEditingConvTitle(conv.title);
    setConfirmDeleteConv(null);
  };

  const submitRenameConv = (e, convId) => {
    e?.preventDefault();
    e?.stopPropagation();
    if (editingConvTitle.trim() && onRenameConversation) {
      onRenameConversation(convId, editingConvTitle.trim());
    }
    setEditingConvId(null);
    setEditingConvTitle('');
  };

  return (
    <aside className="w-64 bg-[#0D121F] border-r border-border flex flex-col h-full select-none flex-shrink-0">
      {/* Header: Workspace / Projects */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <Folder size={14} className="text-blue-400" />
          <span>Proyectos</span>
        </div>
        <div className="flex items-center space-x-1">
          <button
            onClick={handleOpenLocalRepo}
            className="p-1 rounded hover:bg-surfaceHover text-slate-400 hover:text-emerald-400 transition"
            title="Abrir Repositorio Local"
          >
            <FolderGit size={16} />
          </button>
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
      <div className="max-h-44 overflow-y-auto p-2 space-y-1 border-b border-border/80">
        {projects.length === 0 ? (
          <div className="p-3 text-center text-slate-500 text-xs">
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
                className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left text-xs transition cursor-pointer group ${
                  isActive
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 font-medium'
                    : 'text-slate-300 hover:bg-surface hover:text-slate-100 border border-transparent'
                }`}
                title={proj.name}
              >
                <div className="flex items-center space-x-2 truncate min-w-0 mr-2">
                  <Folder
                    size={13}
                    className={
                      isActive ? 'text-blue-400 flex-shrink-0' : 'text-slate-400 group-hover:text-slate-300 flex-shrink-0'
                    }
                  />
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
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                          isActive ? 'bg-blue-500/20 text-blue-300' : 'bg-surface text-slate-500'
                        }`}
                      >
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

      {/* Multi-Conversations Section for Active Project */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="px-3 py-2.5 border-b border-border/70 flex items-center justify-between bg-[#0B0F19]">
          <div className="flex items-center space-x-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            <MessageSquare size={13} className="text-purple-400" />
            <span>Conversaciones</span>
            <span className="text-[10px] bg-surface text-slate-400 px-1.5 py-0.2 rounded-full font-mono">
              {conversations.length}
            </span>
          </div>
          <button
            type="button"
            disabled={!activeProject || isStreaming}
            onClick={() => onCreateConversation && onCreateConversation()}
            className="flex items-center space-x-1 text-[11px] bg-purple-600/20 hover:bg-purple-600/35 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded transition disabled:opacity-40"
            title="Crear nueva conversación en este proyecto"
          >
            <Plus size={12} />
            <span>Nueva</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {!activeProject ? (
            <p className="text-[11px] text-slate-500 text-center py-4 italic">
              Selecciona un proyecto para ver sus conversaciones.
            </p>
          ) : conversations.length === 0 ? (
            <p className="text-[11px] text-slate-500 text-center py-4 italic">Sin conversaciones</p>
          ) : (
            conversations.map((conv) => {
              const isConvActive = conv.id === activeConversationId;
              const isEditingThis = editingConvId === conv.id;
              const isConfirmingDel = confirmDeleteConv === conv.id;
              const msgCount = Array.isArray(conv.messages) ? conv.messages.length : 0;

              return (
                <div
                  key={conv.id}
                  onClick={() => !isEditingThis && !isConfirmingDel && onSelectConversation && onSelectConversation(conv.id)}
                  onDoubleClick={(e) => startRenameConv(e, conv)}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-xs transition cursor-pointer group ${
                    isConvActive
                      ? 'bg-purple-600/15 text-purple-300 border border-purple-500/30 font-medium'
                      : 'text-slate-300 hover:bg-surface hover:text-slate-100 border border-transparent'
                  }`}
                  title={`${conv.title} (${msgCount} mensajes) • Doble clic para renombrar`}
                >
                  {isEditingThis ? (
                    <form
                      onSubmit={(e) => submitRenameConv(e, conv.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center space-x-1 w-full"
                    >
                      <input
                        type="text"
                        autoFocus
                        maxLength={60}
                        value={editingConvTitle}
                        onChange={(e) => setEditingConvTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Escape') {
                            setEditingConvId(null);
                            setEditingConvTitle('');
                          }
                        }}
                        onBlur={(e) => submitRenameConv(e, conv.id)}
                        className="w-full text-xs bg-background border border-purple-500 rounded px-1.5 py-0.5 text-slate-100 focus:outline-none"
                      />
                    </form>
                  ) : (
                    <>
                      <div className="flex items-center space-x-2 truncate min-w-0 mr-1.5">
                        <MessageSquare
                          size={12}
                          className={
                            isConvActive
                              ? 'text-purple-400 flex-shrink-0'
                              : 'text-slate-500 group-hover:text-slate-300 flex-shrink-0'
                          }
                        />
                        <span className="truncate">{conv.title}</span>
                      </div>

                      <div className="flex items-center space-x-0.5 flex-shrink-0">
                        {isConfirmingDel ? (
                          <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              onClick={() => {
                                onDeleteConversation && onDeleteConversation(conv.id);
                                setConfirmDeleteConv(null);
                              }}
                              className="p-1 bg-rose-600 text-white rounded hover:bg-rose-500"
                              title="Confirmar eliminar conversación"
                            >
                              <Check size={10} />
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteConv(null)}
                              className="p-1 bg-surfaceHover text-slate-300 rounded hover:text-white"
                              title="Cancelar"
                            >
                              <X size={10} />
                            </button>
                          </div>
                        ) : (
                          <>
                            <span
                              className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                                isConvActive ? 'bg-purple-500/20 text-purple-300' : 'bg-surface text-slate-500'
                              }`}
                            >
                              {msgCount}
                            </span>
                            <button
                              type="button"
                              onClick={(e) => startRenameConv(e, conv)}
                              className="opacity-0 group-hover:opacity-100 p-1 hover:text-blue-400 text-slate-500 rounded transition"
                              title="Renombrar conversación"
                            >
                              <Edit2 size={11} />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setConfirmDeleteConv(conv.id);
                              }}
                              className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 text-slate-500 rounded transition"
                              title="Eliminar conversación"
                            >
                              <Trash2 size={11} />
                            </button>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>
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

          <div className="max-h-28 overflow-y-auto space-y-1 text-xs">
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