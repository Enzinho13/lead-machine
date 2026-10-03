import logging
from typing import Dict, Any

from ai_service import ai, AIError, AIResponseError

logger = logging.getLogger(__name__)

def _design_valido(resultado: Dict[str, Any]) -> bool:
    """Uma resposta só é aceita se der para montar um site com ela."""
    layout = resultado.get("layout")
    if not isinstance(layout, list) or not layout:
        return False
    for componente in layout:
        if not isinstance(componente, dict) or not isinstance(componente.get("type"), str):
            return False
        if not isinstance(componente.get("props", {}), dict):
            return False
    if not isinstance(resultado.get("theme", {}), dict):
        return False
    if "nome_limpo" in resultado:
        nome = resultado["nome_limpo"]
        if not isinstance(nome, str) or not nome.strip():
            return False
    return True


class DesignDirector:
    def generate_design(self, lead_data: Dict[str, Any], audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to generate design direction based on business context and audit data."""
        nome_bruto = lead_data.get("nome", "")
        nicho = lead_data.get("nicho", "")
        cidade = lead_data.get("cidade", "")

        logger.info(f"[AI] Design Director para: {nome_bruto}...")

        contexto_extra = ""
        if audit_data and audit_data.get("status") == "Sucesso":
            textos = audit_data.get("textos_principais", "")
            cor = audit_data.get("cor_detectada", "Nenhuma")
            techs = audit_data.get("checks", {}).get("technology", {}).get("technologies", [])
            contexto_extra = f"""
            [DADOS DO SITE ATUAL]
            Textos extraídos: {textos[:800]}
            Cor detectada: {cor}
            Tecnologias: {', '.join(techs) if techs else 'Não identificadas'}
            Score da auditoria: {audit_data.get('score')}/100
            Problemas: {audit_data.get('motivos')}
            """

        prompt = f"""
        Atue como um Diretor de Arte Sênior criando a direção de design para um site.
        
        NEGÓCIO:
        - Nome: "{nome_bruto}"
        - Nicho: "{nicho}"
        - Cidade: "{cidade}"
        
        {contexto_extra}
        
        REGRAS CRÍTICAS (ANTI-AI-SLOP):
        - O design DEVE refletir o nicho do negócio. Uma padaria deve parecer uma padaria, não uma startup de tech. Um escritório de advocacia recebe HeroEditorial, fontes serifadas e cores sóbrias. Uma padaria recebe HeroSplit, cores quentes, fontes sem serifa ou serifa suave.
        - NÃO invente informações que não existem (telefones, depoimentos, métricas, prêmios).
        - NÃO use estética genérica de SaaS/dashboard/startup para negócios locais.
        - Escreva copy altamente contextual ao negócio e nicho (nada de "Somos os melhores da cidade").
        - Se existem textos do site atual, use-os como base para manter a identidade.
        - Para componentes que exigem imagem (como HeroSplit, FeatureServices), adicione a chave 'image_url' no 'props'. Gere o valor no formato: https://image.pollinations.ai/prompt/[prompt-em-ingles]?width=1200&height=800&nologo=true (exemplo: https://image.pollinations.ai/prompt/cozy+bakery+interior?width=1200&height=800&nologo=true).
        
        Você deve retornar um objeto JSON complexo contendo 'theme' e 'layout'.
        """

        schema = {
            "type": "object",
            "properties": {
                "nome_limpo": {"type": "string", "description": "Nome comercial limpo"},
                "design_brief": {"type": "string", "description": "Resumo das decisões de design"},
                "theme": {
                    "type": "object",
                    "properties": {
                        "primary_color": {"type": "string"},
                        "font_heading": {"type": "string"},
                        "font_body": {"type": "string"}
                    },
                    "required": ["primary_color", "font_heading", "font_body"]
                },
                "layout": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string", 
                                "enum": ["HeroMinimalist", "HeroEditorial", "HeroSplit", "GridServices", "ListServices", "FeatureServices", "AboutEditorial", "PricingTable", "ContactForm", "TestimonialCards", "GalleryGrid", "FooterMinimal", "FooterStandard"]
                            },
                            "props": {
                                "type": "object",
                                "description": "Propriedades específicas de cada componente. PricingTable: 'plans' ([name, price, features]). TestimonialCards: 'testimonials' ([quote, author]). GalleryGrid: 'images' ([url]). ContactForm: 'title'."
                            }
                        },
                        "required": ["type", "props"]
                    }
                }
            },
            "required": ["nome_limpo", "design_brief", "theme", "layout"]
        }

        try:
            resultado = ai.generate_structured(prompt, schema_hint=schema)
            if not _design_valido(resultado):
                raise AIResponseError("Design Director devolveu layout/tema/nome inválido ou vazio.")
            return resultado
        except AIError as e:
            logger.error(f"[AI] Falha no Design Director: {e}")
            # Fallback: marcado com ai_fallback=True para o pipeline não publicar um site genérico
            return {
                "ai_fallback": True,
                "nome_limpo": nome_bruto,
                "slogan": f"{nome_bruto} — {nicho}",
                "subtitulo": f"Atendimento especializado em {cidade}.",
                "design_brief": "Fallback — IA indisponível.",
                "theme": {
                    "primary_color": "#1C1C1C",
                    "secondary_color": "#666666",
                    "font_heading": "Inter",
                    "font_body": "Inter"
                },
                "layout": [
                    {
                        "type": "HeroMinimalist",
                        "props": {
                            "title": f"{nome_bruto} — {nicho}",
                            "subtitle": f"Atendimento especializado em {cidade}."
                        }
                    },
                    {
                        "type": "GridServices",
                        "props": {
                            "services": [
                                {"name": "Atendimento Especializado", "description": f"Soluções completas em {nicho}."}
                            ]
                        }
                    },
                    {
                        "type": "FooterMinimal",
                        "props": {
                            "text": f"© {nome_bruto}"
                        }
                    }
                ]
            }
