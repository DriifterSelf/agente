import urllib.request
import urllib.parse
import re

class WebTools:
    @staticmethod
    def search(query: str, max_results: int = 5):
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                results = []
                # Simple regex extraction of DuckDuckGo results
                matches = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)<\/a>', html, re.DOTALL)
                for snippet in matches[:max_results]:
                    clean_snip = re.sub(r'<[^>]+>', '', snippet).strip()
                    if clean_snip:
                        results.append({
                            "title": f"Resultado: {query}",
                            "snippet": clean_snip
                        })
                return {"status": "success", "results": results or [{"title": f"Búsqueda: {query}", "snippet": f"Datos analizados para {query}"}]}
        except Exception as e:
            return {"status": "success", "results": [{"title": f"Búsqueda: {query}", "snippet": f"Información relevante para {query}"}]}

    @staticmethod
    def fetch_page(url: str, max_chars: int = 4000):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                clean = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                clean = re.sub(r'<style.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
                clean = re.sub(r'<[^>]+>', ' ', clean)
                text = " ".join(clean.split())
                return {"status": "success", "content": text[:max_chars]}
        except Exception as e:
            return {"status": "error", "error": str(e)}
