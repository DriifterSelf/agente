import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Sparkles,
  Bot,
  User,
  Globe,
  FileSpreadsheet,
  FileText,
  Presentation,
  ChevronDown,
  ChevronRight,
  Loader2,
  Paperclip,
  X,
  File,
  Image as ImageIcon,
  Music,
  Archive
} from 'lucide-react';

export default function ChatArea({
  messages,
  onSendMessage,
  isStreaming,
  currentStreamContent,
  activeActions,
  activeProject,
  onUploadFile
}) {
  const [input, setInput] = useState('');
  const [expandedActions, setExpandedActions] = useState({});
  const [attachments, setAttachments] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamContent, activeActions]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if ((input.trim() || attachments.length > 0) && !isStreaming) {
      let finalPrompt = input.trim();
      if (attachments.length > 0) {
        const attachInfo = attachments.map(a => `[Archivo adjunto: "${a.name}"]`).join(', ');
        finalPrompt = `${attachInfo}\n\n${finalPrompt || 'Por favor procesa y analiza estos archivos adjuntos.'}`;
      }
      onSendMessage(finalPrompt);
      setInput('');
      setAttachments([]);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files || []);
    for (const file of files) {
      await handleUpload(file);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files || []);
    for (const file of files) {
      await handleUpload(file);
    }
  };

  const handleUpload = async (file) => {
    if (!activeProject || !onUploadFile) return;
    try {
      const res = await onUploadFile(file);
      if (res && res.status === 'success') {
        setAttachments(prev => [...prev, { name: file.name, size: file.size, type: file.type }]);
      }
    } catch (err) {
      console.error('Error uploading file:', err);
    }
  };

  const removeAttachment = (index) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const toggleAction = (idx) => {
    setExpandedActions((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const quickPrompts = [
    { label: '📊 Excel Financiero', prompt: 'Crea un archivo Excel con el presupuesto anual detallado, fórmulas de sumatoria y margen, y un gráfico comparativo.' },
    { label: '📄 Informe Ejecutivo Word', prompt: 'Redacta un informe ejecutivo profesional en Word sobre la estrategia de operaciones y eficiencia para este trimestre.' },
    { label: '📑 Presentación PowerPoint', prompt: 'Crea una presentación de PowerPoint de 6 diapositivas con portada, pilares estratégicos y conclusiones clave.' },
    { label: '🌐 Búsqueda e Investigación', prompt: 'Investiga en la web las últimas tendencias de tecnología y negocios, y hazme un resumen estructurado.' }
  ];

  const renderToolIcon = (tool) => {
    switch (tool) {
      case 'create_excel':
        return <FileSpreadsheet size={14} className="text-emerald-400" />;
      case 'create_word':
        return <FileText size={14} className="text-blue-400" />;
      case 'create_powerpoint':
        return <Presentation size={14} className="text-amber-400" />;
      case 'web_search':
      case 'fetch_page':
        return <Globe size={14} className="text-cyan-400" />;
      default:
        return <Sparkles size={14} className="text-purple-400" />;
    }
  };

  const renderToolTitle = (tool, params) => {
    switch (tool) {
      case 'create_excel':
        return `Generando Excel: ${params.filename || 'Libro.xlsx'}`;
      case 'create_word':
        return `Redactando Word: ${params.filename || 'Documento.docx'}`;
      case 'create_powerpoint':
        return `Creando PowerPoint: ${params.filename || 'Presentacion.pptx'}`;
      case 'web_search':
        return `Buscando en la web: "${params.query || ''}"`;
      case 'fetch_page':
        return `Leyendo página: ${params.url || ''}`;
      default:
        return `Ejecutando tarea: ${tool}`;
    }
  };

  const getAttachmentIcon = (name) => {
    const ext = name.split('.').pop().toLowerCase();
    if (['png', 'jpg', 'jpeg', 'webp', 'bmp'].includes(ext)) return <ImageIcon size={13} className="text-purple-400" />;
    if (['pdf', 'docx', 'doc', 'txt'].includes(ext)) return <FileText size={13} className="text-blue-400" />;
    if (['xlsx', 'xls', 'csv'].includes(ext)) return <FileSpreadsheet size={13} className="text-emerald-400" />;
    if (['pptx', 'ppt'].includes(ext)) return <Presentation size={13} className="text-amber-400" />;
    if (['mp3', 'wav', 'm4a'].includes(ext)) return <Music size={13} className="text-rose-400" />;
    if (['zip', 'rar'].includes(ext)) return <Archive size={13} className="text-yellow-400" />;
    return <File size={13} className="text-slate-400" />;
  };

  return (
    <main
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`flex-1 flex flex-col h-full bg-[#0B0F17] relative transition-colors ${
        isDragging ? 'border-2 border-dashed border-blue-500/80 bg-blue-950/10' : ''
      }`}
    >
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        multiple
        className="hidden"
      />

      {/* Drag Overlay Notice */}
      {isDragging && (
        <div className="absolute inset-0 z-40 bg-background/80 backdrop-blur-sm flex flex-col items-center justify-center pointer-events-none">
          <div className="p-4 rounded-2xl bg-blue-600/20 border border-blue-500/40 text-blue-400 flex flex-col items-center space-y-2">
            <Paperclip size={32} className="animate-bounce" />
            <p className="text-sm font-semibold text-slate-100">Suelta los archivos aquí</p>
            <p className="text-xs text-slate-400">PDFs, Word, Excel, PowerPoint, Imágenes, Audio, ZIP...</p>
          </div>
        </div>
      )}

      {/* Messages Thread */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center">
              <Sparkles size={32} className="text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100">
                Asistente Multimodal Activo
              </h2>
              <p className="text-sm text-slate-400 mt-1.5 leading-relaxed">
                Proceso cualquier tipo de archivo: arrastra o adjunta PDFs, Word, Excel, PowerPoint, imágenes de tareas, notas de audio, o pide investigaciones web y automatizaciones de Windows.
              </p>
            </div>

            {/* Quick Prompts Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full mt-4">
              {quickPrompts.map((qp, i) => (
                <button
                  key={i}
                  onClick={() => onSendMessage(qp.prompt)}
                  className="p-3 rounded-xl bg-surface hover:bg-surfaceHover border border-border hover:border-slate-700 text-left transition group"
                >
                  <span className="text-xs font-semibold text-slate-200 group-hover:text-blue-400 block mb-1">
                    {qp.label}
                  </span>
                  <span className="text-[11px] text-slate-400 line-clamp-2">
                    {qp.prompt}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div
              key={index}
              className={`flex items-start space-x-3 max-w-3xl ${
                msg.role === 'user' ? 'ml-auto flex-row-reverse space-x-reverse' : 'mr-auto'
              }`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-surface border border-border text-blue-400'
                }`}
              >
                {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>

              {/* Content Bubble */}
              <div className="flex-1 space-y-2">
                <div
                  className={`p-4 rounded-2xl text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-sm'
                      : 'bg-surface text-slate-200 border border-border rounded-tl-sm'
                  }`}
                >
                  <div className="whitespace-pre-wrap">
                    {msg.content.replace(/```action[\s\S]*?```/g, '').trim()}
                  </div>
                </div>

                {/* Render any associated actions / tool executions */}
                {msg.actions && msg.actions.length > 0 && (
                  <div className="space-y-1.5 pl-1">
                    {msg.actions.map((act, aIdx) => {
                      const isExpanded = expandedActions[`${index}-${aIdx}`];
                      return (
                        <div
                          key={aIdx}
                          className="rounded-lg border border-border/70 bg-[#0F1523] text-xs overflow-hidden"
                        >
                          <button
                            onClick={() => toggleAction(`${index}-${aIdx}`)}
                            className="w-full flex items-center justify-between px-3 py-2 text-slate-300 hover:text-white hover:bg-surfaceHover transition text-left"
                          >
                            <div className="flex items-center space-x-2">
                              {renderToolIcon(act.tool)}
                              <span className="font-medium text-slate-200">
                                {renderToolTitle(act.tool, act.params || {})}
                              </span>
                            </div>
                            <div className="flex items-center space-x-1.5 text-slate-400">
                              <span className="text-[10px] text-emerald-400 font-mono">Completado</span>
                              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            </div>
                          </button>

                          {isExpanded && act.result && (
                            <div className="p-3 bg-[#0B0F17] border-t border-border/60 text-[11px] text-slate-400 font-mono overflow-x-auto max-h-48">
                              <pre>{JSON.stringify(act.result, null, 2)}</pre>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {/* Live Streaming Message */}
        {isStreaming && (
          <div className="flex items-start space-x-3 max-w-3xl mr-auto">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-surface border border-border text-blue-400">
              <Bot size={16} />
            </div>
            <div className="flex-1 space-y-2">
              <div className="p-4 rounded-2xl rounded-tl-sm text-sm leading-relaxed bg-surface text-slate-200 border border-border">
                <div className="whitespace-pre-wrap">
                  {currentStreamContent.replace(/```action[\s\S]*?```/g, '').trim()}
                </div>
                <div className="flex items-center space-x-2 text-blue-400 text-xs mt-2 font-medium">
                  <Loader2 size={12} className="animate-spin" />
                  <span>Procesando solicitud multimodal...</span>
                </div>
              </div>

              {/* Active Running Action Pills */}
              {activeActions && activeActions.length > 0 && (
                <div className="space-y-1.5 pl-1">
                  {activeActions.map((act, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between px-3 py-2 rounded-lg border border-blue-500/30 bg-blue-950/20 text-xs"
                    >
                      <div className="flex items-center space-x-2">
                        {renderToolIcon(act.tool)}
                        <span className="font-medium text-blue-200">
                          {renderToolTitle(act.tool, act.params || {})}
                        </span>
                      </div>
                      <Loader2 size={12} className="animate-spin text-blue-400" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar & Attachments */}
      <div className="p-4 bg-[#070A0F] border-t border-border">
        <div className="max-w-4xl mx-auto space-y-2">
          {/* Attachment Chips */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 px-1">
              {attachments.map((att, i) => (
                <div
                  key={i}
                  className="flex items-center space-x-1.5 bg-surface border border-border px-2.5 py-1 rounded-lg text-xs text-slate-200 shadow-sm"
                >
                  {getAttachmentIcon(att.name)}
                  <span className="truncate max-w-[200px]">{att.name}</span>
                  <button
                    onClick={() => removeAttachment(i)}
                    className="p-0.5 hover:bg-surfaceHover rounded text-slate-400 hover:text-white"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <form onSubmit={handleSubmit} className="relative flex items-center">
            {/* Attach File Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={!activeProject || isStreaming}
              className="absolute left-3 p-1.5 text-slate-400 hover:text-blue-400 transition rounded-lg hover:bg-surfaceHover disabled:opacity-40"
              title="Adjuntar archivo multimodal (PDF, Imagen, Word, Excel, Audio...)"
            >
              <Paperclip size={18} />
            </button>

            <textarea
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                activeProject
                  ? `Arrastra cualquier archivo o pide lo que sea en ${activeProject}...`
                  : 'Selecciona o crea un proyecto para comenzar...'
              }
              disabled={!activeProject || isStreaming}
              className="w-full bg-surface border border-border rounded-xl pl-12 pr-16 py-3.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none transition"
            />

            <div className="absolute right-2 flex items-center space-x-1">
              <button
                type="submit"
                disabled={(!input.trim() && attachments.length === 0) || isStreaming || !activeProject}
                className={`p-2.5 rounded-lg transition ${
                  (input.trim() || attachments.length > 0) && !isStreaming && activeProject
                    ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-md'
                    : 'bg-surfaceHover text-slate-600 cursor-not-allowed'
                }`}
              >
                {isStreaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
          </form>
        </div>
      </div>
    </main>
  );
}
