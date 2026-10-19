import React, { useState, useEffect } from 'react';
import TitleBar from './components/TitleBar';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import ArtifactsPanel from './components/ArtifactsPanel';

const API_BASE = 'http://127.0.0.1:8765';

export default function App() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState('');
  const [projectFiles, setProjectFiles] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [messages, setMessages] = useState([]);
  
  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamContent, setCurrentStreamContent] = useState('');
  const [activeActions, setActiveActions] = useState([]);
  
  // Hardware/System state
  const [systemStatus, setSystemStatus] = useState(null);

  // 1. Initial Load: Projects & Status
  useEffect(() => {
    fetchProjects();
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // 2. When activeProject changes: Load files and artifacts
  useEffect(() => {
    if (activeProject) {
      fetchProjectFiles(activeProject);
    }
  }, [activeProject]);

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/status`);
      if (res.ok) {
        const data = await res.json();
        setSystemStatus(data);
      }
    } catch (e) {
      // Backend might still be spinning up
    }
  };

  const fetchProjects = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/projects`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
        if (data.length > 0 && !activeProject) {
          setActiveProject(data[0].name);
        }
      }
    } catch (e) {
      console.error('Error fetching projects:', e);
    }
  };

  const fetchProjectFiles = async (projName) => {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projName)}/files`);
      if (res.ok) {
        const files = await res.json();
        setProjectFiles(files);
        
        // Filter out created artifacts (.xlsx, .docx, .pptx, etc.)
        const arts = files.filter(f => !f.is_dir && /\.(xlsx|docx|pptx|pdf|csv|png|jpg)$/i.test(f.name));
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
        setActiveProject(created.name || name);
        setMessages([]);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`No se pudo crear el proyecto: ${err.detail || 'Verifica el nombre.'}`);
      }
    } catch (e) {
      console.error('Error creating project:', e);
      alert(`Error conectando con el motor local (${API_BASE}): ${e.message}\nVerifica que el servicio esté activo.`);
    }
  };

  const handleOpenProjectFolder = async (projName) => {
    try {
      await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projName)}/open-folder`, {
        method: 'POST'
      });
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
      // First try via Electron native IPC if available
      if (window.electronAPI && window.electronAPI.openPath) {
        await window.electronAPI.openPath(filePath);
      } else {
        // Fallback to FastAPI backend
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

  const handleSendMessage = async (userText) => {
    if (!activeProject || isStreaming) return;

    const userMsg = { role: 'user', content: userText };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);

    setIsStreaming(true);
    setCurrentStreamContent('');
    setActiveActions([]);

    let accumulatedContent = '';
    const completedActions = [];

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: activeProject,
          messages: newMessages
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep remainder

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
                setActiveActions(prev => [...prev, { tool: event.tool, params: event.params }]);
              } else if (event.type === 'action_end') {
                setActiveActions(prev => prev.filter(a => a.tool !== event.tool));
                completedActions.push({ tool: event.tool, result: event.result });
              } else if (event.type === 'artifact_created') {
                // Refresh project artifacts immediately
                fetchProjectFiles(activeProject);
              }
            } catch (err) {
              console.error('Failed to parse SSE event:', err);
            }
          }
        }
      }

      // Finalize message in thread
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: accumulatedContent,
          actions: completedActions
        }
      ]);
    } catch (e) {
      console.error('Error sending message:', e);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Ocurrió un error al procesar la solicitud. Por favor intenta de nuevo.'
        }
      ]);
    } finally {
      setIsStreaming(false);
      setCurrentStreamContent('');
      setActiveActions([]);
      fetchProjectFiles(activeProject);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background">
      {/* 1. Frameless Custom TitleBar */}
      <TitleBar activeProject={activeProject} systemStatus={systemStatus} />

      {/* 2. Main 3-Column Antigravity Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Projects & Files */}
        <Sidebar
          projects={projects}
          activeProject={activeProject}
          onSelectProject={(name) => {
            setActiveProject(name);
            setMessages([]);
          }}
          onCreateProject={handleCreateProject}
          onOpenProjectFolder={handleOpenProjectFolder}
          projectFiles={projectFiles}
        />

        {/* Center: Interactive Chat & Action Capsules */}
        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          isStreaming={isStreaming}
          currentStreamContent={currentStreamContent}
          activeActions={activeActions}
          activeProject={activeProject}
          onUploadFile={handleUploadFile}
        />

        {/* Right: Artifacts & Deliverables (.xlsx, .docx, .pptx) */}
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
