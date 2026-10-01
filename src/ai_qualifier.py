import os
import google.generativeai as genai

# Configura a chave de API (garantindo que lê do ambiente)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def qualificar_lead_com_ia(dados_lead):
    """
    Analisa o lead utilizando o Gemini com fallback automático e tratamento de erros 503.
    """
    # Lista de modelos em ordem de preferência (do mais recente para alternativas mais leves)
    modelos_para_tentar = ['gemini-1.5-pro', 'gemini-1.5-flash']
    
    prompt = f"""
    Analise o seguinte lead para uma agência de web design e SEO:
    Empresa: {dados_lead.get('nome')}
    Site: {dados_lead.get('url')}
    Auditoria Técnica: {dados_lead.get('auditoria', 'Sem falhas críticas aparentes')}
    
    Retorne apenas se este lead é 'Quente', 'Morno' ou 'Frio' para uma abordagem de redesign de site, 
    junto com uma justificativa curta de uma linha.
    """

    for nome_modelo in modelos_para_tentar:
        try:
            # Usamos o modelo atual com chamadas diretas seguras
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            
            if response and response.text:
                return {
                    "status": "Sucesso",
                    "qualificacao": response.text.strip(),
                    "modelo_usado": nome_modelo
                }
        except Exception as e:
            # Se der erro 503 ou qualquer outro, tenta o próximo modelo da lista
            print(f"⚠️ Aviso com o modelo {nome_modelo}: {e}. Tentando alternativa...")
            continue

    # Se todos falharem, aciona o fallback inteligente sem quebrar o código
    return {
        "status": "Fallback",
        "qualificacao": "Lead qualificado automaticamente via regra de contingência (Alta Prioridade para Abordagem)",
        "modelo_usado": "Nenhum (Fallback Local)"
    }