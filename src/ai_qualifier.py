"""
AI Qualifier — Uses audit data to produce explainable lead scoring and qualification.
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_service import ai


def qualificar_lead_com_ia(dados_lead: dict) -> dict:
    """
    Qualifies a lead based on real audit data.
    Returns structured qualification with score, priority, and reasoning.
    """
    audit_data = dados_lead.get("auditoria", {})
    checks = audit_data.get("checks", {}) if isinstance(audit_data, dict) else {}

    # Deterministic scoring from audit data
    score = audit_data.get("score", 50) if isinstance(audit_data, dict) else 50
    motivos = audit_data.get("motivos", "") if isinstance(audit_data, dict) else ""

    # Build qualification factors
    factors = []
    opportunities = []

    if isinstance(checks, dict):
        perf = checks.get("performance", {})
        if perf.get("load_time", 0) > 2.0:
            factors.append(f"Site lento ({perf['load_time']}s)")
            opportunities.append("Otimização de performance")

        seo = checks.get("seo", {})
        seo_issues = seo.get("issues", [])
        if seo_issues:
            factors.extend(seo_issues)
            opportunities.append("Otimização SEO")

        mobile = checks.get("mobile", {})
        if not mobile.get("has_viewport", True):
            factors.append("Não otimizado para mobile")
            opportunities.append("Redesign responsivo")

        security = checks.get("security", {})
        if not security.get("has_https", True):
            factors.append("Sem HTTPS")
            opportunities.append("Certificado SSL")

        images = checks.get("images", {})
        if images.get("missing_alt", 0) > 0:
            factors.append(f"{images['missing_alt']} imagens sem alt text")
            opportunities.append("Otimização de imagens")

        tech = checks.get("technology", {})
        techs = tech.get("technologies", [])
        if "WordPress" in techs:
            opportunities.append("Modernização da plataforma")

    # Priority based on score
    if score <= 40:
        priority = "high"
        qualificacao = "Quente"
    elif score <= 70:
        priority = "medium"
        qualificacao = "Morno"
    else:
        priority = "low"
        qualificacao = "Frio"

    return {
        "status": "Sucesso",
        "qualificacao": qualificacao,
        "priority": priority,
        "score": score,
        "factors": factors,
        "opportunities": opportunities,
        "motivos": motivos,
    }