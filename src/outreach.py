import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

def gerar_mensagem(nome_empresa: str, qualificacao: dict):
    """
    Transforma a análise técnica em uma mensagem comercial amigável e direta.
    """
    print(f"✍️ Escrevendo mensagem personalizada para: {nome_empresa}...")
    
    # Extraímos os problemas da qualificação
    problemas = qualificacao.get('main_problems', [])
    motivo = qualificacao.get('reason', '')
    
    prompt = f"""
    Você é um desenvolvedor web. Escreva uma mensagem de prospecção curta e natural para o WhatsApp desta empresa.
    
    Empresa: {nome_empresa}
    Problemas técnicos reais do site deles: {', '.join(problemas)}
    Impacto: {motivo}
    
    REGRAS DA MENSAGEM:
    1. Seja educado, humano e direto.
    2. NÃO pareça um robô ou vendedor agressivo. Sem spam.
    3. Traduza os problemas técnicos (meta description, alt tag) para uma linguagem de negócios simples (ex: "estão perdendo visibilidade nas buscas locais").
    4. Termine com uma pergunta leve para iniciar a conversa (ex: "Faz sentido batermos um papo rápido sobre isso?").
    5. Retorne APENAS o texto da mensagem, sem aspas, sem formatação extra.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
        )
        return response.text.strip()
        
    except Exception as e:
        print(f" ⚠️ IA Indisponível. Usando Fallback de template estático: {e}")
        # Se a IA cair, usamos um template padrão preenchido com as variáveis
        problemas_str = " e ".join(problemas[:2]) if problemas else "alguns detalhes técnicos"
        return f"Olá, equipe da {nome_empresa}! Dei uma olhada no site de vocês e notei {problemas_str}. Isso pode estar prejudicando a captação de novos pacientes pelo Google. Vocês teriam interesse em ver como podemos corrigir isso?"

if __name__ == "__main__":
    # Vamos simular a passagem de dados usando exatamente o JSON que o seu terminal gerou
    qualificacao_mock = {
      "lead_score": 85,
      "priority": "high",
      "main_problems": [
        "Falta de Meta Description",
        "8 imagens da página sem texto alternativo (alt tag)"
      ],
      "reason": "Afeta diretamente a visibilidade nas buscas locais e a conversão de pacientes potenciais."
    }
    
    mensagem = gerar_mensagem("Odontoclinic (Unidade Bragança Paulista)", qualificacao_mock)
    
    print("\n=== MENSAGEM DE PROSPECÇÃO GERADA ===")
    print(mensagem)
    print("======================================\n")