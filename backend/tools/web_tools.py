import requests
from bs4 import BeautifulSoup

class WebTools:
    @staticmethod
    def search(query: str, max_results: int = 5):
        try:
            # Simple fallback search using duckduckgo html
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}", headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for a in soup.select(".result__body")[:max_results]:
                    title_elem = a.select_one(".result__title a")
                    snippet_elem = a.select_one(".result__snippet")
                    if title_elem:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": title_elem.get("href"),
                            "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
                        })
                return {"status": "success", "results": results}
            return {"status": "error", "error": f"Status {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def fetch_page(url: str, max_chars: int = 4000):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for s in soup(["script", "style"]):
                    s.decompose()
                text = " ".join(soup.stripped_strings)
                return {"status": "success", "content": text[:max_chars]}
            return {"status": "error", "error": f"Status {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
