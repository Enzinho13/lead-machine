import streamlit as st
import os
import sys
import time
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from main import executar_pipeline_completo
from database import get_all_leads, update_lead_status, init_db

try:
    from lead_scraper import buscar_empresas
except ImportError:
    st.error("⚠ Falha crítica: Módulo de discovery inacessível.")

# --- BARREIRA DE PROTEÇÃO ---
init_db()

st.set_page_config(page_title="Lead Machine | Megabrain", page_icon="🧠", layout="wide")
st.title("🧠 Lead Machine - Command Center")
col1, col2 = st.columns([1, 2])

with col1:
    st.header("🎯 1. Discovery Engine")
    nicho_alvo = st.text_input("Qual é o Nicho?", placeholder="Ex: Escritorio de Advogados")
    cidade_alvo = st.text_input("Qual é a Região/Cidade?", placeholder="Ex: São Paulo")
    max_leads = st.slider("Alvo de leads limpos:", min_value=5, max_value=50, value=15)
    
    if st.button("🔍 Iniciar Discovery"):
        if nicho_alvo and cidade_alvo:
            with st.spinner(f"Executando crawler para {max_leads} leads limpos..."):
                try:
                    buscar_empresas(nicho_alvo, cidade_alvo, max_resultados=max_leads)
                    st.success("Discovery concluído. Banco de dados atualizado.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"[SYSTEM ERROR] {e}")
        else:
            st.warning("Parâmetros de busca insuficientes.")

with col2:
    st.header("⚙️ 2. Radar de Qualificação & Pipeline")
    
    leads = get_all_leads()
    
    if leads:
        df = pd.DataFrame(leads)
        
        # --- SISTEMA DE ABAS ---
        tab_pendentes, tab_concluidos = st.tabs(["🔴 Fila de Trabalho (Pendentes)", "🟢 Deploys Concluídos"])
        
        with tab_pendentes:
            df_pendentes = df[df['status'].isin(['NEW', 'AUDITED'])].copy()
            
            if not df_pendentes.empty:
                leads_para_auditar = df_pendentes[df_pendentes['status'] == 'NEW'].to_dict('records')
                
                if len(leads_para_auditar) > 0:
                    st.info(f"Existem {len(leads_para_auditar)} leads sem auditoria.")
                    if st.button("🔎 Executar Auditoria Técnica e Calcular Scores"):
                        from auditor import auditar_site_lead
                        from database import update_lead_score
                        
                        barra = st.progress(0)
                        for i, lead in enumerate(leads_para_auditar):
                            dados_auditoria = auditar_site_lead(lead['url'])
                            update_lead_score(lead['url'], dados_auditoria['score'], dados_auditoria['motivos'])
                            barra.progress((i + 1) / len(leads_para_auditar))
                        st.success("Auditoria concluída!")
                        time.sleep(1)
                        st.rerun()

                st.markdown("### Selecione os Alvos (Score baixo = Venda fácil)")
                df_pendentes.insert(0, "Deploy", False) 
                
                cols = ["Deploy", "score", "motivos_score", "nome", "url"]
                df_view = df_pendentes[[c for c in cols if c in df_pendentes.columns]]
                
                edited_df = st.data_editor(
                    df_view,
                    column_config={
                        "Deploy": st.column_config.CheckboxColumn("Atacar?"),
                        "score": st.column_config.NumberColumn("Score (0-100)"),
                        "motivos_score": st.column_config.TextColumn("Falhas Encontradas"),
                        "url": st.column_config.LinkColumn("Site Original")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                leads_para_ataque = edited_df[edited_df["Deploy"] == True].to_dict('records')
                
                if st.button(f"🚀 Acionar Pipeline para {len(leads_para_ataque)} leads", type="primary", disabled=len(leads_para_ataque)==0):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, lead in enumerate(leads_para_ataque):
                        nome_cli = lead['nome']
                        url_cli = lead['url']
                        status_text.text(f"[PIPELINE] Gerando infraestrutura para: {nome_cli}...")
                        
                        # AGARRA O LINK AQUI
                        link_vercel = executar_pipeline_completo(nome_cli, lead.get('nicho', 'Nicho'), lead.get('cidade', 'Cidade'), url_cli)
                        
                        # GUARDA O LINK NO BANCO
                        update_lead_status(url_cli, 'DEPLOYED', vercel_url=link_vercel if link_vercel else '')
                        
                        progress_bar.progress((i + 1) / len(leads_para_ataque))
                        
                    st.success("[PIPELINE] Ciclo concluído.")
                    time.sleep(1.5)
                    st.rerun()
            else:
                st.info("Não há leads pendentes nesta fila.")
                
        with tab_concluidos:
            # Mostra apenas os leads que já foram processados
            df_concluidos = df[df['status'] == 'DEPLOYED'].copy()
            if not df_concluidos.empty:
                st.success(f"Você já gerou infraestrutura para {len(df_concluidos)} leads!")
                
                # PREPARA A COLUNA DO LINK VERCEL
                cols_concluidos = ["nome", "nicho", "cidade", "vercel_url"]
                df_view_concluidos = df_concluidos[[c for c in cols_concluidos if c in df_concluidos.columns]]
                
                st.dataframe(
                    df_view_concluidos,
                    column_config={
                        "vercel_url": st.column_config.LinkColumn("🔥 Site Gerado (Vercel)")
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Ainda não fez nenhum deploy com sucesso.")
    else:
        st.info("Database vazio. Inicie o Discovery Engine.")