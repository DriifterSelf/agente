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
  Paperclip
} from 'lucide-react';

export default function ChatArea({
  messages,
  onSendMessage,
  isStreaming,
  currentStreamContent,
  activeActions,
  activeProject
}) {
  const [input, setInput] = useState('');
  const [expandedActions, setExpandedActions] = useState({});
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamContent, activeActions]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isStreaming) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
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

  return (
    <main className="flex-1 flex flex-col h-full bg-[#0B0F17] relative">
      {/* Messages Thread */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center">
              <Sparkles size={32} className="text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100">
                ¿En qué puedo ayudarte hoy?
              </h2>
              <p className="text-sm text-slate-400 mt-1.5 leading-relaxed">
                Soy tu asistente digital local. Puedo crear y editar hojas de Excel con fórmulas, documentos Word con diseño profesional, presentaciones de PowerPoint, investigar en internet y gestionar tus tareas en Windows.
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
                  {/* Clean up raw ```action blocks from user view for high-end UX */}
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
                  <span>Procesando solicitud...</span>
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

      {/* Input Bar */}
      <div className="p-4 bg-[#070A0F] border-t border-border">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative flex items-center">
          <textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              activeProject
                ? `Pide cualquier tarea en ${activeProject} (Word, Excel, PowerPoint, Web)...`
                : 'Selecciona o crea un proyecto para comenzar...'
            }
            disabled={!activeProject || isStreaming}
            className="w-full bg-surface border border-border rounded-xl px-4 py-3.5 pr-20 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none transition"
          />
          <div className="absolute right-2 flex items-center space-x-1">
            <button
              type="submit"
              disabled={!input.trim() || isStreaming || !activeProject}
              className={`p-2.5 rounded-lg transition ${
                input.trim() && !isStreaming && activeProject
                  ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-md'
                  : 'bg-surfaceHover text-slate-600 cursor-not-allowed'
              }`}
            >
              {isStreaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
