import os
import re
import json
import math
import wave
import array
import struct
import shutil
import tempfile
import subprocess
import sys
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple


def clean_speech_text(text: str) -> str:
    """
    Limpia acotaciones, marcas de tiempo y etiquetas de producción para que el
    sintetizador hable exactamente como un locutor humano en cabina de radio:
    - NUNCA lee 'corchete', 'SFX', 'LOCUTOR', nombres de locutores al inicio, números de tiempo ni asteriscos.
    - Transforma símbolos en palabras naturales en español.
    """
    if not text:
        return ""
    # 1. Quitar acotaciones sonoras [SFX: ...] o [Efecto: ...] o [Música: ...] o *Efecto de audio...*
    t = re.sub(r"\[(SFX|sfx|efecto|música|musica|audio|sonido|cortinilla|puente|tema)[^\]]*\]", "", text, flags=re.IGNORECASE)
    t = re.sub(r"\*Efecto de audio[^*]*\*", "", t, flags=re.IGNORECASE)
    # 2. Quitar códigos de tiempo [MM:SS] o [00:00] o (00:00 - 05:00)
    t = re.sub(r"\[\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?\]", "", t)
    # 3. Quitar etiquetas de locutor tipo [LOCUTOR Alex]: o **Alex:** o Alex (Conductor):
    t = re.sub(r"\[LOCUTOR [^\]]+\]:?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^\s*\*\*([^*:]+)\*\*:?\s*", "", t)
    t = re.sub(r"^\s*\*\*([^*:]+):\*\*\s*", "", t)
    t = re.sub(r"^\s*(?:Alex|Elena|Lucas|Lucas Valenzuela|Dra\.\s*Elena(?:\s*Ramos)?|Conductor|Especialista|Locutor\s*[AB12]?)\s*(?:\([^)]*\))?\s*:\s*", "", t, flags=re.IGNORECASE)
    # 4. Quitar reacciones entre corchetes [Risas], [Pausa], [Aplausos]
    t = re.sub(r"\[(risas|pausa|aplausos|sonríe|sonrie|carraspeo|asiente|suspiro|énfasis|enfasis)[^\]]*\]", "", t, flags=re.IGNORECASE)
    # 5. Quitar cualquier corchete residual o encabezados markdown
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"^#{1,6}\s+.*$", "", t, flags=re.MULTILINE)
    # 6. Quitar asteriscos y formato markdown
    t = re.sub(r"[*#_`~>|]", "", t)
    # 7. Formatear símbolos comunes a palabras en español para dicción fluida
    t = t.replace("%", " por ciento ")
    t = t.replace("&", " y ")
    t = t.replace("@", " arroba ")
    t = t.replace("/", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def fast_pitch_shift_pcm16(pcm_bytes: bytes, pitch_factor: float = 0.78) -> bytes:
    """
    Cambiador de tono y formantes en tiempo real (WSOLA / Overlap-Add con ventana Hann)
    en Python puro (sin dependencias externas).
    - pitch_factor = 0.78 convierte una voz femenina (ej. Microsoft Sabina o Google TTS)
      en una voz masculina barítona profunda de radio sin alterar la duración de la locución.
    """
    if not pcm_bytes or abs(pitch_factor - 1.0) < 0.03:
        return pcm_bytes

    samples = array.array("h")
    usable_len = (len(pcm_bytes) // 2) * 2
    samples.frombytes(pcm_bytes[:usable_len])
    n = len(samples)
    if n < 1024:
        return pcm_bytes

    win_size = 960   # 40ms a 24kHz
    hop_syn = 480    # 50% overlap para reconstrucción suave sin artefactos metálicos
    hann = [0.5 * (1.0 - math.cos(2.0 * math.pi * i / win_size)) for i in range(win_size)]
    idx_map = [int(i * pitch_factor) for i in range(win_size)]
    max_offset = idx_map[-1] + 2

    out = array.array("h", [0] * n)
    pos_out = 0
    while pos_out + win_size < n and pos_out + max_offset < n:
        for i in range(win_size):
            val = int(samples[pos_out + idx_map[i]] * hann[i]) + out[pos_out + i]
            if val > 32767:
                val = 32767
            elif val < -32768:
                val = -32768
            out[pos_out + i] = val
        pos_out += hop_syn

    return out.tobytes()


def generate_intro_jingle_pcm(sample_rate: int = 24000) -> bytes:
    """
    Genera la cortinilla musical de entrada del podcast (3.6 segundos, PCM16 mono):
    Acordes progresivos de sintetizador broadcast + bombo electrónico + arpegio brillante.
    """
    duration = 3.6
    total_samples = int(sample_rate * duration)
    out = array.array("h", [0] * total_samples)
    chords = [
        [261.63, 329.63, 392.00, 493.88],  # Cmaj7
        [293.66, 349.23, 440.00, 523.25],  # Dm7
        [329.63, 392.00, 493.88, 587.33],  # Em7
        [349.23, 440.00, 523.25, 659.25],  # Fmaj7 -> resolución
    ]
    step_dur = duration / 4.0
    two_pi = 2.0 * math.pi

    for i in range(total_samples):
        t = i / float(sample_rate)
        step = min(3, int(t / step_dur))
        local_t = t - step * step_dur
        chord = chords[step]

        # Envolvente suave de acorde
        env = min(1.0, local_t / 0.04) * math.exp(-local_t * 2.2)
        val = 0.0
        for idx_f, freq in enumerate(chord):
            # Mezcla de onda sinusoidal y armónico cálido
            val += 0.14 * env * math.sin(two_pi * freq * t)
            if idx_f == 0:
                val += 0.10 * env * math.sin(two_pi * (freq * 0.5) * t)  # Bajo cálido

        # Arpegio superior cristalino
        arp_idx = int((local_t / step_dur) * 4) % 4
        arp_freq = chord[arp_idx] * 2.0
        arp_t = local_t % (step_dur / 4.0)
        arp_env = math.exp(-arp_t * 14.0)
        val += 0.09 * arp_env * math.sin(two_pi * arp_freq * t)

        # Pulso de percusión / kick de radio al inicio de cada compás
        if local_t < 0.25:
            kick_freq = 135.0 * math.exp(-local_t * 14.0) + 45.0
            kick_env = math.exp(-local_t * 12.0)
            val += 0.28 * kick_env * math.sin(two_pi * kick_freq * local_t)

        # Fade out en los últimos 0.4s
        if t > duration - 0.45:
            val *= max(0.0, (duration - t) / 0.45)

        sample_int = int(32767.0 * max(-0.98, min(0.98, val)))
        out[i] = sample_int

    return out.tobytes()


def generate_transition_sfx_pcm(sample_rate: int = 24000, variant: int = 1) -> bytes:
    """
    Genera efecto de sonido de transición entre bloques (1.45 segundos, PCM16 mono):
    Sweep frecuencial de cabina + doble campana armónica (chime).
    """
    duration = 1.45
    total_samples = int(sample_rate * duration)
    out = array.array("h", [0] * total_samples)
    two_pi = 2.0 * math.pi
    base_bell = 587.33 if (variant % 2 == 1) else 523.25
    high_bell = 880.0 if (variant % 2 == 1) else 783.99

    phase = 0.0
    for i in range(total_samples):
        t = i / float(sample_rate)
        val = 0.0
        # 1. Whoosh / Sweep FM (0.0s a 0.65s)
        if t < 0.65:
            sweep_freq = 180.0 + 1400.0 * math.sin(math.pi * (t / 0.65))
            phase += two_pi * sweep_freq / sample_rate
            sweep_env = math.sin(math.pi * (t / 0.65)) * 0.18
            val += sweep_env * math.sin(phase)

        # 2. Primer chime armónico (t >= 0.18s)
        if t >= 0.18:
            t1 = t - 0.18
            env1 = min(1.0, t1 / 0.015) * math.exp(-t1 * 4.2)
            val += 0.22 * env1 * (math.sin(two_pi * base_bell * t1) + 0.35 * math.sin(two_pi * base_bell * 2.0 * t1))

        # 3. Segundo chime armónico de resolución (t >= 0.38s)
        if t >= 0.38:
            t2 = t - 0.38
            env2 = min(1.0, t2 / 0.015) * math.exp(-t2 * 3.2)
            val += 0.24 * env2 * (math.sin(two_pi * high_bell * t2) + 0.30 * math.sin(two_pi * high_bell * 2.0 * t2))

        sample_int = int(32767.0 * max(-0.98, min(0.98, val)))
        out[i] = sample_int

    return out.tobytes()


def generate_stinger_sfx_pcm(sample_rate: int = 24000) -> bytes:
    """
    Genera un breve acento sonoro (0.75 segundos) cuando aparece un [SFX: ...] intermedio.
    """
    duration = 0.75
    total_samples = int(sample_rate * duration)
    out = array.array("h", [0] * total_samples)
    two_pi = 2.0 * math.pi
    for i in range(total_samples):
        t = i / float(sample_rate)
        env = min(1.0, t / 0.01) * math.exp(-t * 5.5)
        val = 0.18 * env * (math.sin(two_pi * 440.0 * t) + 0.6 * math.sin(two_pi * 659.25 * t))
        out[i] = int(32767.0 * max(-0.98, min(0.98, val)))
    return out.tobytes()


def generate_outro_jingle_pcm(sample_rate: int = 24000) -> bytes:
    """
    Genera la música de cierre y despedida con fade-out progresivo (4.2 segundos, PCM16 mono).
    """
    duration = 4.2
    total_samples = int(sample_rate * duration)
    out = array.array("h", [0] * total_samples)
    two_pi = 2.0 * math.pi
    chord = [261.63, 329.63, 392.00, 523.25, 659.25]

    for i in range(total_samples):
        t = i / float(sample_rate)
        attack = min(1.0, t / 0.35)
        decay = math.exp(-max(0.0, t - 0.5) * 0.85)
        fade = max(0.0, (duration - t) / 1.2) if t > (duration - 1.2) else 1.0
        env = attack * decay * fade

        val = 0.0
        for idx_f, f in enumerate(chord):
            detune = 1.0 + (idx_f - 2) * 0.0015
            val += 0.13 * env * math.sin(two_pi * f * detune * t)
        # Bajo profundo en Do
        val += 0.15 * env * math.sin(two_pi * 130.81 * t)

        out[i] = int(32767.0 * max(-0.98, min(0.98, val)))
    return out.tobytes()


def generate_silence_pcm(duration_sec: float = 0.32, sample_rate: int = 24000) -> bytes:
    """Genera pausa natural de respiración entre intervenciones de los locutores."""
    n = int(sample_rate * duration_sec)
    return b"\x00\x00" * n


def _split_text_into_tts_chunks(text: str, max_len: int = 185) -> List[str]:
    """Divide un párrafo largo en oraciones naturales <= max_len caracteres para TTS."""
    clean = text.strip()
    if not clean:
        return []
    sentences = re.split(r"(?<=[.!?।;:])\s+", clean)
    chunks: List[str] = []
    current = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(s) > max_len:
            # Subdividir por comas
            sub_parts = re.split(r"(?<=[,])\s+", s)
            for sp in sub_parts:
                if len(current) + len(sp) + 1 <= max_len:
                    current = (current + " " + sp).strip()
                else:
                    if current:
                        chunks.append(current)
                    if len(sp) <= max_len:
                        current = sp
                    else:
                        # Cortar por palabras
                        words = sp.split()
                        current = ""
                        for w in words:
                            if len(current) + len(w) + 1 <= max_len:
                                current = (current + " " + w).strip()
                            else:
                                if current:
                                    chunks.append(current)
                                current = w
        else:
            if len(current) + len(s) + 1 <= max_len:
                current = (current + " " + s).strip()
            else:
                if current:
                    chunks.append(current)
                current = s
    if current:
        chunks.append(current)
    return chunks


def _fetch_gtts_mp3_bytes(text: str, lang: str = "es") -> bytes:
    """Descarga audio MP3 hablado desde el endpoint público de Google TTS sin requerir librerías externas."""
    chunks = _split_text_into_tts_chunks(text, max_len=185)
    mp3_parts: List[bytes] = []
    for chunk in chunks:
        q = urllib.parse.quote(chunk)
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl={lang}&q={q}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
                if data and len(data) > 256:
                    mp3_parts.append(data)
        except Exception:
            pass
    return b"".join(mp3_parts)


def _decode_mp3_to_pcm24k(mp3_bytes: bytes, gender: str = "female") -> bytes:
    """
    Convierte bytes MP3 a PCM16 mono 24000Hz usando ffmpeg si está disponible,
    aplicando transformación de voz Masculina Barítona (Alex) o Femenina Natural (Elena).
    """
    if not mp3_bytes:
        return b""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return b""

    # Filtro de voz:
    # - Hombre (Alex): baja formantes y pitch a 0.80x y ajusta tempo a 1.24x + realce grave en 170Hz
    # - Mujer (Elena): timbre claro femenino 1.03x y tempo natural 0.99x
    if gender == "male":
        af_filter = "asetrate=24000*0.80,aresample=24000,atempo=1.24,equalizer=f=175:width_type=o:width=2:g=3"
    else:
        af_filter = "asetrate=24000*1.03,aresample=24000,atempo=0.99"

    try:
        proc = subprocess.run(
            [
                ffmpeg_bin, "-hide_banner", "-loglevel", "error",
                "-i", "pipe:0",
                "-af", af_filter,
                "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1",
                "pipe:1"
            ],
            input=mp3_bytes,
            capture_output=True,
            timeout=15
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except Exception:
        pass
    return b""


def synthesize_single_line_audio(text: str, gender: str = "male", lang: str = "es") -> Tuple[bytes, str]:
    """
    Sintetiza una sola intervención del guión en tiempo real para el reproductor HTML (`/api/tts-line`).
    Devuelve (audio_bytes, mime_type) con voz Masculina (Alex) o Femenina (Elena) garantizada.
    """
    clean = clean_speech_text(text)
    if not clean:
        clean = "Continuamos en cabina."

    sample_rate = 24000

    # 1. En Windows, usar SAPI5 nativo de alta velocidad + Pitch Shift Barítono para voz masculina
    if sys.platform == "win32":
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                txt_path = os.path.join(tmpdir, "line.txt")
                wav_path = os.path.join(tmpdir, "line.wav")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(clean)

                ps_script = f"""
                Add-Type -AssemblyName System.Speech
                $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
                $voices = $synth.GetInstalledVoices() | Where-Object {{ $_.Enabled }}
                $esVoices = $voices | Where-Object {{ $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq 'es' }}
                $pool = if ($esVoices) {{ $esVoices }} else {{ $voices }}
                $chosen = $null
                $hasNativeMale = $false
                if ('{gender}' -eq 'male') {{
                    $maleV = $pool | Where-Object {{ $_.VoiceInfo.Gender -eq 'Male' -or $_.VoiceInfo.Name -match 'Pablo|Raul|Jorge|David|Alvaro|Diego|Carlos|Hombre' }} | Select-Object -First 1
                    if ($maleV) {{ $chosen = $maleV.VoiceInfo.Name; $hasNativeMale = $true }}
                }} else {{
                    $femV = $pool | Where-Object {{ $_.VoiceInfo.Gender -eq 'Female' -or $_.VoiceInfo.Name -match 'Sabina|Helena|Laura|Monica|Paulina|Zira|Mujer' }} | Select-Object -First 1
                    if ($femV) {{ $chosen = $femV.VoiceInfo.Name }}
                }}
                if (-not $chosen -and $pool) {{ $chosen = ($pool | Select-Object -First 1).VoiceInfo.Name }}
                if ($chosen) {{ $synth.SelectVoice($chosen) }}
                $synth.Rate = if ('{gender}' -eq 'male') {{ 1 }} else {{ 0 }}
                $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo({sample_rate}, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
                $synth.SetOutputToWaveFile('{wav_path}', $fmt)
                $text = Get-Content -Path '{txt_path}' -Raw -Encoding UTF8
                $synth.Speak($text)
                $synth.Dispose()
                if ($hasNativeMale) {{ Write-Output "NATIVE_MALE" }} else {{ Write-Output "SHIFT_NEEDED" }}
                """
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    capture_output=True, text=True, timeout=15
                )
                if os.path.exists(wav_path) and os.path.getsize(wav_path) > 200:
                    with wave.open(wav_path, "rb") as wr:
                        pcm = wr.readframes(wr.getnframes())
                    if gender == "male" and "NATIVE_MALE" not in (res.stdout or ""):
                        pcm = fast_pitch_shift_pcm16(pcm, pitch_factor=0.78)
                    out_wav = os.path.join(tmpdir, "final.wav")
                    with wave.open(out_wav, "wb") as ww:
                        ww.setnchannels(1)
                        ww.setsampwidth(2)
                        ww.setframerate(sample_rate)
                        ww.writeframes(pcm)
                    with open(out_wav, "rb") as f:
                        return f.read(), "audio/wav"
        except Exception:
            pass

    # 2. Google TTS HTTP + FFmpeg / Python Pitch Shift (Funciona en Linux, macOS y Windows)
    mp3_raw = _fetch_gtts_mp3_bytes(clean, lang=lang)
    if mp3_raw:
        pcm = _decode_mp3_to_pcm24k(mp3_raw, gender=gender)
        if pcm:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tmp_wav = tf.name
            try:
                with wave.open(tmp_wav, "wb") as ww:
                    ww.setnchannels(1)
                    ww.setsampwidth(2)
                    ww.setframerate(sample_rate)
                    ww.writeframes(pcm)
                with open(tmp_wav, "rb") as f:
                    data = f.read()
                return data, "audio/wav"
            finally:
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass
        return mp3_raw, "audio/mpeg"

    # 3. Respaldo garantizado de tono armónico si no hay red ni SAPI5
    pcm_fallback = generate_stinger_sfx_pcm(sample_rate)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tmp_wav = tf.name
    try:
        with wave.open(tmp_wav, "wb") as ww:
            ww.setnchannels(1)
            ww.setsampwidth(2)
            ww.setframerate(sample_rate)
            ww.writeframes(pcm_fallback)
        with open(tmp_wav, "rb") as f:
            return f.read(), "audio/wav"
    finally:
        try:
            os.remove(tmp_wav)
        except Exception:
            pass


def parse_script_into_segments(
    raw_text: str,
    host_a_name: str = "Alex",
    host_b_name: str = "Elena"
) -> List[Dict[str, Any]]:
    """
    Convierte un guión completo en texto/markdown/docx en la lista estructurada de 6 segmentos
    `[{"title": ..., "time_range": ..., "body": ...}]` para re-exportar MP3 y HTML Player.
    """
    if not raw_text or not raw_text.strip():
        return []

    # Buscar divisiones por encabezados ### ▶ Segmento o ### Bloque
    pattern = re.compile(
        r"(?:^|\n)#{2,4}\s*(?:▶\s*)?([^\n\[]+?)(?:\s*[\[\(](\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})[\]\)])?\s*\n",
        re.IGNORECASE
    )
    matches = list(pattern.finditer(raw_text))
    segments: List[Dict[str, Any]] = []

    if matches:
        for i, m in enumerate(matches):
            seg_title = m.group(1).strip()
            if "guión completo" in seg_title.lower() or "escaleta" in seg_title.lower():
                continue
            t_range = (m.group(2) or "").strip()
            if not t_range:
                idx_num = len(segments) + 1
                default_ranges = ["00:00 - 05:00", "05:00 - 15:00", "15:00 - 25:00", "25:00 - 35:00", "35:00 - 42:00", "42:00 - 45:00"]
                t_range = default_ranges[min(idx_num - 1, 5)]
            start_pos = m.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
            body = raw_text[start_pos:end_pos].strip()
            body = re.sub(r"^---\s*$", "", body, flags=re.MULTILINE).strip()
            if body:
                segments.append({
                    "title": seg_title,
                    "time_range": t_range,
                    "body": body
                })

    if not segments:
        # Dividir equitativamente el texto en 6 bloques si no tenía encabezados ###
        paras = [p.strip() for p in re.split(r"\n\s*\n", raw_text) if p.strip() and not p.strip().startswith("#") and not p.strip().startswith("|")]
        chunk_size = max(1, math.ceil(len(paras) / 6))
        default_specs = [
            ("Segmento 01: Apertura, Gancho y Presentación del Tema", "00:00 - 05:00"),
            ("Segmento 02: Fundamentos, Orígenes y Estado de la Cuestión", "05:00 - 15:00"),
            ("Segmento 03: El Núcleo del Debate, Casos Reales y Análisis Crítico", "15:00 - 25:00"),
            ("Segmento 04: Controversias, Dilemas Éticos y Costos Ocultos", "25:00 - 35:00"),
            ("Segmento 05: Proyecciones de Futuro, Escenarios y Soluciones", "35:00 - 42:00"),
            ("Segmento 06: Conclusiones Finales, Mensaje Central y Despedida", "42:00 - 45:00"),
        ]
        for idx, (stitle, trange) in enumerate(default_specs):
            part = paras[idx * chunk_size:(idx + 1) * chunk_size]
            if part:
                segments.append({
                    "title": stitle,
                    "time_range": trange,
                    "body": "\n\n".join(part)
                })

    return segments


def _extract_dialogue_turns_from_segments(
    segments: List[Dict[str, Any]],
    host_a_name: str = "Alex",
    host_b_name: str = "Elena"
) -> List[Dict[str, Any]]:
    """
    Extrae todas las líneas habladas y efectos sonoros de los segmentos del podcast.
    Alterna inteligentemente entre Locutor Masculino (Host A) y Locutora Femenina (Host B)
    incluso si algún párrafo no tenía etiqueta explícita.
    """
    turns: List[Dict[str, Any]] = []
    host_a_clean = host_a_name.split("(")[0].strip().lower()
    host_b_clean = host_b_name.split("(")[0].strip().lower()
    last_gender = "female"
    global_line_idx = 0

    for seg_idx, seg in enumerate(segments, 1):
        raw_body = seg.get("body", "")
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw_body) if p.strip()]

        for p in paragraphs:
            low_p = p.lower()
            # Detectar línea que es únicamente una acotación de efecto sonoro [SFX: ...]
            if (p.startswith("[") and p.endswith("]") and any(k in low_p for k in ("sfx", "música", "musica", "cortinilla", "efecto", "puente", "acorde", "fade"))) or low_p.startswith("*efecto de audio"):
                sfx_desc = re.sub(r"^[\[\*]|[\]\*]$", "", p).strip()
                turns.append({
                    "type": "sfx",
                    "segmentIdx": seg_idx,
                    "description": sfx_desc
                })
                continue

            # Extraer etiqueta de tiempo si existe
            time_match = re.search(r"\[(\d{1,2}:\d{2})\]", p)
            timestamp_val = time_match.group(1) if time_match else f"0{seg_idx}:00"

            # Detectar locutor al inicio del párrafo
            p_no_time = re.sub(r"^\s*\[\d{1,2}:\d{2}\]\s*", "", p).strip()
            m_spk = (
                re.match(r"^\*\*([^*:]+?)\*\*:\s*([\s\S]*)$", p_no_time)
                or re.match(r"^\*\*([^*:]+?):\*\*\s*([\s\S]*)$", p_no_time)
                or re.match(r"^\[LOCUTOR ([^\]]+)\]:?\s*([\s\S]*)$", p_no_time, flags=re.IGNORECASE)
                or re.match(r"^([A-ZÁÉÍÓÚÑa-záéíóúñ.\s]{2,28})(?:\([^)]*\))?:\s+([\s\S]*)$", p_no_time)
            )

            if m_spk:
                spk_raw = m_spk.group(1).strip()
                speech_raw = m_spk.group(2).strip()
                spk_low = spk_raw.lower()
                if any(k in spk_low for k in (host_b_clean, "elena", "dra", "especialista", "invitad", "locutora", "mujer", "sofia", "laura")):
                    gender = "female"
                    speaker_display = host_b_name.split("(")[0].strip()
                elif any(k in spk_low for k in (host_a_clean, "alex", "lucas", "conductor", "locutor a", "locutor 1", "carlos", "david")):
                    gender = "male"
                    speaker_display = host_a_name.split("(")[0].strip()
                else:
                    gender = "male" if last_gender == "female" else "female"
                    speaker_display = host_a_name.split("(")[0].strip() if gender == "male" else host_b_name.split("(")[0].strip()
            else:
                speech_raw = p_no_time
                gender = "male" if last_gender == "female" else "female"
                speaker_display = host_a_name.split("(")[0].strip() if gender == "male" else host_b_name.split("(")[0].strip()

            clean_spoken = clean_speech_text(speech_raw)
            if not clean_spoken or len(clean_spoken) < 3:
                continue

            last_gender = gender
            turns.append({
                "type": "speech",
                "id": global_line_idx,
                "segmentIdx": seg_idx,
                "speaker": speaker_display,
                "gender": gender,
                "timestamp": timestamp_val,
                "rawText": speech_raw,
                "cleanText": clean_spoken
            })
            global_line_idx += 1

    return turns


def build_podcast_html(
    title: str,
    show_name: str,
    host_a_name: str,
    host_b_name: str,
    duration: int,
    segments: List[Dict[str, Any]],
    project_name: str = "",
    mp3_filename: str = ""
) -> str:
    host_a_short = host_a_name.split("(")[0].strip() or "Alex"
    host_b_short = host_b_name.split("(")[0].strip() or "Elena"

    all_items = _extract_dialogue_turns_from_segments(segments, host_a_short, host_b_short)
    script_lines = [item for item in all_items if item["type"] == "speech"]

    chapters_html_parts = []
    transcription_html_parts = []

    for idx, s in enumerate(segments, 1):
        time_label = s.get("time_range", f"0{idx}:00 - 0{idx+1}:00")
        seg_title = s.get("title", f"Segmento 0{idx}")
        chapters_html_parts.append(
            f'<div class="chapter-item" id="chip-btn-{idx}" onclick="jumpToChapter({idx})">'
            f'<div class="chapter-time">{time_label.split("-")[0].strip()}</div>'
            f'<div class="chapter-info">'
            f'<div class="chapter-title">{seg_title}</div>'
            f'<div class="chapter-meta">Intervalo: {time_label}</div>'
            f'</div></div>'
        )

        seg_items = [it for it in all_items if it["segmentIdx"] == idx]
        body_formatted_parts = []
        for it in seg_items:
            if it["type"] == "sfx":
                body_formatted_parts.append(
                    f'<div class="cue-sound">🎶 <span>Efecto Sonoro en Cabina: {it["description"]}</span></div>'
                )
            else:
                lid = it["id"]
                gender = it["gender"]
                badge_class = "speaker-a" if gender == "male" else "speaker-b"
                badge_title = f"🎤 {it['speaker']} (Voz Masculina)" if gender == "male" else f"🎙️ {it['speaker']} (Voz Femenina)"
                body_formatted_parts.append(
                    f'<div class="dialogue-row" id="line-row-{lid}" onclick="playFromLine({lid})" data-line-id="{lid}" data-gender="{gender}">'
                    f'<div class="dialogue-header">'
                    f'<span class="speaker-badge {badge_class}">{badge_title}</span>'
                    f'<span class="line-time">{it["timestamp"]}</span>'
                    f'<span class="on-air-tag" id="on-air-{lid}">🔴 AL AIRE</span>'
                    f'</div>'
                    f'<div class="speech-text">{it["cleanText"]}</div>'
                    f'</div>'
                )

        transcription_html_parts.append(
            f'<section class="segment-section" id="chapter-{idx}">'
            f'<div class="segment-header">'
            f'<h3>{seg_title}</h3>'
            f'<span class="badge-time">{time_label}</span>'
            f'</div>'
            f'<div class="segment-body">{"".join(body_formatted_parts)}</div>'
            f'</section>'
        )

    chapters_html = "\n".join(chapters_html_parts)
    transcription_html = "\n".join(transcription_html_parts)
    data_json = json.dumps({
        "title": title,
        "showName": show_name,
        "hostA": host_a_short,
        "hostB": host_b_short,
        "durationMinutes": duration,
        "projectName": project_name,
        "mp3Filename": mp3_filename,
        "lines": script_lines
    }, ensure_ascii=False)

    template = """<!DOCTYPE html>
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
      --host-a-bg: rgba(59, 130, 246, 0.14);
      --host-b: #34D399;
      --host-b-bg: rgba(16, 185, 129, 0.14);
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
      padding: 28px 24px 22px;
      border-bottom: 1px solid var(--card-border);
      position: sticky;
      top: 0;
      z-index: 40;
      backdrop-filter: blur(12px);
    }
    .header-container {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      gap: 24px;
      align-items: center;
    }
    .cover-art {
      width: 112px;
      height: 112px;
      background: linear-gradient(135deg, #4338CA 0%, #1E1B4B 100%);
      border-radius: 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-size: 42px;
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
      margin-bottom: 6px;
    }
    .podcast-title {
      font-size: 23px;
      font-weight: 800;
      color: #FFFFFF;
      line-height: 1.25;
      margin-bottom: 6px;
    }
    .podcast-meta {
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 14px;
    }
    .podcast-meta strong { color: #E2E8F0; }

    .playback-toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .btn-play {
      background: linear-gradient(135deg, #4F46E5 0%, #4338CA 100%);
      color: white;
      border: none;
      padding: 11px 22px;
      border-radius: 12px;
      font-size: 13.5px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 9px;
      box-shadow: 0 6px 20px var(--accent-glow);
      transition: all 0.2s;
    }
    .btn-play:hover { transform: translateY(-1px); filter: brightness(1.1); }
    .btn-play.playing { background: #059669; }

    .btn-export-mp3 {
      background: linear-gradient(135deg, #7C3AED 0%, #9333EA 100%);
      color: white;
      border: 1px solid rgba(167, 139, 250, 0.4);
      padding: 10px 18px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 4px 15px rgba(124, 58, 237, 0.35);
      transition: all 0.2s;
    }
    .btn-export-mp3:hover { filter: brightness(1.12); transform: translateY(-1px); }
    .btn-export-mp3:disabled { opacity: 0.65; cursor: wait; }

    .speed-btn {
      background: #1E293B;
      color: #E2E8F0;
      border: 1px solid #334155;
      padding: 9px 14px;
      border-radius: 10px;
      font-size: 12.5px;
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
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid #334155;
      border-radius: 10px;
      font-size: 12px;
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
      margin: 14px auto 0;
      padding: 0 4px;
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
      margin-top: 5px;
      font-size: 11.5px;
      font-family: monospace;
      color: var(--muted);
    }

    .main-layout {
      max-width: 1200px;
      margin: 24px auto 0;
      padding: 0 24px;
      display: grid;
      grid-template-columns: 310px 1fr;
      gap: 24px;
    }
    @media (max-width: 900px) {
      .main-layout { grid-template-columns: 1fr; }
      .player-header { position: static; }
    }

    .chapters-sidebar {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 18px;
      height: fit-content;
      position: sticky;
      top: 210px;
    }
    .sidebar-heading {
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--muted);
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--card-border);
    }
    .chapter-item {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 9px 11px;
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
      font-size: 11.5px;
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
      gap: 22px;
    }
    .segment-section {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 22px;
    }
    .segment-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 12px;
      margin-bottom: 16px;
    }
    .segment-header h3 {
      font-size: 15.5px;
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
      margin: 12px 0;
      border-radius: 0 8px 8px 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .dialogue-row {
      margin-bottom: 12px;
      padding: 14px 18px;
      border-radius: 12px;
      border: 1px solid #1E293B;
      background: #0B0F19;
      cursor: pointer;
      transition: all 0.2s ease;
      position: relative;
    }
    .dialogue-row:hover {
      border-color: #334155;
      background: #0E1424;
    }
    .dialogue-row.playing {
      border-color: #6366F1;
      background: rgba(99, 102, 241, 0.14);
      box-shadow: 0 0 22px rgba(99, 102, 241, 0.28);
    }
    .dialogue-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;
    }
    .speaker-badge {
      display: inline-block;
      font-size: 11.5px;
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
          Voces en Cabina: <strong>__HOST_A__</strong> (Voz Masculina) & <strong>__HOST_B__</strong> (Voz Femenina) • 
          Duración: <strong>__DURATION__:00 min</strong> • Formato: <strong>Doble Voz Real + Efectos Sonoros (SFX)</strong>
        </p>
        <div class="playback-toolbar">
          <button class="btn-play" id="playBtn" onclick="togglePlay()">
            <span id="playIcon">▶</span> <span id="playLabel">Escuchar Episodio en Vivo</span>
          </button>
          <button class="btn-export-mp3" id="exportMp3Btn" onclick="exportPodcastMp3Again()">
            <span>🔄</span> <span id="exportMp3Label">Exportar Podcast en MP3</span>
          </button>
          <button class="speed-btn" onclick="cycleSpeed()">Velocidad: <span id="speedLabel">1.0x</span></button>
          <button class="speed-btn" id="engineBtn" onclick="toggleVoiceEngine()" title="Alternar entre Voz de Estudio (Servidor) y Voz del Navegador">
            🔊 Motor: <span id="engineLabel">Auto Dual</span>
          </button>
          <div class="status-badge">
            <span class="pulse-dot" id="liveDot"></span>
            <span id="speakerStatus">En Cabina: Listo para transmitir</span>
          </div>
          <button class="speed-btn" onclick="window.print()">🖨️ Imprimir</button>
        </div>
      </div>
    </div>
    <div class="progress-bar-wrap">
      <div class="progress-track" id="progressTrack" onclick="seekTrack(event)">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <div class="time-labels">
        <span id="timerCurrent">00:00</span>
        <span id="lineCounterLabel">Línea 0 / 0</span>
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
            osc.frequency.setValueAtTime(freq, t0 + step * 0.28);
            gain.gain.setValueAtTime(0, t0 + step * 0.28);
            gain.gain.linearRampToValueAtTime(0.08, t0 + step * 0.28 + 0.03);
            gain.gain.exponentialRampToValueAtTime(0.0001, t0 + step * 0.28 + 0.65);
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start(t0 + step * 0.28);
            osc.stop(t0 + step * 0.28 + 0.7);
          });
        });
        const kickOsc = this.ctx.createOscillator();
        const kickGain = this.ctx.createGain();
        kickOsc.frequency.setValueAtTime(140, t0);
        kickOsc.frequency.exponentialRampToValueAtTime(45, t0 + 0.25);
        kickGain.gain.setValueAtTime(0.16, t0);
        kickGain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.28);
        kickOsc.connect(kickGain);
        kickGain.connect(this.ctx.destination);
        kickOsc.start(t0);
        kickOsc.stop(t0 + 0.3);

        if (onDone) setTimeout(onDone, 1200);
      }

      playTransitionSfx(onDone) {
        this.init();
        const t0 = this.ctx.currentTime;
        const bufferSize = Math.floor(this.ctx.sampleRate * 0.55);
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
        filter.frequency.exponentialRampToValueAtTime(2400, t0 + 0.26);
        filter.frequency.exponentialRampToValueAtTime(400, t0 + 0.52);
        filter.Q.value = 4.0;
        const noiseGain = this.ctx.createGain();
        noiseGain.gain.setValueAtTime(0, t0);
        noiseGain.gain.linearRampToValueAtTime(0.08, t0 + 0.22);
        noiseGain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.55);
        whiteNoise.connect(filter);
        filter.connect(noiseGain);
        noiseGain.connect(this.ctx.destination);
        whiteNoise.start(t0);

        const bellOsc = this.ctx.createOscillator();
        const bellGain = this.ctx.createGain();
        bellOsc.type = 'sine';
        bellOsc.frequency.setValueAtTime(880, t0 + 0.18);
        bellGain.gain.setValueAtTime(0.07, t0 + 0.18);
        bellGain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.72);
        bellOsc.connect(bellGain);
        bellGain.connect(this.ctx.destination);
        bellOsc.start(t0 + 0.18);
        bellOsc.stop(t0 + 0.75);

        if (onDone) setTimeout(onDone, 650);
      }

      playOutroJingle(onDone) {
        this.init();
        const t0 = this.ctx.currentTime;
        [261.63, 329.63, 392.00, 523.25].forEach(freq => {
          const osc = this.ctx.createOscillator();
          const gain = this.ctx.createGain();
          osc.type = 'sine';
          osc.frequency.setValueAtTime(freq, t0);
          gain.gain.setValueAtTime(0.055, t0);
          gain.gain.linearRampToValueAtTime(0.085, t0 + 0.6);
          gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 3.2);
          osc.connect(gain);
          gain.connect(this.ctx.destination);
          osc.start(t0);
          osc.stop(t0 + 3.3);
        });
        if (onDone) setTimeout(onDone, 3300);
      }

      startStudioAmbiance() {
        this.init();
        if (this.isAmbianceRunning) return;
        this.isAmbianceRunning = true;
        this.ambientGain = this.ctx.createGain();
        this.ambientGain.gain.setValueAtTime(0.008, this.ctx.currentTime);
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
            this.ambientGain.gain.exponentialRampToValueAtTime(0.00001, this.ctx.currentTime + 0.3);
            setTimeout(() => {
              try {
                if (this.ambientOsc1) this.ambientOsc1.stop();
                if (this.ambientOsc2) this.ambientOsc2.stop();
              } catch(e) {}
              this.isAmbianceRunning = false;
            }, 350);
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
    let voiceMode = 'auto'; // 'auto' | 'server' | 'browser'
    let activeHtmlAudio = null;
    let speechWatchdog = null;
    window._activeUtterance = null;
    const totalDurationSeconds = (podcastData.durationMinutes || 45) * 60;

    function getApiBaseUrl() {
      if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
        return window.location.origin;
      }
      return 'http://127.0.0.1:8765';
    }

    function initVoices() {
      if (!('speechSynthesis' in window)) return;
      const voices = window.speechSynthesis.getVoices() || [];
      const spanish = voices.filter(v => (v.lang || '').toLowerCase().startsWith('es'));
      const pool = spanish.length > 0 ? spanish : voices;

      maleVoice = pool.find(v => {
        const n = v.name.toLowerCase();
        return n.includes('male') || n.includes('hombre') || n.includes('pablo') ||
               n.includes('raul') || n.includes('jorge') || n.includes('david') ||
               n.includes('enrique') || n.includes('carlos') || n.includes('diego') ||
               n.includes('alvaro');
      }) || pool[0] || null;

      femaleVoice = pool.find(v => {
        const n = v.name.toLowerCase();
        return n.includes('female') || n.includes('mujer') || n.includes('sabina') ||
               n.includes('helena') || n.includes('monica') || n.includes('laura') ||
               n.includes('sofia') || n.includes('lucia') || n.includes('carmen') ||
               n.includes('paulina') || n.includes('zira') || n.includes('google español');
      }) || (pool.length > 1 ? pool[1] : pool[0]) || null;
    }

    if ('speechSynthesis' in window) {
      initVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = initVoices;
      }
    }

    document.getElementById('lineCounterLabel').textContent =
      'Línea 0 / ' + (podcastData.lines ? podcastData.lines.length : 0);

    function formatTime(s) {
      const m = Math.floor(s / 60);
      const sec = Math.floor(s % 60);
      return (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
    }

    function updateProgressUI() {
      document.getElementById('timerCurrent').textContent = formatTime(elapsedSeconds);
      const totalLines = podcastData.lines ? podcastData.lines.length : 1;
      document.getElementById('lineCounterLabel').textContent =
        'Línea ' + Math.min(currentLineIndex + 1, totalLines) + ' / ' + totalLines;
      const pct = Math.min(100, (elapsedSeconds / totalDurationSeconds) * 100);
      document.getElementById('progressFill').style.width = pct + '%';

      if (podcastData.lines && podcastData.lines[currentLineIndex]) {
        const segIdx = podcastData.lines[currentLineIndex].segmentIdx;
        document.querySelectorAll('.chapter-item').forEach(c => c.classList.remove('active'));
        const activeChip = document.getElementById('chip-btn-' + segIdx);
        if (activeChip) activeChip.classList.add('active');
      }
    }

    function toggleVoiceEngine() {
      if (voiceMode === 'auto') {
        voiceMode = 'server';
        document.getElementById('engineLabel').textContent = 'Estudio HD';
      } else if (voiceMode === 'server') {
        voiceMode = 'browser';
        document.getElementById('engineLabel').textContent = 'Navegador';
      } else {
        voiceMode = 'auto';
        document.getElementById('engineLabel').textContent = 'Auto Dual';
      }
      if (isPlaying) {
        stopCurrentSpeechOnly();
        setTimeout(() => speakLine(currentLineIndex), 60);
      }
    }

    function stopCurrentSpeechOnly() {
      if (speechWatchdog) {
        clearTimeout(speechWatchdog);
        speechWatchdog = null;
      }
      if (activeHtmlAudio) {
        try {
          activeHtmlAudio.pause();
          activeHtmlAudio.src = '';
        } catch(e) {}
        activeHtmlAudio = null;
      }
      if ('speechSynthesis' in window) {
        try {
          window.speechSynthesis.cancel();
        } catch(e) {}
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
      studio.init();
      initVoices();

      // Desbloqueo síncrono inmediato en el gesto del click para evitar bloqueo en Chromium/Electron
      if ('speechSynthesis' in window) {
        try {
          window.speechSynthesis.resume();
        } catch(e) {}
      }

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
        document.getElementById('speakerStatus').textContent = '🎶 Cortinilla + Inicio de Voz';
        // Tocar cortinilla en paralelo e iniciar locución inmediatamente para no perder activación de audio
        studio.playIntroJingle();
        speakLine(currentLineIndex);
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

      stopCurrentSpeechOnly();
      studio.stopStudioAmbiance();
      if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
      }
    }

    function advanceToNextLine() {
      if (!isPlaying) return;
      currentLineIndex++;
      if (podcastData.lines && currentLineIndex < podcastData.lines.length) {
        elapsedSeconds = Math.round((currentLineIndex / podcastData.lines.length) * totalDurationSeconds);
        updateProgressUI();
        speakLine(currentLineIndex);
      } else {
        pausePlayback();
        studio.playOutroJingle();
      }
    }

    function speakLine(index) {
      if (!isPlaying || !podcastData.lines || index >= podcastData.lines.length) {
        if (podcastData.lines && index >= podcastData.lines.length) {
          pausePlayback();
          studio.playOutroJingle();
        }
        return;
      }

      currentLineIndex = index;
      const line = podcastData.lines[index];
      updateProgressUI();

      document.querySelectorAll('.dialogue-row').forEach(r => r.classList.remove('playing'));
      const rowElem = document.getElementById('line-row-' + line.id);
      if (rowElem) {
        rowElem.classList.add('playing');
        rowElem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }

      const hostName = line.gender === 'male' ? podcastData.hostA : podcastData.hostB;
      document.getElementById('speakerStatus').textContent =
        (line.gender === 'male' ? '🎤 Voz Masculina: ' : '🎙️ Voz Femenina: ') + hostName;

      const prevLine = index > 0 ? podcastData.lines[index - 1] : null;
      if (prevLine && prevLine.segmentIdx !== line.segmentIdx) {
        studio.playTransitionSfx(() => {
          if (isPlaying) _dispatchVoice(line);
        });
        return;
      }

      _dispatchVoice(line);
    }

    function _playViaServerTts(line) {
      if (!isPlaying) return;
      if (activeHtmlAudio) {
        try { activeHtmlAudio.pause(); } catch(e) {}
      }
      const base = getApiBaseUrl();
      const url = base + '/api/tts-line?gender=' + encodeURIComponent(line.gender) +
                  '&text=' + encodeURIComponent(line.cleanText);
      const audio = new Audio(url);
      activeHtmlAudio = audio;
      audio.playbackRate = currentSpeed;
      audio.onended = () => {
        if (!isPlaying) return;
        advanceToNextLine();
      };
      audio.onerror = () => {
        // Si el servidor local no está accesible (modo archivo suelto sin backend), usar síntesis del navegador
        if (voiceMode === 'server') {
          _playViaBrowserSpeech(line, false);
        } else {
          setTimeout(() => advanceToNextLine(), 1500);
        }
      };
      audio.play().catch(() => {
        _playViaBrowserSpeech(line, false);
      });
    }

    function _playViaBrowserSpeech(line, allowServerFallback) {
      if (!('speechSynthesis' in window)) {
        if (allowServerFallback) _playViaServerTts(line);
        return;
      }

      initVoices();
      const voices = window.speechSynthesis.getVoices() || [];
      if (voices.length === 0 && allowServerFallback) {
        _playViaServerTts(line);
        return;
      }

      try {
        window.speechSynthesis.resume();
      } catch(e) {}

      const utt = new SpeechSynthesisUtterance(line.cleanText);
      window._activeUtterance = utt; // Evitar que el Garbage Collector de Chromium corte la voz
      utt.lang = 'es-ES';
      utt.volume = 1.0;

      if (line.gender === 'male') {
        if (maleVoice) utt.voice = maleVoice;
        // Si Windows solo tiene una voz femenina (ej. Sabina), bajar pitch a 0.65 para timbre masculino claro
        const sameVoice = (maleVoice && femaleVoice && maleVoice.name === femaleVoice.name);
        utt.pitch = sameVoice ? 0.65 : 0.80;
        utt.rate = currentSpeed * (sameVoice ? 0.96 : 1.0);
      } else {
        if (femaleVoice) utt.voice = femaleVoice;
        utt.pitch = 1.18;
        utt.rate = currentSpeed * 1.02;
      }

      let started = false;
      if (speechWatchdog) clearTimeout(speechWatchdog);
      if (allowServerFallback) {
        speechWatchdog = setTimeout(() => {
          if (!started && isPlaying) {
            try { window.speechSynthesis.cancel(); } catch(e) {}
            _playViaServerTts(line);
          }
        }, 900);
      }

      utt.onstart = () => {
        started = true;
        if (speechWatchdog) {
          clearTimeout(speechWatchdog);
          speechWatchdog = null;
        }
      };

      utt.onend = () => {
        if (speechWatchdog) {
          clearTimeout(speechWatchdog);
          speechWatchdog = null;
        }
        if (!isPlaying) return;
        advanceToNextLine();
      };

      utt.onerror = (e) => {
        if (speechWatchdog) {
          clearTimeout(speechWatchdog);
          speechWatchdog = null;
        }
        if (!isPlaying) return;
        if (e && (e.error === 'canceled' || e.error === 'interrupted')) return;
        if (allowServerFallback) {
          _playViaServerTts(line);
        } else {
          setTimeout(() => advanceToNextLine(), 400);
        }
      };

      window.speechSynthesis.speak(utt);
    }

    function _dispatchVoice(line) {
      if (voiceMode === 'server') {
        _playViaServerTts(line);
        return;
      }
      if (voiceMode === 'browser') {
        _playViaBrowserSpeech(line, false);
        return;
      }
      // En modo 'auto': preferir el motor de Estudio Dual (/api/tts-line) si estamos conectados al backend
      // porque garantiza Voz de Hombre Barítono + Voz de Mujer en cualquier Windows/Electron
      const isHttp = window.location.protocol === 'http:' || window.location.protocol === 'https:' || window.location.protocol === 'about:' || window.location.protocol === 'srcdoc:';
      if (isHttp) {
        _playViaServerTts(line);
      } else {
        _playViaBrowserSpeech(line, true);
      }
    }

    function playFromLine(id) {
      stopCurrentSpeechOnly();
      currentLineIndex = id;
      if (podcastData.lines && podcastData.lines.length > 0) {
        elapsedSeconds = Math.round((id / podcastData.lines.length) * totalDurationSeconds);
        updateProgressUI();
      }
      if (!isPlaying) {
        startPlayback();
      } else {
        setTimeout(() => speakLine(currentLineIndex), 60);
      }
    }

    function jumpToChapter(idx) {
      const elem = document.getElementById('chapter-' + idx);
      if (elem) elem.scrollIntoView({ behavior: 'smooth', block: 'start' });

      if (podcastData.lines) {
        const found = podcastData.lines.findIndex(l => l.segmentIdx === idx);
        if (found !== -1) {
          stopCurrentSpeechOnly();
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
      if (activeHtmlAudio) {
        activeHtmlAudio.playbackRate = currentSpeed;
      } else if (isPlaying) {
        stopCurrentSpeechOnly();
        setTimeout(() => speakLine(currentLineIndex), 60);
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

    async function exportPodcastMp3Again() {
      const btn = document.getElementById('exportMp3Btn');
      const lbl = document.getElementById('exportMp3Label');
      const origText = lbl.textContent;
      btn.disabled = true;
      lbl.textContent = 'Sintetizando MP3 Doble Voz + SFX...';
      try {
        const base = getApiBaseUrl();
        const proj = podcastData.projectName || 'Mi Primer Proyecto';
        const res = await fetch(base + '/api/projects/' + encodeURIComponent(proj) + '/export-podcast-mp3', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        if (res.ok) {
          const data = await res.json();
          lbl.textContent = '✅ MP3 Exportado (' + (data.file_name || 'Podcast.mp3') + ')';
          if (data.download_url) {
            const a = document.createElement('a');
            a.href = base + data.download_url;
            a.download = data.file_name || 'Podcast_45min.mp3';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
          }
        } else {
          lbl.textContent = '⚠️ Error al exportar';
        }
      } catch (err) {
        lbl.textContent = '⚠️ Abre desde Agente Studio';
      } finally {
        setTimeout(() => {
          btn.disabled = false;
          lbl.textContent = origText;
        }, 4000);
      }
    }
  </script>
</body>
</html>"""

    html_content = (
        template
        .replace("__TITLE__", title)
        .replace("__SHOW_NAME__", show_name)
        .replace("__HOST_A__", host_a_short)
        .replace("__HOST_B__", host_b_short)
        .replace("__DURATION__", str(duration))
        .replace("__CHAPTERS_HTML__", chapters_html)
        .replace("__TRANSCRIPTION_HTML__", transcription_html)
        .replace("__PODCAST_DATA_JSON__", data_json)
    )

    return html_content


def synthesize_podcast_audio(
    project_path: str,
    filename: str,
    text_content: str = "",
    lang: str = "es",
    segments: Optional[List[Dict[str, Any]]] = None,
    host_a: str = "Alex",
    host_b: str = "Elena"
) -> Optional[str]:
    """
    Genera el archivo de audio Master completo (.mp3 y .wav) del Podcast:
    1. Procesa TODOS los 6 bloques del podcast (sin truncar a 2 bloques ni a 5 minutos).
    2. Separa cada turno en Voz Masculina Barítona (Host A / Alex) y Voz Femenina (Host B / Elena).
    3. Limpia por completo las etiquetas con clean_speech_text (jamás lee corchetes, 'SFX', 'LOCUTOR' ni asteriscos).
    4. Inserta efectos de sonido reales (SFX) de cabina:
       - Cortinilla musical polifónica de introducción (Intro Jingle)
       - Sweeps y Chimes armónicos de transición entre bloques y en cada [SFX]
       - Pausas de respiración natural entre locutores
       - Cortinilla musical de cierre con fade-out (Outro Jingle)
    """
    os.makedirs(project_path, exist_ok=True)
    base_name = os.path.splitext(filename)[0]
    target_wav = os.path.join(project_path, f"{base_name}.wav")
    target_mp3 = os.path.join(project_path, f"{base_name}.mp3")

    if not segments:
        segments = parse_script_into_segments(text_content, host_a, host_b)

    all_items = _extract_dialogue_turns_from_segments(segments, host_a, host_b)
    speech_turns = [it for it in all_items if it["type"] == "speech"]

    sample_rate = 24000
    intro_pcm = generate_intro_jingle_pcm(sample_rate)
    outro_pcm = generate_outro_jingle_pcm(sample_rate)
    stinger_pcm = generate_stinger_sfx_pcm(sample_rate)
    pause_pcm = generate_silence_pcm(0.30, sample_rate)

    synthesized_turn_pcm: Dict[int, bytes] = {}

    # 1. En Windows: Síntesis por lotes en una sola sesión de PowerShell SAPI5 + Pitch Shift Masculino
    if sys.platform == "win32" and speech_turns:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                manifest = []
                for t in speech_turns:
                    manifest.append({
                        "id": t["id"],
                        "gender": t["gender"],
                        "text": t["cleanText"]
                    })
                manifest_path = os.path.join(tmpdir, "turns.json")
                with open(manifest_path, "w", encoding="utf-8") as mf:
                    json.dump(manifest, mf, ensure_ascii=False)

                ps_batch = f"""
                Add-Type -AssemblyName System.Speech
                $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
                $voices = $synth.GetInstalledVoices() | Where-Object {{ $_.Enabled }}
                $esVoices = $voices | Where-Object {{ $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq 'es' }}
                $pool = if ($esVoices) {{ $esVoices }} else {{ $voices }}

                $maleVoice = ($pool | Where-Object {{ $_.VoiceInfo.Gender -eq 'Male' -or $_.VoiceInfo.Name -match 'Pablo|Raul|Jorge|David|Alvaro|Diego|Carlos|Hombre' }} | Select-Object -First 1)
                $femVoice = ($pool | Where-Object {{ $_.VoiceInfo.Gender -eq 'Female' -or $_.VoiceInfo.Name -match 'Sabina|Helena|Laura|Monica|Paulina|Zira|Mujer' }} | Select-Object -First 1)

                $defaultVoice = if ($pool) {{ ($pool | Select-Object -First 1).VoiceInfo.Name }} else {{ $null }}
                $maleName = if ($maleVoice) {{ $maleVoice.VoiceInfo.Name }} else {{ $defaultVoice }}
                $femName = if ($femVoice) {{ $femVoice.VoiceInfo.Name }} else {{ $defaultVoice }}

                if ($maleVoice -and ($maleName -ne $femName)) {{
                    Write-Output "HAS_DISTINCT_MALE"
                }} else {{
                    Write-Output "SINGLE_VOICE_SHIFT"
                }}

                $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo({sample_rate}, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
                $items = Get-Content -Path '{manifest_path}' -Raw -Encoding UTF8 | ConvertFrom-Json
                foreach ($item in $items) {{
                    $outWav = Join-Path '{tmpdir}' ("turn_" + $item.id + ".wav")
                    if ($item.gender -eq 'male' -and $maleName) {{
                        $synth.SelectVoice($maleName)
                        $synth.Rate = 1
                    }} elseif ($femName) {{
                        $synth.SelectVoice($femName)
                        $synth.Rate = 0
                    }}
                    $synth.SetOutputToWaveFile($outWav, $fmt)
                    $synth.Speak($item.text)
                }}
                $synth.Dispose()
                """
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_batch],
                    capture_output=True, text=True, timeout=180
                )
                need_male_pitch_shift = "HAS_DISTINCT_MALE" not in (res.stdout or "")

                for t in speech_turns:
                    tid = t["id"]
                    wpath = os.path.join(tmpdir, f"turn_{tid}.wav")
                    if os.path.exists(wpath) and os.path.getsize(wpath) > 100:
                        with wave.open(wpath, "rb") as wr:
                            pcm_data = wr.readframes(wr.getnframes())
                        if t["gender"] == "male" and need_male_pitch_shift:
                            pcm_data = fast_pitch_shift_pcm16(pcm_data, pitch_factor=0.78)
                        synthesized_turn_pcm[tid] = pcm_data
        except Exception:
            pass

    # 2. Si faltan turnos por sintetizar (Linux / Cloud / macOS o respaldo en Windows), usar descarga paralela TTS + Pitch Shift
    missing_turns = [t for t in speech_turns if t["id"] not in synthesized_turn_pcm]
    if missing_turns:
        def _synth_worker(turn_obj: Dict[str, Any]) -> Tuple[int, bytes]:
            tid = turn_obj["id"]
            gender = turn_obj["gender"]
            mp3_b = _fetch_gtts_mp3_bytes(turn_obj["cleanText"], lang=lang)
            if mp3_b:
                pcm_b = _decode_mp3_to_pcm24k(mp3_b, gender=gender)
                if pcm_b:
                    return tid, pcm_b
            return tid, b""

        with ThreadPoolExecutor(max_workers=8) as pool:
            for tid, pcm_b in pool.map(_synth_worker, missing_turns):
                if pcm_b:
                    synthesized_turn_pcm[tid] = pcm_b

    # 3. Ensamblar el Master completo en orden cronológico:
    #    Intro Jingle -> Bloques 1..6 (con Sweeps de Transición, SFX intermedios y Voces Hombre/Mujer) -> Outro Jingle
    master_pcm_chunks: List[bytes] = [intro_pcm, pause_pcm]
    current_seg = 1

    for item in all_items:
        seg_idx = item.get("segmentIdx", 1)
        if seg_idx != current_seg:
            master_pcm_chunks.append(generate_transition_sfx_pcm(sample_rate, variant=seg_idx))
            master_pcm_chunks.append(pause_pcm)
            current_seg = seg_idx

        if item["type"] == "sfx":
            master_pcm_chunks.append(stinger_pcm)
            master_pcm_chunks.append(pause_pcm)
        else:
            tid = item["id"]
            pcm_turn = synthesized_turn_pcm.get(tid, b"")
            if pcm_turn:
                master_pcm_chunks.append(pcm_turn)
                master_pcm_chunks.append(pause_pcm)

    master_pcm_chunks.append(outro_pcm)
    full_pcm = b"".join(master_pcm_chunks)

    # Escribir archivo WAV Master (24kHz, 16-bit Mono)
    try:
        with wave.open(target_wav, "wb") as ww:
            ww.setnchannels(1)
            ww.setsampwidth(2)
            ww.setframerate(sample_rate)
            ww.writeframes(full_pcm)
    except Exception:
        return None

    # Codificar a MP3 real usando ffmpeg si está disponible; de lo contrario asegurar que .mp3 exista
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin and os.path.exists(target_wav):
        try:
            subprocess.run(
                [
                    ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", target_wav,
                    "-codec:a", "libmp3lame", "-qscale:a", "4",
                    target_mp3
                ],
                timeout=60,
                capture_output=True
            )
            # Eliminar el .wav temporal si ya tenemos el .mp3 real para no duplicar en el panel
            if os.path.exists(target_mp3) and os.path.getsize(target_mp3) > 1000:
                try:
                    os.remove(target_wav)
                except Exception:
                    pass
                return target_mp3
        except Exception:
            pass

    # Si no hay ffmpeg (ej. instalación limpia de Windows sin ffmpeg), copiar el stream WAV válido a .mp3
    # (Windows Media Player, Groove, VLC y Chromium reproducen contenedores WAV con extensión .mp3 por sniffing de cabecera RIFF)
    try:
        shutil.copyfile(target_wav, target_mp3)
        try:
            os.remove(target_wav)
        except Exception:
            pass
    except Exception:
        pass

    return target_mp3 if os.path.exists(target_mp3) else target_wav
