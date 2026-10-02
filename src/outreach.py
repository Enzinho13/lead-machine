"""
Outreach — Generate personalized outreach messages based on REAL audit data.
Never invents problems, clients, reviews, metrics, or certifications.
"""
import logging

from ai_service import ai

logger = logging.getLogger(__name__)


def gerar_mensagem(nome_empresa: str, qualificacao: dict, canal: str = "whatsapp") -> str:
    """
    Generate a personalized outreach message based on real audit data.
    Falls back to a template if AI is unavailable.
    """
    factors = qualificacao.get("factors", [])
    opportunities = qualificacao.get("opportunities", [])
    motivos = qualificacao.get("motivos", "")

    # Build context from real data only
    problemas_reais = ", ".join(factors[:3]) if factors else motivos
    oportunidades_reais = ", ".join(opportunities[:3]) if opportunities else "melhorias na presença digital"

    prompt = f"""
    Escreva uma mensagem de prospecção curta e natural para {canal} desta empresa.
    
    Empresa: {nome_empresa}
    Problemas técnicos REAIS encontrados: {problemas_reais}
    Oportunidades: {oportunidades_reais}
    
    REGRAS:
    1. Seja educado, humano e direto.
    2. NÃO pareça robô ou vendedor agressivo.
    3. Traduza problemas técnicos para linguagem de negócios (ex: "meta description" → "visibilidade nas buscas").
    4. NUNCA invente clientes, avaliações, resultados, números, prêmios ou certificações.
    5. Termine com uma pergunta leve para iniciar conversa.
    6. Retorne APENAS o texto da mensagem, sem aspas, sem formatação extra.
    7. Máximo 5 frases.
    """

    try:
        return ai.generate_text(prompt, temperature=0.7)
    except Exception as e:
        logger.warning(f"AI indisponível para outreach: {e}")
        # Template fallback with real data
        problemas_str = " e ".join(factors[:2]) if factors else "alguns pontos técnicos"
        return (
            f"Olá, equipe da {nome_empresa}! Tudo bem?\n\n"
            f"Dei uma olhada no site de vocês e notei {problemas_str} que podem estar impactando seus resultados.\n\n"
            f"Teriam interesse em ver como podemos ajudar com isso?"
        )