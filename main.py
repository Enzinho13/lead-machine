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

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

class DicionarioBlindado(dict):
    def __missing__(self, key):
        return ""

def criar_slug_seguro(nome: str) -> str:
    import re
    nome = nome.lower().replace("ç", "c").replace("ã", "a").replace("á", "a").replace("é", "e")
    nome = re.sub(r'[^a-z0-9]', ' ', nome)
    nome = re.sub(r'\s+', '-', nome).strip('-')
    return nome[:50]

def salvar_mensagem_whatsapp(nome_cliente: str, url_online: str):
    arquivo_msg = "mensagens_whatsapp.txt"
    mensagem = (
        f"==================================================\n"
        f"🏢 CLIENTE: {nome_cliente}\n"
        f"==================================================\n"
        f"Olá, equipe da {nome_cliente}! Tudo bem?\n\n"
        f"Fiz uma auditoria técnica no site atual de vocês e identifiquei oportunidades claras de melhoria no design e conversão.\n\n"
        f"Como especialista no setor, montei um protótipo de alta performance respeitando a identidade da marca, mas com uma arquitetura editorial premium.\n\n"
        f"Vejam a diferença:\n👉 {url_online}\n\n"
        f"Gostariam de agendar 10 minutos para falarmos sobre como esta estrutura pode aumentar os vossos contactos diários?\n\n\n"
    )
    with open(arquivo_msg, 'a', encoding='utf-8') as f:
        f.write(mensagem)

def enriquecer_dados_com_ia(nome_bruto: str, nicho: str, cidade: str, dados_auditoria: dict) -> dict:
    print(f"[AI] Iniciando Design Director para: {nome_bruto}...")
    
    # Injetando contexto real (se houver)
    contexto_extra = ""
    if dados_auditoria.get("status") == "Sucesso":
        contexto_extra = f"""
        [ATENÇÃO] O cliente JÁ POSSUI um site. Extraí os textos atuais deles:
        {dados_auditoria.get('textos_principais')}
        
        USE ESTES TEXTOS como base para entender EXATAMENTE os serviços que eles prestam (ex: se forem advogados criminais, não coloque direito tributário). 
        Melhore o copywriting deles para algo mais persuasivo e premium.
        """
        if dados_auditoria.get('cor_detectada'):
            contexto_extra += f"\nA cor meta do site atual é {dados_auditoria['cor_detectada']}. Inspire-se nisso ou crie um tom mais luxuoso."

    prompt = f"""
    Atue como um Diretor de Arte Sênior. 
    Cliente: "{nome_bruto}" | Nicho: "{nicho}" | Cidade: "{cidade}"
    
    {contexto_extra}
    
    Devolva APENAS JSON válido com as seguintes chaves EXATAS:
    "nome_limpo": O nome comercial limpo.
    "slogan": Frase de impacto para o hero.
    "subtitulo": Parágrafo de apoio persuasivo.
    "cor_destaque": Código HEX sofisticado adequado ao nicho (ex: #3B2F2F para advogados).
    "tema_imagem": Um prompt EM INGLÊS que descreva o cenário/fundo (ex: "luxurious law firm office", "modern dental clinic"). SEM TEXTOS NA IMAGEM.
    "servico_1_titulo": Nome do principal serviço prestado.
    "servico_1_desc": Descrição curta.
    "servico_2_titulo": Nome do serviço 2.
    "servico_2_desc": Descrição curta.
    "servico_3_titulo": Nome do serviço 3.
    "servico_3_desc": Descrição curta.
    """
    
    try:
        # FASE 2: Output Estruturado Nativo do Gemini
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
        resposta = model.generate_content(prompt)
        return json.loads(resposta.text)
    except Exception as e:
        print(f"[AI ERROR] Falha no parse: {e}")
        return {}

# Agora o pipeline exige a URL para auditar
def executar_pipeline_completo(nome_bruto: str, nicho: str, cidade: str, url_lead: str):
    # 1. Auditoria
    dados_auditoria = auditar_site_lead(url_lead)
    
    # 2. IA Contextualizada
    dados_ia = enriquecer_dados_com_ia(nome_bruto, nicho, cidade, dados_auditoria)
    
    nome_limpo = dados_ia.get("nome_limpo", nome_bruto[:20])
    slug_gerado = criar_slug_seguro(nome_limpo)
    
    # Imagem adaptativa
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
        "cor_primaria": dados_ia.get("cor_destaque", "#1C1C1C"), # Fallback neutro
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
        salvar_mensagem_whatsapp(nome_limpo, url_online)
        
    return url_online