import streamlit as st
import os
import json
import sys

# Adiciona a pasta src ao caminho para podermos importar o scraper
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from main import executar_pipeline_completo

# IMPORTANTE: Importe a função principal do seu scraper aqui.
# Substitua 'executar_scraper' pelo nome real da função que está dentro do seu lead_scraper.py
try:
    from lead_scraper import buscar_empresas
except ImportError:
    st.error("⚠️ Não foi possível importar o scraper. Verifique o nome da função no ficheiro src/lead_scraper.py")

st.set_page_config(page_title="Lead Machine | Dashboard", page_icon="🚀", layout="wide")

st.title("🚀 Lead Machine - Agência Automatizada")
st.markdown("Bem-vindo ao painel de controlo. Gere leads reais e faça deploys de alta conversão com um clique.")

col1, col2 = st.columns(2)

with col1:
    st.header("🎯 1. Definir Alvo (Scraper Real)")
    nicho_alvo = st.text_input("Qual é o Nicho?", placeholder="Ex: Harmonização Facial")
    cidade_alvo = st.text_input("Qual é a Região/Cidade?", placeholder="Ex: Brooklin, São Paulo")
    
    if st.button("🔍 Iniciar Raspagem de Dados"):
        if nicho_alvo and cidade_alvo:
            with st.spinner(f"A varrer a internet por {nicho_alvo} em {cidade_alvo}... Isto pode demorar alguns minutos."):
                
                # --- LIGAÇÃO AO SCRAPER REAL ---
                termo_busca = f"{nicho_alvo} em {cidade_alvo}"
                try:
                    # Chama a sua função real. Ajuste os parâmetros se o seu scraper exigir nomes diferentes
                    buscar_empresas(termo_busca)
                    st.success(f"Busca concluída! A base de dados 'leads_qualificados.json' foi atualizada com leads de {cidade_alvo}.")
                except Exception as e:
                    st.error(f"Ocorreu um erro ao rodar o scraper: {e}")
                    
        else:
            st.warning("Por favor, preencha o Nicho e a Cidade.")

with col2:
    st.header("⚙️ 2. Máquina de Vendas")
    st.markdown("Verifique os leads encontrados e inicie a geração de sites e deploys na Vercel.")
    
    if os.path.exists("leads_qualificados.json"):
        with open("leads_qualificados.json", "r", encoding="utf-8") as f:
            try:
                leads = json.load(f)
                st.dataframe(leads) 
                
                if st.button("🚀 Iniciar Geração & Deploy em Lote", type="primary"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, lead in enumerate(leads):
                        status_text.text(f"A processar: {lead['nome']}...")
                        
                        executar_pipeline_completo(
                            nome_bruto=lead['nome'], 
                            nicho=lead.get('nicho', nicho_alvo), 
                            cidade=lead.get('cidade', cidade_alvo)
                        )
                        
                        progress_bar.progress((i + 1) / len(leads))
                        st.success(f"✅ Deploy concluído para: {lead['nome']}")
                    
                    status_text.text("Todos os sites estão no ar!")
                    st.balloons() 
                    
            except json.JSONDecodeError:
                st.info("O ficheiro de leads está vazio ou mal formatado. Faça uma nova busca.")
    else:
        st.info("Faça uma busca primeiro para encontrar leads.")

st.markdown("---")
st.subheader("📱 Mensagens de Abordagem")
if os.path.exists("mensagens_whatsapp.txt"):
    with open("mensagens_whatsapp.txt", "r", encoding="utf-8") as f:
        mensagens = f.read()
        st.text_area("Copie os guiões abaixo para enviar aos clientes:", value=mensagens, height=300)
else:
    st.text("Os guiões aparecerão aqui após os deploys.")