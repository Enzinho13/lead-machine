"""
Testes de integração: o pipeline PREPARA o outreach a partir dos contatos reais do lead (nada é enviado).

Roda o executar_pipeline_completo real com tudo externo mockado (auditoria, design, SEO, geração de site,
QA e DEPLOY), mantendo reais o banco (SQLite temporário), o OutreachEngine e a análise de contatos.
Sem rede (socket.connect bloqueado), sem API de IA (fake), sem deploy e sem envio de mensagens.
Roda com `python tests/test_pipeline_outreach.py` ou com pytest.
"""
import inspect
import os
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))
sys.path.insert(0, ROOT_DIR)

import database
import main
import outreach
from ai_service import AIRequestError

URL = "https://clinica.com.br/"
URL_ONLINE = "https://clinica-boa.vercel.app"
CELULAR = "+5511975859568"
FIXO = "+551140123456"
EMAIL = "contato@clinica.com.br"
MSG_COM_LINK = f"Mensagem preparada\n\nVeja o protótipo: {URL_ONLINE}"
AUDITORIA = {
    "status": "Sucesso", "score": 30, "motivos": "Lento",
    "checks": {"performance": {"load_time": 5.0}, "security": {"has_https": False}},
}


# ---------------------------------------------------------------- helpers

class DbTemp:
    """Aponta database.DB_PATH para um arquivo temporário (nunca o leads.db real)."""
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "teste.db")
        self._patch = mock.patch.object(database, "DB_PATH", self.path)
        self._patch.start()
        outreach._rate_limits.clear()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()
        outreach._rate_limits.clear()


class FakeAI:
    """Substitui o singleton `ai` do outreach e registra os prompts recebidos."""
    def __init__(self, texto="Mensagem preparada", erro=None):
        self.texto, self.erro, self.prompts = texto, erro, []

    def generate_text(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if self.erro:
            raise self.erro
        return self.texto


class DesignFake:
    def generate_design(self, lead_data, dados_auditoria):
        return {"nome_limpo": "Clínica Boa", "design_brief": "brief editorial", "theme": {},
                "layout": [{"type": "HeroMinimalist", "props": {}}]}


def sem_rede():
    return mock.patch("socket.socket.connect", side_effect=AssertionError("tentou acessar a rede"))


def criar_lead(telefone="", email="", status="QUALIFIED", url=URL):
    """Cria o lead e grava os contatos EXATAMENTE como passados, via SQL."""
    database.init_db()
    database.insert_lead("Clínica", url, "d", "n", "c")
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("UPDATE leads SET telefone = ?, email = ?, status = ? WHERE url = ?", (telefone, email, status, url))
    return database.get_lead_by_url(url)["id"]


def rascunhos():
    with sqlite3.connect(database.DB_PATH) as conn:
        return conn.execute("SELECT canal, mensagem, status FROM outreach ORDER BY id").fetchall()


def rodar_pipeline(ai=None, url_lead=URL, url_online=URL_ONLINE):
    """Executa o pipeline completo; devolve o link e os mocks para as asserções."""
    ai = ai or FakeAI()
    with mock.patch.object(main, "auditar_site_lead", return_value=AUDITORIA), \
         mock.patch.object(main, "DesignDirector", DesignFake), \
         mock.patch.object(main, "otimizar_seo", return_value={"meta_title": "x"}), \
         mock.patch.object(main, "gerar_site_cliente") as gerar, \
         mock.patch.object(main, "executar_qa", return_value=True), \
         mock.patch.object(main, "fazer_deploy_site", return_value=url_online) as deploy, \
         mock.patch.object(outreach, "ai", ai), \
         mock.patch.object(outreach.OutreachEngine, "dispatch") as dispatch, \
         sem_rede():
        link = main.executar_pipeline_completo("Clínica", "Advocacia", "Curitiba", url_lead)
    return SimpleNamespace(link=link, ai=ai, dispatch=dispatch, deploy=deploy, gerar=gerar)


# ---------------------------------------------------------------- os 4 cenários de contato, pelo pipeline

def test_pipeline_lead_sem_contato_nao_gera_mensagem_nao_chama_dispatch_e_segue():
    with DbTemp():
        criar_lead()
        r = rodar_pipeline()
        assert r.link == URL_ONLINE and r.deploy.call_count == 1  # o pipeline segue normalmente
        assert r.ai.prompts == []                                  # nenhuma chamada de IA
        assert r.dispatch.called is False                          # dispatch não é chamado
        assert rascunhos() == []                                   # nada gravado em outreach
        assert database.get_lead_by_url(URL)["status"] == "QUALIFIED"
        assert database.get_all_leads()[0]["design_brief"] == "brief editorial"  # o brief do site não se perde


def test_pipeline_telefone_fixo_conta_como_sem_canal():
    with DbTemp():
        criar_lead(telefone=FIXO)
        r = rodar_pipeline()
        assert r.link == URL_ONLINE and r.ai.prompts == [] and r.dispatch.called is False and rascunhos() == []


def test_pipeline_somente_celular_prepara_so_whatsapp():
    with DbTemp():
        criar_lead(telefone=CELULAR)
        r = rodar_pipeline()
        assert r.link == URL_ONLINE and r.dispatch.called is False
        assert rascunhos() == [("WHATSAPP", MSG_COM_LINK, "DRAFT")]
        assert len(r.ai.prompts) == 1 and "whatsapp" in r.ai.prompts[0]


def test_pipeline_somente_email_prepara_so_email():
    with DbTemp():
        criar_lead(email=EMAIL)
        r = rodar_pipeline()
        assert r.link == URL_ONLINE and r.dispatch.called is False
        assert rascunhos() == [("EMAIL", MSG_COM_LINK, "DRAFT")]
        assert len(r.ai.prompts) == 1 and "email" in r.ai.prompts[0]


def test_pipeline_com_ambos_prepara_os_dois_canais_sem_enviar():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        r = rodar_pipeline()
        assert r.link == URL_ONLINE and r.dispatch.called is False
        assert rascunhos() == [("WHATSAPP", MSG_COM_LINK, "DRAFT"), ("EMAIL", MSG_COM_LINK, "DRAFT")]
        assert {status for _, _, status in rascunhos()} == {"DRAFT"}
        assert database.get_lead_by_url(URL)["status"] != "CONTACTED"
        assert len(r.ai.prompts) == 2


# ---------------------------------------------------------------- nada é "enviado"; status comercial intacto

def test_nenhuma_mensagem_e_marcada_como_enviada():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        rodar_pipeline()
        assert {status for _, _, status in rascunhos()} == {"DRAFT"}
        with mock.patch.object(outreach, "ai", FakeAI()), sem_rede():
            resultado = main.preparar_outreach_do_lead(URL, "Clínica", AUDITORIA, URL_ONLINE)
        assert resultado["sent"] is False and all(p["sent"] is False for p in resultado["payloads"])
        assert {status for _, _, status in rascunhos()} == {"DRAFT"}


def test_preparar_outreach_nunca_muda_o_status_comercial_do_lead():
    cenarios = [("", ""), (FIXO, ""), (CELULAR, ""), ("", EMAIL), (CELULAR, EMAIL)]
    for telefone, email in cenarios:
        for status in ("NEW", "AUDITED", "QUALIFIED"):
            with DbTemp():
                criar_lead(telefone=telefone, email=email, status=status)
                rodar_pipeline()
                lead_status = database.get_lead_by_url(URL)["status"]
                assert lead_status == status, (telefone, email, status)
                assert lead_status != "CONTACTED"


def test_resultado_de_preparar_outreach_e_explicito():
    with DbTemp():
        criar_lead()
        with mock.patch.object(outreach, "ai", FakeAI()):
            semcontato = main.preparar_outreach_do_lead(URL, "Clínica", AUDITORIA, URL_ONLINE, "brief")
        assert semcontato["status"] == "no_contact" and semcontato["situacao"] == "sem_contato"
        assert semcontato["canais"] == [] and semcontato["sent"] is False and semcontato["reason"]
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        with mock.patch.object(outreach, "ai", FakeAI()):
            pronto = main.preparar_outreach_do_lead(URL, "Clínica", AUDITORIA, URL_ONLINE)
        assert pronto["status"] == "ready" and pronto["canais"] == ["whatsapp", "email"] and pronto["sent"] is False
    with DbTemp():
        criar_lead(telefone=CELULAR, status="LOST")
        with mock.patch.object(outreach, "ai", FakeAI()):
            bloqueado = main.preparar_outreach_do_lead(URL, "Clínica", AUDITORIA, URL_ONLINE)
        assert bloqueado["status"] == "blocked" and bloqueado["sent"] is False and rascunhos() == []
    with DbTemp():
        database.init_db()
        assert main.preparar_outreach_do_lead(URL, "Clínica", AUDITORIA, URL_ONLINE) == {"status": "lead_not_found", "sent": False}


# ---------------------------------------------------------------- o pipeline continua quando o outreach não é preparado

def test_pipeline_continua_quando_o_outreach_nao_pode_ser_preparado():
    with DbTemp():  # lead bloqueado (LOST)
        criar_lead(telefone=CELULAR, email=EMAIL, status="LOST")
        r = rodar_pipeline()
        assert r.link == URL_ONLINE and r.ai.prompts == [] and rascunhos() == [] and r.dispatch.called is False
    with DbTemp():  # lead que não está no banco
        database.init_db()
        r = rodar_pipeline()
        assert r.link == URL_ONLINE and r.ai.prompts == [] and rascunhos() == []
    with DbTemp():  # falha inesperada ao preparar: o site já foi publicado e o link não pode se perder
        criar_lead(telefone=CELULAR)
        with mock.patch.object(outreach.OutreachEngine, "preparar_envio", side_effect=RuntimeError("falha simulada")):
            r = rodar_pipeline()
        assert r.link == URL_ONLINE and r.deploy.call_count == 1 and rascunhos() == []
        assert database.get_lead_by_url(URL)["status"] == "QUALIFIED"


def test_deploy_falho_nao_prepara_outreach():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        r = rodar_pipeline(url_online=None)
        assert r.link is None and r.ai.prompts == [] and rascunhos() == [] and r.dispatch.called is False


def test_ia_fora_do_ar_prepara_rascunho_com_template_e_nao_envia():
    with DbTemp():
        criar_lead(telefone=CELULAR)
        r = rodar_pipeline(ai=FakeAI(erro=AIRequestError("fora do ar")))
        assert r.link == URL_ONLINE
        (canal, mensagem, status), = rascunhos()
        assert (canal, status) == ("WHATSAPP", "DRAFT") and "Clínica" in mensagem and URL_ONLINE in mensagem


def test_rerodar_o_pipeline_atualiza_o_rascunho_sem_duplicar():
    with DbTemp():
        criar_lead(telefone=CELULAR, email=EMAIL)
        rodar_pipeline(ai=FakeAI("Primeira versão"))
        rodar_pipeline(ai=FakeAI("Segunda versão"))
        linhas = rascunhos()
        assert [(c, s) for c, _, s in linhas] == [("WHATSAPP", "DRAFT"), ("EMAIL", "DRAFT")]
        assert all(m.startswith("Segunda versão") for _, m, _ in linhas)


# ---------------------------------------------------------------- banco: rascunhos, brief e CRM

def test_save_outreach_draft_atualiza_por_canal_e_corrige_sent_legado():
    with DbTemp():
        lead_id = criar_lead()
        with sqlite3.connect(database.DB_PATH) as conn:  # linha antiga que dizia ter sido enviada (falsa)
            conn.execute("INSERT INTO outreach (lead_id, canal, mensagem, status) VALUES (?, 'WHATSAPP', 'antiga', 'SENT')", (lead_id,))
        database.save_outreach_draft(lead_id, "whatsapp", "nova")
        database.save_outreach_draft(lead_id, "email", "msg email")
        database.save_outreach_draft(lead_id, "whatsapp", "nova 2")
        assert rascunhos() == [("WHATSAPP", "nova 2", "DRAFT"), ("EMAIL", "msg email", "DRAFT")]


def test_get_all_leads_nao_duplica_lead_com_varios_rascunhos():
    with DbTemp():
        id_a = criar_lead(url="https://a.com.br/")
        id_b = criar_lead(url="https://b.com.br/")
        database.save_outreach_draft(id_a, "whatsapp", "zap A")
        database.save_outreach_draft(id_a, "email", "email A")
        database.save_outreach_draft(id_b, "email", "email B")
        database.save_design_brief("https://a.com.br/", "brief A")
        leads = database.get_all_leads()
        assert sorted(l["url"] for l in leads) == ["https://a.com.br/", "https://b.com.br/"]
        a = next(l for l in leads if l["url"] == "https://a.com.br/")
        assert a["outreach_message"] == "zap A" and a["design_brief"] == "brief A"


def test_save_design_brief_nao_cria_outreach_e_preserva_o_link_depois():
    with DbTemp():
        criar_lead()
        database.save_design_brief(URL, "brief 1")
        assert rascunhos() == []
        database.update_lead_status(URL, "DEPLOYED", vercel_url=URL_ONLINE)
        database.save_design_brief(URL, "brief 2")
        lead = database.get_all_leads()[0]
        assert (lead["design_brief"], lead["vercel_url"]) == ("brief 2", URL_ONLINE)
        database.save_design_brief("https://inexistente.com/", "x")  # lead desconhecido: não cria nada
        assert len(database.get_all_leads()) == 1


# ---------------------------------------------------------------- o código do pipeline

def test_codigo_do_pipeline_nao_usa_dispatch_nem_fixa_whatsapp_nem_muda_status_ao_preparar():
    with open(os.path.join(ROOT_DIR, "main.py"), encoding="utf-8") as f:
        fonte = f.read()
    assert ".dispatch(" not in fonte and 'canal="whatsapp"' not in fonte and "save_outreach_data" not in fonte
    assert "preparar_envio(" in inspect.getsource(main.preparar_outreach_do_lead)
    assert "update_lead_status" not in inspect.getsource(main.preparar_outreach_do_lead)
    assert "'SENT'" not in fonte and '"SENT"' not in fonte


# ---------------------------------------------------------------- runner (sem depender do pytest)

if __name__ == "__main__":
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = 0
    print("=== Testes de integração: pipeline + preparação de outreach ===\n")
    for nome, fn in testes:
        try:
            fn()
            print(f"✓ {nome}")
        except Exception as e:
            falhas += 1
            print(f"✗ {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    sys.exit(1 if falhas else 0)
