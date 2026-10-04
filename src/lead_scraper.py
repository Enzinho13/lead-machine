from ddgs import DDGS
import os
import sys

# Garante que o database pode ser importado corretamente
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import init_db, insert_lead, get_lead_by_url, update_lead_contacts, get_leads_sem_contato
from contact_extractor import buscar_contatos_do_site

# REGRA DE NEGÓCIO: Domínios proibidos (Diretórios, Redes Sociais, Agregadores)
BANNED_DOMAINS = [
    "instagram.com", "facebook.com", "linkedin.com", "youtube.com",
    "jusbrasil.com.br", "guiamais.com.br", "listamais.com.br", 
    "doctoralia.com.br", "guiatelefone.com", "telelistas.net",
    "yelp.com", "tripadvisor.com", "comerciosaopaulo.com.br"
]

def _enriquecer_contatos(site_url: str) -> bool:
    """Busca telefone/e-mail públicos no site e grava só onde o lead ainda não tem. Nunca derruba o discovery."""
    try:
        contatos = buscar_contatos_do_site(site_url)
        update_lead_contacts(site_url, contatos["telefone"], contatos["email"])
        return bool(contatos["telefone"] or contatos["email"])
    except Exception as e:
        print(f"[WARN] Falha ao buscar contatos de {site_url}: {e}")
        return False

def enriquecer_contatos_pendentes() -> int:
    """Backfill: busca contatos dos leads já salvos que não têm telefone nem e-mail. Retorna quantos receberam algum contato."""
    init_db()
    return sum(1 for lead in get_leads_sem_contato() if _enriquecer_contatos(lead["url"]))

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

                    # CONTATOS: só busca no site se o lead (novo ou já existente) ainda não tem nenhum
                    lead_salvo = get_lead_by_url(site_url)
                    if lead_salvo and not (lead_salvo.get("telefone") or lead_salvo.get("email")):
                        _enriquecer_contatos(site_url)
                    leads_encontrados += 1
                    
    except Exception as e:
        print(f"[ERROR] Falha na camada de Discovery: {e}")
    
    print(f"[DISCOVERY] Concluído. {leads_encontrados} leads salvos/ignorados (duplicados barrados).")