"""
Lead Machine — Dashboard (Streamlit)
Command center for the full pipeline.
"""
import streamlit as st
import os
import sys
import time
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from database import init_db, get_all_leads, update_lead_status, update_lead_score, get_leads_by_status, save_audit
from lead_scraper import buscar_empresas
from auditor import auditar_site_lead
from ai_qualifier import qualificar_lead_com_ia
from main import executar_pipeline_completo

# --- Init ---
init_db()

st.set_page_config(page_title="Lead Machine", page_icon="🧠", layout="wide")
st.title("🧠 Lead Machine — Command Center")

# --- Sidebar: CRM Stats ---
with st.sidebar:
    st.header("📊 CRM")
    all_leads = get_all_leads()
    if all_leads:
        status_counts = {}
        for lead in all_leads:
            s = lead.get("status", "UNKNOWN")
            status_counts[s] = status_counts.get(s, 0) + 1
        for status, count in sorted(status_counts.items()):
            st.metric(status, count)
    st.divider()
    st.caption(f"Total: {len(all_leads)} leads")

# --- Main Layout ---
col1, col2 = st.columns([1, 2])

# === DISCOVERY ===
with col1:
    st.header("🎯 Discovery Engine")
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
with col2:
    st.header("⚙️ Pipeline de Qualificação")

    leads = get_all_leads()

    if not leads:
        st.info("Database vazio. Inicie o Discovery Engine.")
    else:
        df = pd.DataFrame(leads)

        tab_pendentes, tab_concluidos, tab_todos = st.tabs([
            "🔴 Fila de Trabalho",
            "🟢 Deploys Concluídos",
            "📋 Todos os Leads",
        ])

        # --- Pending tab ---
        with tab_pendentes:
            pending_statuses = ["NEW", "AUDITED", "QUALIFIED"]
            df_pendentes = df[df["status"].isin(pending_statuses)].copy()

            if df_pendentes.empty:
                st.info("Não há leads pendentes.")
            else:
                # Audit button
                leads_new = df_pendentes[df_pendentes["status"] == "NEW"].to_dict("records")
                if leads_new:
                    st.info(f"{len(leads_new)} leads aguardando auditoria.")
                    if st.button("🔎 Executar Auditoria Técnica"):
                        bar = st.progress(0)
                        for i, lead in enumerate(leads_new):
                            resultado = auditar_site_lead(lead["url"])
                            score = resultado.get("score", 0)
                            motivos = resultado.get("motivos", "")

                            # Save detailed audit
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
                            bar.progress((i + 1) / len(leads_new))

                        st.success("Auditoria concluída!")
                        time.sleep(1)
                        st.rerun()

                # Show pending leads
                st.markdown("### Selecione Alvos")
                df_pendentes.insert(0, "Deploy", False)

                cols = ["Deploy", "score", "motivos_score", "nome", "url", "status"]
                df_view = df_pendentes[[c for c in cols if c in df_pendentes.columns]]

                edited_df = st.data_editor(
                    df_view,
                    column_config={
                        "Deploy": st.column_config.CheckboxColumn("Atacar?"),
                        "score": st.column_config.NumberColumn("Score (0-100)"),
                        "motivos_score": st.column_config.TextColumn("Problemas"),
                        "url": st.column_config.LinkColumn("Site"),
                        "status": st.column_config.TextColumn("Status"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )

                selected = edited_df[edited_df["Deploy"] == True].to_dict("records")

                if st.button(
                    f"🚀 Pipeline para {len(selected)} leads",
                    type="primary",
                    disabled=len(selected) == 0,
                ):
                    bar = st.progress(0)
                    status_text = st.empty()

                    for i, lead in enumerate(selected):
                        nome = lead["nome"]
                        url = lead["url"]
                        status_text.text(f"Processando: {nome}...")

                        link = executar_pipeline_completo(
                            nome,
                            lead.get("nicho", nicho or "Negócio"),
                            lead.get("cidade", cidade or "Brasil"),
                            url,
                        )

                        update_lead_status(url, "DEPLOYED", vercel_url=link if link else "")
                        bar.progress((i + 1) / len(selected))

                    st.success("Pipeline concluído!")
                    time.sleep(1.5)
                    st.rerun()

        # --- Completed tab ---
        with tab_concluidos:
            df_done = df[df["status"] == "DEPLOYED"].copy()
            if df_done.empty:
                st.info("Nenhum deploy concluído.")
            else:
                st.success(f"{len(df_done)} sites gerados!")
                cols = ["nome", "nicho", "cidade", "vercel_url"]
                df_view = df_done[[c for c in cols if c in df_done.columns]]
                st.dataframe(
                    df_view,
                    column_config={"vercel_url": st.column_config.LinkColumn("🔥 Site Gerado")},
                    use_container_width=True,
                    hide_index=True,
                )

        # --- All leads tab ---
        with tab_todos:
            st.dataframe(
                df[["nome", "url", "nicho", "cidade", "status", "score", "criado_em"]],
                column_config={
                    "url": st.column_config.LinkColumn("Site"),
                    "score": st.column_config.NumberColumn("Score"),
                },
                use_container_width=True,
                hide_index=True,
            )