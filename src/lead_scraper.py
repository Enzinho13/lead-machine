from ddgs import DDGS

def buscar_empresas(termo_busca: str, max_resultados: int = 5):
    """
    Busca potenciais clientes diretamente em motores de busca,
    simulando como um usuário normal procuraria por serviços.
    """
    print(f"Buscando leads para: '{termo_busca}' (aguarde)...")
    
    empresas = []
    try:
        # Inicializa o buscador com a nova biblioteca
        with DDGS() as ddgs:
            resultados = list(ddgs.text(termo_busca, max_results=max_resultados))
            
            for r in resultados:
                site_url = r.get('href', '')
                
                # Removemos redes sociais para focar apenas em sites próprios
                if site_url and "instagram.com" not in site_url and "facebook.com" not in site_url:
                    empresas.append({
                        "titulo": r.get('title', 'Sem título'),
                        "site": site_url,
                        "descricao": r.get('body', 'Sem descrição')
                    })
                    
        return empresas
        
    except Exception as e:
        print(f"Erro na requisição: {e}")
        return []

if __name__ == "__main__":
    leads = buscar_empresas("clínica odontológica Bragança Paulista", 5)
    
    print(f"\nEncontramos {len(leads)} sites reais para auditar:\n")
    for lead in leads:
        print(f"Empresa: {lead['titulo']}")
        print(f"Site: {lead['site']}")
        print("-" * 50)