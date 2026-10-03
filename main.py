"""
Lead Machine — Main Pipeline
Discovery → Audit → Design Director → Site Generation → QA → Deploy → Outreach
"""
import os
import sys
import re
import urllib.parse
import logging

from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from auditor import auditar_site_lead
from database import save_outreach_data
from deployer import fazer_deploy_site
from design_director import DesignDirector
from qa_engine import executar_qa
from site_generator import gerar_site_cliente
from seo_optimizer import otimizar_seo

logger = logging.getLogger(__name__)


def criar_slug_seguro(nome: str) -> str:
    replacements = {"ç": "c", "ã": "a", "á": "a", "é": "e", "ê": "e", "í": "i", "ó": "o", "ô": "o", "ú": "u"}
    slug = nome.lower()
    for orig, repl in replacements.items():
        slug = slug.replace(orig, repl)
    slug = re.sub(r"[^a-z0-9]", " ", slug)
    return re.sub(r"\s+", "-", slug).strip("-")[:50]


# Outreach is now handled via OutreachEngine


def executar_pipeline_completo(nome_bruto: str, nicho: str, cidade: str, url_lead: str) -> str | None:
    """Execute the full pipeline: Audit → Design Director → SEO → Generate → QA → Deploy → Outreach."""
    # 1. Audit
    logger.info(f"[PIPELINE] Auditando: {url_lead}")
    dados_auditoria = auditar_site_lead(url_lead)

    # 2. Design Director
    lead_data = {"nome": nome_bruto, "nicho": nicho, "cidade": cidade, "url": url_lead}
    director = DesignDirector()
    dados_ia = director.generate_design(lead_data, dados_auditoria)

    if dados_ia.get("ai_fallback"):
        logger.error(f"[PIPELINE] IA indisponível no Design Director para {url_lead}. Pipeline cancelado: nenhum site genérico será gerado ou publicado.")
        return None

    nome_limpo = dados_ia.get("nome_limpo", nome_bruto[:30])
    slug = criar_slug_seguro(nome_limpo)

    # 3. SEO Optimization
    logger.info(f"[PIPELINE] Otimizando SEO e Conteúdo para: {nome_limpo}")
    dados_seo = otimizar_seo(lead_data, dados_ia)

    # 4. Prepare site data
    dados_site = {
        "slug": slug,
        "title": nome_limpo,
        "theme": dados_ia.get("theme", {"font_heading": "serif", "font_body": "sans-serif", "primary_color": "#000000"}),
        "layout": dados_ia.get("layout", []),
        "seo": dados_seo
    }

    # 5. Generate site
    logger.info(f"[PIPELINE] Gerando site dinâmico: {nome_limpo}")
    gerar_site_cliente(dados_site)

    # 5.5. QA Automation
    logger.info(f"[PIPELINE] Executando QA Automático: {slug}")
    qa_passed = executar_qa(slug)
    if not qa_passed:
        logger.error(f"[PIPELINE] Falha no QA para {slug}. Deploy cancelado.")
        return None

    # 6. Deploy
    logger.info(f"[PIPELINE] Deploy: {slug}")
    url_online = fazer_deploy_site(slug)

    # 6. Outreach
    if url_online:
        from database import get_lead_by_url, DB_PATH
        from ai_qualifier import qualificar_lead_com_ia
        from outreach import OutreachEngine
        
        lead_db = get_lead_by_url(url_lead)
        if lead_db:
            qual = qualificar_lead_com_ia({"auditoria": dados_auditoria})
            engine = OutreachEngine(DB_PATH)
            
            # Use real AI generated outreach with real audit context
            result = engine.dispatch(lead_db['id'], nome_limpo, qual, canal="whatsapp")
            
            if result.get("status") == "success":
                msg = result["message"]
                # Append prototype link to generated AI message
                msg += f"\n\nVeja o protótipo: {url_online}"
                
                brief = dados_ia.get("design_brief", "")
                save_outreach_data(url_lead, msg, brief)
                logger.info(f"[PIPELINE] Outreach Gerado: {url_online}")
            else:
                logger.warning(f"[PIPELINE] Outreach bloqueado: {result.get('reason')}")

    return url_online