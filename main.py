import os
import sys
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Adiciona o diretório src ao PYTHONPATH para garantir importações limpas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from site_generator import gerar_site_cliente
from deployer import fazer_deploy_site

# Configuração da Inteligência Artificial
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- DICIONÁRIO BLINDADO ANTI-ERROS ---
class DicionarioBlindado(dict):
    def __missing__(self, key):
        if 'imagem' in key or 'foto' in key or 'logo' in key or 'bg' in key:
            return "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&q=80"
        elif 'link' in key or 'url' in key:
            return "#"
        else:
            return ""

# --- SANITIZADOR DE SLUGS ---
def criar_slug_seguro(nome: str) -> str:
    nome = nome.lower().replace("ç", "c").replace("ã", "a").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    nome = re.sub(r'[^a-z0-9]', ' ', nome)
    nome = re.sub(r'\s+', '-', nome).strip('-')
    return nome[:50].strip('-')

# --- NOVO: MÓDULO DE INTELIGÊNCIA ARTIFICIAL (COPYWRITING) ---
def enriquecer_dados_com_ia(nome_bruto: str, nicho: str, cidade: str) -> dict:
    print("🧠 IA a analisar a marca e a criar copywriting de alta conversão...")
    
    prompt = f"""
    És um copywriter de elite a trabalhar para uma agência de web design.
    Recebeste um lead com os seguintes dados em bruto do Google:
    Nome Bruto: "{nome_bruto}"
    Nicho: "{nicho}"
    Localização: "{cidade}"
    
    A tua tarefa é extrair e criar os dados de marketing para o novo site. 
    Devolve APENAS um objeto JSON válido, sem formatação markdown, com as seguintes chaves:
    "nome_limpo": O nome comercial real e curto da empresa (extrai a melhor parte do nome bruto).
    "slogan": Uma frase de impacto curta e persuasiva para o título principal do site.
    "subtitulo": Um parágrafo curto de apoio ao slogan, destacando a excelência no atendimento em {cidade}.
    "depoimento_1": Uma frase de testemunho realista de um cliente satisfeito.
    "nome_cliente_1": Nome inventado para o cliente 1.
    "depoimento_2": Outro testemunho realista.
    "nome_cliente_2": Nome inventado para o cliente 2.
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        resposta = model.generate_content(prompt)
        
        # Limpar a formatação markdown se a IA a devolver
        texto_limpo = resposta.text.replace("```json", "").replace("```", "").strip()
        dados_ia = json.loads(texto_limpo)
        return dados_ia
    except Exception as e:
        print(f"⚠️ Erro na IA ({e}). A aplicar fallback básico.")
        nome_curto = nome_bruto.split('|')[-1].split('-')[-1].strip() # Tenta extrair a última parte
        return {
            "nome_limpo": nome_curto,
            "slogan": f"Excelência em {nicho}",
            "subtitulo": f"O melhor atendimento em {cidade} para si e para a sua família.",
            "depoimento_1": "Atendimento fantástico e muito profissional!",
            "nome_cliente_1": "Maria S.",
            "depoimento_2": "Recomendo vivamente, mudou a minha vida.",
            "nome_cliente_2": "João P."
        }

# --- GERADOR DE COPY DE VENDAS ---
def salvar_mensagem_whatsapp(nome_cliente: str, url_online: str):
    arquivo_msg = "mensagens_whatsapp.txt"
    mensagem = (
        f"==================================================\n"
        f"🏢 CLIENTE: {nome_cliente}\n"
        f"==================================================\n"
        f"Olá, equipa da {nome_cliente}! Tudo bem?\n\n"
        f"Dei uma vista de olhos na presença digital da vossa clínica e notei oportunidades de melhoria, principalmente na versão mobile.\n\n"
        f"Como sou especialista em web design para o vosso setor, adiantei-me e montei um protótipo de alta performance com um design muito mais premium.\n\n"
        f"Vejam como ficou a nova estrutura (já está no ar para testarem no telemóvel):\n"
        f"👉 {url_online}\n\n"
        f"O que acham de falarmos rapidamente sobre como um site deste nível pode multiplicar os vossos agendamentos?\n\n\n"
    )
    with open(arquivo_msg, 'a', encoding='utf-8') as f:
        f.write(mensagem)

def executar_pipeline_completo(nome_bruto: str, nicho: str, cidade: str):
    print(f"\n==================================================")
    print(f"🚀 A INICIAR PIPELINE DE GERAÇÃO & DEPLOY: {nome_bruto}")
    print(f"==================================================\n")
    
    # 1. Enriquecer com IA
    dados_ia = enriquecer_dados_com_ia(nome_bruto, nicho, cidade)
    nome_limpo = dados_ia.get("nome_limpo", nome_bruto)
    
    slug_gerado = criar_slug_seguro(nome_limpo)
    
    # Misturar os dados estáticos com a criatividade da IA
    dados_base = {
        "nome_empresa": nome_limpo,
        "slogan": dados_ia.get("slogan"),
        "subtitulo": dados_ia.get("subtitulo"),
        "nicho": nicho,
        "cidade": cidade,
        "slug_pasta": slug_gerado,
        "meta_description": f"{dados_ia.get('slogan')} - {cidade}",
        "titulo_seo": f"{nome_limpo} | {nicho}",
        "whatsapp": "5511999999999",
        "telefone": "(11) 99999-9999",
        "cor_primaria": "#2563eb",
        "imagem_hero": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&q=80&w=1200",
        "depoimento_1": dados_ia.get("depoimento_1"),
        "nome_cliente_1": dados_ia.get("nome_cliente_1"),
        "depoimento_2": dados_ia.get("depoimento_2"),
        "nome_cliente_2": dados_ia.get("nome_cliente_2")
    }
    
    dados_cliente = DicionarioBlindado(dados_base)
    
    print(f"[1/3] A forjar a obra-prima digital para '{nome_limpo}'...")
    gerar_site_cliente(dados_cliente)
    print(f"✅ Site gerado com sucesso na pasta: clientes_gerados/{slug_gerado}")
    
    print(f"\n[2/3] A subir o site para a nuvem da Vercel...")
    url_online = fazer_deploy_site(slug_gerado)
    
    if url_online:
        print(f"\n[3/3] A criar guião de abordagem de vendas...")
        salvar_mensagem_whatsapp(nome_limpo, url_online)
        print(f"✅ Guião guardado no ficheiro 'mensagens_whatsapp.txt'")
        
        print(f"\n🎉 SUCESSO: {nome_limpo}")
        print(f"🌐 Link no Ar: {url_online}")
    else:
        print("⚠️ O site foi gerado localmente, mas ocorreu um erro no deploy automático.")

if __name__ == "__main__":
    arquivo_leads = "leads_qualificados.json"
    
    if os.path.exists("mensagens_whatsapp.txt"):
        os.remove("mensagens_whatsapp.txt")
        
    if os.path.exists(arquivo_leads):
        with open(arquivo_leads, 'r', encoding='utf-8') as f:
            try:
                leads = json.load(f)
                print(f"\n📦 A INICIAR PROCESSAMENTO EM LOTE: Encontrados {len(leads)} leads reais!")
                
                for lead in leads:
                    nome = lead.get('nome', 'Empresa Desconhecida')
                    nicho = lead.get('nicho', 'Clínica Odontológica')
                    cidade = lead.get('cidade', 'Bragança Paulista')
                    
                    executar_pipeline_completo(nome_bruto=nome, nicho=nicho, cidade=cidade)
                    
                print("\n✅✅✅ TODOS OS LEADS PROCESSADOS! Verifique o ficheiro 'mensagens_whatsapp.txt' ✅✅✅")
                
            except json.JSONDecodeError:
                print("❌ Erro ao ler o ficheiro JSON.")
    else:
        executar_pipeline_completo(nome_bruto="Dentista em Bragança Paulista | Brag Dentes", nicho="Odontologia Estética", cidade="Bragança Paulista")