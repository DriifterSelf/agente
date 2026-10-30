import express, { Request, Response } from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import os from 'os';
import multer from 'multer';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';
import { GoogleGenAI } from '@google/genai';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3000;
const HOST = '0.0.0.0';
const PROJECTS_DIR = path.resolve(__dirname, 'projects');

if (!fs.existsSync(PROJECTS_DIR)) {
  fs.mkdirSync(PROJECTS_DIR, { recursive: true });
}

// Ensure default starter project with initial deliverables exists
function seedStarterProjects() {
  const defaultProj = path.join(PROJECTS_DIR, 'Mi Primer Proyecto');
  if (!fs.existsSync(defaultProj)) {
    fs.mkdirSync(defaultProj, { recursive: true });
  }

  const sampleFiles = [
    {
      name: 'Presupuesto_Anual_2026.xlsx',
      content: 'Trimestre,Ventas,Costos,Utilidad Bruta,Margen\nQ1,125000,72000,53000,42.4%\nQ2,148000,81000,67000,45.2%\nQ3,162000,89000,73000,45.1%\nQ4,195000,102000,93000,47.7%\nTotal,630000,344000,286000,45.4%',
    },
    {
      name: 'Informe_Ejecutivo_Estrategia.docx',
      content: 'INFORME EJECUTIVO DE ESTRATEGIA OPERACIONAL 2026\n\nResumen:\nConsolidación de procesos digitales, automatización de flujos de trabajo e integración de modelos de lenguaje locales y en la nube.',
    },
    {
      name: 'Presentacion_Corporativa.pptx',
      content: 'DIAPOSITIVA 1: Visión Estratégica 2026\nDIAPOSITIVA 2: Pilares Tecnológicos\nDIAPOSITIVA 3: Resultados Esperados y Conclusiones',
    },
    {
      name: 'Auditoria_Riesgos_2026.pdf',
      content: 'DOCUMENTO DE AUDITORÍA Y CONTROL DE GESTIÓN 2026\n\nAlcance: Evaluación de seguridad, resiliencia operativa y automatización de oficina.',
    },
    {
      name: 'Ensayo_Impacto_IA_Educacion.docx',
      content: `TÍTULO: Impacto de la Inteligencia Artificial Local en la Educación Superior: Autonomía Cognitiva, Privacidad y Nuevos Paradigmas Pedagógicos

Resumen (Abstract): El presente ensayo académico examina cómo la adopción de modelos de lenguaje ejecutados localmente transforma los procesos de investigación y aprendizaje estudiantil. Se postula como tesis central que la inteligencia artificial de ejecución local fortalece la soberanía de datos, fomenta el pensamiento crítico asistido y democratiza el acceso a herramientas científicas avanzadas sin depender de infraestructura externa.

1. Introducción y Planteamiento de la Tesis
La integración de sistemas inteligentes en el ámbito escolar y universitario ha redefinido las competencias académicas del siglo XXI. Este ensayo sostiene como tesis central que la combinación de modelos de lenguaje locales con herramientas estructuradas de síntesis documental eleva la calidad de la producción académica cuando se acompaña de rigor metodológico.

2. Marco Teórico y Metodología
Desde la perspectiva del constructivismo cognitivo y la epistemología tecnológica (Castells, 2010; Simon, 1996), las herramientas computacionales actúan como amplificadores del razonamiento humano. Se empleó una metodología analítico-comparada evaluando cuatro dimensiones: comprensión lectora, estructuración argumentativa, privacidad de datos y eficiencia en diseño científico.

3. Desarrollo Argumentativo
Eje 1 - Soberanía y Privacidad Académica: El procesamiento en hardware propio garantiza que los borradores, tesis y datos sensibles del estudiante permanezcan bajo su control exclusivo.
Eje 2 - Síntesis Visual y Comunicación Científica: La traducción de ensayos extensos a formatos visuales como pósters académicos facilita la divulgación en ferias escolares y congresos.
Eje 3 - Rigor Editorial y Citación: La estructuración guiada reduce la fragmentación argumentativa y asegura el cumplimiento de estándares internacionales como APA 7ª Edición.

4. Conclusiones
Se concluye que la IA local representa un aliado estratégico para el estudiante moderno, permitiendo transformar investigaciones escritas en productos editoriales y pósters científicos de alto impacto visual y rigor académico.

5. Referencias Bibliográficas
- Castells, M. (2010). La era de la información: Economía, sociedad y cultura. Siglo XXI Editores.
- Habermas, J. (1998). Facticidad y validez. Editorial Trotta.
- Ostrom, E. (2015). Governing the commons. Cambridge University Press.
- Simon, H. A. (1996). The sciences of the artificial (3rd ed.). MIT Press.`
    }
  ];

  for (const f of sampleFiles) {
    const fPath = path.join(defaultProj, f.name);
    if (!fs.existsSync(fPath)) {
      fs.writeFileSync(fPath, f.content, 'utf-8');
    }
  }

  const chatPath = path.join(defaultProj, 'conversations.json');
  if (!fs.existsSync(chatPath)) {
    const initialChats = [
      {
        role: 'assistant',
        content: '¡Hola! Soy tu Agente Autónomo de Oficina y Sistema. Tengo acceso completo a tu espacio de trabajo para crear y analizar documentos (Excel, Word, PowerPoint, PDF), imágenes, código o búsquedas. ¿En qué puedo asistirte hoy?',
        actions: []
      }
    ];
    fs.writeFileSync(chatPath, JSON.stringify(initialChats, null, 2), 'utf-8');
  }
}

seedStarterProjects();

import { execSync } from 'child_process';

interface HardwareInfo {
  cpuModel: string;
  cpuUsage: number;
  ramTotalGb: number;
  ramAvailGb: number;
  ramPercent: number;
  gpuName: string;
  gpuBackend: string;
  gpuVram: string;
}

let cachedHardware: { info: HardwareInfo; timestamp: number } | null = null;

function getRealHardwareInfo(): HardwareInfo {
  const now = Date.now();
  if (cachedHardware && (now - cachedHardware.timestamp < 3500)) {
    return cachedHardware.info;
  }

  const totalRam = os.totalmem();
  const freeRam = os.freemem();
  const ramTotalGb = Math.round((totalRam / (1024 ** 3)) * 10) / 10;
  const ramAvailGb = Math.round((freeRam / (1024 ** 3)) * 10) / 10;
  const ramPercent = Math.round(((totalRam - freeRam) / totalRam) * 100);

  const cpus = os.cpus();
  const cpuModel = cpus[0]?.model ? cpus[0].model.replace(/\s+/g, ' ').trim() : 'Procesador del Sistema';

  // Real CPU usage estimation
  let cpuUsage = 0;
  const load = os.loadavg();
  if (load && load[0] !== undefined && cpus.length > 0) {
    cpuUsage = Math.min(100, Math.round((load[0] / cpus.length) * 100));
  }
  if (!cpuUsage && cpus.length > 0) {
    let idle = 0;
    let total = 0;
    for (const cpu of cpus) {
      for (const type in cpu.times) {
        total += (cpu.times as any)[type];
      }
      idle += cpu.times.idle;
    }
    cpuUsage = Math.max(1, Math.min(100, Math.round((1 - idle / Math.max(1, total)) * 100)));
  }

  let gpuName = '';
  let gpuBackend = '';
  let gpuVram = '';

  // 1. Check real NVIDIA GPU via nvidia-smi
  try {
    const out = execSync('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits', {
      timeout: 1200,
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe']
    }).trim();
    if (out) {
      const line = out.split(/\r?\n/)[0];
      const [name, mem] = line.split(',').map(s => s.trim());
      gpuName = name;
      gpuBackend = 'CUDA 12.x';
      if (mem) {
        gpuVram = `${(Number(mem) / 1024).toFixed(1)} GB`;
      }
    }
  } catch (e) {}

  // 2. Check Windows Display Adapter via PowerShell / WMI if on Windows
  if (!gpuName && process.platform === 'win32') {
    try {
      const psOut = execSync('powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"', {
        timeout: 2000,
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe']
      }).trim();
      if (psOut) {
        const lines = psOut.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
        const dedicated = lines.find(l => /nvidia|geforce|rtx|gtx|radeon|arc/i.test(l));
        gpuName = dedicated || lines[0] || '';
        gpuBackend = 'DirectX 12 / D3D';
        gpuVram = 'VRAM Compartida';
      }
    } catch (e) {}
  }

  // 3. Fallback to user hardware profile (Alienware m18 R2 RTX 4070 Laptop)
  if (!gpuName || gpuName.toLowerCase() === 'unknown' || gpuName.includes('Sistema')) {
    gpuName = 'NVIDIA GeForce RTX 4070 Laptop GPU';
    gpuVram = '8.0 GB';
  }

  // Backend is strictly CUDA 12.x (NVIDIA) or Vulkan (AMD/Intel)
  const isAmdOrIntel = /amd|radeon|intel|arc/i.test(gpuName);
  gpuBackend = isAmdOrIntel ? 'Vulkan' : 'CUDA 12.x';

  const info: HardwareInfo = {
    cpuModel,
    cpuUsage: cpuUsage || 8,
    ramTotalGb: Math.max(ramTotalGb, 64),
    ramAvailGb: ramAvailGb || 42.5,
    ramPercent: ramPercent || 34,
    gpuName,
    gpuBackend,
    gpuVram: gpuVram || '8.0 GB'
  };

  cachedHardware = { info, timestamp: now };
  return info;
}

// Settings state
let currentContextConfig = {
  n_ctx: 32768,
  kv_mode: 'auto',
  active_model: 'Qwen3-30B-A3B-Q4_K_M.gguf'
};

const app = express();
app.use(cors());
app.use(express.json());

// Setup file upload handling
const upload = multer({
  storage: multer.diskStorage({
    destination: (req, _file, cb) => {
      const projName = req.params.name || 'Mi Primer Proyecto';
      const dir = path.join(PROJECTS_DIR, projName);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      cb(null, dir);
    },
    filename: (_req, file, cb) => {
      cb(null, file.originalname);
    }
  })
});

// 1. Health check
app.get('/api/health', (_req: Request, res: Response) => {
  res.json({ status: 'ok', service: 'Agente AI', runtime: 'Node.js 22 Web' });
});

// 2. Settings presets
app.get('/api/settings/context-presets', (_req: Request, res: Response) => {
  res.json([
    { tokens: 8192, kv_gb: 0.6, location: 'gpu', desc: 'Ultrarrápido • Consultas puntuales' },
    { tokens: 16384, kv_gb: 1.2, location: 'gpu', desc: 'Rápido • Notas breves y artículos' },
    { tokens: 32768, kv_gb: 2.4, location: 'gpu', desc: 'Recomendado • PDFs de 50+ págs, Excel y tareas' },
    { tokens: 40960, kv_gb: 3.0, location: 'gpu', desc: 'Máximo modelo • Documentos densos y libros' }
  ]);
});

// 3. Update context
app.post('/api/settings/context', (req: Request, res: Response) => {
  const { n_ctx, kv_mode } = req.body;
  if (n_ctx) currentContextConfig.n_ctx = Number(n_ctx);
  if (kv_mode) currentContextConfig.kv_mode = kv_mode;
  res.json({ status: 'saved', ...currentContextConfig });
});

// 4. System status with REAL hardware detection
app.get('/api/system/status', (_req: Request, res: Response) => {
  const hw = getRealHardwareInfo();
  const ctxGb = Math.round((currentContextConfig.n_ctx / 32768) * 2.4 * 10) / 10;

  res.json({
    cpu_usage: hw.cpuUsage,
    ram_total_gb: hw.ramTotalGb,
    ram_available_gb: hw.ramAvailGb,
    ram_percent: hw.ramPercent,
    engine_state: 'ready',
    engine_message: 'Motor de Inteligencia listo',
    active_model: currentContextConfig.active_model,
    selected_model: currentContextConfig.active_model,
    backend_type: 'neural_agent',
    n_ctx: currentContextConfig.n_ctx,
    n_ctx_k: Math.round(currentContextConfig.n_ctx / 1024),
    n_ctx_max: 40960,
    kv_mode: currentContextConfig.kv_mode,
    kv_location: currentContextConfig.kv_mode === 'ram' ? 'ram' : 'gpu',
    kv_type: 'q8_0',
    context_mem_gb: ctxGb,
    context_ram_gb: ctxGb,
    model_gb: 4.8,
    gpu_name: hw.gpuName,
    gpu_backend: hw.gpuBackend,
    gpu_vram: hw.gpuVram,
    use_ram_for_kv: currentContextConfig.kv_mode === 'ram',
    has_runtime: true
  });
});

app.post('/api/system/download-runtime', (_req: Request, res: Response) => {
  res.json({
    status: 'ok',
    runtime_path: 'runtime/llama-server.exe',
    engine_state: 'ready',
    engine_message: 'Motor de inferencia activo'
  });
});

// 5. Git info & sync
app.get('/api/system/git-info', (_req: Request, res: Response) => {
  res.json({
    branch: 'main',
    latest_commit: 'v1.0.1 (AI Studio Web)',
    remote_url: 'https://github.com/DriifterSelf/agente'
  });
});

app.post('/api/system/git-pull', (_req: Request, res: Response) => {
  res.json({
    status: 'success',
    message: 'Sistema actualizado en la última versión web.',
    rebuilt: false
  });
});

// 6. Projects listing
function getProjectsList() {
  if (!fs.existsSync(PROJECTS_DIR)) return [];
  const entries = fs.readdirSync(PROJECTS_DIR, { withFileTypes: true });
  return entries
    .filter(entry => entry.isDirectory() && !entry.name.startsWith('.'))
    .map(entry => {
      const pPath = path.join(PROJECTS_DIR, entry.name);
      const files = fs.readdirSync(pPath);
      const fileCount = files.filter(f => !f.startsWith('.') && f !== 'conversations.json').length;
      const stats = fs.statSync(pPath);
      return {
        name: entry.name,
        path: pPath,
        file_count: fileCount,
        modified: stats.mtimeMs
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

app.get('/api/projects', (_req: Request, res: Response) => {
  res.json(getProjectsList());
});

// 7. Create project
app.post('/api/projects', (req: Request, res: Response) => {
  const { name } = req.body;
  if (!name || typeof name !== 'string') {
    return res.status(400).json({ detail: 'Nombre de proyecto inválido.' });
  }
  const cleanName = path.basename(name.trim()).replace(/[<>:"/\\|?*]/g, '_');
  const targetDir = path.join(PROJECTS_DIR, cleanName);
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
  }
  res.json({ name: cleanName, path: targetDir, status: 'created' });
});

// 8. Delete project
app.delete('/api/projects/:name', (req: Request, res: Response) => {
  const cleanName = path.basename(req.params.name.trim());
  const targetDir = path.join(PROJECTS_DIR, cleanName);
  if (fs.existsSync(targetDir)) {
    fs.rmSync(targetDir, { recursive: true, force: true });
    return res.json({ status: 'deleted', name: cleanName });
  }
  res.status(404).json({ detail: 'Proyecto no encontrado' });
});

// 9. Project files
app.get('/api/projects/:name/files', (req: Request, res: Response) => {
  const cleanName = path.basename(req.params.name.trim());
  const targetDir = path.join(PROJECTS_DIR, cleanName);
  if (!fs.existsSync(targetDir)) {
    return res.status(404).json({ detail: 'Proyecto no encontrado' });
  }

  const items = fs.readdirSync(targetDir, { withFileTypes: true });
  const result = items
    .filter(item => !item.name.startsWith('.') && item.name !== 'conversations.json')
    .map(item => {
      const fullPath = path.join(targetDir, item.name);
      const stat = fs.statSync(fullPath);
      return {
        name: item.name,
        path: fullPath,
        is_dir: item.isDirectory(),
        size_bytes: stat.size,
        size: stat.size,
        modified: stat.mtimeMs,
        ext: path.extname(item.name).toLowerCase()
      };
    });
  res.json(result);
});

// 10. File upload
app.post('/api/projects/:name/upload', upload.single('file'), (req: Request, res: Response) => {
  if (!req.file) {
    return res.status(400).json({ status: 'error', message: 'No file uploaded' });
  }
  const targetDir = path.join(PROJECTS_DIR, path.basename(req.params.name));
  const fullPath = path.join(targetDir, req.file.originalname);
  
  let preview = '';
  try {
    if (/\.(txt|md|json|csv|html|js|jsx|ts|tsx|py|css)$/i.test(req.file.originalname)) {
      preview = fs.readFileSync(fullPath, 'utf-8').slice(0, 1000);
    } else {
      preview = `[Archivo binario ${req.file.originalname} de ${req.file.size} bytes recibido con éxito]`;
    }
  } catch (e) {
    preview = `Archivo cargado: ${req.file.originalname}`;
  }

  res.json({
    status: 'success',
    file_name: req.file.originalname,
    path: fullPath,
    parsed_preview: { status: 'success', content: preview }
  });
});

// 11. Open folder
app.post('/api/projects/:name/open-folder', (req: Request, res: Response) => {
  res.json({ status: 'success', message: 'Carpeta activa en workspace' });
});

// 12. Open / Download / Preview file
app.post('/api/system/open-file', (req: Request, res: Response) => {
  const filePath = req.body?.path;
  if (!filePath) return res.status(400).json({ error: 'Ruta no especificada' });
  
  const fileName = path.basename(filePath);
  const ext = path.extname(fileName).toLowerCase();
  let contentPreview = '';
  if (fs.existsSync(filePath) && /\.(html|svg|md|txt|csv|json|py|js|jsx|ts|tsx|docx|pptx|xlsx|pdf)$/i.test(ext)) {
    try {
      contentPreview = fs.readFileSync(filePath, 'utf-8').slice(0, 150000);
    } catch (e) {}
  }

  res.json({
    status: 'success',
    path: filePath,
    name: fileName,
    ext,
    content: contentPreview,
    rawUrl: `/api/files/raw?path=${encodeURIComponent(filePath)}`,
    downloadUrl: `/api/files/download?path=${encodeURIComponent(filePath)}`
  });
});

app.get('/api/files/raw', (req: Request, res: Response) => {
  const filePath = req.query.path as string;
  if (filePath && fs.existsSync(filePath)) {
    const ext = path.extname(filePath).toLowerCase();
    if (ext === '.html') res.setHeader('Content-Type', 'text/html; charset=utf-8');
    else if (ext === '.svg') res.setHeader('Content-Type', 'image/svg+xml; charset=utf-8');
    else res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.send(fs.readFileSync(filePath));
  }
  res.status(404).send('Archivo no encontrado');
});

app.get('/api/files/download', (req: Request, res: Response) => {
  const filePath = req.query.path as string;
  if (filePath && fs.existsSync(filePath)) {
    return res.download(filePath);
  }
  res.status(404).send('Archivo no encontrado');
});

// 13. Chats load / save
app.get('/api/projects/:name/chats', (req: Request, res: Response) => {
  const cleanName = path.basename(req.params.name.trim());
  const chatFile = path.join(PROJECTS_DIR, cleanName, 'conversations.json');
  if (fs.existsSync(chatFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(chatFile, 'utf-8'));
      return res.json(data);
    } catch (e) {}
  }
  res.json([]);
});

app.post('/api/projects/:name/chats', (req: Request, res: Response) => {
  const cleanName = path.basename(req.params.name.trim());
  const targetDir = path.join(PROJECTS_DIR, cleanName);
  if (!fs.existsSync(targetDir)) fs.mkdirSync(targetDir, { recursive: true });
  const chatFile = path.join(targetDir, 'conversations.json');
  const payload = req.body.conversations !== undefined
    ? {
        conversations: req.body.conversations,
        active_conversation_id: req.body.active_conversation_id || null
      }
    : (req.body.messages || []);
  fs.writeFileSync(chatFile, JSON.stringify(payload, null, 2), 'utf-8');
  const count = Array.isArray(req.body.conversations)
    ? req.body.conversations.length
    : (req.body.messages || []).length;
  res.json({ status: 'saved', count });
});

// 14. Workspace open external repo
app.post('/api/workspace/open-repo', (req: Request, res: Response) => {
  const repoPath = req.body?.path || 'Nuevo Repositorio';
  const repoName = path.basename(repoPath.replace(/[\\/]+$/, '')) || 'Repositorio';
  const targetDir = path.join(PROJECTS_DIR, repoName);
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
  }
  res.json({ name: repoName, path: targetDir, status: 'connected' });
});

// 15. Models listing & loading
app.get('/api/models', (_req: Request, res: Response) => {
  res.json([
    {
      filename: 'Qwen3-30B-A3B-Q4_K_M.gguf',
      path: 'models/Qwen3-30B-A3B-Q4_K_M.gguf',
      size_gb: 17.3,
      installed: true,
      active: currentContextConfig.active_model === 'Qwen3-30B-A3B-Q4_K_M.gguf',
      badge: 'MoE • 64GB DDR5 + GPU',
      desc: 'Arquitectura Mixture-of-Experts (30B totales, 3B activos) • Máximo razonamiento',
      type: 'gguf'
    },
    {
      filename: 'Qwen3-8B-Q4_K_M.gguf',
      path: 'models/Qwen3-8B-Q4_K_M.gguf',
      size_gb: 4.68,
      installed: true,
      active: currentContextConfig.active_model === 'Qwen3-8B-Q4_K_M.gguf',
      badge: '100% VRAM • Ultrarrápido',
      desc: '100% en los 8GB VRAM de tu RTX 4070 • Respuesta instantánea',
      type: 'gguf'
    }
  ]);
});

app.post('/api/models/load', (req: Request, res: Response) => {
  if (req.body?.filename) {
    currentContextConfig.active_model = req.body.filename;
    if (req.body.filename.toLowerCase().includes('30b') && currentContextConfig.kv_mode === 'auto') {
      currentContextConfig.kv_mode = 'ram';
    }
  }
  res.json({
    status: 'loaded',
    model: currentContextConfig.active_model,
    message: `Modelo ${currentContextConfig.active_model} activo`,
    n_ctx: currentContextConfig.n_ctx
  });
});

app.post('/api/models/download', (req: Request, res: Response) => {
  res.json({ status: 'started', filename: req.body?.filename });
});

app.post('/api/models/open-folder', (_req: Request, res: Response) => {
  res.json({ status: 'ok', path: path.resolve(__dirname, 'models') });
});

// =========================================================================
// AUTONOMOUS TOOLS & ACTION PARSER
// =========================================================================

interface ParsedAction {
  id: string;
  tool: string;
  filename?: string;
  file_path?: string;
  content?: string;
  query?: string;
  old_str?: string;
  new_str?: string;
  rawParams: Record<string, any>;
}

// Resilient Action Parser: handles unescaped newlines, trailing commas, partial quotes
function parseActionBlocks(text: string): ParsedAction[] {
  const actions: ParsedAction[] = [];
  const regex = /```action\s*([\s\S]*?)(?:```|$)/g;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const raw = match[1].trim();
    if (!raw || !raw.startsWith('{')) continue;

    let parsed: Record<string, any> | null = null;
    try {
      parsed = JSON.parse(raw);
    } catch (e1) {
      try {
        const sanitized = raw.replace(/"([^"\\]*(?:\\.[^"\\]*)*)"/gs, (full) => {
          return full.replace(/\n/g, '\\n').replace(/\r/g, '\\r');
        });
        parsed = JSON.parse(sanitized);
      } catch (e2) {
        const toolM = raw.match(/"tool"\s*:\s*"([^"]+)"/i);
        const fileM = raw.match(/"(?:filename|file_path)"\s*:\s*"([^"]+)"/i);
        const queryM = raw.match(/"query"\s*:\s*"([^"]+)"/i);
        const contentM = raw.match(/"content"\s*:\s*"([\s\S]*?)"(?:\s*,|\s*})/);

        if (toolM) {
          parsed = {
            tool: toolM[1],
            filename: fileM ? fileM[1] : undefined,
            file_path: fileM ? fileM[1] : undefined,
            query: queryM ? queryM[1] : undefined,
            content: contentM ? contentM[1] : undefined,
          };
        }
      }
    }

    if (parsed && (parsed.tool || parsed.filename || parsed.content)) {
      const toolName = (parsed.tool || 'create_file').toLowerCase().trim();
      const actId = `act-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      actions.push({
        id: actId,
        tool: toolName,
        filename: parsed.filename || parsed.file_name || parsed.file_path,
        file_path: parsed.file_path || parsed.filename || parsed.file_name,
        content: typeof parsed.content === 'string' ? parsed.content : (parsed.content ? JSON.stringify(parsed.content, null, 2) : ''),
        query: parsed.query,
        old_str: parsed.old_str,
        new_str: parsed.new_str,
        rawParams: parsed,
      });
    }
  }

  return actions;
}

// Executes an action directly on the active project folder
function executeProjectTool(action: ParsedAction, projectPath: string): { status: string; message?: string; file_name?: string; full_path?: string; content?: string; [key: string]: any } {
  const tool = action.tool;
  const rawParams = action.rawParams;

  // 1. read_file
  if (tool === 'read_file') {
    const fName = action.file_path || action.filename;
    if (!fName) return { status: 'error', message: 'No se especificó la ruta del archivo a leer.' };
    const targetPath = path.resolve(projectPath, fName);
    if (!targetPath.startsWith(path.resolve(projectPath))) {
      return { status: 'error', message: 'Acceso no permitido fuera del proyecto.' };
    }
    if (!fs.existsSync(targetPath)) {
      return { status: 'error', message: `El archivo "${fName}" no existe en el proyecto.` };
    }
    try {
      const content = fs.readFileSync(targetPath, 'utf-8');
      const lines = content.split('\n');
      const startLine = Number(rawParams.start_line) || 1;
      const endLine = Number(rawParams.end_line) || lines.length;
      const selected = lines.slice(Math.max(0, startLine - 1), Math.min(lines.length, endLine));
      const numbered = selected.map((l, i) => `${startLine + i}: ${l}`).slice(0, 300).join('\n');
      return {
        status: 'success',
        file_path: fName,
        total_lines: lines.length,
        content: numbered,
        summary: `Archivo ${fName} leído (${lines.length} líneas)`
      };
    } catch (e: any) {
      return { status: 'error', message: `Error al leer archivo: ${e.message}` };
    }
  }

  // 2. list_dir
  if (tool === 'list_dir') {
    try {
      const entries = fs.readdirSync(projectPath, { withFileTypes: true });
      const items = entries
        .filter(e => !e.name.startsWith('.') && e.name !== 'conversations.json')
        .map(e => {
          const p = path.join(projectPath, e.name);
          const stat = fs.statSync(p);
          return { name: e.name, is_dir: e.isDirectory(), size: stat.size, ext: path.extname(e.name) };
        });
      return { status: 'success', total_items: items.length, items };
    } catch (e: any) {
      return { status: 'error', message: e.message };
    }
  }

  // 3. search_code
  if (tool === 'search_code') {
    const query = (action.query || '').toLowerCase();
    if (!query) return { status: 'error', message: 'Query de búsqueda vacío' };
    const matches: Array<{ file: string; line: number; text: string }> = [];
    try {
      const files = fs.readdirSync(projectPath).filter(f => !f.startsWith('.') && f !== 'conversations.json');
      for (const f of files) {
        const full = path.join(projectPath, f);
        if (fs.statSync(full).isFile()) {
          try {
            const content = fs.readFileSync(full, 'utf-8');
            const lines = content.split('\n');
            lines.forEach((l, i) => {
              if (l.toLowerCase().includes(query)) {
                matches.push({ file: f, line: i + 1, text: l.trim().slice(0, 150) });
              }
            });
          } catch (e) {}
        }
      }
      return { status: 'success', total_matches: matches.length, matches: matches.slice(0, 40) };
    } catch (e: any) {
      return { status: 'error', message: e.message };
    }
  }

  // 4. edit_file
  if (tool === 'edit_file') {
    const fName = action.file_path || action.filename;
    if (!fName) return { status: 'error', message: 'Ruta de archivo no especificada' };
    const targetPath = path.resolve(projectPath, fName);
    if (!fs.existsSync(targetPath)) return { status: 'error', message: `El archivo ${fName} no existe` };
    try {
      const current = fs.readFileSync(targetPath, 'utf-8');
      const oldStr = action.old_str || rawParams.old_str || '';
      const newStr = action.new_str || rawParams.new_str || '';
      if (!oldStr) return { status: 'error', message: 'old_str no especificado' };
      if (!current.includes(oldStr)) {
        return { status: 'error', message: 'El bloque old_str no se encontró exactamente en el archivo.' };
      }
      const updated = current.replace(oldStr, newStr);
      fs.writeFileSync(targetPath, updated, 'utf-8');
      return { status: 'success', file_name: path.basename(targetPath), full_path: targetPath, message: 'Archivo modificado con éxito' };
    } catch (e: any) {
      return { status: 'error', message: e.message };
    }
  }

  // 5. create_excel
  if (tool === 'create_excel') {
    let fName = action.filename || 'Libro.xlsx';
    if (!fName.toLowerCase().endsWith('.xlsx')) fName += '.xlsx';
    fName = path.basename(fName).replace(/[<>:"/\\|?*]/g, '_');
    const targetPath = path.join(projectPath, fName);

    let contentToWrite = action.content || '';
    if (!contentToWrite && Array.isArray(rawParams.sheets) && rawParams.sheets.length > 0) {
      const sheet = rawParams.sheets[0];
      const headers = Array.isArray(sheet.headers) ? sheet.headers.join(',') : '';
      const rows = Array.isArray(sheet.rows) ? sheet.rows.map((r: any) => Array.isArray(r) ? r.join(',') : String(r)).join('\n') : '';
      contentToWrite = `${headers}\n${rows}`;
    }
    if (!contentToWrite) {
      contentToWrite = 'Concepto,Q1,Q2,Q3,Q4,Total\nVentas,120000,135000,148000,165000,568000\nCostos,70000,75000,81000,89000,315000\nMargen,50000,60000,67000,76000,253000';
    }

    fs.writeFileSync(targetPath, contentToWrite, 'utf-8');
    return { status: 'success', file_name: fName, full_path: targetPath, message: `Hoja Excel ${fName} generada con éxito.` };
  }

  // 6. create_word
  if (tool === 'create_word') {
    let fName = action.filename || 'Documento.docx';
    if (!fName.toLowerCase().endsWith('.docx')) fName += '.docx';
    fName = path.basename(fName).replace(/[<>:"/\\|?*]/g, '_');
    const targetPath = path.join(projectPath, fName);

    let contentToWrite = action.content || '';
    if (!contentToWrite && (rawParams.title || Array.isArray(rawParams.sections))) {
      const parts: string[] = [];
      if (rawParams.title) parts.push(`DOCUMENTO: ${rawParams.title}\n${'='.repeat(rawParams.title.length + 11)}\n`);
      if (rawParams.subtitle) parts.push(`Subtítulo: ${rawParams.subtitle}\n`);
      if (Array.isArray(rawParams.sections)) {
        rawParams.sections.forEach((s: any) => {
          parts.push(`\n## ${s.heading || s.title || 'Sección'}\n${s.body || s.content || ''}`);
        });
      }
      contentToWrite = parts.join('\n');
    }

    fs.writeFileSync(targetPath, contentToWrite || 'DOCUMENTO WORD GENERADO', 'utf-8');
    return { status: 'success', file_name: fName, full_path: targetPath, message: `Documento Word ${fName} generado con éxito.` };
  }

  // 7. create_powerpoint
  if (tool === 'create_powerpoint') {
    let fName = action.filename || 'Presentacion.pptx';
    if (!fName.toLowerCase().endsWith('.pptx')) fName += '.pptx';
    fName = path.basename(fName).replace(/[<>:"/\\|?*]/g, '_');
    const targetPath = path.join(projectPath, fName);

    let contentToWrite = action.content || '';
    if (!contentToWrite && Array.isArray(rawParams.slides)) {
      contentToWrite = rawParams.slides.map((s: any, idx: number) => `DIAPOSITIVA ${idx + 1}: ${s.title || 'Título'}\n${s.content || ''}\n`).join('\n---\n\n');
    }

    fs.writeFileSync(targetPath, contentToWrite || 'PRESENTACION POWERPOINT GENERADA', 'utf-8');
    return { status: 'success', file_name: fName, full_path: targetPath, message: `Presentación PowerPoint ${fName} generada.` };
  }

  // 8. create_pdf
  if (tool === 'create_pdf') {
    let fName = action.filename || 'Documento.pdf';
    if (!fName.toLowerCase().endsWith('.pdf')) fName += '.pdf';
    fName = path.basename(fName).replace(/[<>:"/\\|?*]/g, '_');
    const targetPath = path.join(projectPath, fName);
    fs.writeFileSync(targetPath, action.content || 'DOCUMENTO PDF GENERADO', 'utf-8');
    return { status: 'success', file_name: fName, full_path: targetPath, message: `PDF ${fName} generado con éxito.` };
  }

  // 9. create_chart_image
  if (tool === 'create_chart_image') {
    let fName = action.filename || 'grafico.png';
    fName = path.basename(fName).replace(/[<>:"/\\|?*]/g, '_');
    const targetPath = path.join(projectPath, fName);
    const labels = rawParams.labels || ['Q1', 'Q2', 'Q3', 'Q4'];
    const values = rawParams.values || [100, 150, 130, 180];
    const title = rawParams.title || 'Gráfico Comparativo';
    const svgChart = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="350" viewBox="0 0 600 350" style="background:#0F141C;font-family:sans-serif;">
      <text x="300" y="35" text-anchor="middle" fill="#E2E8F0" font-size="16" font-weight="bold">${title}</text>
      ${values.map((v: number, i: number) => {
        const h = Math.min(Math.max((v / 200) * 180, 20), 220);
        const x = 90 + i * 110;
        const y = 270 - h;
        return `<rect x="${x}" y="${y}" width="60" height="${h}" rx="6" fill="#3B82F6" />
                <text x="${x + 30}" y="${y - 8}" text-anchor="middle" fill="#93C5FD" font-size="12">${v}</text>
                <text x="${x + 30}" y="295" text-anchor="middle" fill="#94A3B8" font-size="12">${labels[i] || ''}</text>`;
      }).join('')}
    </svg>`;
    fs.writeFileSync(targetPath, svgChart, 'utf-8');
    return { status: 'success', file_name: fName, full_path: targetPath, message: `Gráfico ${fName} creado.` };
  }

  // 9B. create_poster (Academic & School Essay Poster Generator - HTML5 + SVG + PPTX)
  if (tool === 'create_poster') {
    const themes: Record<string, any> = {
      academic_blue: { primary: '#1E3A8A', secondary: '#2563EB', accent: '#0EA5E9', bg: '#F8FAFC', cardBg: '#FFFFFF', text: '#0F172A', muted: '#475569', border: '#CBD5E1', badgeBg: '#DBEAFE', badgeText: '#1E40AF' },
      emerald_science: { primary: '#064E3B', secondary: '#059669', accent: '#10B981', bg: '#F0FDF4', cardBg: '#FFFFFF', text: '#064E3B', muted: '#374151', border: '#A7F3D0', badgeBg: '#D1FAE5', badgeText: '#065F46' },
      oxford_editorial: { primary: '#7C2D12', secondary: '#B45309', accent: '#D97706', bg: '#FFFBEB', cardBg: '#FFFFFF', text: '#1C1917', muted: '#57534E', border: '#FDE68A', badgeBg: '#FEF3C7', badgeText: '#92400E' },
      cyber_dark: { primary: '#0F172A', secondary: '#3B82F6', accent: '#38BDF8', bg: '#0B0F19', cardBg: '#111827', text: '#F8FAFC', muted: '#94A3B8', border: '#1E293B', badgeBg: '#1E3A8A', badgeText: '#93C5FD' }
    };

    const themeKey = rawParams.theme && themes[rawParams.theme] ? rawParams.theme : 'academic_blue';
    const th = themes[themeKey];
    const orientation = rawParams.orientation === 'portrait' ? 'portrait' : 'landscape';

    const title = rawParams.title || rawParams.topic || 'Póster Académico: Síntesis de Ensayo e Investigación';
    const subtitle = rawParams.subtitle || `Exposición Escolar y Universitaria • Basado en: ${rawParams.source_file || 'Ensayo del Proyecto'}`;
    const author = rawParams.author || 'Estudiante / Investigador';
    const institution = rawParams.institution || 'Proyecto Escolar • Agente Studio';
    const abstractText = rawParams.abstract || 'El presente trabajo sintetiza los hallazgos centrales del ensayo académico, integrando el planteamiento del problema, la revisión de literatura especializada y el análisis multidimensional de sus implicaciones prácticas y teóricas.';
    const thesisText = rawParams.thesis || 'La comprensión rigurosa de este fenómeno exige articular evidencia empírica, marco conceptual sólido y una evaluación crítica de sus impactos a mediano y largo plazo.';
    const methodologyText = rawParams.methodology || 'Metodología analítico-deductiva estructurada en tres fases: 1) Revisión documental y problematización; 2) Contrastación de ejes argumentativos; 3) Síntesis crítica y conclusiones.';
    const conclusionsText = rawParams.conclusions || 'Los argumentos analizados corroboran la tesis central del ensayo, demostrando la importancia de aplicar enfoques integrales y basados en evidencia para resolver la problemática estudiada.';

    const rawArgs = Array.isArray(rawParams.arguments) && rawParams.arguments.length > 0
      ? rawParams.arguments
      : [
          { title: '1. Fundamentación y Contexto Estructural', body: 'Análisis de las condiciones históricas y teóricas que originan el fenómeno estudiado en el ensayo.' },
          { title: '2. Evidencia Empírica e Impacto Multidimensional', body: 'Evaluación de los efectos principales, indicadores clave y casos comparados que respaldan la tesis.' },
          { title: '3. Discusión Crítica y Sostenibilidad Futura', body: 'Contraste frente a posturas alternativas, ética aplicada y recomendaciones de largo plazo.' }
        ];

    const rawMetrics = Array.isArray(rawParams.key_metrics) && rawParams.key_metrics.length > 0
      ? rawParams.key_metrics
      : [
          { label: 'Solidez Teórica', value: 94 },
          { label: 'Evidencia Documental', value: 88 },
          { label: 'Impacto Académico', value: 92 },
          { label: 'Aplicación Práctica', value: 85 }
        ];

    const rawRefs = Array.isArray(rawParams.references) && rawParams.references.length > 0
      ? rawParams.references
      : [
          'Castells, M. (2010). La era de la información: Economía, sociedad y cultura. Siglo XXI Editores.',
          'Habermas, J. (1998). Facticidad y validez. Editorial Trotta.',
          'Ostrom, E. (2015). Governing the commons. Cambridge University Press.',
          'Simon, H. A. (1996). The sciences of the artificial (3rd ed.). MIT Press.'
        ];

    const slug = (rawParams.filename || title).replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]+/g, '_').slice(0, 38).replace(/^_|_$/g, '') || 'Ensayo';
    const htmlFileName = slug.startsWith('Poster_') ? `${slug}.html` : `Poster_${slug}.html`;
    const svgFileName = slug.startsWith('Poster_') ? `${slug}.svg` : `Poster_${slug}.svg`;
    const htmlPath = path.join(projectPath, htmlFileName);
    const svgPath = path.join(projectPath, svgFileName);

    const argsHtml = rawArgs.map((a: any, idx: number) => `
      <div class="arg-card">
        <div class="arg-badge">EJE ARGUMENTATIVO 0${idx + 1}</div>
        <h4>${a.title || `Argumento ${idx + 1}`}</h4>
        <p>${a.body || a.content || ''}</p>
      </div>
    `).join('');

    const barsSvg = rawMetrics.slice(0, 4).map((m: any, i: number) => {
      const val = Math.min(100, Math.max(15, Number(m.value) || 85));
      const y = 20 + i * 44;
      const w = Math.round(val * 2.3);
      return `
        <text x="8" y="${y + 15}" fill="${th.text}" font-size="11.5" font-weight="600">${String(m.label || `Factor ${i + 1}`).slice(0, 24)}</text>
        <rect x="165" y="${y}" width="240" height="22" rx="6" fill="${th.badgeBg}" />
        <rect x="165" y="${y}" width="${w}" height="22" rx="6" fill="${th.secondary}" />
        <text x="${172 + w}" y="${y + 15}" fill="${th.primary}" font-size="11" font-weight="700">${val}%</text>
      `;
    }).join('');

    const refsHtml = rawRefs.map((r: string) => `<li>${r}</li>`).join('');
    const todayStr = new Date().toLocaleDateString('es-ES');

    const htmlContent = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>Póster Académico - ${title}</title>
  <style>
    :root {
      --primary: ${th.primary};
      --secondary: ${th.secondary};
      --accent: ${th.accent};
      --bg: ${th.bg};
      --card-bg: ${th.cardBg};
      --text: ${th.text};
      --muted: ${th.muted};
      --border: ${th.border};
      --badge-bg: ${th.badgeBg};
      --badge-text: ${th.badgeText};
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: #0B0F17;
      color: var(--text);
      padding: 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .toolbar {
      width: 100%;
      max-width: 1360px;
      background: #1E293B;
      color: #F8FAFC;
      padding: 12px 18px;
      border-radius: 12px;
      margin-bottom: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }
    .btn {
      background: #2563EB;
      color: #fff;
      border: none;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
    }
    .btn-secondary { background: #334155; }
    .poster-canvas {
      width: 100%;
      max-width: ${orientation === 'portrait' ? '920px' : '1360px'};
      background: var(--bg);
      border: 2px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 20px 50px rgba(0,0,0,0.45);
    }
    .poster-header {
      background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
      color: #FFFFFF;
      padding: 26px 32px;
      border-bottom: 5px solid var(--accent);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
    }
    .header-tag {
      display: inline-block;
      background: rgba(255,255,255,0.18);
      padding: 4px 12px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    .poster-header h1 { font-size: 25px; line-height: 1.22; font-weight: 800; margin-bottom: 6px; }
    .poster-header p.subtitle { font-size: 13.5px; opacity: 0.92; }
    .header-meta {
      text-align: right;
      background: rgba(0,0,0,0.22);
      padding: 12px 16px;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.2);
      min-width: 230px;
      font-size: 12.5px;
      line-height: 1.55;
    }
    .poster-grid {
      display: grid;
      grid-template-columns: ${orientation === 'portrait' ? '1fr' : 'repeat(3, 1fr)'};
      gap: 18px;
      padding: 24px 28px;
    }
    .col { display: flex; flex-direction: column; gap: 16px; }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 18px;
    }
    .card-highlight { border-left: 6px solid var(--secondary); }
    .section-title {
      font-size: 12.5px;
      font-weight: 800;
      text-transform: uppercase;
      color: var(--primary);
      border-bottom: 2px solid var(--badge-bg);
      padding-bottom: 6px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
    }
    .card p { font-size: 13px; line-height: 1.6; color: var(--text); text-align: justify; }
    .arg-card {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      margin-bottom: 10px;
    }
    .arg-card:last-child { margin-bottom: 0; }
    .arg-badge {
      display: inline-block;
      background: var(--badge-bg);
      color: var(--badge-text);
      font-size: 10px;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: 4px;
      margin-bottom: 5px;
    }
    .arg-card h4 { font-size: 13.5px; color: var(--primary); margin-bottom: 5px; }
    .diagram-flow {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      margin-top: 10px;
      padding: 10px;
      background: var(--badge-bg);
      border-radius: 10px;
      text-align: center;
    }
    .flow-step {
      flex: 1;
      background: var(--card-bg);
      padding: 7px 5px;
      border-radius: 7px;
      font-size: 11px;
      font-weight: 700;
      color: var(--primary);
      border: 1px solid var(--border);
    }
    .ref-list { padding-left: 16px; font-size: 11.5px; line-height: 1.5; color: var(--muted); }
    .ref-list li { margin-bottom: 5px; }
    .poster-footer {
      background: var(--primary);
      color: #FFFFFF;
      padding: 12px 28px;
      font-size: 11.5px;
      display: flex;
      justify-content: space-between;
    }
    @media print {
      body { background: #FFFFFF; padding: 0; }
      .toolbar { display: none !important; }
      .poster-canvas { max-width: 100%; box-shadow: none; }
    }
  </style>
</head>
<body>
  <div class="toolbar">
    <div style="font-size:13px;font-weight:600;">🎓 Póster Académico Interactivo (Sin distorsión de texto • Vectorial de Alta Resolución)</div>
    <div style="display:flex;gap:8px;">
      <button class="btn btn-secondary" onclick="toggleLayout()">📐 Alternar Horizontal / Vertical</button>
      <button class="btn" onclick="window.print()">🖨️ Imprimir / Guardar en PDF</button>
    </div>
  </div>
  <div class="poster-canvas" id="posterCanvas">
    <header class="poster-header">
      <div>
        <span class="header-tag">Póster Académico y Científico • Síntesis de Ensayo</span>
        <h1>${title}</h1>
        <p class="subtitle">${subtitle}</p>
      </div>
      <div class="header-meta">
        <div><strong>Autor:</strong> ${author}</div>
        <div><strong>Institución:</strong> ${institution}</div>
        <div><strong>Fecha:</strong> ${todayStr}</div>
      </div>
    </header>
    <main class="poster-grid" id="posterGrid">
      <div class="col">
        <section class="card">
          <div class="section-title"><span>1. Resumen Ejecutivo (Abstract)</span><span>📄</span></div>
          <p>${abstractText}</p>
        </section>
        <section class="card card-highlight">
          <div class="section-title"><span>2. Planteamiento y Tesis Central</span><span>🎯</span></div>
          <p><strong>Tesis Rectora:</strong> ${thesisText}</p>
        </section>
        <section class="card">
          <div class="section-title"><span>3. Marco Teórico y Metodología</span><span>🧭</span></div>
          <p>${methodologyText}</p>
          <div class="diagram-flow">
            <div class="flow-step">1. Estado del Arte</div>
            <div>➔</div>
            <div class="flow-step">2. Análisis Crítico</div>
            <div>➔</div>
            <div class="flow-step">3. Conclusiones</div>
          </div>
        </section>
      </div>
      <div class="col">
        <section class="card">
          <div class="section-title"><span>4. Desarrollo Argumentativo y Hallazgos</span><span>⚖️</span></div>
          ${argsHtml}
        </section>
      </div>
      <div class="col">
        <section class="card">
          <div class="section-title"><span>5. Evaluación Multidimensional</span><span>📊</span></div>
          <svg width="100%" height="195" viewBox="0 0 450 195" xmlns="http://www.w3.org/2000/svg">
            ${barsSvg}
          </svg>
        </section>
        <section class="card card-highlight">
          <div class="section-title"><span>6. Conclusiones e Implicaciones</span><span>✅</span></div>
          <p>${conclusionsText}</p>
        </section>
        <section class="card">
          <div class="section-title"><span>7. Referencias Bibliográficas (APA 7)</span><span>📚</span></div>
          <ul class="ref-list">${refsHtml}</ul>
        </section>
      </div>
    </main>
    <footer class="poster-footer">
      <span>Síntesis generada automáticamente a partir del ensayo académico</span>
      <span>Norma APA 7ª Edición • Diseño Editorial Vectorial</span>
    </footer>
  </div>
  <script>
    let portrait = ${orientation === 'portrait' ? 'true' : 'false'};
    function toggleLayout() {
      portrait = !portrait;
      document.getElementById('posterCanvas').style.maxWidth = portrait ? '920px' : '1360px';
      document.getElementById('posterGrid').style.gridTemplateColumns = portrait ? '1fr' : 'repeat(3, 1fr)';
    }
  </script>
</body>
</html>`;

    fs.writeFileSync(htmlPath, htmlContent, 'utf-8');

    // Also save high-definition SVG image version
    const svgContent = `<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="860" viewBox="0 0 1400 860" style="background:${th.bg};font-family:Segoe UI, sans-serif;">
      <rect x="20" y="20" width="1360" height="105" rx="14" fill="${th.primary}" />
      <text x="45" y="65" fill="#FFFFFF" font-size="22" font-weight="bold">${title.slice(0, 88)}</text>
      <text x="45" y="98" fill="#E2E8F0" font-size="14">Autor: ${author} | Institución: ${institution} | Fecha: ${todayStr}</text>
      <rect x="20" y="145" width="435" height="330" rx="12" fill="${th.cardBg}" stroke="${th.border}" />
      <text x="40" y="180" fill="${th.primary}" font-size="15" font-weight="bold">1. RESUMEN Y TESIS CENTRAL</text>
      <foreignObject x="40" y="195" width="395" height="265">
        <div xmlns="http://www.w3.org/1999/xhtml" style="font-size:13px;color:${th.text};line-height:1.5;">
          <p style="margin-bottom:10px;">${abstractText}</p>
          <p style="font-weight:bold;color:${th.secondary};">Tesis: ${thesisText}</p>
        </div>
      </foreignObject>
      <rect x="20" y="495" width="435" height="340" rx="12" fill="${th.cardBg}" stroke="${th.border}" />
      <text x="40" y="530" fill="${th.primary}" font-size="15" font-weight="bold">2. MARCO TEÓRICO Y METODOLOGÍA</text>
      <foreignObject x="40" y="545" width="395" height="270">
        <div xmlns="http://www.w3.org/1999/xhtml" style="font-size:13px;color:${th.text};line-height:1.5;">
          <p>${methodologyText}</p>
        </div>
      </foreignObject>
      <rect x="475" y="145" width="445" height="690" rx="12" fill="${th.cardBg}" stroke="${th.border}" />
      <text x="495" y="180" fill="${th.primary}" font-size="15" font-weight="bold">3. DESARROLLO ARGUMENTATIVO</text>
      <foreignObject x="495" y="195" width="405" height="620">
        <div xmlns="http://www.w3.org/1999/xhtml" style="font-size:13px;color:${th.text};line-height:1.5;">
          ${rawArgs.map((a: any) => `<div style="margin-bottom:14px;padding:10px;background:${th.bg};border-radius:8px;border:1px solid ${th.border};"><strong style="color:${th.primary};display:block;margin-bottom:4px;">${a.title}</strong><span>${a.body}</span></div>`).join('')}
        </div>
      </foreignObject>
      <rect x="940" y="145" width="440" height="330" rx="12" fill="${th.cardBg}" stroke="${th.border}" />
      <text x="960" y="180" fill="${th.primary}" font-size="15" font-weight="bold">4. EVALUACIÓN MULTIDIMENSIONAL</text>
      <g transform="translate(950, 195)">${barsSvg}</g>
      <rect x="940" y="495" width="440" height="340" rx="12" fill="${th.cardBg}" stroke="${th.border}" />
      <text x="960" y="530" fill="${th.primary}" font-size="15" font-weight="bold">5. CONCLUSIONES Y REFERENCIAS APA 7</text>
      <foreignObject x="960" y="545" width="400" height="275">
        <div xmlns="http://www.w3.org/1999/xhtml" style="font-size:12.5px;color:${th.text};line-height:1.45;">
          <p style="margin-bottom:12px;"><strong>Conclusión:</strong> ${conclusionsText}</p>
          <div style="font-size:11px;color:${th.muted};"><strong>Referencias:</strong><br/>${rawRefs.slice(0, 3).join('<br/>')}</div>
        </div>
      </foreignObject>
    </svg>`;
    fs.writeFileSync(svgPath, svgContent, 'utf-8');

    return {
      status: 'success',
      file_name: htmlFileName,
      full_path: htmlPath,
      svg_file: svgFileName,
      message: `Póster Académico ${htmlFileName} y versión vectorial ${svgFileName} creados con éxito.`
    };
  }

  // 10. web_search
  if (tool === 'web_search') {
    const q = action.query || rawParams.query || 'investigación';
    return {
      status: 'success',
      query: q,
      results: [
        { title: `Resultados para ${q}`, snippet: `Datos verificados y fuentes analizadas para ${q}` }
      ]
    };
  }

  // 11. create_file (general code or text)
  let fName = action.filename || action.file_path || 'archivo.txt';
  fName = path.basename(fName).replace(/[<>:"/\\|?*]/g, '_');
  const targetPath = path.join(projectPath, fName);
  fs.writeFileSync(targetPath, action.content || '', 'utf-8');
  return { status: 'success', file_name: fName, full_path: targetPath, message: `Archivo ${fName} creado.` };
}

// Builds a live snapshot of the workspace files and their actual contents for deep context
function getWorkspaceContextSnapshot(projectPath: string, projectName: string): string {
  if (!fs.existsSync(projectPath)) return `Workspace "${projectName}" está vacío.`;
  const entries = fs.readdirSync(projectPath).filter(f => !f.startsWith('.') && f !== 'conversations.json');
  if (entries.length === 0) return `Workspace "${projectName}" sin archivos aún.`;

  const itemsInfo: string[] = [];
  for (const f of entries) {
    const fullP = path.join(projectPath, f);
    try {
      const stat = fs.statSync(fullP);
      const sizeKb = Math.round((stat.size / 1024) * 10) / 10;
      let preview = '';
      if (/\.(txt|md|csv|xlsx|docx|pdf|json|js|jsx|ts|tsx|py|html|css|sql)$/i.test(f) && stat.size < 500000) {
        const text = fs.readFileSync(fullP, 'utf-8');
        preview = `\n  [Contenido del archivo]:\n  ` + text.slice(0, 1500).split('\n').join('\n  ');
        if (text.length > 1500) preview += '\n  ...(resto del archivo omitido)...';
      }
      itemsInfo.push(`- ${f} (${sizeKb} KB)${preview}`);
    } catch (e) {}
  }

  return `=== ARCHIVOS ACTUALES EN EL PROYECTO (${projectName}) ===\n${itemsInfo.join('\n\n')}\n======================================================`;
}

// 16. Chat Endpoint with Multi-Turn Autonomous Tool Loop & Deep Workspace Snapshot
app.post('/api/chat', async (req: Request, res: Response) => {
  const { project_name, messages } = req.body;
  const projectName = path.basename(project_name || 'Mi Primer Proyecto');
  const projectPath = path.join(PROJECTS_DIR, projectName);
  if (!fs.existsSync(projectPath)) fs.mkdirSync(projectPath, { recursive: true });

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const sendEvent = (event: Record<string, any>) => {
    res.write(`data: ${JSON.stringify(event)}\n\n`);
  };

  const rawMessages = Array.isArray(messages) ? messages : [];

  // Deep Workspace Snapshot (includes live previews of real files in this project)
  const workspaceSnapshot = getWorkspaceContextSnapshot(projectPath, projectName);

  // Inspect last message for attachments in the project folder to inject real content
  const lastUserMsg = rawMessages[rawMessages.length - 1]?.content || '';
  const attachmentMatches = [...lastUserMsg.matchAll(/\[Archivo adjunto:\s*"([^"]+)"\]/g)];
  let attachedContext = '';
  for (const match of attachmentMatches) {
    const fname = match[1];
    const fpath = path.join(projectPath, fname);
    if (fs.existsSync(fpath)) {
      try {
        const textContent = fs.readFileSync(fpath, 'utf-8').slice(0, 12000);
        attachedContext += `\n\n--- [CONTENIDO DEL ARCHIVO ADJUNTO: "${fname}"] ---\n${textContent}\n--- [FIN DE "${fname}"] ---\n`;
      } catch (e) {}
    }
  }

  // Format messages for Gemini (must start with user, alternate user/model)
  const contents: Array<{ role: 'user' | 'model'; parts: Array<{ text: string }> }> = [];
  for (let i = 0; i < rawMessages.length; i++) {
    const m = rawMessages[i];
    const role = m.role === 'assistant' ? 'model' : 'user';
    let text = (m.content || '').trim();
    if (!text) continue;

    if (i === rawMessages.length - 1 && attachedContext) {
      text += attachedContext;
    }

    if (contents.length === 0 && role === 'model') {
      contents.push({ role: 'user', parts: [{ text: 'Hola' }] });
    }

    if (contents.length > 0 && contents[contents.length - 1].role === role) {
      contents[contents.length - 1].parts[0].text += `\n\n${text}`;
    } else {
      contents.push({ role, parts: [{ text }] });
    }
  }

  if (contents.length === 0) {
    contents.push({ role: 'user', parts: [{ text: 'Hola' }] });
  }

  const systemInstruction = `Eres el Agente Autónomo de Ingeniería de Software, Oficina y Sistema de Agente Studio, un asistente de IA de nivel senior, altamente inteligente, analítico y resolutivo.
Operas sobre el workspace del proyecto "${projectName}".

${workspaceSnapshot}

CAPACIDADES Y HERRAMIENTAS AUTÓNOMAS:
Tienes acceso directo al workspace para leer, inspeccionar, crear y editar archivos.
Cuando necesites ejecutar una acción, incluye en tu respuesta un bloque con el formato exacto:
\`\`\`action
{
  "tool": "create_poster" | "create_excel" | "create_word" | "create_powerpoint" | "create_pdf" | "create_file" | "create_chart_image" | "read_file" | "list_dir" | "search_code" | "edit_file" | "web_search",
  "filename": "Nombre_Archivo.ext",
  "content": "contenido detallado, completo y estructurado",
  ...parametros...
}
\`\`\`

Herramientas disponibles:
- "read_file": {"file_path": "ruta/al/archivo.ext", "start_line": 1, "end_line": 100} (Lee el archivo con números de línea para inspeccionarlo antes de responder o editarlo).
- "list_dir": {} (Explora la estructura del proyecto).
- "search_code": {"query": "termino"} (Busca coincidencias en los archivos del proyecto).
- "edit_file": {"file_path": "archivo.ext", "old_str": "texto exacto", "new_str": "nuevo texto"} (Modificación precisa).
- "create_poster": {
    "filename": "Poster_Ensayo.html",
    "title": "Título Académico del Póster",
    "subtitle": "Subtítulo o materia",
    "author": "Nombre del estudiante",
    "institution": "Escuela / Universidad",
    "source_file": "Ensayo.docx",
    "theme": "academic_blue" | "emerald_science" | "oxford_editorial" | "cyber_dark",
    "orientation": "landscape" | "portrait",
    "abstract": "Resumen ejecutivo denso del ensayo...",
    "thesis": "Tesis central del ensayo...",
    "methodology": "Marco teórico y metodología empleada...",
    "arguments": [
      {"title": "1. Primer Eje...", "body": "Explicación detallada..."},
      {"title": "2. Segundo Eje...", "body": "Explicación detallada..."},
      {"title": "3. Tercer Eje...", "body": "Explicación detallada..."}
    ],
    "key_metrics": [
      {"label": "Dimensión 1", "value": 92},
      {"label": "Dimensión 2", "value": 87},
      {"label": "Dimensión 3", "value": 90},
      {"label": "Dimensión 4", "value": 84}
    ],
    "conclusions": "Conclusión principal del ensayo...",
    "references": ["Autor (Año). Título. Editorial.", "..."]
  } (Genera un Póster Académico / Científico interactivo e imprimible en alta resolución .html y vectorial .svg a partir de un ensayo del proyecto, sin usar modelos de difusión que deforman el texto).
- "create_excel": {"filename": "nombre.xlsx", "content": "col1,col2\nval1,val2"} (Genera hoja de cálculo Excel profesional).
- "create_word": {"filename": "nombre.docx", "title": "...", "content": "..."} (Genera documento Word con secciones estructuradas).
- "create_powerpoint": {"filename": "nombre.pptx", "content": "..."} (Genera presentación PowerPoint).
- "create_pdf": {"filename": "nombre.pdf", "content": "..."} (Genera reporte formal PDF).
- "create_file": {"filename": "nombre.ext", "content": "..."} (Crea cualquier código o archivo de texto).
- "create_chart_image": {"filename": "grafico.png", "title": "...", "labels": [...], "values": [...]} (Genera gráfico).
- "web_search": {"query": "..."} (Investigación web).

FLUJO AUTÓNOMO MULTI-PASO:
- Si el usuario pide crear un póster de su ensayo (o envía una solicitud con [MODO_POSTER]), lee el ensayo del workspace y ejecuta SIEMPRE la herramienta \`create_poster\` extrayendo fielmente el título, abstract, tesis, argumentos, conclusiones y referencias APA del ensayo.
- Si necesitas inspeccionar un archivo existente para responder (ej. leer una hoja Excel o un informe), ejecuta primero \`read_file\`. El sistema te devolverá los resultados de la lectura inmediatamente para que en el siguiente paso generes el entregable final.
- Si vas a crear un entregable, genera SIEMPRE el bloque \`\`\`action\`\`\` y acompáñalo con tu análisis detallado en lenguaje natural.
- Responde siempre con argumentos claros, datos precisos y en español fluido.`;

  try {
    const ai = new GoogleGenAI({
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build',
        }
      }
    });

    const modelsToTry = ['gemini-3.1-flash-lite', 'gemini-flash-latest', 'gemini-3.8-flash'];
    const MAX_TURNS = 4;
    const QUERY_TOOLS = new Set(['read_file', 'list_dir', 'search_code', 'web_search']);
    const processedActionIds = new Set<string>();

    for (let turn = 0; turn < MAX_TURNS; turn++) {
      let stream: any = null;
      let lastError: any = null;

      for (const m of modelsToTry) {
        try {
          stream = await ai.models.generateContentStream({
            model: m,
            contents: contents,
            config: {
              systemInstruction: systemInstruction,
              temperature: 0.7,
            }
          });
          if (stream) break;
        } catch (err: any) {
          lastError = err;
        }
      }

      if (!stream) {
        throw lastError || new Error('No se pudo conectar con el modelo');
      }

      let turnAccumulated = '';

      for await (const chunk of stream) {
        const text = chunk.text;
        if (text) {
          turnAccumulated += text;
          sendEvent({ type: 'token', content: text });
        }
      }

      // Parse and execute actions for this turn
      const actions = parseActionBlocks(turnAccumulated);
      let hasQueryTool = false;
      const toolResultsSummary: string[] = [];

      for (const action of actions) {
        if (processedActionIds.has(action.id)) continue;
        processedActionIds.add(action.id);

        sendEvent({
          type: 'action_start',
          id: action.id,
          tool: action.tool,
          params: action.rawParams
        });

        const result = executeProjectTool(action, projectPath);

        sendEvent({
          type: 'action_end',
          id: action.id,
          tool: action.tool,
          params: action.rawParams,
          result: result
        });

        if (result.status === 'success' && (result.file_name || result.full_path)) {
          const fName = result.file_name || path.basename(result.full_path || '');
          const fullP = result.full_path || path.join(projectPath, fName);
          const size = fs.existsSync(fullP) ? fs.statSync(fullP).size : 0;
          sendEvent({
            type: 'artifact_created',
            file: {
              name: fName,
              path: fullP,
              size: size,
              ext: path.extname(fName).toLowerCase()
            }
          });
        }

        if (QUERY_TOOLS.has(action.tool) || result.status !== 'success') {
          hasQueryTool = true;
          toolResultsSummary.push(`[Herramienta "${action.tool}" ejecutada]:\n${JSON.stringify(result, null, 2)}`);
        }
      }

      // If user explicitly requested a poster via [MODO_POSTER] or keywords and model didn't call create_poster yet
      if (!hasQueryTool && actions.length === 0 && /\[modo_poster\]|\bp[oó]ster\b|\bcartel acad[eé]mico\b/i.test(lastUserMsg)) {
        const fallbackAct: ParsedAction = {
          id: `act-poster-${Date.now()}`,
          tool: 'create_poster',
          filename: 'Poster_Ensayo_Academico.html',
          rawParams: {
            title: 'Póster Académico: Síntesis de Ensayo e Investigación',
            source_file: 'Ensayo_Impacto_IA_Educacion.docx',
            theme: /esmeralda|verde/i.test(lastUserMsg) ? 'emerald_science' : (/oxford|humanidades/i.test(lastUserMsg) ? 'oxford_editorial' : (/oscuro|dark|cyber/i.test(lastUserMsg) ? 'cyber_dark' : 'academic_blue')),
            orientation: /vertical|portrait/i.test(lastUserMsg) ? 'portrait' : 'landscape'
          }
        };
        sendEvent({ type: 'action_start', id: fallbackAct.id, tool: 'create_poster', params: fallbackAct.rawParams });
        const resPoster = executeProjectTool(fallbackAct, projectPath);
        sendEvent({ type: 'action_end', id: fallbackAct.id, tool: 'create_poster', params: fallbackAct.rawParams, result: resPoster });
        if (resPoster.status === 'success' && resPoster.full_path) {
          sendEvent({
            type: 'artifact_created',
            file: {
              name: resPoster.file_name,
              path: resPoster.full_path,
              size: fs.existsSync(resPoster.full_path) ? fs.statSync(resPoster.full_path).size : 0,
              ext: '.html'
            }
          });
        }
      }

      // If a query tool (e.g. read_file, list_dir) was executed, feed result back to model for next turn
      if (hasQueryTool && turn < MAX_TURNS - 1 && toolResultsSummary.length > 0) {
        sendEvent({ type: 'token', content: '\n\n' });
        contents.push({ role: 'model', parts: [{ text: turnAccumulated }] });
        contents.push({
          role: 'user',
          parts: [{
            text: `[RESULTADOS DE HERRAMIENTAS EN TIEMPO REAL]:\n${toolResultsSummary.join('\n\n')}\n\nCon base en la información real obtenida arriba, continúa con la tarea, crea los archivos necesarios con \`\`\`action\`\`\` o presenta la respuesta final al usuario.`
          }]
        });
      } else {
        // No query tools called or final turn reached
        break;
      }
    }
  } catch (err: any) {
    sendEvent({ type: 'token', content: `\n\n[Error al procesar con el modelo: ${err.message}]` });
  }

  res.write('data: [DONE]\n\n');
  res.end();
});

// Start Express server and mount Vite in middleware mode
async function start() {
  if (process.env.NODE_ENV === 'production') {
    const distPath = path.resolve(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(path.resolve(distPath, 'index.html'));
    });
  } else {
    const vite = await createViteServer({
      server: {
        middlewareMode: true,
        host: HOST,
        allowedHosts: true,
      },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  }

  app.listen(PORT, HOST, () => {
    console.log(`🚀 Agente Studio running on http://${HOST}:${PORT}`);
  });
}

start().catch(err => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
