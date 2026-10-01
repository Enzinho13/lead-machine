import json
import time
from src.lead_scraper import buscar_empresas
from src.auditor import auditar_site
from src.ai_qualifier import qualificar_lead
from src.outreach import gerar_mensagem

def executar_pipeline():
    termo = "clínica odontológica Bragança Paulista"
    print(f"=== INICIANDO PIPELINE COMPLETO DE PROSPECÇÃO ===")
    
    # 1. Busca
    leads_brutos = buscar_empresas(termo, max_resultados=3) # Reduzido para 3 para teste rápido
    if not leads_brutos:
        print("Nenhum lead encontrado.")
        return

    leads_finais = []

    for lead in leads_brutos:
        url = lead['site']
        if "guiatelefone" in url or "comerciosaopaulo" in url:
            continue
            
        print(f"\nProcessando: {lead['titulo']}")
        
        # 2. Auditoria
        auditoria = auditar_site(url)
        if not auditoria:
            continue
            
        # 3. Qualificação
        qualificacao = qualificar_lead(lead['titulo'], auditoria)
        if not qualificacao:
            continue
            
        # 4. Mensagem de Prospecção
        mensagem = gerar_mensagem(lead['titulo'], qualificacao)
        
        # Consolida tudo no perfil do lead para o CRM
        lead_completo = {
            "nome": lead['titulo'],
            "url": url,
            "score": qualificacao.get('lead_score', 0),
            "prioridade": qualificacao.get('priority', 'low'),
            "problemas": qualificacao.get('main_problems', []),
            "servico_recomendado": qualificacao.get('recommended_service', ''),
            "mensagem_pronta": mensagem,
            "status": "NOVO" # Status inicial para o CRM
        }
        
        leads_finais.append(lead_completo)
        time.sleep(2)

    # 5. Salva no "Banco de Dados" do CRM
    nome_arquivo = "leads_qualificados.json"
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        json.dump(leads_finais, f, ensure_ascii=False, indent=4)
        
    print(f"\n✅ Pipeline concluído! {len(leads_finais)} leads prontos no arquivo '{nome_arquivo}'.")

if __name__ == "__main__":
    executar_pipeline()