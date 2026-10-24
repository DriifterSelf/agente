import React, { useState, useEffect, useRef } from 'react';
import TitleBar from './components/TitleBar';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import ArtifactsPanel from './components/ArtifactsPanel';

import { API_BASE } from './config';

function createBlankConversation(index = 1, customTitle = '') {
  const now = Date.now();
  return {
    id: `conv-${now}-${Math.random().toString(36).slice(2, 7)}`,
    title: customTitle.trim() || (index === 1 ? 'Nueva conversación' : `Conversación ${index}`),
    createdAt: now,
    updatedAt: now,
    messages: []
  };
}

function deriveTitleFromPrompt(promptText) {
  const cleaned = String(promptText || '')
    .replace(/\[Archivo adjunto:\s*"[^"]+"\]\s*,?\s*/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!cleaned) return 'Análisis de archivos';
  return cleaned.length > 38 ? `${cleaned.slice(0, 38)}…` : cleaned;
}

function normalizeLoadedConversations(raw) {
  // 1. Format: { conversations: [...], active_conversation_id: '...' }
  if (raw && typeof raw === 'object' && !Array.isArray(raw) && Array.isArray(raw.conversations)) {
    const convs = raw.conversations.filter(Boolean).map((c, idx) => ({
      id: c.id || `conv-${idx + 1}`,
      title: c.title || `Conversación ${idx + 1}`,
      createdAt: c.createdAt || Date.now(),
      updatedAt: c.updatedAt || Date.now(),
      messages: Array.isArray(c.messages) ? c.messages : []
    }));
    if (convs.length === 0) {
      const blank = createBlankConversation(1);
      return { conversations: [blank], activeId: blank.id };
    }
    const targetActive =
      raw.active_conversation_id && convs.some((c) => c.id === raw.active_conversation_id)
        ? raw.active_conversation_id
        : convs[0].id;
    return { conversations: convs, activeId: targetActive };
  }

  // 2. Format: Array
  if (Array.isArray(raw)) {
    if (raw.length === 0) {
      const blank = createBlankConversation(1);
      return { conversations: [blank], activeId: blank.id };
    }
    // Check if array of conversation objects vs legacy array of messages
    if (raw[0] && typeof raw[0] === 'object' && Array.isArray(raw[0].messages)) {
      const convs = raw.map((c, idx) => ({
        id: c.id || `conv-${idx + 1}`,
        title: c.title || `Conversación ${idx + 1}`,
        createdAt: c.createdAt || Date.now(),
        updatedAt: c.updatedAt || Date.now(),
        messages: Array.isArray(c.messages) ? c.messages : []
      }));
      return { conversations: convs, activeId: convs[0].id };
    } else {
      // Legacy flat array of messages -> migrate into first conversation
      const firstUserMsg = raw.find((m) => m && m.role === 'user' && m.content);
      const migrated = {
        id: 'conv-principal',
        title: firstUserMsg ? deriveTitleFromPrompt(firstUserMsg.content) : 'Conversación Principal',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        messages: raw
      };
      return { conversations: [migrated], activeId: migrated.id };
    }
  }

  const blank = createBlankConversation(1);
  return { conversations: [blank], activeId: blank.id };
}

export default function App() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState('');
  const [projectFiles, setProjectFiles] = useState([]);
  const [artifacts, setArtifacts] = useState([]);

  // Multi-conversation state per project
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState('');

  // Streaming & abort state
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamContent, setCurrentStreamContent] = useState('');
  const [activeActions, setActiveActions] = useState([]);
  const abortControllerRef = useRef(null);

  // Hardware/System state
  const [systemStatus, setSystemStatus] = useState(null);
  const [isBackendConnected, setIsBackendConnected] = useState(false);

  const activeConversation =
    conversations.find((c) => c.id === activeConversationId) || conversations[0] || null;
  const messages = activeConversation ? activeConversation.messages : [];

  // 1. Initial Load: Projects & Status
  useEffect(() => {
    checkHealthAndLoad();
    const interval = setInterval(checkHealthAndLoad, 4000);
    return () => clearInterval(interval);
  }, []);

  // 2. When activeProject changes: Load files and all conversations for that project
  useEffect(() => {
    if (activeProject) {
      fetchProjectFiles(activeProject);
      loadProjectChats(activeProject);
    } else {
      setProjectFiles([]);
      setArtifacts([]);
      setConversations([]);
      setActiveConversationId('');
    }
  }, [activeProject]);

  const loadProjectChats = async (projName) => {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projName)}/chats`);
      if (res.ok) {
        const data = await res.json();
        const { conversations: loadedConvs, activeId } = normalizeLoadedConversations(data);
        setConversations(loadedConvs);
        setActiveConversationId(activeId);
        return;
      }
    } catch (e) {}
    const blank = createBlankConversation(1);
    setConversations([blank]);
    setActiveConversationId(blank.id);
  };

  const persistProjectConversations = async (projName, updatedConversations, nextActiveId) => {
    if (!projName) return;
    const activeIdToSave = nextActiveId || activeConversationId || updatedConversations[0]?.id || null;
    const currentConv =
      updatedConversations.find((c) => c.id === activeIdToSave) || updatedConversations[0];
    try {
      await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projName)}/chats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversations: updatedConversations,
          active_conversation_id: activeIdToSave,
          messages: currentConv ? currentConv.messages : []
        })
      });
    } catch (e) {}
  };

  const handleCreateConversation = (customTitle = '') => {
    if (!activeProject || isStreaming) return;
    const newConv = createBlankConversation(conversations.length + 1, customTitle);
    const updated = [newConv, ...conversations];
    setConversations(updated);
    setActiveConversationId(newConv.id);
    persistProjectConversations(activeProject, updated, newConv.id);
  };

  const handleSelectConversation = (convId) => {
    if (isStreaming || !convId) return;
    if (conversations.some((c) => c.id === convId)) {
      setActiveConversationId(convId);
      persistProjectConversations(activeProject, conversations, convId);
    }
  };

  const handleRenameConversation = (convId, newTitle) => {
    const trimmed = String(newTitle || '').trim();
    if (!trimmed) return;
    const updated = conversations.map((c) =>
      c.id === convId ? { ...c, title: trimmed, updatedAt: Date.now() } : c
    );
    setConversations(updated);
    persistProjectConversations(activeProject, updated, activeConversationId);
  };

  const handleDeleteConversation = (convId) => {
    if (isStreaming) return;
    const remaining = conversations.filter((c) => c.id !== convId);
    if (remaining.length === 0) {
      const fresh = createBlankConversation(1);
      setConversations([fresh]);
      setActiveConversationId(fresh.id);
      persistProjectConversations(activeProject, [fresh], fresh.id);
    } else {
      const nextActive =
        activeConversationId === convId ? remaining[0].id : activeConversationId;
      setConversations(remaining);
      setActiveConversationId(nextActive);
      persistProjectConversations(activeProject, remaining, nextActive);
    }
  };

  const checkHealthAndLoad = async () => {
    try {
      const healthRes = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(2500) });
      if (healthRes.ok) {
        setIsBackendConnected(true);
        fetchProjects();
        fetchSystemStatus();
      } else {
        setIsBackendConnected(false);
      }
    } catch (e) {
      setIsBackendConnected(false);
    }
  };

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/status`);
      if (res.ok) {
        const data = await res.json();
        setSystemStatus(data);
      }
    } catch (e) {}
  };

  const fetchProjects = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/projects`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
        setActiveProject((prev) => {
          if (!prev && data.length > 0) return data[0].name;
          if (prev && !data.some((p) => p.name === prev)) return data.length > 0 ? data[0].name : '';
          return prev;
        });
      }
    } catch (e) {
      console.error('Error fetching projects:', e);
    }
  };

  const fetchProjectFiles = async (projName) => {
    if (!projName) return;
    try {
      const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projName)}/files`);
      if (res.ok) {
        const files = await res.json();
        const visibleFiles = files.filter((f) => f.name !== 'conversations.json');
        setProjectFiles(visibleFiles);
        const arts = visibleFiles.filter(
          (f) =>
            !f.is_dir &&
            /\.(xlsx|docx|pptx|pdf|csv|png|jpg|jpeg|webp|zip|json|html|md|txt|mp3|wav|m4a|mp4|mkv|mov)$/i.test(
              f.name
            )
        );
        setArtifacts(arts);
      }
    } catch (e) {
      console.error('Error fetching project files:', e);
    }
  };

  const handleCreateProject = async (name) => {
    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      if (res.ok) {
        const created = await res.json();
        await fetchProjects();
        const projName = created.name || name;
        setActiveProject(projName);
        const fresh = createBlankConversation(1);
        setConversations([fresh]);
        setActiveConversationId(fresh.id);
      }
    } catch (e) {
      console.error('Error creating project:', e);
    }
  };

  const handleDeleteProject = async (name) => {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(name)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await fetchProjects();
        if (activeProject === name) {
          setConversations([]);
          setActiveConversationId('');
        }
      }
    } catch (e) {
      console.error('Error deleting project:', e);
    }
  };

  const handleOpenProjectFolder = async (projName) => {
    try {
      await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projName)}/open-folder`, { method: 'POST' });
    } catch (e) {
      console.error('Error opening project folder:', e);
    }
  };

  const handleUploadFile = async (file) => {
    if (!activeProject) return;
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(activeProject)}/upload`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        await fetchProjectFiles(activeProject);
        return await res.json();
      }
    } catch (e) {
      console.error('Error uploading file:', e);
    }
    return { status: 'error' };
  };

  const handleOpenFile = async (filePath) => {
    try {
      if (window.electronAPI && window.electronAPI.openPath) {
        await window.electronAPI.openPath(filePath);
      } else {
        await fetch(`${API_BASE}/api/system/open-file`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: filePath })
        });
      }
    } catch (e) {
      console.error('Error opening file:', e);
    }
  };

  const updateConversationMessages = (targetConvId, newMsgs, autoTitlePrompt = null) => {
    setConversations((prev) => {
      const updated = prev.map((c) => {
        if (c.id !== targetConvId) return c;
        const shouldAutoTitle =
          autoTitlePrompt &&
          (c.title === 'Nueva conversación' || /^Conversación \d+$/i.test(c.title)) &&
          c.messages.filter((m) => m.role === 'user').length === 0;
        return {
          ...c,
          title: shouldAutoTitle ? deriveTitleFromPrompt(autoTitlePrompt) : c.title,
          updatedAt: Date.now(),
          messages: newMsgs
        };
      });
      persistProjectConversations(activeProject, updated, targetConvId);
      return updated;
    });
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
      if (currentStreamContent && activeConversation) {
        const updatedMsgs = [
          ...messages,
          { role: 'assistant', content: currentStreamContent + '\n\n*(Generación detenida)*', actions: [] }
        ];
        updateConversationMessages(activeConversation.id, updatedMsgs);
      }
      setCurrentStreamContent('');
      setActiveActions([]);
    }
  };

  const handleSendMessage = async (userText) => {
    if (!activeProject || isStreaming) return;

    let targetConv = activeConversation;
    let currentConvs = conversations;
    if (!targetConv) {
      targetConv = createBlankConversation(1);
      currentConvs = [targetConv];
      setConversations(currentConvs);
      setActiveConversationId(targetConv.id);
    }

    const targetConvId = targetConv.id;
    const userMsg = { role: 'user', content: userText, timestamp: Date.now() };
    const newMessages = [...(targetConv.messages || []), userMsg];

    updateConversationMessages(targetConvId, newMessages, userText);

    setIsStreaming(true);
    setCurrentStreamContent('');
    setActiveActions([]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let accumulatedContent = '';
    const completedActions = [];

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: activeProject,
          conversation_id: targetConvId,
          messages: newMessages
        }),
        signal: controller.signal
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '').trim();
            if (dataStr === '[DONE]') break;

            try {
              const event = JSON.parse(dataStr);
              if (event.type === 'token') {
                accumulatedContent += event.content;
                setCurrentStreamContent(accumulatedContent);
              } else if (event.type === 'action_start') {
                const actId = event.id || `${event.tool}-${Date.now()}`;
                setActiveActions((prev) => [...prev, { id: actId, tool: event.tool, params: event.params }]);
              } else if (event.type === 'action_end') {
                const targetId = event.id;
                setActiveActions((prev) =>
                  prev.filter((a) => (targetId ? a.id !== targetId : a.tool !== event.tool))
                );
                completedActions.push({ tool: event.tool, params: event.params, result: event.result });
              } else if (event.type === 'artifact_created') {
                fetchProjectFiles(activeProject);
              }
            } catch (err) {}
          }
        }
      }

      setActiveActions([]);

      const finalMsgs = [
        ...newMessages,
        {
          role: 'assistant',
          content: accumulatedContent,
          actions: completedActions,
          timestamp: Date.now()
        }
      ];
      updateConversationMessages(targetConvId, finalMsgs);
    } catch (e) {
      if (e.name !== 'AbortError') {
        const errMsgs = [
          ...newMessages,
          {
            role: 'assistant',
            content: 'Ocurrió un error al procesar la solicitud. Revisa la consola o intenta de nuevo.',
            timestamp: Date.now()
          }
        ];
        updateConversationMessages(targetConvId, errMsgs);
      }
    } finally {
      setIsStreaming(false);
      setCurrentStreamContent('');
      setActiveActions([]);
      fetchProjectFiles(activeProject);
    }
  };

  // Estimación en tiempo real de tokens en contexto de la conversación activa para el HUD central
  const totalChars =
    messages.reduce((acc, m) => acc + (m.content || '').length, 0) + (currentStreamContent || '').length;
  const estimatedTokens = Math.round(totalChars / 3.7);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background">
      <TitleBar
        activeProject={activeProject}
        systemStatus={systemStatus}
        isBackendConnected={isBackendConnected}
        onRefreshStatus={fetchSystemStatus}
        usedTokens={estimatedTokens}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          projects={projects}
          activeProject={activeProject}
          onSelectProject={(name) => setActiveProject(name)}
          onCreateProject={handleCreateProject}
          onDeleteProject={handleDeleteProject}
          onOpenProjectFolder={handleOpenProjectFolder}
          onOpenFile={handleOpenFile}
          projectFiles={projectFiles}
          conversations={conversations}
          activeConversationId={activeConversation?.id || ''}
          onSelectConversation={handleSelectConversation}
          onCreateConversation={handleCreateConversation}
          onRenameConversation={handleRenameConversation}
          onDeleteConversation={handleDeleteConversation}
          isStreaming={isStreaming}
        />

        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          onStopGeneration={handleStopGeneration}
          isStreaming={isStreaming}
          currentStreamContent={currentStreamContent}
          activeActions={activeActions}
          activeProject={activeProject}
          onUploadFile={handleUploadFile}
          conversations={conversations}
          activeConversationId={activeConversation?.id || ''}
          onSelectConversation={handleSelectConversation}
          onCreateConversation={handleCreateConversation}
          onRenameConversation={handleRenameConversation}
          onDeleteConversation={handleDeleteConversation}
        />

        <ArtifactsPanel
          artifacts={artifacts}
          onOpenFile={handleOpenFile}
          onOpenProjectFolder={handleOpenProjectFolder}
          activeProject={activeProject}
        />
      </div>
    </div>
  );
}