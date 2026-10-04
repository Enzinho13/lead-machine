"""
Outreach Engine — Manages campaigns, rate limits, opt-outs, and follow-ups.
Generates personalized messages based on REAL audit data.
"""
import logging
import sqlite3
import time
from urllib.parse import quote
from typing import Dict, Any, List, Optional

from ai_service import ai, AIError
from contact_extractor import eh_celular_br, normalizar_telefone_br, normalizar_email

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

    def get_contacts(self, lead_id: int) -> Dict[str, str]:
        """Telefone/e-mail públicos já capturados do lead ('' quando não há). Somente leitura: nada é enviado."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT telefone, email FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return {"telefone": (row[0] or "") if row else "", "email": (row[1] or "") if row else ""}

    def analisar_lead(self, lead_id: int) -> Dict[str, Any]:
        """Situação de contato e canais disponíveis do lead, lidos do banco. Somente leitura."""
        return analisar_contatos(self.get_contacts(lead_id))

    def preparar_envio(self, lead_id: int, nome_empresa: str, qualificacao: dict,
                       mensagem: Optional[str] = None, link_prototipo: Optional[str] = None) -> Dict[str, Any]:
        """Prepara, SEM enviar, os dados de envio de cada canal disponível do lead.

        Retorna status 'ready' (com 'payloads'), 'no_contact' ou 'blocked'; 'sent' é sempre False.
        Não altera contatos nem grava nada no banco. Se 'mensagem' vier pronta, ela é usada em todos os
        canais; senão a mensagem é gerada (IA ou template de fallback) para cada canal.
        """
        if self.check_opt_out(lead_id):
            return {"status": "blocked", "reason": "Opt-out (LOST status)", "lead_id": lead_id, "sent": False}

        analise = self.analisar_lead(lead_id)
        resultado = {"lead_id": lead_id, "situacao": analise["situacao"], "canais": analise["canais"], "sent": False}
        if not analise["canais"]:
            motivo = ("Só há telefone fixo: sem canal automático disponível"
                      if analise["situacao"] == SOMENTE_TELEFONE else "Lead sem telefone nem e-mail válidos")
            return {**resultado, "status": "no_contact", "reason": motivo}

        payloads = []
        for canal in analise["canais"]:
            destino = analise["telefone"] if canal == "whatsapp" else analise["email"]
            if mensagem:
                texto, usou_fallback = mensagem, False
            else:
                texto, usou_fallback = self.generate_message_with_status(nome_empresa, qualificacao, canal)
            if link_prototipo and link_prototipo not in texto:
                texto = f"{texto}\n\nVeja o protótipo: {link_prototipo}"
            payload = montar_payload_envio(canal, destino, texto, nome_empresa)
            payload["usou_fallback"] = usou_fallback
            payloads.append(payload)
        return {**resultado, "status": "ready", "payloads": payloads}

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
        """Gera a mensagem e registra um RASCUNHO (status DRAFT) em outreach. NÃO envia nada.

        O nome é mantido por compatibilidade com o pipeline. Para dados de envio por canal, use preparar_envio.
        """
        if self.check_opt_out(lead_id):
            return {"status": "blocked", "reason": "Opt-out (LOST status)"}
            
        if self.is_rate_limited(canal):
            return {"status": "rate_limited", "reason": "Too many messages sent recently on this channel."}
            
        msg, used_fallback = self.generate_message_with_status(nome_empresa, qualificacao, canal)
        self.record_dispatch(canal)
        
        # Save to DB history
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO outreach (lead_id, canal, mensagem, status) VALUES (?, ?, ?, 'DRAFT')", 
                      (lead_id, canal.upper(), msg))
            conn.commit()
            
        return {"status": "success", "message": msg, "used_fallback": used_fallback, "sent": False}


# Situação de contato do lead, calculada apenas com contatos VÁLIDOS
SEM_CONTATO = "sem_contato"
SOMENTE_TELEFONE = "somente_telefone"
SOMENTE_EMAIL = "somente_email"
TELEFONE_E_EMAIL = "telefone_e_email"


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def analisar_contatos(contatos) -> Dict[str, Any]:
    """Classifica os contatos de um lead SEM alterá-los (sem rede, sem IA, sem banco).

    Aceita um dict ou uma linha de lead (qualquer objeto com .get). Valor inválido conta como ausente.
    'telefone' e 'email' devolvidos são as versões normalizadas, usadas só para o envio futuro.
    """
    telefone = normalizar_telefone_br(_texto(contatos.get("telefone")))
    email = normalizar_email(_texto(contatos.get("email")))
    celular = eh_celular_br(telefone)
    if telefone and email:
        situacao = TELEFONE_E_EMAIL
    elif telefone:
        situacao = SOMENTE_TELEFONE
    elif email:
        situacao = SOMENTE_EMAIL
    else:
        situacao = SEM_CONTATO
    canais = ((["whatsapp"] if celular else []) + (["email"] if email else []))
    return {"telefone": telefone, "email": email, "telefone_eh_celular": celular, "situacao": situacao, "canais": canais}


def montar_payload_envio(canal: str, destino: str, mensagem: str, nome_empresa: str = "") -> Dict[str, Any]:
    """Monta os dados para um FUTURO envio. Só constrói o dicionário: não envia nem grava nada."""
    payload = {"canal": canal, "destino": destino, "mensagem": mensagem, "sent": False}
    if canal == "whatsapp":
        payload["link_whatsapp"] = f"https://wa.me/{destino.lstrip('+')}?text={quote(mensagem, safe='')}"
    elif canal == "email":
        payload["assunto"] = f"Sobre o site da {nome_empresa}" if nome_empresa else "Sobre o site da sua empresa"
    else:
        raise ValueError(f"Canal não suportado: {canal}")
    return payload


def canais_disponiveis(contatos: Dict[str, str]) -> List[str]:
    """Canais utilizáveis a partir dos contatos do lead: WhatsApp exige celular; e-mail exige e-mail.

    Telefone fixo sozinho não habilita nenhum canal automático. Aceita o dict de get_contacts ou uma linha de lead.
    """
    return analisar_contatos(contatos)["canais"]


# Backward compatibility wrapper
def gerar_mensagem(nome_empresa: str, qualificacao: dict, canal: str = "whatsapp") -> str:
    from database import DB_PATH
    engine = OutreachEngine(DB_PATH)
    return engine.generate_message(nome_empresa, qualificacao, canal)