import requests
import time
from bs4 import BeautifulSoup

def auditar_site_lead(url: str) -> dict:
    if not url or url == "#" or not url.startswith("http"):
        return {"status": "Invalido", "score": 0, "motivos": "Sem site", "textos_principais": ""}
    
    print(f"[AUDITOR] Executando diagnóstico técnico em: {url}")
    
    score = 100
    motivos_penalizacao = []
    
    try:
        start_time = time.time()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        tempo_resposta = round(time.time() - start_time, 2)
        
        # 1. Análise de Performance
        if tempo_resposta > 3.0:
            score -= 30
            motivos_penalizacao.append(f"Muito Lento ({tempo_resposta}s)")
        elif tempo_resposta > 1.5:
            score -= 10
            motivos_penalizacao.append(f"Lento ({tempo_resposta}s)")
            
        # 2. Análise de Segurança
        if not url.startswith("https"):
            score -= 20
            motivos_penalizacao.append("Inseguro (Sem HTTPS)")
            
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 3. Análise Mobile (Viewport)
            viewport = soup.find('meta', attrs={'name': 'viewport'})
            if not viewport:
                score -= 40
                motivos_penalizacao.append("Não otimizado para Mobile")
                
            # 4. Análise SEO Básica
            if not soup.find('h1'):
                score -= 10
                motivos_penalizacao.append("SEO Fraco (Sem H1)")
                
            # Extração de Cores e Textos (Para a IA)
            theme_color = soup.find('meta', attrs={'name': 'theme-color'})
            cor_detectada = theme_color['content'] if theme_color else None
            
            textos = []
            for tag in ['title', 'h1', 'h2', 'p']:
                for el in soup.find_all(tag, limit=3):
                    texto = el.get_text(strip=True)
                    if len(texto) > 15:
                        textos.append(texto)
                        
            resumo_textual = " | ".join(textos)[:1500] 
            
            # Limites de score
            score = max(0, score)
            motivos_finais = ", ".join(motivos_penalizacao) if motivos_penalizacao else "Site Excelente"
            
            print(f"[AUDITOR] Concluído. Score: {score}/100. Problemas: {motivos_finais}")
            return {
                "status": "Sucesso",
                "score": score,
                "motivos": motivos_finais,
                "cor_detectada": cor_detectada,
                "textos_principais": resumo_textual
            }
        else:
            return {"status": "Erro HTTP", "score": 10, "motivos": f"Erro {response.status_code}", "textos_principais": ""}
            
    except Exception as e:
        print(f"[AUDITOR WARNING] Site fora do ar ou bloqueado: {url}")
        return {"status": "Offline", "score": 0, "motivos": "Site Fora do Ar", "textos_principais": ""}