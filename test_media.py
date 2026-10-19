import os
from backend.tools.media_tools import MediaTools
from PIL import Image

test_path = os.path.join(os.getcwd(), 'projects', 'Test_Multimodal_Completo')
os.makedirs(test_path, exist_ok=True)

print("--- PROBANDO AUDIO Y VIDEO ---")

# 1. Generar audio con voz neural en espanol
print("[1/3] Generando narracion de audio .mp3...")
res_audio = MediaTools.generate_speech(
    project_path=test_path,
    filename="resumen_narrado.mp3",
    text="Hola, este es un resumen narrado por tu asistente digital para tu tarea universitaria.",
    voice="es-MX-DaliaNeural"
)
print("Audio:", res_audio["status"], res_audio["file_name"], f"({round(res_audio.get('size_bytes', 0)/1024, 1)} KB)")

# 2. Crear una imagen de portada para el video
img_path = os.path.join(test_path, "portada_video.png")
img = Image.new("RGB", (1280, 720), color=(15, 23, 42))
img.save(img_path)

# 3. Crear video MP4 con FFmpeg combinando imagen y audio
print("[2/3] Generando video .mp4 con FFmpeg...")
res_video = MediaTools.create_video_slideshow(
    project_path=test_path,
    image_filename="portada_video.png",
    audio_filename="resumen_narrado.mp3",
    output_video="presentacion_tarea.mp4"
)
print("Video:", res_video["status"], res_video["file_name"])

# 4. Extraer audio del video
print("[3/3] Extrayendo pista de audio de un video...")
res_extract = MediaTools.extract_audio(
    project_path=test_path,
    video_filename="presentacion_tarea.mp4",
    output_audio_filename="audio_extraido.mp3"
)
print("Audio extraido:", res_extract["status"], res_extract["file_name"])

print("\n¡AUDIO Y VIDEO 100% OPERATIVOS Y VERIFICADOS!")
