"""
SEO Optimizer — Generates metadata, schema.json, and SEO-optimized content for the generated sites.
"""
import logging
from typing import Dict, Any, List
from ai_service import ai

logger = logging.getLogger(__name__)

class SEOOptimizer:
    def generate_seo_package(self, lead_data: Dict[str, Any], design_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a complete SEO package including meta tags, schema, and keywords."""
        nome = design_data.get("nome_limpo", lead_data.get("nome", ""))
        nicho = lead_data.get("nicho", "Negócio Local")
        cidade = lead_data.get("cidade", "Brasil")
        
        prompt = f"""
        Gere um pacote de SEO otimizado para um novo site.
        
        NEGÓCIO: {nome}
        NICHO: {nicho}
        CIDADE: {cidade}
        BREVE DO DESIGN: {design_data.get('design_brief', '')}
        
        REGRAS:
        1. Meta Title deve ter entre 50-60 caracteres, incluindo a cidade.
        2. Meta Description deve ter entre 140-160 caracteres, persuasiva e com CTA.
        3. Gere 5 palavras-chave foco.
        4. Gere um objeto JSON-LD (Schema.org) do tipo 'LocalBusiness' ou similar adequado ao nicho.
        5. NÃO invente telefones ou endereços específicos se não fornecidos. Use placeholders genéricos como "Atendimento em {cidade}".
        
        Retorne um JSON puro.
        """
        
        schema = {
            "type": "object",
            "properties": {
                "meta_title": {"type": "string"},
                "meta_description": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "schema_json": {"type": "object", "description": "Objeto JSON-LD"},
                "seo_slugs": {"type": "array", "items": {"type": "string"}, "description": "Sugestões de slugs para páginas secundárias"}
            },
            "required": ["meta_title", "meta_description", "keywords", "schema_json"]
        }
        
        try:
            logger.info(f"[SEO] Gerando pacote para {nome}...")
            return ai.generate_structured(prompt, schema_hint=schema)
        except Exception as e:
            logger.error(f"[SEO] Falha ao gerar pacote: {e}")
            return {
                "meta_title": f"{nome} | {nicho} em {cidade}",
                "meta_description": f"Conheça a {nome}, especialista em {nicho} atendendo toda a região de {cidade}. Qualidade e confiança para você.",
                "keywords": [nicho, cidade, nome],
                "schema_json": {
                    "@context": "https://schema.org",
                    "@type": "LocalBusiness",
                    "name": nome,
                    "address": {"@type": "PostalAddress", "addressLocality": cidade}
                }
            }

def otimizar_seo(lead_data: Dict[str, Any], design_data: Dict[str, Any]) -> Dict[str, Any]:
    optimizer = SEOOptimizer()
    return optimizer.generate_seo_package(lead_data, design_data)
