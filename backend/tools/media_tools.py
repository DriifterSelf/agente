import os

class MediaTools:
    @staticmethod
    def create_chart_image(project_path: str, filename: str, chart_type: str, title: str, labels: list, values: list):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(8, 5))
            if chart_type == 'pie':
                ax.pie(values, labels=labels, autopct='%1.1f%%')
            elif chart_type == 'line':
                ax.plot(labels, values, marker='o', color='#38bdf8')
            else:
                ax.bar(labels, values, color='#6366f1')

            ax.set_title(title)
            target = os.path.join(project_path, filename)
            fig.tight_layout()
            fig.savefig(target, dpi=200)
            plt.close(fig)
            return {"status": "success", "file": target}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def generate_speech(project_path: str, filename: str, text: str, lang: str = "es"):
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang)
            target = os.path.join(project_path, filename)
            tts.save(target)
            return {"status": "success", "file": target}
        except Exception as e:
            return {"status": "error", "error": str(e)}
