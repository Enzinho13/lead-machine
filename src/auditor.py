import requests
import time
from bs4 import BeautifulSoup

class AuditEngine:
    def __init__(self, url):
        self.url = url
        self.soup = None
        self.load_time = 0

    def fetch(self):
        try:
            start = time.time()
            res = requests.get(self.url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            self.load_time = round(time.time() - start, 2)
            if res.status_code == 200:
                self.soup = BeautifulSoup(res.text, 'html.parser')
                return True
        except:
            pass
        return False

    def check_performance(self):
        if self.load_time > 3.0: return -30, f"Muito Lento ({self.load_time}s)"
        if self.load_time > 1.5: return -10, f"Lento ({self.load_time}s)"
        return 0, ""

    def check_security(self):
        return (-20, "Sem HTTPS") if not self.url.startswith("https") else (0, "")

    def check_mobile(self):
        if self.soup and not self.soup.find('meta', attrs={'name': 'viewport'}):
            return -40, "Não otimizado para Mobile"
        return 0, ""

    def check_seo(self):
        if self.soup and not self.soup.find('h1'):
            return -10, "SEO Fraco (Sem H1)"
        return 0, ""

    def extract_data(self):
        if not self.soup: return "", None
        theme = self.soup.find('meta', attrs={'name': 'theme-color'})
        cor = theme['content'] if theme else None
        textos = [el.get_text(strip=True) for t in ['title', 'h1', 'h2', 'p'] 
                  for el in self.soup.find_all(t, limit=3) if len(el.get_text(strip=True)) > 15]
        return " | ".join(textos)[:1500], cor

def auditar_site_lead(url: str) -> dict:
    if not url or not url.startswith("http"):
        return {"status": "Invalido", "score": 0, "motivos": "Sem URL", "textos_principais": ""}
    
    engine = AuditEngine(url)
    if not engine.fetch():
        return {"status": "Offline", "score": 0, "motivos": "Fora do Ar", "textos_principais": ""}
    
    score = 100
    motivos = []
    
    for penalty, reason in [engine.check_performance(), engine.check_security(), engine.check_mobile(), engine.check_seo()]:
        if penalty < 0:
            score += penalty
            motivos.append(reason)
            
    textos, cor = engine.extract_data()
    
    return {
        "status": "Sucesso",
        "score": max(0, score),
        "motivos": ", ".join(motivos) if motivos else "Excelente",
        "textos_principais": textos,
        "cor_detectada": cor
    }