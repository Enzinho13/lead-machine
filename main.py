import os
import sys
import json
import urllib.parse
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from site_generator import gerar_site_cliente
from deployer import fazer_deploy_site
from auditor import auditar_site_lead
from database import save_outreach_data

# --- AI LAYER ---
class AIService:
    def __init__(self):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})

    def generate_structured(self, prompt: str) -> dict:
        try:
            resposta = self.model.generate_content(prompt)
            return json.loads(resposta.text)
        except Exception as e:
            print(f"[AI ERROR] Parse failed: {e}")
            return {}

ai_service = AIService()

class DicionarioBlindado(dict):
    def __missing__(self, key):
        return ""

def criar_slug_seguro(nome: str) -> str:
    import re
    nome = nome.lower().replace("ç", "c").replace("ã", "a").replace("á", "a").replace("é", "e")
    nome = re.sub(r'[^a-z0-9]', ' ', nome)
    return re.sub(r'\s+', '-', nome).strip('-')[:50]

def gerar_outreach_personalizado(nome_cliente: str, url_online: str, dados_auditoria: dict) -> str:
    falhas = dados_auditoria.get("motivos", "site genérico")
    score = dados_auditoria.get("score", 0)
    
    mensagem = (
        f"==================================================\n"
        f"🏢 CLIENTE: {nome_cliente}\n"
        f"==================================================\n"
        f"Olá, equipe da {nome_cliente}! Tudo bem?\n\n"
        f"Fizemos uma auditoria técnica no site atual de vocês e o sistema registrou um score de {score}/100.\n"
        f"Identificamos os seguintes gargalos técnicos que prejudicam o tráfego: {falhas}.\n\n"
        f"Como especialista no setor, montei um protótipo de alta performance focado em conversão.\n\n"
        f"Veja a diferença:\n👉 {url_online}\n\n"
        f"Gostariam de agendar 10 minutos para falarmos sobre a estrutura?\n\n"
    )
    
    with open("mensagens_whatsapp.txt", 'a', encoding='utf-8') as f:
        f.write(mensagem)
        
    return mensagem

def enriquecer_dados_com_ia(nome_bruto: str, nicho: str, cidade: str, dados_auditoria: dict) -> dict:
    print(f"[AI] Iniciando Design Director para: {nome_bruto}...")
    
    contexto_extra = ""
    if dados_auditoria.get("status") == "Sucesso":
        contexto_extra = f"""
        [ATENÇÃO] Cliente JÁ POSSUI site. Textos extraídos:
        {dados_auditoria.get('textos_principais')}
        
        Cor atual detectada: {dados_auditoria.get('cor_detectada', 'Nenhuma')}.
        """

    prompt = f"""
    Atue como um Diretor de Arte Sênior. 
    Cliente: "{nome_bruto}" | Nicho: "{nicho}" | Cidade: "{cidade}"
    
    {contexto_extra}
    
    Devolva APENAS JSON válido com as seguintes chaves EXATAS:
    "nome_limpo": O nome comercial limpo.
    "slogan": Frase de impacto para o hero.
    "subtitulo": Parágrafo de apoio persuasivo.
    "cor_destaque": Código HEX sofisticado adequado ao nicho.
    "tema_imagem": Prompt EM INGLÊS que descreva o cenário/fundo (SEM TEXTOS NA IMAGEM).
    "servico_1_titulo": Nome do principal serviço.
    "servico_1_desc": Descrição curta.
    "servico_2_titulo": Serviço 2.
    "servico_2_desc": Descrição curta.
    "servico_3_titulo": Serviço 3.
    "servico_3_desc": Descrição curta.
    "design_brief": Parágrafo resumindo as decisões de design e tom de voz.
    """
    
    return ai_service.generate_structured(prompt)

def executar_pipeline_completo(nome_bruto: str, nicho: str, cidade: str, url_lead: str):
    dados_auditoria = auditar_site_lead(url_lead)
    dados_ia = enriquecer_dados_com_ia(nome_bruto, nicho, cidade, dados_auditoria)
    
    nome_limpo = dados_ia.get("nome_limpo", nome_bruto[:20])
    slug_gerado = criar_slug_seguro(nome_limpo)
    
    tema_imagem = dados_ia.get("tema_imagem", "luxury minimalist corporate office")
    prompt_img_seguro = urllib.parse.quote(f"Architectural photography of {tema_imagem}, cinematic lighting, highly detailed")
    imagem_hero_dinamica = f"https://image.pollinations.ai/prompt/{prompt_img_seguro}?width=1200&height=800&nologo=true"
    
    dados_base = {
        "nome_empresa": nome_limpo,
        "slogan": dados_ia.get("slogan", "A excelência que procura."),
        "subtitulo": dados_ia.get("subtitulo", f"O melhor atendimento em {cidade}."),
        "cidade": cidade,
        "telefone": "(11) 99999-9999",
        "whatsapp": "5511999999999",
        "slug_pasta": slug_gerado,
        "cor_primaria": dados_ia.get("cor_destaque", "#1C1C1C"),
        "imagem_hero": imagem_hero_dinamica,
        "servicos": [
            {"titulo": dados_ia.get("servico_1_titulo", "Atendimento Premium"), "desc": dados_ia.get("servico_1_desc", "Soluções completas.")},
            {"titulo": dados_ia.get("servico_2_titulo", "Consultoria Especializada"), "desc": dados_ia.get("servico_2_desc", "Expertise focada.")},
            {"titulo": dados_ia.get("servico_3_titulo", "Suporte Completo"), "desc": dados_ia.get("servico_3_desc", "Resultados comprovados.")}
        ]
    }
    
    dados_cliente = DicionarioBlindado(dados_base)
    print(f"[SITE GEN] Renderizando código de '{nome_limpo}'...")
    gerar_site_cliente(dados_cliente)
    
    print(f"[DEPLOY] Acionando pipeline da Vercel...")
    url_online = fazer_deploy_site(slug_gerado)
    
    if url_online:
        # FASE 8 & CRM: Outreach gerado salva no DB
        msg_outreach = gerar_outreach_personalizado(nome_limpo, url_online, dados_auditoria)
        brief = dados_ia.get("design_brief", "Design atualizado para melhoria de conversão.")
        save_outreach_data(url_lead, msg_outreach, brief)
        
    return url_online