import os
import json
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

def qualificador_local_fallback(nome_empresa: str, auditoria: dict):
    """
    Plano B: Se a IA externa falhar, usamos lógica de programação (Engenharia de Software clássica) 
    para simular a qualificação e não travar o pipeline.
    """
    problemas = auditoria.get('problemas', [])
    
    # Calculamos o score com base na quantidade de erros (quanto mais erros, melhor o lead)
    score_base = 30 + (len(problemas) * 20)
    lead_score = min(score_base, 95) # Limita a nota a 95
    
    priority = "high" if lead_score >= 70 else ("medium" if lead_score >= 50 else "low")
    
    return {
        "lead_score": lead_score,
        "priority": priority,
        "main_problems": problemas[:2], # Pegamos os 2 primeiros problemas
        "recommended_service": "Reformulação completa com foco em SEO e Conversão" if priority == "high" else "Otimização técnica de SEO",
        "reason": f"O site possui {len(problemas)} problemas técnicos evidentes que prejudicam a aquisição de clientes."
    }

def qualificar_lead(nome_empresa: str, auditoria: dict):
    print(f"🧠 IA analisando o lead: {nome_empresa}...")
    
    prompt = f"""
    Você é um consultor de vendas. Analise os dados da auditoria deste site e retorne um JSON estrito.
    Empresa: {nome_empresa}
    Dados: {json.dumps(auditoria, ensure_ascii=False)}
    Retorne EXATAMENTE este JSON: {{"lead_score": 85, "priority": "high", "main_problems": ["..."], "recommended_service": "...", "reason": "..."}}
    """
    
    # Vamos tentar apenas 1 vez para não perder tempo. Se falhar, aciona o Fallback.
    try:
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
        )
        texto_resposta = response.text.strip()
        if texto_resposta.startswith("```json"):
            texto_resposta = texto_resposta.replace("```json", "", 1).replace("```", "")
        return json.loads(texto_resposta)
        
    except Exception as e:
        print(f" ⚠️ IA Indisponível no momento ({e}).")
        print(" 🔄 Acionando motor de Fallback de contingência local...")
        return qualificador_local_fallback(nome_empresa, auditoria)

if __name__ == "__main__":
    caminho_arquivo = "../leads_qualificados.json" if not os.path.exists("leads_qualificados.json") else "leads_qualificados.json"
    
    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            leads = json.load(f)
            
        if leads:
            primeiro_lead = leads[0]
            resultado = qualificar_lead(primeiro_lead['titulo'], primeiro_lead['auditoria'])
            
            print("\n=== RESULTADO DA QUALIFICAÇÃO ===")
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
            print("=================================\n")
        else:
            print("Nenhum lead encontrado no JSON.")
            
    except FileNotFoundError:
        print("Arquivo leads_qualificados.json não encontrado. Rode o main.py primeiro.")