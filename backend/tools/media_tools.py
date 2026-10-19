import os
import subprocess
import asyncio
from typing import Dict, Any, Optional

class MediaTools:
    @staticmethod
    def generate_speech(project_path: str, filename: str, text: str, voice: str = "es-MX-DaliaNeural") -> Dict[str, Any]:
        """
        Generates crystal-clear neural speech audio (.mp3) from text.
        Voices: 'es-MX-DaliaNeural' (female), 'es-MX-JorgeNeural' (male), 'es-ES-AlvaroNeural' (male)
        """
        if not filename.endswith(".mp3"):
            filename += ".mp3"
        full_path = os.path.join(project_path, filename)
        
        async def _speak():
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(full_path)
            
        try:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(asyncio.run, _speak()).result()
                else:
                    loop.run_until_complete(_speak())
            except RuntimeError:
                asyncio.run(_speak())
                
            return {
                "status": "success",
                "file_name": filename,
                "full_path": full_path,
                "voice": voice,
                "size_bytes": os.path.getsize(full_path),
                "message": f"Audio narrado '{filename}' generado exitosamente."
            }
        except Exception as e:
            return {"status": "error", "message": f"Error generando audio: {str(e)}"}

    @staticmethod
    def extract_audio(project_path: str, video_filename: str, output_audio_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts the audio track from a video (.mp4, .mkv, .mov) into an audio file (.mp3).
        """
        input_path = os.path.join(project_path, video_filename)
        if not os.path.exists(input_path):
            return {"status": "error", "message": f"Video no encontrado: {video_filename}"}
            
        if not output_audio_filename:
            base = os.path.splitext(video_filename)[0]
            output_audio_filename = f"{base}_audio.mp3"
            
        output_path = os.path.join(project_path, output_audio_filename)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            output_path
        ]
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and os.path.exists(output_path):
                return {
                    "status": "success",
                    "file_name": output_audio_filename,
                    "full_path": output_path,
                    "message": f"Pista de audio '{output_audio_filename}' extraída con éxito del video."
                }
            return {"status": "error", "message": res.stderr}
        except Exception as e:
            return {"status": "error", "message": f"Error con FFmpeg: {str(e)}"}

    @staticmethod
    def convert_media(project_path: str, input_filename: str, output_filename: str) -> Dict[str, Any]:
        """
        Converts any audio or video file between formats (.mp4, .avi, .mkv, .mov, .webm, .mp3, .wav).
        """
        input_path = os.path.join(project_path, input_filename)
        output_path = os.path.join(project_path, output_filename)
        
        if not os.path.exists(input_path):
            return {"status": "error", "message": f"Archivo no encontrado: {input_filename}"}
            
        cmd = ["ffmpeg", "-y", "-i", input_path, output_path]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if res.returncode == 0 and os.path.exists(output_path):
                return {
                    "status": "success",
                    "file_name": output_filename,
                    "full_path": output_path,
                    "message": f"Archivo convertido con éxito a '{output_filename}'."
                }
            return {"status": "error", "message": res.stderr}
        except Exception as e:
            return {"status": "error", "message": f"Error en conversión: {str(e)}"}

    @staticmethod
    def create_video_slideshow(project_path: str, image_filename: str, audio_filename: str, output_video: str = "video_final.mp4") -> Dict[str, Any]:
        """
        Combines an image/slide with an audio narration to produce an MP4 video.
        """
        if not output_video.endswith(".mp4"):
            output_video += ".mp4"
            
        img_path = os.path.join(project_path, image_filename)
        audio_path = os.path.join(project_path, audio_filename)
        out_path = os.path.join(project_path, output_video)
        
        if not os.path.exists(img_path) or not os.path.exists(audio_path):
            return {"status": "error", "message": "Imagen o audio no encontrados."}
            
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", img_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            out_path
        ]
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and os.path.exists(out_path):
                return {
                    "status": "success",
                    "file_name": output_video,
                    "full_path": out_path,
                    "message": f"Video MP4 '{output_video}' generado con éxito combinando imagen y voz."
                }
            return {"status": "error", "message": res.stderr}
        except Exception as e:
            return {"status": "error", "message": f"Error creando video: {str(e)}"}
