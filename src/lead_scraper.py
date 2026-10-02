from ddgs import DDGS
import os
import sys

# Garante que o database pode ser importado corretamente
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import init_db, insert_lead

# REGRA DE NEGÓCIO: Domínios proibidos (Diretórios, Redes Sociais, Agregadores)
BANNED_DOMAINS = [
    "instagram.com", "facebook.com", "linkedin.com", "youtube.com",
    "jusbrasil.com.br", "guiamais.com.br", "listamais.com.br", 
    "doctoralia.com.br", "guiatelefone.com", "telelistas.net",
    "yelp.com", "tripadvisor.com", "comerciosaopaulo.com.br"
]

def buscar_empresas(nicho: str, cidade: str, max_resultados: int = 5):
    print(f"[DISCOVERY] Iniciando busca por '{nicho} em {cidade}'...")
    init_db() # Garante que o banco SQLite existe
    
    termo_busca = f"{nicho} em {cidade}"
    leads_encontrados = 0
    
    try:
        with DDGS() as ddgs:
            # Buscamos o triplo de resultados para compensar os lixos que vamos descartar
            resultados = list(ddgs.text(termo_busca, max_results=max_resultados * 3)) 
            
            for r in resultados:
                if leads_encontrados >= max_resultados:
                    break # Atingimos a meta solicitada pelo usuário
                    
                site_url = r.get('href', '').lower()
                
                # CRAWLER: Validação de Lixo
                is_banned = any(banned in site_url for banned in BANNED_DOMAINS)
                
                if site_url and not is_banned:
                    nome = r.get('title', 'Sem título')
                    descricao = r.get('body', 'Sem descrição')
                    
                    # CRAWLER: Limpeza primária de SEO Titles
                    nome_limpo = nome.split(" - ")[0].split(" | ")[0]
                    
                    # DATA EXTRACTION: Salva no SQLite
                    insert_lead(nome_limpo, site_url, descricao, nicho, cidade)
                    leads_encontrados += 1
                    
    except Exception as e:
        print(f"[ERROR] Falha na camada de Discovery: {e}")
    
    print(f"[DISCOVERY] Concluído. {leads_encontrados} leads salvos/ignorados (duplicados barrados).")