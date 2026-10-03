"""
Outreach Engine — Manages campaigns, rate limits, opt-outs, and follow-ups.
Generates personalized messages based on REAL audit data.
"""
import logging
import sqlite3
import time
from typing import Dict, Any, List

from ai_service import ai, AIError

logger = logging.getLogger(__name__)

# Mocked rate limit registry in memory (in production use Redis/DB)
_rate_limits = {}

class OutreachEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def check_opt_out(self, lead_id: int) -> bool:
        """Check if lead has opted out."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT status FROM leads WHERE id = ?", (lead_id,))
            row = c.fetchone()
            if row and row[0] == 'LOST':
                return True
        return False

    def is_rate_limited(self, channel: str) -> bool:
        """Simple rate limiting: max 5 messages per minute per channel."""
        now = time.time()
        timestamps = _rate_limits.get(channel, [])
        # Keep only timestamps from the last 60 seconds
        timestamps = [t for t in timestamps if now - t < 60]
        _rate_limits[channel] = timestamps
        
        if len(timestamps) >= 5:
            return True
        return False

    def record_dispatch(self, channel: str):
        _rate_limits.setdefault(channel, []).append(time.time())

    def generate_message(self, nome_empresa: str, qualificacao: dict, canal: str = "whatsapp") -> str:
        """Retorna só o texto da mensagem (IA ou template). Para saber qual foi usado, veja generate_message_with_status."""
        return self.generate_message_with_status(nome_empresa, qualificacao, canal)[0]

    def generate_message_with_status(self, nome_empresa: str, qualificacao: dict, canal: str = "whatsapp") -> tuple[str, bool]:
        """
        Generate a personalized outreach message based on real audit data.
        Falls back to a template if AI is unavailable.
        """
        factors = qualificacao.get("factors", [])
        opportunities = qualificacao.get("opportunities", [])
        motivos = qualificacao.get("motivos", "")

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
            return ai.generate_text(prompt, temperature=0.7), False
        except AIError as e:
            logger.warning(f"AI indisponível para outreach, usando template de fallback: {e}")
            problemas_str = " e ".join(factors[:2]) if factors else "alguns pontos técnicos"
            return (
                f"Olá, equipe da {nome_empresa}! Tudo bem?\n\n"
                f"Dei uma olhada no site de vocês e notei {problemas_str} que podem estar impactando seus resultados.\n\n"
                f"Teriam interesse em ver como podemos ajudar com isso?"
            ), True

    def dispatch(self, lead_id: int, nome_empresa: str, qualificacao: dict, canal: str = "whatsapp") -> Dict[str, Any]:
        """Orchestrates message generation, validation, and simulated dispatch."""
        if self.check_opt_out(lead_id):
            return {"status": "blocked", "reason": "Opt-out (LOST status)"}
            
        if self.is_rate_limited(canal):
            return {"status": "rate_limited", "reason": "Too many messages sent recently on this channel."}
            
        msg, used_fallback = self.generate_message_with_status(nome_empresa, qualificacao, canal)
        self.record_dispatch(canal)
        
        # Save to DB history
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO outreach (lead_id, canal, mensagem, status) VALUES (?, ?, ?, 'SENT')", 
                      (lead_id, canal.upper(), msg))
            conn.commit()
            
        return {"status": "success", "message": msg, "used_fallback": used_fallback}


# Backward compatibility wrapper
def gerar_mensagem(nome_empresa: str, qualificacao: dict, canal: str = "whatsapp") -> str:
    from database import DB_PATH
    engine = OutreachEngine(DB_PATH)
    return engine.generate_message(nome_empresa, qualificacao, canal)