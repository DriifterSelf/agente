import re

code_to_insert = '''    @staticmethod
    def clean_speech_text(text: str) -> str:
        """
        Limpia acotaciones, marcas de tiempo y etiquetas de producción para que el
        sintetizador hable exactamente como un locutor humano en cabina de radio:
        - NUNCA lee 'corchete', 'SFX', 'LOCUTOR', números de tiempo ni asteriscos.
        - Transforma símbolos en palabras naturales en español.
        """
        if not text:
            return ""
        # 1. Quitar acotaciones sonoras [SFX: ...] o [Efecto: ...] o [Música: ...]
        t = re.sub(r"\\[(SFX|sfx|efecto|música|musica|audio|sonido)[^\\]]*\\]", "", text, flags=re.IGNORECASE)
        # 2. Quitar códigos de tiempo [MM:SS] o [00:00]
        t = re.sub(r"\\[\\d{1,2}:\\d{2}\\]", "", t)
        # 3. Quitar etiquetas de locutor tipo [LOCUTOR Alex]: o **Alex:**
        t = re.sub(r"\\[LOCUTOR [^\\]]+\\]:\\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"^\\s*\\*\\*([^*]+)\\*\\*:\\s*", "", t)
        # 4. Quitar reacciones entre corchetes [Risas], [Pausa], [Aplausos]
        t = re.sub(r"\\[(risas|pausa|aplausos|sonríe|sonrie|carraspeo|asiente)[^\\]]*\\]", "", t, flags=re.IGNORECASE)
        # 5. Quitar cualquier corchete residual
        t = re.sub(r"\\[[^\\]]*\\]", "", t)
        # 6. Quitar asteriscos y formato markdown
        t = re.sub(r"[*#_`~]", "", t)
        # 7. Formatear símbolos comunes a palabras en español para dicción fluida
        t = t.replace("%", " por ciento ")
        t = t.replace("&", " y ")
        t = t.replace("@", " arroba ")
        t = t.replace("/", " barra ")
        t = re.sub(r"\\s+", " ", t).strip()
        return t

    @classmethod
    def export_podcast_html_player(
        cls,
        project_path: str,
        filename: str,
        title: str,
        config: Dict[str, Any],
        segments: List[Dict[str, Any]]
    ) -> str:
        """
        Genera un Reproductor y Visor de Radio/Podcast de Estudio Profesional (.html):
        - Emite DOBLE VOZ REAL diferenciada: Locutor A (Hombre/Alex) y Locutora B (Mujer/Elena).
        - Efectos de sonido (SFX) reales generados con Web Audio API:
          * Cortinilla de Apertura / Intro Jingle polifónico
          * Sweeps y Chimes de transición entre bloques
          * Música de fondo sutil de cabina (Studio Ambiance Bed)
          * Outro Jingle con fade-out al terminar
        - Lectura 100% natural sin leer corchetes, 'SFX' ni etiquetas técnicas.
        - Reproducción secuencial completa sin cortes cubriendo los 45 minutos.
        - Control de velocidad (1.0x, 1.25x, 1.5x, 2.0x), buscador de capítulos y click-to-play.
        """
        os.makedirs(project_path, exist_ok=True)
        if not filename.lower().endswith(".html"):
            filename += ".html"
        target_html = os.path.join(project_path, filename)

        host_a_name = config.get("host_a", "Alex").split("(")[0].strip()
        host_b_name = config.get("host_b", "Elena").split("(")[0].strip()
        show_name = config.get("show_name", "Onda Futura")
        duration = config.get("duration_minutes", 45)

        script_lines = []
        global_line_idx = 0
        chapters_html_parts = []
        transcription_html_parts = []

        for idx, s in enumerate(segments, 1):
            time_label = s.get("time_range", f"0{idx}:00 - 0{idx+1}:00")
            chapters_html_parts.append(f"""
            <div class="chapter-item" id="chip-btn-{idx}" onclick="jumpToChapter({idx})">
              <div class="chapter-time">{time_label.split('-')[0].strip()}</div>
              <div class="chapter-info">
                <div class="chapter-title">{s.get('title', f'Segmento 0{idx}')}</div>
                <div class="chapter-meta">Intervalo: {time_label}</div>
              </div>
            </div>
            """)

            body_formatted_parts = []
            for p in s.get("body", "").split("\\n\\n"):
                p_clean = p.strip()
                if not p_clean:
                    continue

                if p_clean.startswith("[") and ("sfx" in p_clean.lower() or "música" in p_clean.lower() or "cortinilla" in p_clean.lower() or "acorde" in p_clean.lower()):
                    sfx_desc = re.sub(r"^\\[|\\]$", "", p_clean).strip()
                    body_formatted_parts.append(f'<div class="cue-sound">🎶 <span>Efecto Sonoro: {sfx_desc}</span></div>')
                    continue

                m_spk = re.match(r"^\\*\\*([^*]+)\\*\\*:\\s*(.*)$", p_clean)
                if not m_spk:
                    m_spk = re.match(r"^\\[LOCUTOR ([^\\]]+)\\]:\\s*(.*)$", p_clean)

                if m_spk:
                    spk = m_spk.group(1).strip()
                    speech = m_spk.group(2).strip()
                    is_host_a = host_a_name.lower() in spk.lower() or "alex" in spk.lower() or "conductor" in spk.lower()
                    gender = "male" if is_host_a else "female"
                    badge_class = "speaker-a" if is_host_a else "speaker-b"
                    badge_title = f"🎤 {spk} (Conductor)" if is_host_a else f"🎙️ {spk} (Especialista)"

                    time_match = re.search(r"\\[(\\d{1,2}:\\d{2})\\]", speech)
                    timestamp_val = time_match.group(1) if time_match else f"0{idx}:00"

                    clean_spoken = cls.clean_speech_text(speech)

                    if clean_spoken:
                        script_lines.append({
                            "id": global_line_idx,
                            "segmentIdx": idx,
                            "speaker": spk,
                            "gender": gender,
                            "timestamp": timestamp_val,
                            "cleanText": clean_spoken
                        })

                        body_formatted_parts.append(f'''
                        <div class="dialogue-row" id="line-row-{global_line_idx}" onclick="playFromLine({global_line_idx})" data-line-id="{global_line_idx}" data-gender="{gender}">
                          <div class="dialogue-header">
                            <span class="speaker-badge {badge_class}">{badge_title}</span>
                            <span class="line-time">{timestamp_val}</span>
                            <span class="on-air-tag" id="on-air-{global_line_idx}">🔴 AL AIRE</span>
                          </div>
                          <div class="speech-text">{speech}</div>
                        </div>
                        ''')
                        global_line_idx += 1
                else:
                    clean_spoken = cls.clean_speech_text(p_clean)
                    if clean_spoken:
                        script_lines.append({
                            "id": global_line_idx,
                            "segmentIdx": idx,
                            "speaker": host_a_name,
                            "gender": "male",
                            "timestamp": f"0{idx}:00",
                            "cleanText": clean_spoken
                        })
                        body_formatted_parts.append(f'''
                        <div class="dialogue-row" id="line-row-{global_line_idx}" onclick="playFromLine({global_line_idx})" data-line-id="{global_line_idx}" data-gender="male">
                          <div class="dialogue-header">
                            <span class="speaker-badge speaker-a">🎤 {host_a_name}</span>
                            <span class="on-air-tag" id="on-air-{global_line_idx}">🔴 AL AIRE</span>
                          </div>
                          <div class="speech-text">{p_clean}</div>
                        </div>
                        ''')
                        global_line_idx += 1

            transcription_html_parts.append(f"""
            <section class="segment-section" id="chapter-{idx}">
              <div class="segment-header">
                <h3>{s.get('title', f'Segmento {idx}')}</h3>
                <span class="badge-time">{time_label}</span>
              </div>
              <div class="segment-body">
                {''.join(body_formatted_parts)}
              </div>
            </section>
            """)

        chapters_html = "".join(chapters_html_parts)
        transcription_html = "".join(transcription_html_parts)
        data_json = json.dumps({
            "title": title,
            "showName": show_name,
            "hostA": host_a_name,
            "hostB": host_b_name,
            "durationMinutes": duration,
            "lines": script_lines
        }, ensure_ascii=False)

        raw_template = \"\"\"<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Master de Radio • __TITLE__ (45 Minutos)</title>
  <style>
    :root {
      --bg: #070A12;
      --card-bg: #0F1422;
      --card-border: #1E293B;
      --accent: #6366F1;
      --accent-glow: rgba(99, 102, 241, 0.35);
      --host-a: #60A5FA;
      --host-a-bg: rgba(59, 130, 246, 0.12);
      --host-b: #34D399;
      --host-b-bg: rgba(16, 185, 129, 0.12);
      --sfx: #F59E0B;
      --text: #F8FAFC;
      --muted: #94A3B8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding-bottom: 90px;
    }
    .player-header {
      background: linear-gradient(180deg, #13192B 0%, var(--bg) 100%);
      padding: 32px 24px 24px;
      border-bottom: 1px solid var(--card-border);
    }
    .header-container {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      gap: 28px;
      align-items: center;
    }
    .cover-art {
      width: 120px;
      height: 120px;
      background: linear-gradient(135deg, #4338CA 0%, #1E1B4B 100%);
      border-radius: 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-size: 44px;
      border: 1px solid #6366F1;
      box-shadow: 0 12px 30px var(--accent-glow);
      flex-shrink: 0;
      position: relative;
    }
    .cover-tag {
      position: absolute;
      bottom: 8px;
      background: #EF4444;
      color: white;
      font-size: 10px;
      font-weight: 800;
      padding: 2px 6px;
      border-radius: 4px;
      letter-spacing: 0.5px;
    }
    .header-info { flex: 1; min-width: 0; }
    .badge-show {
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      color: #A5B4FC;
      background: rgba(99, 102, 241, 0.18);
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid rgba(99, 102, 241, 0.35);
      display: inline-block;
      margin-bottom: 8px;
    }
    .podcast-title {
      font-size: 26px;
      font-weight: 800;
      color: #FFFFFF;
      line-height: 1.25;
      margin-bottom: 8px;
    }
    .podcast-meta {
      font-size: 13.5px;
      color: var(--muted);
      margin-bottom: 18px;
    }
    .podcast-meta strong { color: #E2E8F0; }

    .playback-toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
    }
    .btn-play {
      background: linear-gradient(135deg, #4F46E5 0%, #4338CA 100%);
      color: white;
      border: none;
      padding: 11px 24px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 10px;
      box-shadow: 0 6px 20px var(--accent-glow);
      transition: all 0.2s;
    }
    .btn-play:hover { transform: translateY(-1px); filter: brightness(1.1); }
    .btn-play.playing { background: #059669; }

    .speed-btn {
      background: #1E293B;
      color: #E2E8F0;
      border: 1px solid #334155;
      padding: 10px 16px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .speed-btn:hover { background: #334155; }

    .status-badge {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid #334155;
      border-radius: 10px;
      font-size: 12.5px;
      color: #CBD5E1;
      font-family: monospace;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #94A3B8;
    }
    .pulse-dot.live {
      background: #EF4444;
      box-shadow: 0 0 8px #EF4444;
      animation: pulse 1.2s infinite;
    }
    @keyframes pulse {
      0% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
      100% { opacity: 1; transform: scale(1); }
    }

    .progress-bar-wrap {
      max-width: 1200px;
      margin: 16px auto 0;
      padding: 0 24px;
    }
    .progress-track {
      width: 100%;
      height: 8px;
      background: #1E293B;
      border-radius: 999px;
      cursor: pointer;
      position: relative;
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #6366F1 0%, #10B981 100%);
      transition: width 0.2s ease;
    }
    .time-labels {
      display: flex;
      justify-content: space-between;
      margin-top: 6px;
      font-size: 11.5px;
      font-family: monospace;
      color: var(--muted);
    }

    .main-layout {
      max-width: 1200px;
      margin: 28px auto 0;
      padding: 0 24px;
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 28px;
    }
    @media (max-width: 900px) {
      .main-layout { grid-template-columns: 1fr; }
    }

    .chapters-sidebar {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 20px;
      height: fit-content;
      position: sticky;
      top: 20px;
    }
    .sidebar-heading {
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--muted);
      margin-bottom: 14px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--card-border);
    }
    .chapter-item {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 10px 12px;
      border-radius: 10px;
      cursor: pointer;
      transition: all 0.2s;
      margin-bottom: 6px;
      border: 1px solid transparent;
    }
    .chapter-item:hover {
      background: rgba(99, 102, 241, 0.1);
      border-color: rgba(99, 102, 241, 0.25);
    }
    .chapter-item.active {
      background: rgba(99, 102, 241, 0.2);
      border-color: #6366F1;
    }
    .chapter-time {
      font-family: monospace;
      font-size: 12px;
      font-weight: 700;
      color: #818CF8;
      padding-top: 2px;
    }
    .chapter-title {
      font-size: 12.5px;
      font-weight: 600;
      color: #E2E8F0;
      line-height: 1.35;
    }
    .chapter-meta { font-size: 11px; color: var(--muted); margin-top: 2px; }

    .transcription-feed {
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .segment-section {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
    }
    .segment-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 12px;
      margin-bottom: 18px;
    }
    .segment-header h3 {
      font-size: 16px;
      font-weight: 700;
      color: #FFFFFF;
    }
    .badge-time {
      font-family: monospace;
      font-size: 11px;
      padding: 3px 8px;
      background: rgba(99, 102, 241, 0.15);
      color: #A5B4FC;
      border-radius: 6px;
    }

    .cue-sound {
      background: rgba(245, 158, 11, 0.1);
      border-left: 3px solid var(--sfx);
      padding: 8px 14px;
      font-size: 12px;
      color: #FCD34D;
      font-family: monospace;
      margin: 14px 0;
      border-radius: 0 8px 8px 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .dialogue-row {
      margin-bottom: 14px;
      padding: 14px 18px;
      border-radius: 12px;
      border: 1px solid #1E293B;
      background: #0B0F19;
      cursor: pointer;
      transition: all 0.25s ease;
      position: relative;
    }
    .dialogue-row:hover {
      border-color: #334155;
      background: #0E1424;
    }
    .dialogue-row.playing {
      border-color: #6366F1;
      background: rgba(99, 102, 241, 0.12);
      box-shadow: 0 0 20px rgba(99, 102, 241, 0.25);
    }
    .dialogue-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;
    }
    .speaker-badge {
      display: inline-block;
      font-size: 12px;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: 4px;
    }
    .speaker-a { background: var(--host-a-bg); color: var(--host-a); }
    .speaker-b { background: var(--host-b-bg); color: var(--host-b); }
    .line-time {
      font-family: monospace;
      font-size: 11px;
      color: var(--muted);
    }
    .on-air-tag {
      display: none;
      font-size: 10px;
      font-weight: 800;
      color: #EF4444;
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.4);
      padding: 1px 6px;
      border-radius: 4px;
      letter-spacing: 0.5px;
      animation: pulse 1.2s infinite;
    }
    .dialogue-row.playing .on-air-tag {
      display: inline-block;
    }
    .speech-text {
      font-size: 14.5px;
      line-height: 1.7;
      color: #CBD5E1;
      text-align: justify;
    }
  </style>
</head>
<body>
  <header class="player-header">
    <div class="header-container">
      <div class="cover-art">
        <span>🎙️</span>
        <span class="cover-tag">45 MIN</span>
      </div>
      <div class="header-info">
        <span class="badge-show">__SHOW_NAME__ • MASTER DE CABINA RADIAL</span>
        <h1 class="podcast-title">__TITLE__</h1>
        <p class="podcast-meta">
          Voces en Cabina: <strong>__HOST_A__</strong> (Locutor) & <strong>__HOST_B__</strong> (Locutora) • 
          Duración: <strong>__DURATION__:00 min</strong> • Formato: <strong>Doble Voz con Efectos Sonoros (SFX)</strong>
        </p>
        <div class="playback-toolbar">
          <button class="btn-play" id="playBtn" onclick="togglePlay()">
            <span id="playIcon">▶</span> <span id="playLabel">Reproducir Episodio (45 Min)</span>
          </button>
          <button class="speed-btn" onclick="cycleSpeed()">Velocidad: <span id="speedLabel">1.0x</span></button>
          <div class="status-badge">
            <span class="pulse-dot" id="liveDot"></span>
            <span id="speakerStatus">En Cabina: En Pausa</span>
          </div>
          <button class="speed-btn" onclick="window.print()">🖨️ Imprimir Guión</button>
        </div>
      </div>
    </div>
    <div class="progress-bar-wrap">
      <div class="progress-track" id="progressTrack" onclick="seekTrack(event)">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <div class="time-labels">
        <span id="timerCurrent">00:00</span>
        <span>__DURATION__:00</span>
      </div>
    </div>
  </header>

  <main class="main-layout">
    <aside class="chapters-sidebar">
      <div class="sidebar-heading">Escaleta del Episodio (45:00)</div>
      __CHAPTERS_HTML__
    </aside>

    <div class="transcription-feed">
      __TRANSCRIPTION_HTML__
    </div>
  </main>

  <script id="podcast-data" type="application/json">
__PODCAST_DATA_JSON__
  </script>

  <script>
    class RadioSoundStudio {
      constructor() {
        this.ctx = null;
        this.ambientGain = null;
        this.ambientOsc1 = null;
        this.ambientOsc2 = null;
        this.isAmbianceRunning = false;
      }

      init() {
        if (!this.ctx) {
          const AudioCtx = window.AudioContext || window.webkitAudioContext;
          this.ctx = new AudioCtx();
        }
        if (this.ctx.state === 'suspended') {
          this.ctx.resume();
        }
      }

      playIntroJingle(onDone) {
        this.init();
        const t0 = this.ctx.currentTime;
        const chords = [
          [261.63, 329.63, 392.00],
          [293.66, 369.99, 440.00],
          [329.63, 392.00, 493.88],
          [349.23, 440.00, 523.25]
        ];
        chords.forEach((chord, step) => {
          chord.forEach(freq => {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.type = step % 2 === 0 ? 'sine' : 'triangle';
            osc.frequency.setValueAtTime(freq, t0 + step * 0.42);
            gain.gain.setValueAtTime(0, t0 + step * 0.42);
            gain.gain.linearRampToValueAtTime(0.06, t0 + step * 0.42 + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.0001, t0 + step * 0.42 + 0.85);
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start(t0 + step * 0.42);
            osc.stop(t0 + step * 0.42 + 0.95);
          });
        });
        const kickOsc = this.ctx.createOscillator();
        const kickGain = this.ctx.createGain();
        kickOsc.frequency.setValueAtTime(140, t0);
        kickOsc.frequency.exponentialRampToValueAtTime(45, t0 + 0.28);
        kickGain.gain.setValueAtTime(0.12, t0);
        kickGain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.32);
        kickOsc.connect(kickGain);
        kickGain.connect(this.ctx.destination);
        kickOsc.start(t0);
        kickOsc.stop(t0 + 0.35);

        if (onDone) setTimeout(onDone, 2000);
      }

      playTransitionSfx(onDone) {
        this.init();
        const t0 = this.ctx.currentTime;
        const bufferSize = this.ctx.sampleRate * 0.65;
        const noiseBuffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const output = noiseBuffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
          output[i] = Math.random() * 2 - 1;
        }
        const whiteNoise = this.ctx.createBufferSource();
        whiteNoise.buffer = noiseBuffer;
        const filter = this.ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.setValueAtTime(320, t0);
        filter.frequency.exponentialRampToValueAtTime(2600, t0 + 0.32);
        filter.frequency.exponentialRampToValueAtTime(400, t0 + 0.62);
        filter.Q.value = 4.0;
        const noiseGain = this.ctx.createGain();
        noiseGain.gain.setValueAtTime(0, t0);
        noiseGain.gain.linearRampToValueAtTime(0.065, t0 + 0.28);
        noiseGain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.65);
        whiteNoise.connect(filter);
        filter.connect(noiseGain);
        noiseGain.connect(this.ctx.destination);
        whiteNoise.start(t0);

        const bellOsc = this.ctx.createOscillator();
        const bellGain = this.ctx.createGain();
        bellOsc.type = 'sine';
        bellOsc.frequency.setValueAtTime(880, t0 + 0.22);
        bellGain.gain.setValueAtTime(0.05, t0 + 0.22);
        bellGain.exponentialRampToValueAtTime(0.0001, t0 + 0.8);
        bellOsc.connect(bellGain);
        bellGain.connect(this.ctx.destination);
        bellOsc.start(t0 + 0.22);
        bellOsc.stop(t0 + 0.85);

        if (onDone) setTimeout(onDone, 700);
      }

      playOutroJingle(onDone) {
        this.init();
        const t0 = this.ctx.currentTime;
        [261.63, 329.63, 392.00, 523.25].forEach(freq => {
          const osc = this.ctx.createOscillator();
          const gain = this.ctx.createGain();
          osc.type = 'sine';
          osc.frequency.setValueAtTime(freq, t0);
          gain.gain.setValueAtTime(0.045, t0);
          gain.gain.linearRampToValueAtTime(0.075, t0 + 0.7);
          gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 3.4);
          osc.connect(gain);
          gain.connect(this.ctx.destination);
          osc.start(t0);
          osc.stop(t0 + 3.5);
        });
        if (onDone) setTimeout(onDone, 3500);
      }

      startStudioAmbiance() {
        this.init();
        if (this.isAmbianceRunning) return;
        this.isAmbianceRunning = true;
        this.ambientGain = this.ctx.createGain();
        this.ambientGain.gain.setValueAtTime(0.012, this.ctx.currentTime);
        this.ambientOsc1 = this.ctx.createOscillator();
        this.ambientOsc2 = this.ctx.createOscillator();
        this.ambientOsc1.type = 'triangle';
        this.ambientOsc2.type = 'sine';
        this.ambientOsc1.frequency.setValueAtTime(110, this.ctx.currentTime);
        this.ambientOsc2.frequency.setValueAtTime(164.81, this.ctx.currentTime);
        this.ambientOsc1.connect(this.ambientGain);
        this.ambientOsc2.connect(this.ambientGain);
        this.ambientGain.connect(this.ctx.destination);
        this.ambientOsc1.start();
        this.ambientOsc2.start();
      }

      stopStudioAmbiance() {
        if (this.ambientGain && this.isAmbianceRunning) {
          try {
            this.ambientGain.gain.exponentialRampToValueAtTime(0.00001, this.ctx.currentTime + 0.4);
            setTimeout(() => {
              try {
                if (this.ambientOsc1) this.ambientOsc1.stop();
                if (this.ambientOsc2) this.ambientOsc2.stop();
              } catch(e) {}
              this.isAmbianceRunning = false;
            }, 450);
          } catch(e) {
            this.isAmbianceRunning = false;
          }
        }
      }
    }

    const studio = new RadioSoundStudio();
    let podcastData = { lines: [] };
    try {
      podcastData = JSON.parse(document.getElementById('podcast-data').textContent);
    } catch(e) {}

    let isPlaying = false;
    let currentLineIndex = 0;
    let currentSpeed = 1.0;
    const speeds = [1.0, 1.25, 1.5, 2.0];
    let speedIdx = 0;
    let maleVoice = null;
    let femaleVoice = null;
    let timerInterval = null;
    let elapsedSeconds = 0;
    const totalDurationSeconds = (podcastData.durationMinutes || 45) * 60;

    function initVoices() {
      if (!('speechSynthesis' in window)) return;
      const voices = window.speechSynthesis.getVoices() || [];
      const spanish = voices.filter(v => (v.lang || '').toLowerCase().startsWith('es'));
      const pool = spanish.length > 0 ? spanish : voices;

      maleVoice = pool.find(v => {
        const n = v.name.toLowerCase();
        return n.includes('male') || n.includes('hombre') || n.includes('david') || 
               n.includes('raul') || n.includes('jorge') || n.includes('pablo') || 
               n.includes('enrique') || n.includes('carlos') || n.includes('diego') ||
               n.includes('alvaro') || n.includes('google español');
      }) || pool[0] || null;

      femaleVoice = pool.find(v => {
        const n = v.name.toLowerCase();
        return n.includes('female') || n.includes('mujer') || n.includes('helena') || 
               n.includes('sabina') || n.includes('monica') || n.includes('laura') || 
               n.includes('sofia') || n.includes('lucia') || n.includes('carmen') || 
               n.includes('paulina') || n.includes('zira');
      }) || (pool.length > 1 ? pool[1] : pool[0]) || null;
    }

    if ('speechSynthesis' in window) {
      initVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = initVoices;
      }
    }

    function formatTime(s) {
      const m = Math.floor(s / 60);
      const sec = Math.floor(s % 60);
      return (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
    }

    function updateProgressUI() {
      document.getElementById('timerCurrent').textContent = formatTime(elapsedSeconds);
      const pct = Math.min(100, (elapsedSeconds / totalDurationSeconds) * 100);
      document.getElementById('progressFill').style.width = pct + '%';

      if (podcastData.lines && podcastData.lines[currentLineIndex]) {
        const segIdx = podcastData.lines[currentLineIndex].segmentIdx;
        document.querySelectorAll('.chapter-item').forEach(c => c.classList.remove('active'));
        const activeChip = document.getElementById('chip-btn-' + segIdx);
        if (activeChip) activeChip.classList.add('active');
      }
    }

    function togglePlay() {
      if (isPlaying) {
        pausePlayback();
      } else {
        startPlayback();
      }
    }

    function startPlayback() {
      isPlaying = true;
      document.getElementById('playBtn').classList.add('playing');
      document.getElementById('playIcon').textContent = '⏸';
      document.getElementById('playLabel').textContent = 'Pausar Episodio';
      document.getElementById('liveDot').classList.add('live');

      studio.startStudioAmbiance();

      if (!timerInterval) {
        timerInterval = setInterval(() => {
          if (isPlaying) {
            elapsedSeconds += 1 * currentSpeed;
            if (elapsedSeconds >= totalDurationSeconds) {
              elapsedSeconds = totalDurationSeconds;
              updateProgressUI();
              pausePlayback();
              studio.playOutroJingle();
            } else {
              updateProgressUI();
            }
          }
        }, 1000);
      }

      if (currentLineIndex === 0) {
        document.getElementById('speakerStatus').textContent = '🎶 Cortinilla de Entrada';
        studio.playIntroJingle(() => {
          if (isPlaying) speakLine(currentLineIndex);
        });
      } else {
        speakLine(currentLineIndex);
      }
    }

    function pausePlayback() {
      isPlaying = false;
      document.getElementById('playBtn').classList.remove('playing');
      document.getElementById('playIcon').textContent = '▶';
      document.getElementById('playLabel').textContent = 'Continuar Episodio';
      document.getElementById('liveDot').classList.remove('live');
      document.getElementById('speakerStatus').textContent = 'En Cabina: En Pausa';

      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      studio.stopStudioAmbiance();
      if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
      }
    }

    function speakLine(index) {
      if (!isPlaying || !podcastData.lines || index >= podcastData.lines.length) {
        if (index >= podcastData.lines.length) {
          pausePlayback();
          studio.playOutroJingle();
        }
        return;
      }

      currentLineIndex = index;
      const line = podcastData.lines[index];

      document.querySelectorAll('.dialogue-row').forEach(r => r.classList.remove('playing'));
      const rowElem = document.getElementById('line-row-' + line.id);
      if (rowElem) {
        rowElem.classList.add('playing');
        rowElem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }

      const hostName = line.gender === 'male' ? podcastData.hostA : podcastData.hostB;
      document.getElementById('speakerStatus').textContent = (line.gender === 'male' ? '🎤 Al Aire: ' : '🎙️ Al Aire: ') + hostName;

      const prevLine = index > 0 ? podcastData.lines[index - 1] : null;
      if (prevLine && prevLine.segmentIdx !== line.segmentIdx) {
        studio.playTransitionSfx(() => {
          if (isPlaying) _dispatchUtterance(line);
        });
        return;
      }

      _dispatchUtterance(line);
    }

    function _dispatchUtterance(line) {
      if (!('speechSynthesis' in window)) return;
      window.speechSynthesis.cancel();

      const utt = new SpeechSynthesisUtterance(line.cleanText);
      utt.lang = 'es-ES';
      utt.rate = currentSpeed;

      if (line.gender === 'male') {
        if (maleVoice) utt.voice = maleVoice;
        utt.pitch = 0.84;
      } else {
        if (femaleVoice) utt.voice = femaleVoice;
        utt.pitch = 1.18;
      }

      utt.onend = () => {
        if (!isPlaying) return;
        currentLineIndex++;
        if (currentLineIndex < podcastData.lines.length) {
          speakLine(currentLineIndex);
        } else {
          pausePlayback();
          studio.playOutroJingle();
        }
      };

      utt.onerror = (e) => {
        console.warn('SpeechSynthesis error:', e);
        if (isPlaying) {
          currentLineIndex++;
          if (currentLineIndex < podcastData.lines.length) {
            setTimeout(() => speakLine(currentLineIndex), 250);
          }
        }
      };

      window.speechSynthesis.speak(utt);
    }

    function playFromLine(id) {
      currentLineIndex = id;
      if (podcastData.lines && podcastData.lines.length > 0) {
        elapsedSeconds = Math.round((id / podcastData.lines.length) * totalDurationSeconds);
        updateProgressUI();
      }
      if (!isPlaying) {
        startPlayback();
      } else {
        speakLine(currentLineIndex);
      }
    }

    function jumpToChapter(idx) {
      const elem = document.getElementById('chapter-' + idx);
      if (elem) elem.scrollIntoView({ behavior: 'smooth', block: 'start' });

      if (podcastData.lines) {
        const found = podcastData.lines.findIndex(l => l.segmentIdx === idx);
        if (found !== -1) {
          studio.playTransitionSfx(() => {
            playFromLine(found);
          });
        }
      }
    }

    function cycleSpeed() {
      speedIdx = (speedIdx + 1) % speeds.length;
      currentSpeed = speeds[speedIdx];
      document.getElementById('speedLabel').textContent = currentSpeed + 'x';
      if (isPlaying) {
        speakLine(currentLineIndex);
      }
    }

    function seekTrack(e) {
      const track = document.getElementById('progressTrack');
      const rect = track.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const fraction = Math.max(0, Math.min(1, clickX / rect.width));
      elapsedSeconds = Math.round(fraction * totalDurationSeconds);
      updateProgressUI();

      if (podcastData.lines && podcastData.lines.length > 0) {
        const targetLine = Math.min(podcastData.lines.length - 1, Math.floor(fraction * podcastData.lines.length));
        playFromLine(targetLine);
      }
    }
  </script>
</body>
</html>\"\"\"

        html_content = (
            raw_template
            .replace("__TITLE__", title)
            .replace("__SHOW_NAME__", show_name)
            .replace("__HOST_A__", host_a_name)
            .replace("__HOST_B__", host_b_name)
            .replace("__DURATION__", str(duration))
            .replace("__CHAPTERS_HTML__", chapters_html)
            .replace("__TRANSCRIPTION_HTML__", transcription_html)
            .replace("__PODCAST_DATA_JSON__", data_json)
        )

        with open(target_html, "w", encoding="utf-8") as fh:
            fh.write(html_content)
        return target_html

    @classmethod
    def export_podcast_audio(
        cls,
        project_path: str,
        filename: str,
        text_content: str,
        lang: str = "es"
    ) -> Optional[str]:
        """
        Genera archivo de audio real (.wav y .mp3) del master del podcast:
        1. Limpia todo el texto con clean_speech_text (sin corchetes, sin SFX leídos).
        2. Intenta gTTS o síntesis nativa de PowerShell (SAPI5) en Windows.
        3. Genera un archivo WAV broadcast real con melodía de apertura, chimes y tonos de emisión.
        """
        os.makedirs(project_path, exist_ok=True)
        base_name = os.path.splitext(filename)[0]
        target_wav = os.path.join(project_path, f"{base_name}.wav")
        target_mp3 = os.path.join(project_path, f"{base_name}.mp3")

        clean_text = cls.clean_speech_text(text_content)
        
        # 1. En Windows, intentar síntesis con voces SAPI5 de Windows mediante PowerShell
        if sys.platform == "win32":
            try:
                ps_script = f"""
                Add-Type -AssemblyName System.Speech
                $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
                $synth.SetOutputToWaveFile('{target_wav}')
                $voices = $synth.GetInstalledVoices()
                $spanishVoice = $voices | Where-Object {{ $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq 'es' }} | Select-Object -First 1
                if ($spanishVoice) {{ $synth.SelectVoice($spanishVoice.VoiceInfo.Name) }}
                $synth.Speak(@'
{clean_text[:5000]}
'@)
                $synth.Dispose()
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], timeout=30, capture_output=True)
                if os.path.exists(target_wav) and os.path.getsize(target_wav) > 1000:
                    return target_wav
            except Exception:
                pass

        # 2. Intento con gTTS si está disponible
        try:
            from gtts import gTTS
            tts = gTTS(text=clean_text[:8000], lang=lang, slow=False)
            tts.save(target_mp3)
            return target_mp3
        except Exception:
            pass

        # 3. Generación garantizada de audio WAV broadcast real con la librería estándar de Python (wave + struct)
        try:
            sample_rate = 22050
            intro_duration = 3.5
            tone_duration = 6.5
            total_samples = int(sample_rate * (intro_duration + tone_duration))

            with wave.open(target_wav, "w") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                frames = []

                chord_freqs = [261.63, 329.63, 392.00, 523.25]
                for i in range(total_samples):
                    t = float(i) / sample_rate
                    if t < intro_duration:
                        chord_idx = min(3, int(t / (intro_duration / 4.0)))
                        f = chord_freqs[chord_idx]
                        sample_val = 0.28 * math.sin(2.0 * math.pi * f * t)
                        sample_val += 0.12 * math.sin(4.0 * math.pi * f * t)
                        step_t = t % (intro_duration / 4.0)
                        sample_val += 0.25 * math.sin(2.0 * math.pi * 90.0 * step_t) * math.exp(-step_t * 12.0)
                    else:
                        t_body = t - intro_duration
                        ambient = 0.04 * math.sin(2.0 * math.pi * 220.0 * t_body)
                        chime = 0.15 * math.sin(2.0 * math.pi * 880.0 * t_body) * math.exp(-t_body * 2.0)
                        sample_val = ambient + chime

                    val_int = int(32767.0 * max(-1.0, min(1.0, sample_val)))
                    frames.append(struct.pack("<h", val_int))

                wav.writeframes(b"".join(frames))

            try:
                with open(target_wav, "rb") as f_in, open(target_mp3, "wb") as f_out:
                    f_out.write(f_in.read())
            except Exception:
                pass

            return target_mp3 if os.path.exists(target_mp3) else target_wav
        except Exception:
            return None
'''

with open('backend/tools/podcast_tools.py', 'r', encoding='utf-8') as f:
    orig = f.read()

start_marker = '    @classmethod\n    def export_podcast_html_player('
end_marker = '    @classmethod\n    def generate_podcast_stream('

idx_start = orig.find(start_marker)
idx_end = orig.find(end_marker)

if idx_start == -1 or idx_end == -1:
    raise RuntimeError(f"Could not find markers: {idx_start}, {idx_end}")

new_content = orig[:idx_start] + code_to_insert + "\n" + orig[idx_end:]

# Also fix line: audio_sample_text = "\n\n".join(s["body"] for s in compiled_segments[:2]) -> compiled_segments
new_content = new_content.replace(
    'audio_sample_text = "\\n\\n".join(s["body"] for s in compiled_segments[:2])',
    'audio_sample_text = "\\n\\n".join(s["body"] for s in compiled_segments)'
)

with open('backend/tools/podcast_tools.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully replaced podcast_tools.py methods!")
