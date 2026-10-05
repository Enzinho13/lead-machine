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
from database import update_lead_status
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


def preparar_outreach_do_lead(url_lead: str, nome_empresa: str, dados_auditoria: dict,
                              url_prototipo: str, design_brief: str = "") -> dict:
    """Prepara (SEM enviar) o outreach do lead a partir dos contatos reais salvos no banco.

    Usa OutreachEngine.preparar_envio: sem contato não há chamada de IA e nada é gravado em outreach;
    com celular e/ou e-mail, grava um RASCUNHO por canal (DRAFT = mensagem preparada, nunca enviada).
    Não altera o status comercial do lead. Retorna o resultado de preparar_envio
    ('ready' | 'no_contact' | 'blocked') ou {'status': 'lead_not_found'}; 'sent' é sempre False.
    """
    from database import DB_PATH, get_lead_by_url, save_design_brief, save_outreach_draft
    from ai_qualifier import qualificar_lead_com_ia
    from outreach import OutreachEngine

    lead = get_lead_by_url(url_lead)
    if not lead:
        logger.warning(f"[PIPELINE] Outreach não preparado: lead não encontrado no banco ({url_lead})")
        return {"status": "lead_not_found", "sent": False}

    if design_brief:
        save_design_brief(url_lead, design_brief)

    qualificacao = qualificar_lead_com_ia({"auditoria": dados_auditoria})
    resultado = OutreachEngine(DB_PATH).preparar_envio(lead["id"], nome_empresa, qualificacao, link_prototipo=url_prototipo)

    if resultado["status"] == "ready":
        for payload in resultado["payloads"]:
            save_outreach_draft(lead["id"], payload["canal"], payload["mensagem"])
        logger.info(f"[PIPELINE] Outreach preparado (rascunho, NÃO enviado) para {url_lead}: canais {resultado['canais']}")
    else:
        logger.warning(f"[PIPELINE] Outreach não preparado para {url_lead}: {resultado['status']} - {resultado.get('reason')}")
    return resultado


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

    # 6. Outreach: apenas PREPARAÇÃO a partir dos contatos reais do lead. Nada é enviado.
    if url_online:
        try:
            preparar_outreach_do_lead(url_lead, nome_limpo, dados_auditoria, url_online, dados_ia.get("design_brief", ""))
        except Exception as e:
            # O site já está publicado: falha ao preparar o outreach não pode derrubar o pipeline
            logger.error(f"[PIPELINE] Falha ao preparar outreach de {url_lead} (site já publicado em {url_online}): {e}")

    return url_online


def executar_pipeline_e_atualizar_status(nome_bruto: str, nicho: str, cidade: str, url_lead: str) -> str | None:
    """Roda o pipeline e só move o lead para DEPLOYED se o site foi publicado.

    CONTACTED é reservado a envio real de mensagem (não acontece aqui).
    Se o pipeline falhar (None), o status do lead não muda e ele pode ser reprocessado.
    """
    link = executar_pipeline_completo(nome_bruto, nicho, cidade, url_lead)
    if link:
        update_lead_status(url_lead, "DEPLOYED", vercel_url=link)
    return link