import requests
from bs4 import BeautifulSoup

def auditar_site(url: str):
    """
    Baixa o HTML do site e procura problemas estruturais reais
    para usarmos na nossa abordagem de vendas.
    """
    print(f"Inspecionando o código de: {url} ...")
    
    # Nos disfarçamos de navegador comum para o site não nos bloquear
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Pede a página com limite de 10 segundos para não travar nosso sistema
        resposta = requests.get(url, headers=headers, timeout=10)
        resposta.raise_for_status()
        
        # O BeautifulSoup transforma o texto do site em algo que o Python entende
        soup = BeautifulSoup(resposta.text, 'html.parser')
        
        problemas = []
        oportunidades = []
        
        # 1. VERIFICAÇÃO DE MOBILE (Viewport)
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            problemas.append("Site antigo, sem tag de responsividade (Não otimizado para celular).")
            
        # 2. VERIFICAÇÃO DE SEO BÁSICO (Title e Description)
        title = soup.title.string if soup.title else None
        if not title:
            problemas.append("Site não possui tag de Título (Péssimo para o Google).")
            
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if not meta_desc:
            problemas.append("Falta a Meta Description (Baixa taxa de clique no Google).")
            
        # 3. VERIFICAÇÃO DE ACESSIBILIDADE E SEO DE IMAGENS (Alt Text)
        imagens = soup.find_all("img")
        imagens_sem_alt = [img for img in imagens if not img.get("alt")]
        
        if len(imagens_sem_alt) > 0:
            problemas.append(f"{len(imagens_sem_alt)} imagens sem atributo 'alt' (Prejudica acessibilidade e SEO).")
            
        # 4. VERIFICAÇÃO DE H1 (Título principal da página)
        h1_tags = soup.find_all("h1")
        if len(h1_tags) == 0:
            problemas.append("A página principal não possui a tag H1 (Falta hierarquia de texto).")
        elif len(h1_tags) > 1:
            oportunidades.append(f"A página tem {len(h1_tags)} tags H1. O ideal é ter apenas uma bem definida.")
            
        return {
            "url": url,
            "total_imagens": len(imagens),
            "problemas": problemas,
            "oportunidades": oportunidades
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar o site: {e}")
        return None

if __name__ == "__main__":
    # Testando com a mesma URL que falhou antes
    site_teste = "https://odontoclinic.com.br/unidades/braganca-paulista/"
    
    resultado = auditar_site(site_teste)
    
    if resultado:
        print("\n=== RELATÓRIO DA AUDITORIA INTERNA ===")
        print(f"URL: {resultado['url']}")
        
        print("\nPROBLEMAS ENCONTRADOS:")
        if resultado['problemas']:
            for p in resultado['problemas']:
                print(f" ❌ {p}")
        else:
            print(" ✅ Nenhum problema crítico encontrado.")
            
        print("\nOPORTUNIDADES DE MELHORIA:")
        if resultado['oportunidades']:
            for o in resultado['oportunidades']:
                print(f" 💡 {o}")
        else:
            print(" - Nenhuma oportunidade extra destacada.")
            
        print("======================================\n")