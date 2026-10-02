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

logger = logging.getLogger(__name__)


def criar_slug_seguro(nome: str) -> str:
    replacements = {"ç": "c", "ã": "a", "á": "a", "é": "e", "ê": "e", "í": "i", "ó": "o", "ô": "o", "ú": "u"}
    slug = nome.lower()
    for orig, repl in replacements.items():
        slug = slug.replace(orig, repl)
    slug = re.sub(r"[^a-z0-9]", " ", slug)
    return re.sub(r"\s+", "-", slug).strip("-")[:50]


def gerar_outreach_personalizado(nome_cliente: str, url_online: str, dados_auditoria: dict) -> str:
    """Generate outreach message based on REAL audit data. Never invent problems."""
    motivos = dados_auditoria.get("motivos", "")

    # Only mention real issues found
    if motivos and motivos != "Nenhum problema crítico":
        problemas_texto = f"identificamos alguns pontos técnicos que podem estar impactando seus resultados: {motivos}"
    else:
        problemas_texto = "identificamos oportunidades de melhoria na presença digital de vocês"

    mensagem = (
        f"Olá, equipe da {nome_cliente}! Tudo bem?\n\n"
        f"Fizemos uma análise técnica no site de vocês e {problemas_texto}.\n\n"
        f"Montamos um protótipo de como ficaria um site otimizado para conversão:\n"
        f"👉 {url_online}\n\n"
        f"Gostariam de agendar 10 minutos para conversarmos sobre isso?\n"
    )

    return mensagem


def executar_pipeline_completo(nome_bruto: str, nicho: str, cidade: str, url_lead: str) -> str | None:
    """Execute the full pipeline: Audit → Design Director → Generate → QA → Deploy → Outreach."""
    # 1. Audit
    logger.info(f"[PIPELINE] Auditando: {url_lead}")
    dados_auditoria = auditar_site_lead(url_lead)

    # 2. Design Director
    lead_data = {"nome": nome_bruto, "nicho": nicho, "cidade": cidade, "url": url_lead}
    director = DesignDirector()
    dados_ia = director.generate_design(lead_data, dados_auditoria)

    nome_limpo = dados_ia.get("nome_limpo", nome_bruto[:30])
    slug = criar_slug_seguro(nome_limpo)

    # 3. Prepare site data
    dados_site = {
        "slug": slug,
        "title": nome_limpo,
        "theme": dados_ia.get("theme", {"font_heading": "serif", "font_body": "sans-serif", "primary_color": "#000000"}),
        "layout": dados_ia.get("layout", [])
    }

    # 4. Generate site
    logger.info(f"[PIPELINE] Gerando site dinâmico: {nome_limpo}")
    gerar_site_cliente(dados_site)

    # 4.5. QA Automation
    logger.info(f"[PIPELINE] Executando QA Automático: {slug}")
    qa_passed = executar_qa(slug)
    if not qa_passed:
        logger.error(f"[PIPELINE] Falha no QA para {slug}. Deploy cancelado.")
        return None

    # 5. Deploy
    logger.info(f"[PIPELINE] Deploy: {slug}")
    url_online = fazer_deploy_site(slug)

    # 6. Outreach
    if url_online:
        msg = gerar_outreach_personalizado(nome_limpo, url_online, dados_auditoria)
        brief = dados_ia.get("design_brief", "")
        save_outreach_data(url_lead, msg, brief)
        logger.info(f"[PIPELINE] Concluído: {url_online}")

    return url_online