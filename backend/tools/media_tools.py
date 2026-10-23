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
        except Exception:
            try:
                target = os.path.join(project_path, filename)
                bars = []
                for i, v in enumerate(values):
                    lbl = labels[i] if i < len(labels) else ""
                    val_num = float(v) if isinstance(v, (int, float)) else 50.0
                    h = min(180, max(20, int(val_num * 1.2)))
                    x = 90 + i * 90
                    y = 260 - h
                    bars.append(f'<rect x="{x}" y="{y}" width="45" height="{h}" rx="4" fill="#3B82F6"/>')
                    bars.append(f'<text x="{x + 22}" y="{y - 6}" text-anchor="middle" fill="#93C5FD" font-size="11">{val_num}</text>')
                    bars.append(f'<text x="{x + 22}" y="280" text-anchor="middle" fill="#94A3B8" font-size="11">{lbl}</text>')
                svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="320" viewBox="0 0 600 320" style="background:#0F141C;font-family:sans-serif;">
                  <text x="300" y="35" text-anchor="middle" fill="#E2E8F0" font-size="15" font-weight="bold">{title}</text>
                  {''.join(bars)}
                </svg>'''
                with open(target, "w", encoding="utf-8") as f:
                    f.write(svg)
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
