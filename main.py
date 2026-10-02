"""
Lead Machine — Main Pipeline
Discovery → Audit → AI Enrichment → Site Generation → Deploy → Outreach
"""
import os
import sys
import re
import urllib.parse
import logging

from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from ai_service import ai
from site_generator import gerar_site_cliente
from deployer import fazer_deploy_site
from auditor import auditar_site_lead
from database import save_outreach_data

logger = logging.getLogger(__name__)


def criar_slug_seguro(nome: str) -> str:
    replacements = {"ç": "c", "ã": "a", "á": "a", "é": "e", "ê": "e", "í": "i", "ó": "o", "ô": "o", "ú": "u"}
    slug = nome.lower()
    for orig, repl in replacements.items():
        slug = slug.replace(orig, repl)
    slug = re.sub(r"[^a-z0-9]", " ", slug)
    return re.sub(r"\s+", "-", slug).strip("-")[:50]


def enriquecer_dados_com_ia(nome_bruto: str, nicho: str, cidade: str, dados_auditoria: dict) -> dict:
    """Use AI to generate design direction based on business context and audit data."""
    logger.info(f"[AI] Design Director para: {nome_bruto}...")

    contexto_extra = ""
    if dados_auditoria.get("status") == "Sucesso":
        textos = dados_auditoria.get("textos_principais", "")
        cor = dados_auditoria.get("cor_detectada", "Nenhuma")
        techs = dados_auditoria.get("checks", {}).get("technology", {}).get("technologies", [])
        contexto_extra = f"""
        [DADOS DO SITE ATUAL]
        Textos extraídos: {textos[:800]}
        Cor detectada: {cor}
        Tecnologias: {', '.join(techs) if techs else 'Não identificadas'}
        Score da auditoria: {dados_auditoria.get('score')}/100
        Problemas: {dados_auditoria.get('motivos')}
        """

    prompt = f"""
    Atue como um Diretor de Arte Sênior criando a direção de design para um site.
    
    NEGÓCIO:
    - Nome: "{nome_bruto}"
    - Nicho: "{nicho}"
    - Cidade: "{cidade}"
    
    {contexto_extra}
    
    REGRAS CRÍTICAS:
    - O design DEVE refletir o nicho do negócio. Uma padaria deve parecer uma padaria, não uma startup de tech.
    - NÃO invente informações que não existem (telefones, depoimentos, métricas, prêmios).
    - NÃO use estética genérica de SaaS/dashboard/startup.
    - Escolha uma paleta de cores adequada ao nicho e posicionamento do negócio.
    - O slogan deve ser relevante ao nicho, não genérico.
    - Se existem textos do site atual, use-os como base para manter a identidade.
    
    Devolva APENAS JSON válido com as chaves:
    "nome_limpo": Nome comercial limpo e correto.
    "slogan": Headline principal contextualizada ao nicho.
    "subtitulo": Parágrafo de apoio (2-3 frases) sobre o negócio.
    "cor_destaque": Código HEX da cor primária adequada ao nicho.
    "cor_secundaria": Código HEX de cor secundária complementar.
    "tom_visual": Descrição curta do tom visual (ex: "profissional e acolhedor", "moderno e minimalista").
    "tema_imagem": Prompt EM INGLÊS para imagem de fundo contextual ao nicho (SEM TEXTO NA IMAGEM).
    "servicos": Array de objetos com "titulo" e "descricao" (3 serviços reais do nicho).
    "design_brief": Parágrafo resumindo decisões de design, paleta, tipografia e tom de voz.
    """

    try:
        return ai.generate_structured(prompt)
    except Exception as e:
        logger.error(f"[AI] Falha no Design Director: {e}")
        return {
            "nome_limpo": nome_bruto,
            "slogan": f"{nome_bruto} — {nicho}",
            "subtitulo": f"Atendimento especializado em {cidade}.",
            "cor_destaque": "#1C1C1C",
            "cor_secundaria": "#666666",
            "tom_visual": "profissional",
            "tema_imagem": f"professional {nicho.lower()} office interior",
            "servicos": [],
            "design_brief": "Fallback — IA indisponível.",
        }


def gerar_outreach_personalizado(nome_cliente: str, url_online: str, dados_auditoria: dict) -> str:
    """Generate outreach message based on REAL audit data. Never invent problems."""
    motivos = dados_auditoria.get("motivos", "")
    score = dados_auditoria.get("score", 0)

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
    """Execute the full pipeline: Audit → AI Design → Generate → Deploy → Outreach."""
    # 1. Audit
    logger.info(f"[PIPELINE] Auditando: {url_lead}")
    dados_auditoria = auditar_site_lead(url_lead)

    # 2. AI Enrichment
    dados_ia = enriquecer_dados_com_ia(nome_bruto, nicho, cidade, dados_auditoria)

    nome_limpo = dados_ia.get("nome_limpo", nome_bruto[:30])
    slug = criar_slug_seguro(nome_limpo)

    # 3. Prepare site data
    tema_imagem = dados_ia.get("tema_imagem", f"professional {nicho.lower()} office")
    prompt_img = urllib.parse.quote(f"Architectural photography of {tema_imagem}, cinematic lighting, highly detailed")
    imagem_hero = f"https://image.pollinations.ai/prompt/{prompt_img}?width=1200&height=800&nologo=true"

    # Parse services from AI response
    servicos_ia = dados_ia.get("servicos", [])
    if isinstance(servicos_ia, list) and servicos_ia:
        servicos = [{"titulo": s.get("titulo", ""), "desc": s.get("descricao", s.get("desc", ""))} for s in servicos_ia[:3]]
    else:
        servicos = [
            {"titulo": "Atendimento Especializado", "desc": f"Soluções completas em {nicho}."},
            {"titulo": "Consultoria Profissional", "desc": f"Expertise focada para {cidade}."},
            {"titulo": "Suporte Dedicado", "desc": "Acompanhamento personalizado."},
        ]

    dados_site = {
        "nome_empresa": nome_limpo,
        "slogan": dados_ia.get("slogan", f"{nome_limpo} — Excelência em {nicho}"),
        "subtitulo": dados_ia.get("subtitulo", f"Atendimento especializado em {cidade}."),
        "cidade": cidade,
        "nicho": nicho,
        "slug_pasta": slug,
        "cor_primaria": dados_ia.get("cor_destaque", "#1C1C1C"),
        "cor_secundaria": dados_ia.get("cor_secundaria", "#666666"),
        "tom_visual": dados_ia.get("tom_visual", "profissional"),
        "imagem_hero": imagem_hero,
        "servicos": servicos,
    }

    # 4. Generate site
    logger.info(f"[PIPELINE] Gerando site: {nome_limpo}")
    gerar_site_cliente(dados_site)

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