"""
Lead Machine — Dashboard (Streamlit)
Command center for the full pipeline and CRM.
"""
import streamlit as st
import os
import sys
import time
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from database import init_db, get_all_leads, update_lead_status, update_lead_score, get_leads_by_status, save_audit, get_lead_with_audit
from lead_scraper import buscar_empresas
from auditor import auditar_site_lead
from ai_qualifier import qualificar_lead_com_ia
from main import executar_pipeline_e_atualizar_status
from outreach import analisar_contatos

# --- Init ---
init_db()

st.set_page_config(page_title="Lead Machine", page_icon="🧠", layout="wide")
st.title("🧠 Lead Machine — Command Center")

CRM_STATES = ["NEW", "DISCOVERED", "AUDITING", "AUDITED", "QUALIFIED", "DEPLOYED", "CONTACTED", "REPLIED", "MEETING", "PROPOSAL", "WON", "LOST"]

# --- Sidebar: CRM Stats ---
with st.sidebar:
    st.header("📊 CRM Metrics")
    all_leads = get_all_leads()
    if all_leads:
        status_counts = {s: 0 for s in CRM_STATES}
        for lead in all_leads:
            s = lead.get("status", "NEW")
            if s in status_counts:
                status_counts[s] += 1
            else:
                status_counts[s] = 1
                
        for status in CRM_STATES:
            if status_counts.get(status, 0) > 0:
                st.metric(status, status_counts[status])
    st.divider()
    st.caption(f"Total: {len(all_leads)} leads")

# --- Main Layout ---
tab_discovery, tab_pipeline, tab_crm = st.tabs([
    "🎯 Discovery Engine", 
    "⚙️ Qualification Pipeline",
    "💼 CRM Manager"
])

# === DISCOVERY ===
with tab_discovery:
    col_d1, col_d2 = st.columns([1, 2])
    with col_d1:
        st.subheader("Buscar Novos Leads")
        nicho = st.text_input("Nicho", placeholder="Ex: Escritório de Advogados")
        cidade = st.text_input("Cidade/Região", placeholder="Ex: São Paulo")
        max_leads = st.slider("Quantidade de leads:", min_value=5, max_value=50, value=15)

        if st.button("🔍 Iniciar Discovery"):
            if nicho and cidade:
                with st.spinner(f"Buscando {max_leads} leads..."):
                    try:
                        buscar_empresas(nicho, cidade, max_resultados=max_leads)
                        st.success("Discovery concluído.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
            else:
                st.warning("Preencha nicho e cidade.")

# === PIPELINE ===
with tab_pipeline:
    if not all_leads:
        st.info("Database vazio. Inicie o Discovery Engine.")
    else:
        df = pd.DataFrame(all_leads)
        pending_statuses = ["NEW", "DISCOVERED", "AUDITED", "QUALIFIED"]
        df_pendentes = df[df["status"].isin(pending_statuses)].copy()

        if df_pendentes.empty:
            st.info("Não há leads pendentes no Pipeline.")
        else:
            # Audit action
            leads_new = df_pendentes[df_pendentes["status"].isin(["NEW", "DISCOVERED"])].to_dict("records")
            if leads_new:
                st.info(f"{len(leads_new)} leads aguardando auditoria.")
                if st.button("🔎 Executar Auditoria Técnica"):
                    bar = st.progress(0)
                    for i, lead in enumerate(leads_new):
                        update_lead_status(lead["url"], "AUDITING")
                        resultado = auditar_site_lead(lead["url"])
                        score = resultado.get("score", 0)
                        motivos = resultado.get("motivos", "")

                        checks = resultado.get("checks", {})
                        audit_row = {
                            "score": score,
                            "motivos": motivos,
                            "performance_time": checks.get("performance", {}).get("load_time", 0),
                            "has_https": checks.get("security", {}).get("has_https", False),
                            "has_viewport": checks.get("mobile", {}).get("has_viewport", False),
                            "has_h1": checks.get("seo", {}).get("has_h1", False),
                            "textos_principais": resultado.get("textos_principais", ""),
                            "cor_detectada": resultado.get("cor_detectada", ""),
                            "raw_data": resultado,
                        }
                        save_audit(lead["id"], audit_row)
                        update_lead_score(lead["url"], score, motivos)
                        # AI Qualifier logic
                        qual = qualificar_lead_com_ia({"auditoria": resultado})
                        if qual.get("priority") in ["high", "medium"]:
                            update_lead_status(lead["url"], "QUALIFIED")
                            
                        bar.progress((i + 1) / len(leads_new))

                    st.success("Auditoria concluída!")
                    time.sleep(1)
                    st.rerun()

            # Generation action
            st.markdown("### Lançar Geração e Deploy")
            df_pendentes.insert(0, "Atacar", False)

            cols = ["Atacar", "score", "nome", "url", "status", "motivos_score"]
            df_view = df_pendentes[[c for c in cols if c in df_pendentes.columns]]

            edited_df = st.data_editor(
                df_view,
                column_config={
                    "Atacar": st.column_config.CheckboxColumn("Atacar?"),
                    "score": st.column_config.NumberColumn("Score"),
                    "url": st.column_config.LinkColumn("Site Original"),
                },
                hide_index=True,
                width='stretch'
            )

            selected = edited_df[edited_df["Atacar"] == True].to_dict("records")

            if st.button(f"🚀 Acionar Gerador para {len(selected)} leads", type="primary", disabled=len(selected) == 0):
                bar = st.progress(0)
                status_text = st.empty()
                falhas = []

                for i, lead in enumerate(selected):
                    nome = lead["nome"]
                    url = lead["url"]
                    status_text.text(f"Processando: {nome}...")

                    # Pipeline: Design -> Component HTML -> QA -> Deploy -> Outreach Msg
                    link = executar_pipeline_e_atualizar_status(
                        nome,
                        lead.get("nicho", "Negócio"),
                        lead.get("cidade", "Brasil"),
                        url,
                    )

                    # DEPLOYED é atribuído dentro do helper, só quando o site é publicado
                    if not link:
                        falhas.append(nome)
                    bar.progress((i + 1) / len(selected))

                if falhas:
                    st.warning(f"Pipeline falhou para {len(falhas)} lead(s): {', '.join(falhas)}. Status mantido; veja os logs.")
                else:
                    st.success("Geração concluída!")
                    time.sleep(1.5)
                    st.rerun()

# === CRM MANAGER ===
with tab_crm:
    st.subheader("Operações CRM")
    if not all_leads:
        st.info("Nenhum lead encontrado.")
    else:
        df_crm = pd.DataFrame(all_leads)
        df_crm["contato"] = df_crm.apply(lambda lead: analisar_contatos(lead)["situacao"], axis=1)
        
        # Action to move states
        st.markdown("#### Atualizar Status do Lead")
        col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
        
        with col_c1:
            lead_selecionado = st.selectbox("Selecione o Lead:", df_crm['nome'] + " (" + df_crm['status'] + ")")
        with col_c2:
            novo_status = st.selectbox("Mover para:", CRM_STATES)
        with col_c3:
            st.write("") # spacing
            st.write("")
            if st.button("Mover", use_container_width=True):
                # find url
                idx = df_crm['nome'] + " (" + df_crm['status'] + ")" == lead_selecionado
                url_alvo = df_crm[idx]['url'].values[0]
                update_lead_status(url_alvo, novo_status)
                st.success(f"Status atualizado para {novo_status}!")
                time.sleep(1)
                st.rerun()

        st.markdown("---")
        st.markdown("#### Visão Geral dos Dados")
        
        st.dataframe(
            df_crm[["nome", "status", "score", "nicho", "cidade", "telefone", "email", "contato", "vercel_url", "url", "outreach_message"]],
            column_config={
                "url": st.column_config.LinkColumn("Site Original"),
                "vercel_url": st.column_config.LinkColumn("Site Gerado"),
                "outreach_message": st.column_config.TextColumn("Mensagem Gerada", width="large")
            },
            hide_index=True,
            width='stretch'
        )