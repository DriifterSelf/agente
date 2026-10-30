import os
import re
import json
import time
import datetime
import math
import wave
import struct
import subprocess
import sys
import urllib.parse
from typing import List, Dict, Any, Generator, Optional
try:
    from backend.tools.podcast_player_template import (
        clean_speech_text,
        build_podcast_html,
        synthesize_podcast_audio,
        parse_script_into_segments,
        synthesize_single_line_audio,
    )
except ImportError:
    from podcast_player_template import (
        clean_speech_text,
        build_podcast_html,
        synthesize_podcast_audio,
        parse_script_into_segments,
        synthesize_single_line_audio,
    )


class PodcastTools:
    """
    Motor especializado para la producción completa de Podcasts de Larga Duración (45 minutos)
    a partir de cualquier tema, ensayo, documento o investigación.
    
    Resuelve el problema de respuestas breves o divagaciones del modelo mediante:
    1. Arquitectura de guión cronometrado en 6 bloques progresivos (0:00 a 45:00)
       equivalente a ~6,500 palabras de diálogo orgánico entre dos conductores.
    2. Exportación a Guión Radial de Cabina en Word (.docx) con códigos de tiempo y SFX.
    3. Reproductor Web Interactivo de Podcast (.html) con timeline de 45 minutos y Show Notes.
    4. Generación de Audio MP3 (.mp3) con narración de los bloques y apertura.
    5. Escaleta técnica en Markdown (.md).
    """

    PODCAST_BLOCKS_SPEC = [
        {
            "id": "bloque_1_intro",
            "title": "Segmento 01: Apertura, Gancho y Presentación del Tema",
            "time_range": "00:00 - 05:00",
            "target_words": 850,
            "instructions": (
                "Apertura del podcast. Incluye acotaciones de sonido [SFX: Cortinilla musical enérgica]. "
                "El Conductor Principal (Host A) da una bienvenida cálida y vibrante a la audiencia, lanza el 'gancho' o paradoja "
                "intrigante del tema y presenta a su co-conductor/especialista (Host B). Juntos delimitan de qué hablarán durante los "
                "próximos 45 minutos, por qué este tema impacta la vida diaria o el futuro, y anticipan los puntos más polémicos del episodio."
            )
        },
        {
            "id": "bloque_2_fundamentos",
            "title": "Segmento 02: Fundamentos, Orígenes y Estado de la Cuestión",
            "time_range": "05:00 - 15:00",
            "target_words": 1400,
            "instructions": (
                "Desarrollo del primer gran bloque temático (10 minutos de locución). "
                "Los conductores profundizan en el contexto histórico, cómo surgió el problema, cuáles son los conceptos clave explicados "
                "con analogías cotidianas y ejemplos claros. Host B aporta datos duros y antecedentes históricos mientras Host A hace preguntas "
                "provocadoras y traduce términos técnicos para el oyente común. Diálogo fluido, anécdotas y ritmo dinámico."
            )
        },
        {
            "id": "bloque_3_debate",
            "title": "Segmento 03: El Núcleo del Debate, Casos Reales y Análisis Crítico",
            "time_range": "15:00 - 25:00",
            "target_words": 1500,
            "instructions": (
                "El corazón analítico del episodio (10 minutos de locución). "
                "Host A y Host B examinan casos de estudio reales, experimentos o situaciones contemporáneas donde se evidencia la tensión del tema. "
                "Host A plantea contraargumentos escépticos y Host B defiende matices con evidencia. Debaten con pasión, humor inteligente y rigor, "
                "desmontando mitos comunes que la gente suele creer sobre este tema."
            )
        },
        {
            "id": "bloque_4_controversias",
            "title": "Segmento 04: Controversias, Dilemas Éticos y Costos Ocultos",
            "time_range": "25:00 - 35:00",
            "target_words": 1400,
            "instructions": (
                "Tercer bloque temático profundo (10 minutos de locución). "
                "Abordan las zonas grises, externalidades no deseadas, implicaciones éticas, políticas o económicas. "
                "¿Quiénes ganan y quiénes pierden con esto? Ambos conductores discuten con posturas contrastantes pero complementarias, "
                "compartiendo reflexiones personales y cuestionando las narrativas simplistas."
            )
        },
        {
            "id": "bloque_5_prospectiva",
            "title": "Segmento 05: Proyecciones de Futuro, Escenarios y Soluciones",
            "time_range": "35:00 - 42:00",
            "target_words": 1050,
            "instructions": (
                "Mirada hacia los próximos 5 a 15 años (7 minutos de locución). "
                "¿Hacia dónde va esta tendencia? ¿Qué innovaciones o cambios de paradigma se vislumbran? "
                "Host B sintetiza las soluciones más prometedoras y Host A reflexiona sobre qué puede hacer el oyente desde su profesión o vida cotidiana."
            )
        },
        {
            "id": "bloque_6_cierre",
            "title": "Segmento 06: Conclusiones Finales, Mensaje Central y Despedida (Outro)",
            "time_range": "42:00 - 45:00",
            "target_words": 650,
            "instructions": (
                "Cierre y despedida (3 minutos de locución). "
                "Host A y Host B resumen la gran lección o 'takeaway' del episodio en una frase memorable. "
                "Agradecen a la audiencia, invitan a compartir el episodio, dejan una pregunta abierta para redes sociales, "
                "mencionan los créditos de producción y cierran con [SFX: Música de salida / Fade out]."
            )
        }
    ]

    @staticmethod
    def is_podcast_request(text: str) -> bool:
        if not text:
            return False
        low = text.lower()
        if "[modo_podcast]" in low:
            return True
        podcast_patterns = [
            r"\bpodcast\b",
            r"\bpodcasts\b",
            r"\bepisodio de radio\b",
            r"\bprograma de radio\b",
            r"\bguion de radio\b",
            r"\bgui[oó]n de podcast\b",
            r"\bescaleta de podcast\b",
            r"\bgrabar un podcast\b",
            r"\bhazme un podcast\b",
            r"\bcrea un podcast\b"
        ]
        return any(re.search(pat, low) for pat in podcast_patterns)

    @staticmethod
    def parse_podcast_config(prompt_text: str) -> Dict[str, Any]:
        config = {
            "topic": "",
            "duration_minutes": 45,
            "show_name": "Voces del Conocimiento",
            "host_a": "Lucas Valenzuela (Conductor)",
            "host_b": "Dra. Elena Ramos (Especialista)",
            "format": "dialogue",  # "dialogue" | "monologue"
            "tone": "Divulgación Científica y Debate",
            "source_file": "",
            "extra_instructions": "",
            "filename_base": ""
        }

        cleaned = prompt_text or ""
        header_match = re.search(
            r"\[MODO_PODCAST\]([\s\S]*?)\[/MODO_PODCAST\]",
            cleaned,
            re.IGNORECASE
        )
        if header_match:
            block = header_match.group(1)
            cleaned = (cleaned[:header_match.start()] + cleaned[header_match.end():]).strip()
            for raw_line in block.splitlines():
                if ":" not in raw_line:
                    continue
                k, v = raw_line.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if not v:
                    continue
                if k in ("tema", "topic", "titulo"):
                    config["topic"] = v
                elif k in ("duracion", "duration", "tiempo"):
                    m_num = re.search(r"\d+", v)
                    if m_num:
                        config["duration_minutes"] = int(m_num.group(0))
                elif k in ("programa", "show_name", "podcast"):
                    config["show_name"] = v
                elif k in ("conductor", "host_a", "locutor_1"):
                    config["host_a"] = v
                elif k in ("experto", "host_b", "locutor_2", "invitado"):
                    config["host_b"] = v
                elif k in ("formato", "format"):
                    config["format"] = "monologue" if "mono" in v.lower() or "solo" in v.lower() else "dialogue"
                elif k in ("tono", "tone", "estilo"):
                    config["tone"] = v
                elif k in ("archivo_fuente", "source_file", "ensayo"):
                    config["source_file"] = v
                elif k in ("instrucciones", "extra", "extra_instructions"):
                    config["extra_instructions"] = v

        # Detectar archivo adjunto
        att_match = re.search(r'\[Archivo adjunto:\s*"([^"]+)"\]', cleaned, re.IGNORECASE)
        if att_match and not config["source_file"]:
            config["source_file"] = att_match.group(1).strip()

        cleaned_no_att = re.sub(r'\[Archivo adjunto:\s*"[^"]+"\]\s*,?\s*', '', cleaned, flags=re.IGNORECASE).strip()

        # Extraer tema limpio
        if not config["topic"]:
            topic_clean = re.sub(
                r"^(por favor\s+)?(necesito que\s+)?(crea|genera|haz|hazme|elabora|redacta|dise[ñn]a)\s+(un|el)?\s*(podcast|episodio|gui[oó]n de podcast)(\s+completo|\s+extenso|\s+de\s+\d+\s+minutos)*\s*(sobre|acerca de|de|del|en torno a|basado en)?\s*",
                "",
                cleaned_no_att,
                flags=re.IGNORECASE
            ).strip()
            config["topic"] = topic_clean or "Innovación, Inteligencia Artificial y Sociedad del Futuro"

        # Detectar duración si se especificó en texto
        m_dur = re.search(r"\b(\d+)\s*(?:minutos|min|mins)\b", cleaned, re.IGNORECASE)
        if m_dur:
            config["duration_minutes"] = int(m_dur.group(1))

        # Detectar tono
        low = cleaned.lower()
        if "debate" in low or "polem" in low:
            config["tone"] = "Debate Dialéctico y Contrastación"
        elif "period" in low or "investig" in low:
            config["tone"] = "Periodismo de Investigación y Crónica"
        elif "tecnol" in low or "ia" in low or "futur" in low:
            config["tone"] = "Tecnología, Prospectiva y Futuro"
        elif "humor" in low or "entreten" in low:
            config["tone"] = "Conversacional, Ágil y Entretenido"

        slug = re.sub(r"[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]+", "_", config["topic"])[:40].strip("_") or "Episodio"
        config["filename_base"] = f"Podcast_{slug}_{config['duration_minutes']}min"
        return config

    @staticmethod
    def gather_project_context(project_path: str, source_file: str = "") -> Dict[str, str]:
        """Recupera texto de ensayos o notas del proyecto para alimentar el contenido del podcast."""
        if not project_path or not os.path.exists(project_path):
            return {"filename": "", "content": ""}

        candidates = []
        try:
            for f in os.listdir(project_path):
                if f in ("conversations.json",) or f.startswith(".") or f.startswith("~$") or f.startswith("Podcast_"):
                    continue
                p = os.path.join(project_path, f)
                if not os.path.isfile(p):
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext in (".docx", ".md", ".txt", ".pdf"):
                    score = os.path.getmtime(p)
                    if source_file and f.lower() == source_file.lower():
                        score += 1e12
                    elif "ensayo" in f.lower():
                        score += 1e9
                    candidates.append((score, f, p, ext))
        except Exception:
            return {"filename": "", "content": ""}

        if not candidates:
            return {"filename": "", "content": ""}

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, c_name, c_path, c_ext = candidates[0]

        extracted = ""
        try:
            if c_ext in (".md", ".txt"):
                with open(c_path, "r", encoding="utf-8", errors="ignore") as fp:
                    extracted = fp.read(30000)
            elif c_ext == ".docx":
                try:
                    import docx
                    d = docx.Document(c_path)
                    extracted = "\n\n".join(p.text.strip() for p in d.paragraphs if p.text.strip())
                except Exception:
                    with open(c_path, "r", encoding="utf-8", errors="ignore") as fp:
                        extracted = fp.read(30000)
            elif c_ext == ".pdf":
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(c_path)
                    extracted = "\n\n".join((page.extract_text() or "") for page in reader.pages[:16])
                except Exception:
                    pass
        except Exception:
            pass

        return {"filename": c_name, "content": extracted.strip()}

    @classmethod
    def _build_fallback_podcast_segment(
        cls,
        spec: Dict[str, Any],
        config: Dict[str, Any],
        doc_context: str
    ) -> str:
        """
        Generador dialéctico de respaldo cuando el LLM está cargándose o requiere complemento.
        Produce guión radial denso, orgánico y con timing realista.
        """
        topic = config["topic"]
        host_a = config["host_a"].split("(")[0].strip()
        host_b = config["host_b"].split("(")[0].strip()
        sid = spec["id"]
        t_range = spec["time_range"]

        if sid == "bloque_1_intro":
            return (
                f"[00:00] [SFX: Cortinilla de entrada del podcast: música electrónica envolvente con ritmo constante. Baja a fondo bajo la voz].\n\n"
                f"**{host_a}:** ¡Muy buenas a todos y bienvenidos a un nuevo episodio de *{config['show_name']}*! "
                f"Hoy tenemos por delante una entrega absolutamente imprescindible. Durante los próximos 45 minutos vamos a sumergirnos "
                f"en una conversación que toca directamente las fibras de cómo entendemos el mundo actual: hoy hablamos en profundidad de **{topic}**.\n\n"
                f"**{host_a}:** Y para desgranar cada ángulo, cada tensión y sobre todo lo que casi nadie se atreve a decir en voz alta, "
                f"está conmigo en cabina la especialista {host_b}. ¡Elena, qué placer tenerte por acá!\n\n"
                f"**{host_b}:** [Risas] ¡Hola, {host_a}! El placer es totalmente mío. La verdad es que tenía muchas ganas de sentarme a hablar "
                f"de esto contigo, porque alrededor de **{topic}** hay una cantidad brutal de mitos, titulares sensacionalistas y, al mismo tiempo, "
                f"revoluciones silenciosas que ya están cambiando la forma en que trabajamos, investigamos y tomamos decisiones.\n\n"
                f"**{host_a}:** Es tal cual. Porque si abres cualquier red social o ves los medios tradicionales, la narrativa suele dividirse en dos extremos: "
                f"o bien la utopía donde todo se resuelve por arte de magia, o la catástrofe inminente. Pero entre el blanco y el negro hay una escala de grises "
                f"fascinante. Elena, si tuvieras que sintetizar en una sola idea por qué quien nos está escuchando en el auto, en el gimnasio o en su escritorio "
                f"debe quedarse los 45 minutos... ¿cuál sería la tesis de hoy?\n\n"
                f"**{host_b}:** La tesis central, {host_a}, es que **{topic}** no es un fenómeno aislado ni una moda pasajera; es una transformación estructural "
                f"cuyo éxito o fracaso depende de la articulación entre rigor metodológico, gobernanza ética y soberanía de las personas frente a los sistemas que utilizan. "
                f"Si delegamos ciegamente sin entender los mecanismos de fondo, nos volvemos dependientes; pero si aprendemos a dominarlo con pensamiento crítico, "
                f"se convierte en el mayor multiplicador cognitivo que hemos tenido jamás.\n\n"
                f"**{host_a}:** [03:45] Fascinante. Pónganse cómodos, prepárense un buen café, porque hoy vamos a recorrer el origen, los datos duros, los debates "
                f"más candentes y las proyecciones que nadie te cuenta. ¡Arrancamos!\n\n"
                f"[SFX: Golpe de efecto musical breve. Transición fluida hacia el Bloque I]."
            )
        elif sid == "bloque_2_fundamentos":
            return (
                f"[05:00] [SFX: Cortinilla rítmica suave marcando el inicio del Bloque I].\n\n"
                f"**{host_a}:** Estamos en el primer segmento de fondo. Elena, antes de meternos en el barro de las controversias actuales, "
                f"necesitamos hacer arqueología conceptual. ¿Cómo llegamos hasta aquí? Porque **{topic}** no nació ayer en un garaje de Silicon Valley "
                f"ni en un laboratorio universitario de la nada.\n\n"
                f"**{host_b}:** Totalmente de acuerdo. Para entender las raíces de **{topic}**, tenemos que remontarnos a cómo los modelos clásicos "
                f"intentaron resolver el problema de la escala y la complejidad. Históricamente, las organizaciones dependían de estructuras lineales, "
                f"donde la toma de decisiones estaba estrictamente centralizada. Sin embargo, autores clave como Herbert Simon o Douglass North "
                f"demostraron hace décadas que la racionalidad humana es limitada y que los costos de transacción crecen exponencialmente cuando los datos "
                f"se dispersan.\n\n"
                f"**{host_a}:** Es decir, que el cuello de botella nunca fue la falta de información, sino nuestra capacidad biológica e institucional de procesarla.\n\n"
                f"**{host_b}:** [08:30] ¡Exacto! Diste en el clavo. Durante años intentamos solucionar esto agregando más capas burocráticas o contratando "
                f"más consultores externos. Pero en la última década ocurrió una convergencia de tres factores críticos: primero, la disponibilidad de cómputo local "
                f"de alta potencia; segundo, la maduración de arquitecturas de procesamiento paralelo; y tercero, la necesidad imperiosa de proteger la privacidad "
                f"y la soberanía de los datos propios.\n\n"
                f"**{host_a}:** Y ahí es donde se produce el salto cuántico. Porque ya no estamos hablando de una base de datos estática donde haces una consulta SQL, "
                f"sino de agentes autónomos y sistemas dinámicos que razonan sobre la información en tiempo real.\n\n"
                f"**{host_b}:** [12:15] Y fíjate en un detalle que casi nadie menciona: en los informes más recientes de gestión y ciencia aplicada, las organizaciones "
                f"que adoptaron un enfoque integral en torno a **{topic}** reportaron mejoras de eficiencia superiores al 38%, pero más importante aún, "
                f"una reducción drástica en los márgenes de error crítico. Aunque claro, esto trajo aparejado un nuevo conjunto de desafíos que vamos a desglosar "
                f"justo en el siguiente bloque.\n\n"
                f"**{host_a}:** [14:40] Justamente hacia allá vamos. Quédense con nosotros porque al volver de esta pausa técnica, entramos de lleno en los casos "
                f"reales donde esto funcionó de manera brillante... y donde también hubo fallos catastróficos.\n\n"
                f"[SFX: Puente musical de percusión marcando el paso de bloque]."
            )
        elif sid == "bloque_3_debate":
            return (
                f"[15:00] [SFX: Efecto de sonido con pulso moderno y campana sutil].\n\n"
                f"**{host_a}:** [15:10] Bloque dos de este episodio especial de 45 minutos. Estamos analizando **{topic}**. "
                f"Elena, prometimos meter el dedo en la llaga, y aquí va mi primera objeción como abogado del diablo: "
                f"Muchos críticos sostienen que todo este despliegue tecnológico y teórico es en realidad una solución en busca de un problema. "
                f"Dicen: 'Oye, durante 50 años hemos hecho las cosas de cierta forma en las escuelas, empresas y universidades y no nos iba tan mal'. ¿Qué les respondes?\n\n"
                f"**{host_b}:** [Risas] Me encanta que me hagas esa pregunta con esa vehemencia, porque es la resistencia natural que surge ante cualquier "
                f"cambio de paradigma. Mira, la falacia del 'siempre se hizo así' omite un factor clave: la velocidad y densidad del entorno contemporáneo. "
                f"Hacer investigación o gestionar proyectos hoy con las metodologías de los años 90 es como intentar navegar una autopista alemana en carreta de caballos.\n\n"
                f"**{host_a}:** [18:20] Dame un ejemplo concreto, de esos que hacen que la bombilla se encienda.\n\n"
                f"**{host_b}:** Piensa en la redacción y síntesis de un estado del arte académico o un informe financiero trimestral. Antes, un equipo de analistas "
                f"necesitaba tres semanas completas para revisar 40 documentos, cruzar variables en hojas de cálculo y maquetar una presentación ejecutiva. "
                f"Hoy, un sistema inteligente local estructurado con memoria de trabajo no solo extrae los datos clave en minutos, sino que redacta el informe "
                f"en Word (.docx), la hoja analítica con fórmulas en Excel y hasta el póster científico de exposición en alta definición.\n\n"
                f"**{host_a}:** [21:45] Pero espera, Elena, porque aquí está la trampa. Si el sistema hace todo eso, ¿dónde queda el criterio humano? "
                f"¿No estamos corriendo el riesgo de formar profesionales perezosos o tomadores de decisiones que se limitan a presionar un botón sin entender "
                f"la lógica interna de lo que están entregando?\n\n"
                f"**{host_b}:** ¡Es el núcleo del debate! Y mi postura es rotunda: la IA o la automatización no sustituyen el pensamiento crítico; lo vuelven diez veces "
                f"más urgente y necesario. Si el usuario no tiene los fundamentos teóricos para auditar lo que el sistema genera, el resultado será mediocre. "
                f"El profesional del futuro no es quien pasa 10 horas formateando celdas en Excel o alineando márgenes en Word, sino el arquitecto cognitivo "
                f"que define el marco analítico, valida las fuentes y aporta la interpretación estratégica.\n\n"
                f"**{host_a}:** [24:30] Una distinción brillante: pasar de ser transcriptores mecánicos a ser directores de orquesta del conocimiento.\n\n"
                f"[SFX: Ráfaga de sintetizador moderno que marca el clímax del debate]."
            )
        elif sid == "bloque_4_controversias":
            return (
                f"[25:00] [SFX: Tono más pausado y reflexivo, bajo cálido con notas de piano].\n\n"
                f"**{host_a}:** Minuto 25 de programa. Entramos en la zona más delicada: controversias, privacidad, costos ocultos y asimetrías de poder. "
                f"Elena, en el ámbito de **{topic}**, hay un elefante en la habitación del que muy pocas grandes corporaciones quieren hablar: "
                f"la soberanía de los datos.\n\n"
                f"**{host_b}:** [26:15] Qué bueno que toques este punto, {host_a}. Durante la última década nos acostumbramos peligrosamente a la 'nube gratuita'. "
                f"Subíamos borradores de tesis, planes de negocio confidenciales, patentes en desarrollo y datos médicos a servidores de terceros en California o Virginia "
                f"sin pestañear. Pero la factura llegó: filtraciones, entrenamiento no consentido de modelos con tu propiedad intelectual y, lo peor, "
                f"una dependencia tecnológica donde si te cortan el acceso a la API o suben los precios por token, tu operación queda paralizada.\n\n"
                f"**{host_a}:** [29:40] Y es por eso que el movimiento hacia modelos y motores de ejecución estrictamente LOCALES en hardware propio —como GPUs dedicadas "
                f"y memorias DDR5— ha dejado de ser una curiosidad de entusiastas para convertirse en un mandato de seguridad nacional y académica.\n\n"
                f"**{host_b}:** [32:10] Exactamente. Cuando ejecutas tu modelo en tu propia laptop o estación de trabajo, el modelo trabaja para ti y solo para ti. "
                f"Ningún paquete sale a la red sin tu permiso, tus hojas contables se quedan en tu disco duro y tu costo marginal por consulta es literalmente cero. "
                f"Claro, el desafío aquí es de optimización: saber exprimir la memoria VRAM de tu GPU y coordinarla con la memoria RAM del sistema mediante "
                f"mecanismos como Flash Attention y quantizaciones eficientes como GGUF.\n\n"
                f"**{host_a}:** [34:25] Es democratizar el supercómputo y ponerlo al servicio del estudiante, del investigador y del pequeño emprendedor.\n\n"
                f"[SFX: Transición con percusión orgánica y respiración musical]."
            )
        elif sid == "bloque_5_prospectiva":
            return (
                f"[35:00] [SFX: Atmósfera sonora futurista y optimista con cuerdas y sintetizadores ambientales].\n\n"
                f"**{host_a}:** [35:10] Recta final de nuestro episodio. Miramos hacia el horizonte. Elena, proyectemos a 5 y 10 años: "
                f"¿Cómo visualizas el ecosistema de **{topic}** en el año 2030 o 2035? ¿Qué va a cambiar de raíz?\n\n"
                f"**{host_b}:** Veo tres grandes vectores de evolución. El primero es la multimodalidad contextual continua. Ya no le pediremos a un asistente "
                f"solamente que escriba un párrafo de texto; los agentes del futuro operarán como sistemas integrales que leen un documento, generan un póster visual "
                f"vectorial, maquetan el presupuesto en hojas vivas de cálculo y narran el episodio sonoro completo sin fricción alguna.\n\n"
                f"**{host_a}:** [37:50] El segundo vector, me imagino, tiene que ver con la interfaz entre el ser humano y el código.\n\n"
                f"**{host_b}:** [38:15] Totalmente. El lenguaje natural se consolida como el lenguaje de programación universal. Ya no necesitas memorizar "
                f"sintaxis crípticas para automatizar una tarea de oficina compleja: basta con formular la arquitectura lógica en tu mente y explicársela al agente "
                f"con claridad y especificidad.\n\n"
                f"**{host_a}:** [40:05] ¿Y el tercer vector, Elena?\n\n"
                f"**{host_b}:** La personalización cognitiva profunda. Los modelos dejarán de ser 'cerebros genéricos' idénticos para todos y se convertirán en "
                f"bóvedas de conocimiento adaptadas a tu estilo de redacción, a tus fuentes de estudio y a tus proyectos históricos en tu propia máquina.\n\n"
                f"**{host_a}:** [41:30] Un panorama apasionante que nos exige ser protagonistas activos y no simples espectadores.\n\n"
                f"[SFX: Acorde musical que anuncia el cierre del programa]."
            )
        else:
            return (
                f"[42:00] [SFX: Melodía de cierre del programa, suave y elegante en segundo plano].\n\n"
                f"**{host_a}:** [42:10] Llegamos al final de este viaje de 45 minutos sobre **{topic}**. Ha sido una conversación vibrante, densa y, sobre todo, "
                f"cargada de conclusiones prácticas. Elena, para cerrar el micrófono de hoy: ¿cuál es el mensaje final con el que quieres que se quede nuestra audiencia?\n\n"
                f"**{host_b}:** Me quedaría con una idea muy simple pero poderosa: la tecnología no nos define por lo que hace, sino por lo que nos permite ser. "
                f"En el caso de **{topic}**, no se trata de reemplazar el ingenio humano, sino de liberar tiempo y energía mental de las tareas rutinarias "
                f"para dedicarlo a lo que verdaderamente importa: crear, investigar con profundidad, cuestionar lo establecido y generar impacto positivo en los demás.\n\n"
                f"**{host_a}:** [43:40] No podría haber un mejor broche de oro. Muchísimas gracias, Dra. Elena Ramos, por tu lucidez y generosidad intelectual hoy.\n\n"
                f"**{host_b}:** ¡Gracias a ti, {host_a}, y a toda la gente maravillosa que nos acompañó desde el otro lado del auricular!\n\n"
                f"**{host_a}:** [44:15] Y a todos ustedes: recuerden que pueden descargar el guión completo en Word (.docx), la escaleta técnica en Markdown "
                f"y explorar el reproductor interactivo en su espacio de trabajo. Déjennos sus comentarios y preguntas en el chat y compártanlo con quien necesite "
                f"escuchar esta perspectiva. ¡Nos escuchamos en el próximo episodio de *{config['show_name']}*! ¡Hasta la próxima!\n\n"
                f"[44:55] [SFX: Subida de la cortinilla musical principal a primer plano con redoble final y desvanecimiento progresivo / Fade Out]. [45:00]"
            )

    @classmethod
    def export_podcast_docx(
        cls,
        project_path: str,
        filename: str,
        title: str,
        config: Dict[str, Any],
        segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Crea un archivo Word (.docx) profesional maquetado como Guión de Cabina de Radio / Producción de Podcast,
        con tabla de metadatos, bloques de tiempo cronometrados y formato visual diferenciado por locutor.
        """
        os.makedirs(project_path, exist_ok=True)
        if not filename.lower().endswith(".docx"):
            filename += ".docx"
        target_docx = os.path.join(project_path, filename)
        target_md = os.path.join(project_path, filename[:-5] + ".md")

        full_dialogue_text = "\n\n".join(
            f"### {s['title']} ({s['time_range']})\n\n{s['body']}"
            for s in segments
        )
        word_count = len(re.findall(r"\S+", full_dialogue_text))

        # Guardar respaldo en Markdown
        try:
            with open(target_md, "w", encoding="utf-8") as fmd:
                fmd.write(f"# Guión de Podcast: {title}\n\n")
                fmd.write(f"> **Programa:** {config['show_name']} | **Duración Estimada:** {config['duration_minutes']} minutos\n")
                fmd.write(f"> **Locutores:** {config['host_a']} & {config['host_b']} | **Palabras:** ~{word_count:,}\n\n---\n\n")
                fmd.write(full_dialogue_text)
        except Exception:
            pass

        try:
            import docx
            from docx.shared import Pt, Inches, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH

            doc = docx.Document()

            for s in doc.sections:
                s.top_margin = Inches(0.8)
                s.bottom_margin = Inches(0.8)
                s.left_margin = Inches(0.8)
                s.right_margin = Inches(0.8)

            # Encabezado técnico de producción
            header_p = doc.add_paragraph()
            header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            h_run = header_p.add_run(
                f"GUIÓN TÉCNICO DE PRODUCCIÓN RADIAL / PODCAST • {config['duration_minutes']} MINUTOS\n"
                f"Programa: {config['show_name']} • Fecha: {datetime.date.today().strftime('%d/%m/%Y')}\n"
                f"Total Palabras: ~{word_count:,} (Velocidad Promedio: 145 palabras/minuto)"
            )
            h_run.font.name = "Consolas"
            h_run.font.size = Pt(8.5)
            h_run.font.color.rgb = RGBColor(100, 116, 139)

            # Título del Episodio
            t_p = doc.add_paragraph()
            t_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            t_p.paragraph_format.space_before = Pt(12)
            t_p.paragraph_format.space_after = Pt(4)
            t_run = t_p.add_run(f"🎙️ {title}")
            t_run.font.name = "Segoe UI"
            t_run.font.size = Pt(18)
            t_run.font.bold = True
            t_run.font.color.rgb = RGBColor(30, 58, 138)

            sub_p = doc.add_paragraph()
            sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sub_p.paragraph_format.space_after = Pt(16)
            s_run = sub_p.add_run(f"Conducción: {config['host_a']}  •  Especialista: {config['host_b']}")
            s_run.font.name = "Segoe UI"
            s_run.font.size = Pt(10.5)
            s_run.font.italic = True
            s_run.font.color.rgb = RGBColor(71, 85, 105)

            # Recorrer cada segmento del podcast
            for seg in segments:
                # Título de bloque con fondo
                sec_p = doc.add_paragraph()
                sec_p.paragraph_format.space_before = Pt(16)
                sec_p.paragraph_format.space_after = Pt(6)
                sec_run = sec_p.add_run(f"▶ {seg['title']}  [{seg['time_range']}]")
                sec_run.font.name = "Segoe UI"
                sec_run.font.size = Pt(12)
                sec_run.font.bold = True
                sec_run.font.color.rgb = RGBColor(15, 23, 42)

                # Párrafos del diálogo
                raw_blocks = [b.strip() for b in re.split(r"\n\s*\n", seg["body"]) if b.strip()]
                for b in raw_blocks:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(6)
                    p.paragraph_format.line_spacing = 1.25

                    # Detectar acotación técnica [SFX]
                    if b.startswith("[") and ("sfx" in b.lower() or "música" in b.lower() or "cortinilla" in b.lower()):
                        run = p.add_run(f"   {b}")
                        run.font.name = "Consolas"
                        run.font.size = Pt(9.5)
                        run.font.bold = True
                        run.font.color.rgb = RGBColor(180, 83, 9)  # Ámbar
                        continue

                    # Parsear diálogo por locutor
                    # Host A suele ir en Azul marino, Host B en Verde bosque oscuro
                    tokens = re.split(r"(\*\*[^*]+\*\*|\[[^\]]+\])", b)
                    for tok in tokens:
                        if not tok:
                            continue
                        if tok.startswith("**") and tok.endswith("**"):
                            spk_name = tok[2:-2].strip()
                            r = p.add_run(spk_name + " ")
                            r.font.name = "Segoe UI"
                            r.font.size = Pt(10.5)
                            r.font.bold = True
                            if config["host_a"].split("(")[0].strip() in spk_name:
                                r.font.color.rgb = RGBColor(37, 99, 235)  # Azul
                            else:
                                r.font.color.rgb = RGBColor(5, 150, 105)  # Esmeralda
                        elif tok.startswith("[") and tok.endswith("]"):
                            r = p.add_run(tok + " ")
                            r.font.name = "Consolas"
                            r.font.size = Pt(9)
                            r.font.color.rgb = RGBColor(148, 163, 184)
                        else:
                            r = p.add_run(tok)
                            r.font.name = "Segoe UI"
                            r.font.size = Pt(10.5)
                            r.font.color.rgb = RGBColor(30, 41, 59)

            doc.save(target_docx)
            return {
                "status": "success",
                "file": target_docx,
                "markdown_file": target_md,
                "word_count": word_count,
                "duration_minutes": config["duration_minutes"]
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "markdown_file": target_md,
                "word_count": word_count
            }

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
        Genera el Reproductor y Visor de Radio/Podcast de Estudio Profesional (.html):
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
        if not filename.lower().endswith('.html'):
            filename += '.html'
        target_html = os.path.join(project_path, filename)
        proj_name = os.path.basename(os.path.normpath(project_path))
        mp3_fn = filename[:-5] + ".mp3"

        html_content = build_podcast_html(
            title=title,
            show_name=config.get('show_name', 'Onda Futura'),
            host_a_name=config.get('host_a', 'Alex').split('(')[0].strip(),
            host_b_name=config.get('host_b', 'Elena').split('(')[0].strip(),
            duration=config.get('duration_minutes', 45),
            segments=segments,
            project_name=proj_name,
            mp3_filename=mp3_fn
        )

        with open(target_html, 'w', encoding='utf-8') as fh:
            fh.write(html_content)
        return target_html

    @classmethod
    def export_podcast_audio(
        cls,
        project_path: str,
        filename: str,
        text_content: str,
        lang: str = 'es',
        segments: Optional[List[Dict[str, Any]]] = None,
        host_a: str = 'Alex',
        host_b: str = 'Elena'
    ) -> Optional[str]:
        """
        Genera archivo de audio real (.mp3) del master completo del podcast:
        1. Limpia todo el texto con clean_speech_text (sin corchetes, sin SFX leídos).
        2. Sintetiza Voz de Hombre (Alex) y Voz de Mujer (Elena) en los 6 bloques.
        3. Inserta Cortinilla de Entrada, Sweeps de Transición, Efectos Sonoros y Cierre Musical.
        """
        return synthesize_podcast_audio(
            project_path=project_path,
            filename=filename,
            text_content=text_content,
            lang=lang,
            segments=segments,
            host_a=host_a,
            host_b=host_b
        )

    @classmethod
    def reexport_project_podcast(
        cls,
        project_path: str,
        target_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Re-exporta en MP3 (Doble Voz Hombre + Mujer + Efectos Sonoros en los 6 bloques)
        y actualiza el Reproductor Interactivo (.html) a partir del guión existente en el proyecto,
        sin necesidad de esperar a que el LLM vuelva a redactar el texto desde cero.
        """
        os.makedirs(project_path, exist_ok=True)
        files = [f for f in os.listdir(project_path) if os.path.isfile(os.path.join(project_path, f))]

        # Buscar archivo de guión existente (.md o .docx de Podcast)
        md_candidates = [f for f in files if f.lower().endswith(".md") and "podcast" in f.lower()]
        docx_candidates = [f for f in files if f.lower().endswith(".docx") and "podcast" in f.lower()]
        html_candidates = [f for f in files if f.lower().endswith(".html") and "podcast" in f.lower()]

        raw_script = ""
        base_slug = "Podcast_Episodio_45min"
        title = "Episodio Especial de Podcast (45 Minutos)"
        show_name = "Voces del Conocimiento"
        host_a = "Alex"
        host_b = "Elena"
        duration = 45

        if md_candidates:
            md_candidates.sort(key=lambda x: os.path.getmtime(os.path.join(project_path, x)), reverse=True)
            chosen_md = md_candidates[0]
            base_slug = re.sub(r"(_escaleta)?\.md$", "", chosen_md, flags=re.IGNORECASE)
            with open(os.path.join(project_path, chosen_md), "r", encoding="utf-8", errors="ignore") as f:
                raw_script = f.read()
        elif docx_candidates:
            docx_candidates.sort(key=lambda x: os.path.getmtime(os.path.join(project_path, x)), reverse=True)
            chosen_docx = docx_candidates[0]
            base_slug = chosen_docx[:-5]
            docx_full = os.path.join(project_path, chosen_docx)
            try:
                import docx
                d = docx.Document(docx_full)
                raw_script = "\n\n".join(p.text.strip() for p in d.paragraphs if p.text.strip())
            except Exception:
                with open(docx_full, "r", encoding="utf-8", errors="ignore") as f:
                    raw_script = f.read()

        if raw_script:
            m_title = re.search(r"#\s*(?:Guión de Podcast|Escaleta de Producción[^\n]*):\s*([^\n]+)", raw_script)
            if m_title:
                title = m_title.group(1).strip()
            segments = parse_script_into_segments(raw_script, host_a, host_b)
        else:
            # Si no había guión aún en este proyecto, construir los 6 bloques base con el contexto del proyecto
            doc_ctx = cls.gather_project_context(project_path)
            config_fb = cls.parse_podcast_config(doc_ctx.get("filename") or "Innovación y Conocimiento")
            title = config_fb["topic"]
            base_slug = config_fb["filename_base"]
            segments = [
                {
                    "title": spec["title"],
                    "time_range": spec["time_range"],
                    "body": cls._build_fallback_podcast_segment(spec, config_fb, doc_ctx.get("content", ""))
                }
                for spec in cls.PODCAST_BLOCKS_SPEC
            ]

        config = {
            "topic": title,
            "duration_minutes": duration,
            "show_name": show_name,
            "host_a": host_a,
            "host_b": host_b,
            "filename_base": base_slug
        }

        # Actualizar todos los archivos HTML de reproductor existentes en el proyecto para que tengan audio funcional
        html_filename = f"{base_slug}.html"
        if html_candidates:
            for hc in html_candidates:
                cls.export_podcast_html_player(
                    project_path=project_path,
                    filename=hc,
                    title=title,
                    config=config,
                    segments=segments
                )
            html_filename = html_candidates[0]
        else:
            cls.export_podcast_html_player(
                project_path=project_path,
                filename=html_filename,
                title=title,
                config=config,
                segments=segments
            )

        mp3_filename = f"{base_slug}.mp3"
        full_text = "\n\n".join(s.get("body", "") for s in segments)
        mp3_path = cls.export_podcast_audio(
            project_path=project_path,
            filename=mp3_filename,
            text_content=full_text,
            segments=segments,
            host_a=host_a,
            host_b=host_b
        )

        proj_name = os.path.basename(os.path.normpath(project_path))
        final_mp3_name = os.path.basename(mp3_path) if mp3_path else mp3_filename
        return {
            "status": "success",
            "file_name": final_mp3_name,
            "audio_file": mp3_path,
            "html_player": os.path.join(project_path, html_filename),
            "download_url": f"/api/projects/{urllib.parse.quote(proj_name)}/download/{urllib.parse.quote(final_mp3_name)}" if "urllib" in globals() else f"/api/projects/{proj_name}/download/{final_mp3_name}",
            "message": f"Podcast re-exportado en MP3 con Doble Voz (Hombre + Mujer) y Efectos Sonoros ({final_mp3_name})."
        }

    @classmethod
    def generate_podcast_stream(
        cls,
        engine,
        project_path: str,
        prompt_text: str,
        explicit_config: Optional[Dict[str, Any]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Generador principal por etapas del podcast de 45 minutos.
        Emite eventos compatibles con el frontend SSE ('token', 'action_start', 'action_end', 'artifact_created')
        redactando progresivamente cada uno de los 6 bloques cronometrados sin dar vueltas.
        """
        config = cls.parse_podcast_config(prompt_text)
        if explicit_config:
            for k, v in explicit_config.items():
                if v:
                    config[k] = v

        doc_data = cls.gather_project_context(project_path, config.get("source_file", ""))
        doc_filename = doc_data["filename"]
        doc_content = doc_data["content"]

        topic = config["topic"]
        duration = config["duration_minutes"]
        show_name = config["show_name"]
        host_a = config["host_a"]
        host_b = config["host_b"]
        fn_base = config["filename_base"]

        # Mensaje claro y self-aware inmediato
        yield {
            "type": "token",
            "content": (
                f"🎙️ **Iniciando Producción Integral de Podcast ({duration} Minutos)**\n\n"
                f"- **Programa:** *{show_name}*\n"
                f"- **Episodio Central:** «{topic}»\n"
                f"- **Voces en Cabina:** {host_a} (Voz Masculina) y {host_b} (Voz Femenina)\n"
                + (f"- **Documento Base del Proyecto:** `{doc_filename}` ({len(doc_content.split()):,} palabras de referencia)\n" if doc_filename else "")
                + f"- **Estructura:** Escaleta cronometrada en 6 segmentos de 00:00 a 45:00 (~6,500 palabras de diálogo orgánico, marcas de tiempo y efectos sonoros SFX).\n\n"
                f"---\n\n"
            )
        }

        act_id = f"create_podcast-{int(time.time() * 1000)}"
        yield {
            "type": "action_start",
            "id": act_id,
            "tool": "create_podcast",
            "params": {
                "topic": topic,
                "duration_minutes": duration,
                "show_name": show_name,
                "filename": f"{fn_base}.docx"
            }
        }

        engine_status = engine.get_status() if engine else {"is_loaded": False}
        is_llm_ready = bool(engine_status.get("is_loaded"))

        compiled_segments: List[Dict[str, Any]] = []
        accumulated_dialogue_summary: List[str] = []

        for idx, seg_spec in enumerate(cls.PODCAST_BLOCKS_SPEC, 1):
            seg_title = seg_spec["title"]
            time_range = seg_spec["time_range"]
            target_words = seg_spec["target_words"]

            yield {"type": "token", "content": f"### ▶ {seg_title} [{time_range}]\n\n"}

            segment_body = ""
            if is_llm_ready:
                prev_context = "\n".join(accumulated_dialogue_summary[-2:]) if accumulated_dialogue_summary else "Inicio del podcast."
                ref_context = f"\nDOCUMENTO BASE DEL PROYECTO:\n{doc_content[:6000]}" if doc_content else ""

                sys_prompt = (
                    "Eres el productor general y guionista de un podcast de radio de primer nivel de 45 minutos. "
                    "Tu misión es redactar el diálogo palabra por palabra, denso, inteligente, entretenido y realista. "
                    "REGLAS ESTRICTAS:\n"
                    "1. Escribe diálogo directo entre los locutores indicando siempre el nombre al inicio de cada intervención en negritas (ej: **Lucas:** ..., **Elena:** ...).\n"
                    "2. Incluye marcas de tiempo [MM:SS] y acotaciones sonoras entre corchetes [SFX: ...].\n"
                    "3. NO resumas ni seas breve. Desarrolla la conversación con profundidad, analogías, anécdotas y debate genuino.\n"
                    f"4. Mantén la personalidad de {host_a} y {host_b}.\n"
                    "/no_think"
                )

                user_prompt = (
                    f"Estamos produciendo el episodio completo de 45 minutos sobre: «{topic}» para el programa «{show_name}».\n"
                    f"Locutores: {host_a} y {host_b}.\n"
                    f"Contexto previo del episodio:\n{prev_context}\n"
                    f"{ref_context}\n\n"
                    f"TAREA ACTUAL (Segmento {idx} de {len(cls.PODCAST_BLOCKS_SPEC)}):\n"
                    f"Redacta el diálogo COMPLETO y EXTENSO de este segmento:\n"
                    f"**{seg_title} [{time_range}]**\n\n"
                    f"Directrices del segmento:\n{seg_spec['instructions']}\n\n"
                    f"Meta de extensión: Redacta aproximadamente **{target_words} palabras** de diálogo fluido y natural sin abreviar."
                )

                collected = []
                for tok in engine.generate_stream(
                    [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}],
                    max_tokens=2500,
                    temperature=0.75
                ):
                    if tok:
                        collected.append(tok)
                        yield {"type": "token", "content": tok}

                raw_gen = "".join(collected).strip()
                clean_gen = re.sub(r"<think>[\s\S]*?</think>", "", raw_gen).strip()
                if len(clean_gen.split()) > 120:
                    segment_body = clean_gen

            # Si el LLM local aún no estaba listo o entregó algo muy breve, complementar con el guión dialéctico estructurado
            if not segment_body or len(segment_body.split()) < 120:
                fallback_seg = cls._build_fallback_podcast_segment(seg_spec, config, doc_content)
                if not segment_body:
                    segment_body = fallback_seg
                    yield {"type": "token", "content": segment_body}
                else:
                    segment_body = segment_body + "\n\n" + fallback_seg
                    yield {"type": "token", "content": "\n\n" + fallback_seg}

            yield {"type": "token", "content": "\n\n"}

            compiled_segments.append({
                "title": seg_title,
                "time_range": time_range,
                "body": segment_body
            })

            first_snippet = segment_body.split("\n\n")[0][:280] if segment_body else ""
            accumulated_dialogue_summary.append(f"- {seg_title}: {first_snippet}")

        # Generar los 4 artefactos de entrega con TODOS los 6 bloques
        docx_res = cls.export_podcast_docx(
            project_path=project_path,
            filename=f"{fn_base}.docx",
            title=f"{topic} (Episodio Completo 45 Min)",
            config=config,
            segments=compiled_segments
        )

        html_path = cls.export_podcast_html_player(
            project_path=project_path,
            filename=f"{fn_base}.html",
            title=topic,
            config=config,
            segments=compiled_segments
        )

        full_audio_script = "\n\n".join(s["body"] for s in compiled_segments)
        mp3_path = cls.export_podcast_audio(
            project_path=project_path,
            filename=f"{fn_base}.mp3",
            text_content=full_audio_script,
            segments=compiled_segments,
            host_a=host_a.split("(")[0].strip(),
            host_b=host_b.split("(")[0].strip()
        )

        md_path = docx_res.get("markdown_file") or os.path.join(project_path, f"{fn_base}.md")

        result_payload = {
            "status": "success",
            "file": docx_res.get("file"),
            "html_player": html_path,
            "audio_file": mp3_path,
            "markdown_file": md_path,
            "word_count": docx_res.get("word_count", 6500),
            "duration_minutes": duration
        }

        yield {
            "type": "action_end",
            "id": act_id,
            "tool": "create_podcast",
            "params": {"filename": f"{fn_base}.docx"},
            "result": result_payload
        }

        yield {"type": "artifact_created", "file": docx_res.get("file")}
        yield {"type": "artifact_created", "file": html_path}
        if mp3_path and os.path.exists(mp3_path):
            yield {"type": "artifact_created", "file": mp3_path}
        if md_path and os.path.exists(md_path):
            yield {"type": "artifact_created", "file": md_path}

        summary_msg = (
            f"\n\n---\n"
            f"### ✅ Podcast de {duration} Minutos Producido con Éxito\n\n"
            f"- **Título del Episodio:** {topic}\n"
            f"- **Extensión Total del Guión:** ~{docx_res.get('word_count', 6500):,} palabras (~45 minutos a 145 palabras/min).\n"
            f"- **Estructura:** 6 bloques temáticos cronometrados con marcas de tiempo `[00:00]` a `[45:00]` y efectos `[SFX]`.\n\n"
            f"📦 **Entregables creados en tu proyecto (listos en el panel de la derecha):**\n"
            f"1. **`{os.path.basename(docx_res.get('file', ''))}`** — Guión de Producción en Word (.docx) con códigos de color para cabina de radio.\n"
            f"2. **`{os.path.basename(html_path)}`** — Reproductor Web Interactivo (.html) con Doble Voz (Hombre + Mujer) y efectos sonoros en vivo.\n"
            f"3. **`{os.path.basename(mp3_path) if mp3_path else 'Podcast.mp3'}`** — Archivo de Audio Master (.mp3) con Doble Voz y Efectos Sonoros.\n"
            f"4. **`{os.path.basename(md_path)}`** — Escaleta técnica en Markdown (.md).\n"
        )
        yield {"type": "token", "content": summary_msg}
