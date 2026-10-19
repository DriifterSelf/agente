import urllib.request
import json
import re
from typing import Dict, Any, List
import requests
from bs4 import BeautifulSoup
import markdownify

class WebTools:
    @staticmethod
    def search(query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Searches the web for recent information, facts, or data.
        Uses DuckDuckGo search API / HTML backend.
        """
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                formatted = []
                for r in results:
                    formatted.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", r.get("link", "")),
                        "snippet": r.get("body", r.get("snippet", ""))
                    })
                return {
                    "status": "success",
                    "query": query,
                    "results": formatted
                }
        except Exception as e:
            # Fallback direct HTML query
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                resp = requests.get(f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}", headers=headers, timeout=10)
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for result in soup.find_all("div", class_="result", limit=max_results):
                    title_elem = result.find("a", class_="result__a")
                    snippet_elem = result.find("a", class_="result__snippet")
                    if title_elem:
                        url = title_elem.get("href", "")
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": url,
                            "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
                        })
                return {
                    "status": "success",
                    "query": query,
                    "results": results
                }
            except Exception as e2:
                return {
                    "status": "error",
                    "message": f"Error buscando en la web: {str(e2)}"
                }

    @staticmethod
    def fetch_page(url: str, max_chars: int = 8000) -> Dict[str, Any]:
        """
        Fetches a web page and converts its content to clean markdown for easy reading.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=12)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Remove scripts, styles, navigation, footer
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"]):
                tag.decompose()
                
            # Convert to markdown
            html_content = str(soup.body or soup)
            md = markdownify.markdownify(html_content, heading_style="ATX", strip=['img'])
            
            # Clean excessive newlines
            md = re.sub(r'\n{3,}', '\n\n', md).strip()
            if len(md) > max_chars:
                md = md[:max_chars] + f"\n\n... [Contenido truncado a {max_chars} caracteres]"
                
            title = soup.title.string.strip() if soup.title and soup.title.string else url
            return {
                "status": "success",
                "title": title,
                "url": url,
                "content": md
            }
        except Exception as e:
            return {
                "status": "error",
                "url": url,
                "message": f"No se pudo acceder a la página: {str(e)}"
            }
