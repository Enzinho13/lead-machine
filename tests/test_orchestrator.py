"""
Testes do orquestrador (um lead por vez, sem Streamlit, sem envio real).
SQLite temporário. Rede, IA, geração e deploy mockados.
"""
import os
import sqlite3
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from unittest import mock

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))
sys.path.insert(0, ROOT_DIR)

import database
import outreach
from ai_service import AIRequestError

import orchestrator

URL = "https://clinica.com.br/"
URL_ONLINE = "https://clinica-boa.vercel.app"
CELULAR = "+5511975859568"
EMAIL = "contato@clinica.com.br"
AUDITORIA_OK = {
    "status": "Sucesso", "score": 30, "motivos": "Lento",
    "checks": {
        "performance": {"load_time": 5.0},
        "security": {"has_https": False},
        "mobile": {"has_viewport": False},
        "seo": {"has_h1": False, "issues": ["Sem H1"]},
    },
    "textos_principais": "texto",
    "cor_detectada": "#000",
}
AUDITORIA_FRIA = {**AUDITORIA_OK, "score": 95, "motivos": ""}
AUDITORIA_OFF = {"status": "Offline", "score": 0, "motivos": "Fora do Ar", "textos_principais": "", "checks": {}}


class DbTemp:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(database, "DB_PATH", os.path.join(self._tmp.name, "teste.db"))
        self._patch.start()
        outreach._rate_limits.clear()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()
        outreach._rate_limits.clear()


class DesignFake:
    def generate_design(self, lead_data, dados_auditoria):
        return {
            "nome_limpo": "Clínica Boa",
            "design_brief": "brief editorial",
            "theme": {},
            "layout": [{"type": "HeroMinimalist", "props": {}}],
        }


class DesignFallback:
    def generate_design(self, lead_data, dados_auditoria):
        return {"ai_fallback": True, "nome_limpo": "X", "layout": [], "theme": {}}


class FakeAI:
    def __init__(self, texto="Mensagem preparada"):
        self.texto, self.prompts = texto, []

    def generate_text(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.texto


def criar_lead(telefone="", email="", status="NEW", url=URL):
    database.init_db()
    database.insert_lead("Clínica", url, "d", "Advocacia", "Curitiba")
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            "UPDATE leads SET telefone = ?, email = ?, status = ? WHERE url = ?",
            (telefone, email, status, url),
        )
    return database.get_lead_by_url(url)


def rascunhos():
    with sqlite3.connect(database.DB_PATH) as conn:
        return conn.execute("SELECT canal, mensagem, status FROM outreach ORDER BY id").fetchall()


def nomes_ok(resultado):
    return [s["stage"] for s in resultado["stages"] if s["ok"]]


def rodar(**overrides):
    patches = {
        "_enriquecer_contatos": mock.MagicMock(return_value=False),
        "auditar_site_lead": mock.MagicMock(return_value=AUDITORIA_OK),
        "DesignDirector": DesignFake,
        "otimizar_seo": mock.MagicMock(return_value={"meta_title": "x"}),
        "gerar_site_cliente": mock.MagicMock(),
        "executar_qa": mock.MagicMock(return_value=True),
        "fazer_deploy_site": mock.MagicMock(return_value=URL_ONLINE),
    }
    patches.update(overrides)
    cm = mock.patch.multiple(orchestrator, **patches)
    with cm, mock.patch.object(outreach, "ai", FakeAI()), \
         mock.patch("socket.socket.connect", side_effect=AssertionError("rede")):
        return orchestrator.process_lead(URL)


def test_lead_inexistente_falha_em_discovery():
    with DbTemp():
        database.init_db()
        r = orchestrator.process_lead(URL)
        assert r["ok"] is False and r["stopped_at"] == "DISCOVERY"
        assert r["stages"][0] == {"stage": "DISCOVERY", "ok": False, "reason": "lead_not_found"}
        assert r["lead_status"] is None


def test_fluxo_completo_deployed_draft_nunca_contacted():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL, status="NEW")
        r = rodar(_enriquecer_contatos=mock.MagicMock(return_value=True))
        assert r["ok"] is True
        assert r["stopped_at"] is None
        assert nomes_ok(r) == list(orchestrator.STAGES)
        assert r["lead_status"] == "DEPLOYED"
        assert database.get_lead_by_url(URL)["status"] == "DEPLOYED"
        assert {st for _, _, st in rascunhos()} == {"DRAFT"}
        assert len(rascunhos()) == 2
        assert database.get_lead_by_url(URL)["status"] != "CONTACTED"
        deploy = next(s for s in r["stages"] if s["stage"] == "DEPLOY")
        outreach_st = next(s for s in r["stages"] if s["stage"] == "OUTREACH_DRAFT")
        assert deploy["ok"] and deploy["vercel_url"] == URL_ONLINE
        assert outreach_st["ok"] and outreach_st["sent"] is False
        assert outreach_st["outreach_status"] == "ready"


def test_auditoria_offline_nao_qualifica_nem_deploya():
    with DbTemp():
        criar_lead(status="NEW")
        r = rodar(auditar_site_lead=mock.MagicMock(return_value=AUDITORIA_OFF))
        assert r["ok"] is False and r["stopped_at"] == "AUDIT"
        assert r["lead_status"] == "AUDITED"
        assert "QUALIFICATION" not in [s["stage"] for s in r["stages"]]
        assert r["lead_status"] != "DEPLOYED"
        assert rascunhos() == []


def test_nao_qualificado_para_em_qualification_sem_gerar():
    gerar = mock.MagicMock()
    with DbTemp():
        criar_lead(status="NEW")
        r = rodar(
            auditar_site_lead=mock.MagicMock(return_value=AUDITORIA_FRIA),
            gerar_site_cliente=gerar,
        )
        assert r["ok"] is False and r["stopped_at"] == "QUALIFICATION"
        qual = next(s for s in r["stages"] if s["stage"] == "QUALIFICATION")
        assert qual["ok"] is True and qual["qualified"] is False
        assert r["lead_status"] == "AUDITED"
        gerar.assert_not_called()
        assert r["lead_status"] != "DEPLOYED"


def test_falha_de_geracao_nao_vira_deployed():
    with DbTemp():
        criar_lead(status="NEW")
        r = rodar(DesignDirector=DesignFallback)
        assert r["ok"] is False and r["stopped_at"] == "GENERATION"
        assert r["lead_status"] == "QUALIFIED"
        assert r["lead_status"] != "DEPLOYED"
        assert rascunhos() == []


def test_falha_de_qa_nao_faz_deploy():
    deploy = mock.MagicMock(return_value=URL_ONLINE)
    with DbTemp():
        criar_lead(status="NEW")
        r = rodar(executar_qa=mock.MagicMock(return_value=False), fazer_deploy_site=deploy)
        assert r["ok"] is False and r["stopped_at"] == "QA"
        assert r["lead_status"] == "QUALIFIED"
        assert r["lead_status"] != "DEPLOYED"
        deploy.assert_not_called()


def test_falha_de_deploy_nao_vira_deployed_nem_contacted():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL, status="NEW")
        r = rodar(fazer_deploy_site=mock.MagicMock(return_value=None))
        assert r["ok"] is False and r["stopped_at"] == "DEPLOY"
        assert r["lead_status"] == "QUALIFIED"
        assert r["lead_status"] != "DEPLOYED"
        assert r["lead_status"] != "CONTACTED"
        assert rascunhos() == []


def test_outreach_sem_contato_ainda_deixa_deployed_e_nao_contacted():
    with DbTemp():
        criar_lead(status="NEW")
        r = rodar()
        assert r["ok"] is True
        assert r["lead_status"] == "DEPLOYED"
        outreach_st = next(s for s in r["stages"] if s["stage"] == "OUTREACH_DRAFT")
        assert outreach_st["ok"] and outreach_st["outreach_status"] == "no_contact"
        assert outreach_st["sent"] is False
        assert rascunhos() == []
        assert database.get_lead_by_url(URL)["status"] != "CONTACTED"


def test_process_next_lead_pega_um_elegivel():
    with DbTemp():
        criar_lead(status="NEW")
        criar_lead(status="DEPLOYED", url="https://outro.com.br/")
        with mock.patch.object(orchestrator, "process_lead", return_value={"ok": True, "url": URL}) as proc:
            r = orchestrator.process_next_lead()
        proc.assert_called_once_with(URL)
        assert r["url"] == URL


def test_process_next_lead_vazio():
    with DbTemp():
        database.init_db()
        assert orchestrator.process_next_lead() is None


def test_run_discovery_reusa_buscar_empresas():
    with DbTemp():
        database.init_db()
        with mock.patch.object(orchestrator, "buscar_empresas") as buscar:
            def _insere(*args, **kwargs):
                database.insert_lead("A", URL, "d", "n", "c")
            buscar.side_effect = _insere
            r = orchestrator.run_discovery("Advocacia", "Curitiba", max_resultados=3)
        buscar.assert_called_once_with("Advocacia", "Curitiba", max_resultados=3)
        assert r["ok"] is True and r["count"] == 1 and r["urls"] == [URL]


def test_codigo_nao_atribui_contacted():
    import inspect
    fonte = inspect.getsource(orchestrator)
    assert '"CONTACTED"' not in fonte and "'CONTACTED'" not in fonte
    assert '"DEPLOYED"' in fonte
    assert "preparar_outreach_do_lead" in fonte
    assert "dispatch(" not in fonte


# ======================================================================
# Claim/lock, retry controlado, recuperação de AUDITING e idempotência
# ======================================================================

URL2 = "https://outra.com.br/"


class Ambiente:
    """patch.multiple no orchestrator + IA falsa + rede bloqueada. Expõe os mocks em .m"""

    def __init__(self, **overrides):
        self.m = {
            "_enriquecer_contatos": mock.MagicMock(return_value=False),
            "auditar_site_lead": mock.MagicMock(return_value=AUDITORIA_OK),
            "DesignDirector": DesignFake,
            "otimizar_seo": mock.MagicMock(return_value={"meta_title": "x"}),
            "gerar_site_cliente": mock.MagicMock(),
            "executar_qa": mock.MagicMock(return_value=True),
            "fazer_deploy_site": mock.MagicMock(return_value=URL_ONLINE),
        }
        self.m.update(overrides)

    def __enter__(self):
        self._stack = ExitStack()
        self._stack.enter_context(mock.patch.multiple(orchestrator, **self.m))
        self._stack.enter_context(mock.patch.object(outreach, "ai", FakeAI()))
        self._stack.enter_context(mock.patch("socket.socket.connect", side_effect=AssertionError("rede")))
        return self

    def __exit__(self, *exc):
        self._stack.close()


def linha(url=URL):
    return database.get_lead_by_url(url)


def n_audits():
    with sqlite3.connect(database.DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM audits").fetchone()[0]


def claim_livre(url=URL):
    row = linha(url)
    return row["claimed_by"] == "" and row["claim_expires_at"] == 0


def assert_semantica_de_status():
    """Nunca CONTACTED; todo outreach é DRAFT."""
    assert all(lead["status"] != "CONTACTED" for lead in database.get_all_leads())
    assert {status for _, _, status in rascunhos()} <= {"DRAFT"}


# ---------------------------------------------------------------- 1) AUDITING nunca fica preso

def test_excecao_na_auditoria_nao_prende_o_lead_em_auditing():
    for status_ini in ("NEW", "AUDITED", "QUALIFIED"):
        with DbTemp():
            criar_lead(status=status_ini)
            with Ambiente(auditar_site_lead=mock.MagicMock(side_effect=RuntimeError("boom"))):
                r = orchestrator.process_lead(URL)
            row = linha()
            assert r["ok"] is False and r["stopped_at"] == "AUDIT"
            assert row["status"] == status_ini and r["lead_status"] == status_ini
            assert row["attempts"] == 1 and "boom" in row["last_error"]
            assert claim_livre()
            assert_semantica_de_status()


def test_excecao_depois_de_auditing_na_gravacao_da_auditoria_tambem_nao_prende():
    with DbTemp():
        criar_lead(status="NEW")
        with Ambiente(_gravar_auditoria=mock.MagicMock(side_effect=RuntimeError("db fora"))):
            r = orchestrator.process_lead(URL)
        assert r["stopped_at"] == "AUDIT" and linha()["status"] == "NEW" and claim_livre()


def test_lead_preso_em_auditing_por_worker_morto_e_recuperado():
    with DbTemp():
        criar_lead(status="AUDITING")
        assert database.claim_lead(URL, "morto", ttl_seconds=1, now=time.time() - 100)  # claim já expirado
        assert orchestrator.next_lead()["url"] == URL
        with Ambiente():
            r = orchestrator.process_lead(URL)
        row = linha()
        assert r["ok"] is True and row["status"] == "DEPLOYED"
        assert row["attempts"] == 0 and row["last_error"] == "" and claim_livre()
        assert_semantica_de_status()


def test_auditing_sem_claim_e_recuperavel_mas_com_claim_ativo_e_intocavel():
    with DbTemp():
        criar_lead(status="AUDITING")                                   # preso sem claim (ex.: queda do app)
        assert orchestrator.next_lead()["url"] == URL
    with DbTemp():
        criar_lead(status="AUDITING")
        assert database.claim_lead(URL, "vivo", ttl_seconds=900)       # outro worker processando agora
        assert orchestrator.next_lead() is None
        with Ambiente() as amb:
            r = orchestrator.process_lead(URL)
        assert r["stopped_at"] == "CLAIM" and r["stages"][0]["reason"] == "already_claimed"
        assert linha()["status"] == "AUDITING" and linha()["claimed_by"] == "vivo"
        amb.m["auditar_site_lead"].assert_not_called()


# ---------------------------------------------------------------- 2) retry controlado, sem loop infinito

def test_retry_e_limitado_e_nao_entra_em_loop_infinito():
    with DbTemp():
        criar_lead(status="NEW")
        audit = mock.MagicMock(side_effect=RuntimeError("boom"))
        with Ambiente(auditar_site_lead=audit):
            t, rodadas = time.time(), 0
            for _ in range(50):                       # teto de segurança do próprio teste
                t += 10_000                           # já passou o backoff
                if orchestrator.process_next_lead(now=t) is None:
                    break
                rodadas += 1
            assert rodadas == orchestrator.MAX_ATTEMPTS and audit.call_count == orchestrator.MAX_ATTEMPTS
            assert orchestrator.next_lead(now=t + 10 ** 7) is None
            row = linha()
            assert row["attempts"] == orchestrator.MAX_ATTEMPTS and row["status"] == "NEW" and claim_livre()
            r = orchestrator.process_lead(URL)        # chamada explícita também é recusada
            assert r["stopped_at"] == "CLAIM" and r["stages"][0]["reason"] == "retries_exhausted"
            assert audit.call_count == orchestrator.MAX_ATTEMPTS


def test_backoff_evita_retry_imediato_e_lead_com_menos_tentativas_vem_primeiro():
    with DbTemp():
        criar_lead(url=URL)
        criar_lead(url=URL2)
        with Ambiente(auditar_site_lead=mock.MagicMock(side_effect=RuntimeError("boom"))):
            orchestrator.process_lead(URL)
        assert orchestrator.next_lead()["url"] == URL2                                # URL está em backoff
        assert orchestrator.next_lead(now=time.time() + 10_000)["url"] == URL2        # após o backoff: menos tentativas primeiro


def test_lead_nao_qualificado_e_resultado_final_e_nao_volta_em_loop():
    with DbTemp():
        criar_lead(status="NEW")
        fria = mock.MagicMock(return_value=AUDITORIA_FRIA)
        with Ambiente(auditar_site_lead=fria):
            r = orchestrator.process_lead(URL)
            assert r["stopped_at"] == "QUALIFICATION" and r["lead_status"] == "AUDITED"
            assert linha()["last_error"] == "not_qualified" and linha()["attempts"] == orchestrator.MAX_ATTEMPTS
            assert orchestrator.next_lead(now=time.time() + 10 ** 7) is None
            assert orchestrator.process_next_lead(now=time.time() + 10 ** 7) is None
        assert fria.call_count == 1 and claim_livre()


# ---------------------------------------------------------------- 3) idempotência

def test_processar_duas_vezes_nao_repete_trabalho_nem_duplica():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL, status="NEW")
        with Ambiente() as amb:
            r1 = orchestrator.process_lead(URL)
            r2 = orchestrator.process_lead(URL)
        assert r1["ok"] is True and r2["ok"] is True and r2["already_done"] is True
        for nome in ("auditar_site_lead", "gerar_site_cliente", "executar_qa", "fazer_deploy_site"):
            assert amb.m[nome].call_count == 1, nome
        assert n_audits() == 1 and len(rascunhos()) == 2
        row = linha()
        assert row["status"] == "DEPLOYED" and row["attempts"] == 0 and row["last_error"] == "" and claim_livre()
        assert len(database.get_all_leads()) == 1
        assert_semantica_de_status()


def test_falha_no_rascunho_retoma_so_o_outreach_sem_refazer_deploy():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        with Ambiente() as amb:
            with mock.patch.object(orchestrator, "preparar_outreach_do_lead", side_effect=RuntimeError("falha rascunho")):
                r1 = orchestrator.process_lead(URL)
            row = linha()
            assert r1["ok"] is False and r1["stopped_at"] == "OUTREACH_DRAFT"
            assert row["status"] == "DEPLOYED" and "OUTREACH_DRAFT" in row["last_error"] and rascunhos() == []
            assert orchestrator.next_lead(now=time.time() + 10_000)["url"] == URL   # DEPLOYED pendente é retomável
            r2 = orchestrator.process_lead(URL)
        assert r2["ok"] is True and r2["resumed"] is True
        for nome in ("auditar_site_lead", "gerar_site_cliente", "executar_qa", "fazer_deploy_site"):
            assert amb.m[nome].call_count == 1, nome
        row = linha()
        assert row["status"] == "DEPLOYED" and row["attempts"] == 0 and row["last_error"] == "" and claim_livre()
        assert [c for c, _, _ in rascunhos()] == ["WHATSAPP", "EMAIL"]
        assert_semantica_de_status()


def test_queda_logo_apos_o_deploy_deixa_o_lead_retomavel_so_no_outreach():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        with Ambiente() as amb:
            with mock.patch.object(orchestrator, "preparar_outreach_do_lead", side_effect=KeyboardInterrupt):
                try:
                    orchestrator.process_lead(URL)
                except KeyboardInterrupt:
                    pass
            row = linha()
            assert row["status"] == "DEPLOYED" and row["last_error"] == "outreach_pending"
            assert claim_livre() and rascunhos() == []
            assert database.claim_lead(URL, "morto", ttl_seconds=1, now=time.time() - 100)  # worker morto: claim abandonado
            assert orchestrator.next_lead()["url"] == URL
            r = orchestrator.process_lead(URL)
        assert r["ok"] is True and r["resumed"] is True
        assert amb.m["fazer_deploy_site"].call_count == 1 and len(rascunhos()) == 2
        assert linha()["last_error"] == "" and claim_livre()
        assert_semantica_de_status()


def test_reaproveita_auditoria_salva_depois_de_falha_posterior():
    with DbTemp():
        criar_lead(status="NEW")
        with Ambiente(DesignDirector=DesignFallback):
            r1 = orchestrator.process_lead(URL)
        assert r1["stopped_at"] == "GENERATION" and linha()["status"] == "QUALIFIED" and n_audits() == 1
        with Ambiente() as amb:
            r2 = orchestrator.process_lead(URL)
        assert r2["ok"] is True and linha()["status"] == "DEPLOYED"
        amb.m["auditar_site_lead"].assert_not_called()          # não audita de novo
        assert n_audits() == 1                                   # e não duplica a linha de auditoria
        assert next(s for s in r2["stages"] if s["stage"] == "AUDIT")["reused"] is True


def test_enriquecimento_so_roda_quando_o_lead_nao_tem_contato():
    with DbTemp():
        criar_lead(telefone=CELULAR)
        with Ambiente() as amb:
            orchestrator.process_lead(URL)
        amb.m["_enriquecer_contatos"].assert_not_called()
        assert linha()["telefone"] == CELULAR and linha()["email"] == ""      # contatos intactos
    with DbTemp():
        criar_lead()
        with Ambiente() as amb:
            orchestrator.process_lead(URL)
        amb.m["_enriquecer_contatos"].assert_called_once_with(URL)


# ---------------------------------------------------------------- 4) claim/lock

def test_dois_workers_nao_claimam_o_mesmo_lead_concorrentemente():
    with DbTemp():
        criar_lead()
        n = 8
        barreira, ganhou = threading.Barrier(n), []

        def worker(i):
            barreira.wait()
            ganhou.append(database.claim_lead(URL, f"w{i}", ttl_seconds=60))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        assert len(ganhou) == n and ganhou.count(True) == 1
        row = linha()
        assert row["claimed_by"] in {f"w{i}" for i in range(n)} and row["attempts"] == 1


def test_segundo_worker_e_recusado_enquanto_o_primeiro_processa():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        entrou, liberar, resultados = threading.Event(), threading.Event(), {}

        def audit_lento(url):
            entrou.set()
            assert liberar.wait(20)
            return AUDITORIA_OK

        with Ambiente(auditar_site_lead=mock.MagicMock(side_effect=audit_lento)) as amb:
            a = threading.Thread(target=lambda: resultados.setdefault("a", orchestrator.process_lead(URL)))
            a.start()
            assert entrou.wait(20)
            b = orchestrator.process_lead(URL)                     # segundo worker, com o primeiro no meio da auditoria
            assert b["ok"] is False and b["stopped_at"] == "CLAIM" and b["stages"][0]["reason"] == "already_claimed"
            assert linha()["status"] == "AUDITING" and linha()["claimed_by"] != ""
            assert orchestrator.next_lead() is None                # nem o scheduler o pega
            liberar.set()
            a.join(30)
        assert resultados["a"]["ok"] is True
        for nome in ("auditar_site_lead", "gerar_site_cliente", "executar_qa", "fazer_deploy_site"):
            assert amb.m[nome].call_count == 1, nome
        assert linha()["status"] == "DEPLOYED" and claim_livre() and n_audits() == 1 and len(rascunhos()) == 2


def test_claim_expirado_pode_ser_recuperado_e_so_o_dono_libera():
    with DbTemp():
        criar_lead()
        assert database.claim_lead(URL, "w1", ttl_seconds=10, now=1000.0) is True
        assert database.claim_lead(URL, "w2", ttl_seconds=10, now=1005.0) is False      # ainda vivo
        assert database.claim_lead(URL, "w2", ttl_seconds=10, now=1009.9) is False
        assert database.claim_lead(URL, "w2", ttl_seconds=10, now=1010.0) is True       # expirou: recuperado
        assert linha()["claimed_by"] == "w2" and linha()["attempts"] == 2
        assert database.release_lead(URL, "w1") is False                                # w1 atrasado não solta o claim do w2
        assert linha()["claimed_by"] == "w2"
        assert database.release_lead(URL, "w2") is True and claim_livre()


def test_sucesso_libera_o_claim():
    with DbTemp():
        criar_lead()
        with Ambiente():
            r = orchestrator.process_lead(URL)
        assert r["ok"] is True and claim_livre()
        assert database.claim_lead(URL, "proximo", ttl_seconds=60) is True


def test_falha_libera_o_claim():
    with DbTemp():
        criar_lead()
        with Ambiente(fazer_deploy_site=mock.MagicMock(return_value=None)):
            r = orchestrator.process_lead(URL)
        assert r["ok"] is False and r["stopped_at"] == "DEPLOY" and claim_livre()
        assert database.claim_lead(URL, "proximo", ttl_seconds=60) is True


def test_excecao_inesperada_e_interrupcao_tambem_liberam_o_claim():
    with DbTemp():
        criar_lead()
        with Ambiente():
            with mock.patch.object(orchestrator, "_process_claimed", side_effect=RuntimeError("x")):
                r = orchestrator.process_lead(URL)
        assert r["ok"] is False and r["stopped_at"] == "UNEXPECTED" and claim_livre()
        assert linha()["status"] == "NEW" and "x" in linha()["last_error"]
    with DbTemp():
        criar_lead()
        with Ambiente():
            with mock.patch.object(orchestrator, "_process_claimed", side_effect=KeyboardInterrupt):
                try:
                    orchestrator.process_lead(URL)
                except KeyboardInterrupt:
                    pass
        assert claim_livre()


# ---------------------------------------------------------------- 5) status, DRAFT e CONTACTED

def test_falha_seguida_de_recuperacao_mantem_status_draft_e_nunca_contacted():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL, status="NEW")
        with Ambiente(fazer_deploy_site=mock.MagicMock(return_value=None)):
            r1 = orchestrator.process_lead(URL)
        assert r1["stopped_at"] == "DEPLOY" and linha()["status"] == "QUALIFIED" and rascunhos() == []
        assert_semantica_de_status()
        with Ambiente():
            r2 = orchestrator.process_lead(URL)
        assert r2["ok"] is True and linha()["status"] == "DEPLOYED"
        assert len(rascunhos()) == 2 and {st for _, _, st in rascunhos()} == {"DRAFT"}
        assert_semantica_de_status()
        with Ambiente():
            r3 = orchestrator.process_lead(URL)       # reprocessar o que já está pronto
        assert r3["already_done"] is True and linha()["status"] == "DEPLOYED" and len(rascunhos()) == 2
        assert_semantica_de_status()


def test_migracao_das_colunas_de_claim_preserva_os_leads_existentes():
    with DbTemp():
        with sqlite3.connect(database.DB_PATH) as conn:
            conn.executescript("""
                CREATE TABLE leads (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, url TEXT UNIQUE, descricao TEXT,
                    nicho TEXT, cidade TEXT, status TEXT DEFAULT 'NEW', score INTEGER DEFAULT 0,
                    motivos_score TEXT DEFAULT '', fonte TEXT DEFAULT '', telefone TEXT DEFAULT '', email TEXT DEFAULT '',
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP, atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                INSERT INTO leads (nome, url, status, telefone, email)
                VALUES ('Antigo', 'https://antigo.com.br/', 'AUDITED', '+5511975859568', 'a@antigo.com.br');
            """)
        database.init_db()
        database.init_db()
        row = database.get_lead_by_url("https://antigo.com.br/")
        assert (row["nome"], row["status"], row["telefone"], row["email"]) == ("Antigo", "AUDITED", "+5511975859568", "a@antigo.com.br")
        assert (row["claimed_by"], row["attempts"], row["last_error"]) == ("", 0, "")


# ======================================================================
# Lease com ownership (token), renovação/heartbeat e perda de lease
# ======================================================================

def test_lease_a_adquire_e_b_e_bloqueado_enquanto_o_lease_de_a_esta_ativo():
    with DbTemp():
        criar_lead()
        ta = database.acquire_lease(URL, "A", ttl_seconds=10, now=1000.0)
        assert isinstance(ta, str) and ta
        assert database.acquire_lease(URL, "B", ttl_seconds=10, now=1005.0) is None
        assert database.acquire_lease(URL, "B", ttl_seconds=10, now=1009.9) is None
        row = linha()
        assert row["claimed_by"] == "A" and row["claim_token"] == ta and row["attempts"] == 1


def test_a_renova_o_lease_e_b_continua_bloqueado_depois_da_renovacao():
    with DbTemp():
        criar_lead()
        ta = database.acquire_lease(URL, "A", ttl_seconds=10, now=1000.0)           # expiraria em 1010
        assert database.renew_lease(URL, ta, ttl_seconds=10, now=1008.0) is True     # agora expira em 1018
        assert linha()["claim_expires_at"] == 1018.0
        assert database.acquire_lease(URL, "B", ttl_seconds=10, now=1012.0) is None  # sem a renovação já teria expirado
        assert database.acquire_lease(URL, "B", ttl_seconds=10, now=1017.9) is None
        assert linha()["claim_token"] == ta
        tb = database.acquire_lease(URL, "B", ttl_seconds=10, now=1018.0)               # só depois da expiração renovada
        assert tb and tb != ta


def test_apos_a_expiracao_b_assume_e_o_token_antigo_perde_toda_autoridade():
    with DbTemp():
        criar_lead()
        ta = database.acquire_lease(URL, "A", ttl_seconds=10, now=1000.0)
        tb = database.acquire_lease(URL, "B", ttl_seconds=10, now=1010.0)            # o lease de A expirou
        assert tb and tb != ta
        assert database.owns_lease(URL, ta) is False and database.owns_lease(URL, tb) is True
        # A (token antigo) não consegue liberar, renovar nem registrar desfecho
        assert database.release_lead(URL, ta) is False
        assert database.renew_lease(URL, ta, ttl_seconds=10, now=1011.0) is False
        assert database.mark_lead_failure(URL, "erro de A", token=ta) is False
        assert database.mark_lead_success(URL, token=ta) is False
        assert database.exhaust_lead(URL, "fim de A", token=ta) is False
        row = linha()
        assert row["claimed_by"] == "B" and row["claim_token"] == tb and row["claim_expires_at"] == 1020.0
        assert row["last_error"] == "" and row["attempts"] == 2 and row["retry_after"] == 0
        # B, o dono legítimo, consegue
        assert database.mark_lead_failure(URL, "erro de B", token=tb) is True and linha()["last_error"] == "erro de B"
        assert database.release_lead(URL, tb) is True and claim_livre()
        assert database.renew_lease(URL, tb, ttl_seconds=10, now=1012.0) is False    # lease liberado: ninguém renova


def test_token_e_unico_por_aquisicao_e_o_antigo_nao_solta_o_novo():
    with DbTemp():
        criar_lead()
        t1 = database.acquire_lease(URL, "A", ttl_seconds=10)
        assert database.release_lead(URL, t1) is True
        t2 = database.acquire_lease(URL, "A", ttl_seconds=10)                        # mesmo worker, nova aquisição
        assert t2 and t2 != t1
        assert database.release_lead(URL, t1) is False and linha()["claim_token"] == t2
        assert database.release_lead(URL, "") is False and database.release_lead(URL, None) is False
        assert database.release_lead(URL, t2) is True and claim_livre() and linha()["claim_token"] == ""


def test_lease_heartbeat_e_reutilizavel_renova_e_detecta_a_perda():
    with DbTemp():
        criar_lead()
        ta = database.acquire_lease(URL, "A", ttl_seconds=0.6)
        with orchestrator.LeaseHeartbeat(URL, ta, ttl_seconds=0.6, interval=0.1) as hb:
            time.sleep(0.9)                                           # > TTL: só sobrevive por causa do heartbeat
            assert database.acquire_lease(URL, "B", ttl_seconds=60) is None
            hb.check()                                                # ainda é o dono
            tb = database.acquire_lease(URL, "B", ttl_seconds=60, now=time.time() + 10_000)  # B assume
            assert tb
            try:
                hb.check()
            except orchestrator.LeaseLost:
                pass
            else:
                raise AssertionError("deveria levantar LeaseLost")
            assert hb.lost.is_set()
        assert linha()["claim_token"] == tb and linha()["claimed_by"] == "B"       # o heartbeat de A não mexeu no claim de B


def test_heartbeat_mantem_o_lease_vivo_alem_do_ttl_durante_o_processamento():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        resultados = {}

        def audit_lento(url):
            time.sleep(1.5)
            return AUDITORIA_OK

        with Ambiente(auditar_site_lead=mock.MagicMock(side_effect=audit_lento)) as amb:
            a = threading.Thread(target=lambda: resultados.setdefault("a", orchestrator.process_lead(URL, claim_ttl=0.6)))
            a.start()
            time.sleep(1.1)                                           # já passou do TTL de 0.6s
            assert database.acquire_lease(URL, "B", ttl_seconds=60) is None    # o heartbeat manteve o lease de A
            assert linha()["status"] == "AUDITING"
            a.join(30)
        assert resultados["a"]["ok"] is True and claim_livre()
        assert amb.m["auditar_site_lead"].call_count == 1 and amb.m["fazer_deploy_site"].call_count == 1


def test_worker_que_perde_o_lease_aborta_e_nao_toca_no_claim_do_novo_dono():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        entrou, liberar, resultados = threading.Event(), threading.Event(), {}

        def audit_lento(url):
            entrou.set()
            assert liberar.wait(20)
            return AUDITORIA_OK

        with Ambiente(auditar_site_lead=mock.MagicMock(side_effect=audit_lento)) as amb:
            a = threading.Thread(target=lambda: resultados.setdefault("a", orchestrator.process_lead(URL)))
            a.start()
            assert entrou.wait(20)
            tb = database.acquire_lease(URL, "B", ttl_seconds=900, now=time.time() + 10_000)   # B assume o lead de A
            assert tb
            liberar.set()
            a.join(30)
        r = resultados["a"]
        assert r["ok"] is False and r["stopped_at"] == "LEASE" and r["lease_lost"] is True
        for nome in ("gerar_site_cliente", "executar_qa", "fazer_deploy_site"):
            amb.m[nome].assert_not_called()                             # A não gerou nem publicou nada depois de perder o lease
        assert rascunhos() == []
        row = linha()
        assert row["claimed_by"] == "B" and row["claim_token"] == tb        # A não liberou o claim de B
        assert row["last_error"] == "" and row["attempts"] == 2             # nem registrou desfecho por cima
        assert database.owns_lease(URL, tb) is True


def test_nao_existe_processamento_concorrente_do_mesmo_lead():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        n = 6
        barreira, resultados = threading.Barrier(n), []

        def audit_lento(url):
            time.sleep(0.6)
            return AUDITORIA_OK

        def worker():
            barreira.wait()
            resultados.append(orchestrator.process_lead(URL))

        with Ambiente(auditar_site_lead=mock.MagicMock(side_effect=audit_lento)) as amb:
            threads = [threading.Thread(target=worker) for _ in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(60)
        assert len(resultados) == n
        executaram = [r for r in resultados if r["stopped_at"] != "CLAIM"]
        assert len(executaram) == 1 and executaram[0]["ok"] is True
        assert all(r["stages"][0]["reason"] == "already_claimed" for r in resultados if r["stopped_at"] == "CLAIM")
        for nome in ("auditar_site_lead", "gerar_site_cliente", "executar_qa", "fazer_deploy_site"):
            assert amb.m[nome].call_count == 1, nome
        assert n_audits() == 1 and len(rascunhos()) == 2 and claim_livre() and linha()["status"] == "DEPLOYED"


def test_processamento_normal_e_falha_liberam_o_lease_com_token():
    with DbTemp():
        criar_lead()
        with Ambiente():
            r = orchestrator.process_lead(URL)
        assert r["ok"] is True and claim_livre() and linha()["claim_token"] == ""
    with DbTemp():
        criar_lead()
        with Ambiente(fazer_deploy_site=mock.MagicMock(return_value=None)):
            r = orchestrator.process_lead(URL)
        assert r["ok"] is False and claim_livre() and linha()["claim_token"] == ""


def test_lease_expirado_de_worker_morto_continua_recuperavel_e_seu_token_perde_autoridade():
    with DbTemp():
        criar_lead(status="AUDITING")
        morto = database.acquire_lease(URL, "morto", ttl_seconds=1, now=time.time() - 100)
        assert orchestrator.next_lead()["url"] == URL
        with Ambiente():
            r = orchestrator.process_lead(URL)
        assert r["ok"] is True and linha()["status"] == "DEPLOYED" and claim_livre()
        assert database.renew_lease(URL, morto, ttl_seconds=900) is False
        assert database.release_lead(URL, morto) is False


# ---------------------------------------------------------------- lacunas encontradas por mutação (backoff e rascunho)

def test_falha_agenda_backoff_e_o_lead_so_volta_depois_da_espera():
    with DbTemp():
        criar_lead()
        with Ambiente(auditar_site_lead=mock.MagicMock(side_effect=RuntimeError("boom"))):
            orchestrator.process_lead(URL)
        row = linha()
        assert row["attempts"] == 1 and row["retry_after"] > time.time()
        assert orchestrator.next_lead() is None                        # em backoff (e não há outro lead)
        assert orchestrator.next_lead(now=time.time() + orchestrator.RETRY_BACKOFF_SECONDS * 2)["url"] == URL


def test_reprocessar_rascunhos_existentes_atualiza_sem_virar_sent_nem_contacted():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        with Ambiente():
            orchestrator.process_lead(URL)
            database.mark_lead_failure(URL, "forcar retomada", 0)       # leva ao caminho de ATUALIZAÇÃO dos rascunhos
            r = orchestrator.process_lead(URL)
        assert r["ok"] is True and r["resumed"] is True
        assert len(rascunhos()) == 2 and {st for _, _, st in rascunhos()} == {"DRAFT"}
        assert_semantica_de_status()
