"""
Testes da camada de preparação de contato do outreach (nenhuma mensagem é enviada).

Sem rede (socket.connect é bloqueado nos testes que preparam envio), sem API de IA (fake), sem deploy
e sem tocar no leads.db real (database.DB_PATH aponta para um SQLite temporário).
Roda com `python tests/test_outreach_prep.py` ou com pytest.
"""
import os
import sqlite3
import sys
import tempfile
from unittest import mock

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))
sys.path.insert(0, ROOT_DIR)

import database
import outreach
from ai_service import AIRequestError
from outreach import (
    SEM_CONTATO, SOMENTE_TELEFONE, SOMENTE_EMAIL, TELEFONE_E_EMAIL,
    analisar_contatos, canais_disponiveis, montar_payload_envio,
)

CELULAR = "+5511975859568"
FIXO = "+551140123456"
URL = "https://clinica.com.br/"
QUAL = {"factors": ["Site lento (5.0s)", "Sem HTTPS"], "opportunities": [], "motivos": ""}


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
    def __init__(self, texto="Mensagem da IA", erro=None):
        self.texto, self.erro, self.prompts = texto, erro, []

    def generate_text(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if self.erro:
            raise self.erro
        return self.texto


def sem_rede():
    return mock.patch("socket.socket.connect", side_effect=AssertionError("tentou acessar a rede"))


def criar_lead(telefone="", email="", status="QUALIFIED", url=URL):
    """Cria o lead e grava os contatos EXATAMENTE como passados (inclusive valores sujos), via SQL."""
    database.init_db()
    database.insert_lead("Clínica", url, "d", "n", "c")
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("UPDATE leads SET telefone = ?, email = ?, status = ? WHERE url = ?", (telefone, email, status, url))
    return outreach.OutreachEngine(database.DB_PATH), database.get_lead_by_url(url)["id"]


def snapshot():
    with sqlite3.connect(database.DB_PATH) as conn:
        leads = conn.execute("SELECT id, telefone, email, status FROM leads ORDER BY id").fetchall()
        n_outreach = conn.execute("SELECT COUNT(*) FROM outreach").fetchone()[0]
    return leads, n_outreach


# ---------------------------------------------------------------- análise: os 4 cenários de contato

def test_lead_sem_contato():
    vazios = [{}, {"telefone": "", "email": ""}, {"telefone": None, "email": None},
              {"telefone": "abc", "email": "sem-arroba"}, {"telefone": float("nan"), "email": float("nan")}]
    for contatos in vazios:
        analise = analisar_contatos(contatos)
        assert analise["situacao"] == SEM_CONTATO, contatos
        assert analise["canais"] == [] and analise["telefone"] == "" and analise["email"] == ""
        assert canais_disponiveis(contatos) == []


def test_lead_so_com_celular_habilita_whatsapp():
    analise = analisar_contatos({"telefone": "(11) 97585-9568", "email": ""})
    assert analise["situacao"] == SOMENTE_TELEFONE
    assert analise["canais"] == ["whatsapp"]
    assert analise["telefone_eh_celular"] is True and analise["telefone"] == CELULAR


def test_lead_so_com_telefone_fixo_nao_habilita_nenhum_canal():
    analise = analisar_contatos({"telefone": "(11) 4012-3456", "email": ""})
    assert analise["situacao"] == SOMENTE_TELEFONE
    assert analise["canais"] == [] and analise["telefone_eh_celular"] is False and analise["telefone"] == FIXO


def test_lead_so_com_email_habilita_email():
    analise = analisar_contatos({"telefone": "", "email": "Contato@Clinica.com.br"})
    assert analise["situacao"] == SOMENTE_EMAIL
    assert analise["canais"] == ["email"] and analise["email"] == "contato@clinica.com.br"


def test_lead_com_ambos():
    completo = analisar_contatos({"telefone": CELULAR, "email": "contato@clinica.com.br"})
    assert completo["situacao"] == TELEFONE_E_EMAIL
    assert completo["canais"] == ["whatsapp", "email"]
    com_fixo = analisar_contatos({"telefone": FIXO, "email": "contato@clinica.com.br"})
    assert com_fixo["situacao"] == TELEFONE_E_EMAIL and com_fixo["canais"] == ["email"]


def test_contato_invalido_conta_como_ausente():
    so_email = analisar_contatos({"telefone": "12345-678", "email": "contato@clinica.com.br"})
    assert so_email["situacao"] == SOMENTE_EMAIL and so_email["canais"] == ["email"]
    so_tel = analisar_contatos({"telefone": CELULAR, "email": "noreply@clinica.com.br"})
    assert so_tel["situacao"] == SOMENTE_TELEFONE and so_tel["canais"] == ["whatsapp"]
    assert canais_disponiveis({"telefone": "", "email": "sem-arroba"}) == []


def test_analise_nao_altera_a_entrada_e_nao_duplica_canais():
    entrada = {"telefone": "(11) 97585-9568", "email": "Contato@Clinica.com.br"}
    copia = dict(entrada)
    analise = analisar_contatos(entrada)
    assert entrada == copia  # só devolve versões normalizadas; o original fica intacto
    assert len(analise["canais"]) == len(set(analise["canais"])) == 2


def test_analise_aceita_linha_de_dataframe_como_no_app():
    try:
        import pandas as pd
    except ImportError:
        return  # pandas é dependência do app, não dos testes
    df = pd.DataFrame([
        {"telefone": CELULAR, "email": "a@clinica.com.br"},
        {"telefone": FIXO, "email": None},
        {"telefone": "", "email": "b@clinica.com.br"},
        {"telefone": None, "email": None},
    ])
    df["contato"] = df.apply(lambda lead: analisar_contatos(lead)["situacao"], axis=1)  # mesma linha do app.py
    assert list(df["contato"]) == [TELEFONE_E_EMAIL, SOMENTE_TELEFONE, SOMENTE_EMAIL, SEM_CONTATO]


# ---------------------------------------------------------------- payload

def test_payload_whatsapp():
    msg = "Olá, tudo bem?\n\nVeja: https://x.vercel.app"
    payload = montar_payload_envio("whatsapp", CELULAR, msg, "Clínica Boa")
    assert payload["canal"] == "whatsapp" and payload["destino"] == CELULAR
    assert payload["mensagem"] == msg and payload["sent"] is False
    assert payload["link_whatsapp"].startswith("https://wa.me/5511975859568?text=")
    assert "%0A%0A" in payload["link_whatsapp"] and " " not in payload["link_whatsapp"]
    assert "assunto" not in payload


def test_payload_email():
    payload = montar_payload_envio("email", "contato@clinica.com.br", "Corpo", "Clínica Boa")
    assert payload["canal"] == "email" and payload["destino"] == "contato@clinica.com.br"
    assert payload["assunto"] == "Sobre o site da Clínica Boa" and payload["sent"] is False
    assert "link_whatsapp" not in payload
    assert montar_payload_envio("email", "a@b.com.br", "x")["assunto"] == "Sobre o site da sua empresa"


def test_payload_canal_desconhecido_e_erro():
    try:
        montar_payload_envio("sms", "123", "x")
    except ValueError:
        return
    raise AssertionError("canal inválido deveria levantar ValueError")


# ---------------------------------------------------------------- preparar_envio (engine + banco)

def test_preparar_envio_sem_contato_nao_gera_mensagem():
    with DbTemp():
        engine, lead_id = criar_lead()
        fake = FakeAI()
        with mock.patch.object(outreach, "ai", fake), sem_rede():
            r = engine.preparar_envio(lead_id, "Clínica", QUAL)
        assert r["status"] == "no_contact" and r["situacao"] == SEM_CONTATO
        assert r["canais"] == [] and r["sent"] is False and "payloads" not in r
        assert fake.prompts == []  # sem canal, não gasta IA


def test_preparar_envio_so_telefone_fixo_e_no_contact_com_motivo():
    with DbTemp():
        engine, lead_id = criar_lead(telefone=FIXO)
        with mock.patch.object(outreach, "ai", FakeAI()):
            r = engine.preparar_envio(lead_id, "Clínica", QUAL)
        assert r["status"] == "no_contact" and r["situacao"] == SOMENTE_TELEFONE
        assert "fixo" in r["reason"]


def test_preparar_envio_so_celular_gera_payload_whatsapp():
    with DbTemp():
        engine, lead_id = criar_lead(telefone=CELULAR)
        with mock.patch.object(outreach, "ai", FakeAI("Oi!")), sem_rede():
            r = engine.preparar_envio(lead_id, "Clínica", QUAL)
        assert r["status"] == "ready" and r["situacao"] == SOMENTE_TELEFONE and r["sent"] is False
        assert [p["canal"] for p in r["payloads"]] == ["whatsapp"]
        assert r["payloads"][0]["destino"] == CELULAR and r["payloads"][0]["mensagem"] == "Oi!"


def test_preparar_envio_so_email_gera_payload_email():
    with DbTemp():
        engine, lead_id = criar_lead(email="contato@clinica.com.br")
        with mock.patch.object(outreach, "ai", FakeAI("Olá!")), sem_rede():
            r = engine.preparar_envio(lead_id, "Clínica", QUAL)
        assert r["status"] == "ready" and r["situacao"] == SOMENTE_EMAIL
        assert [p["canal"] for p in r["payloads"]] == ["email"]
        assert r["payloads"][0]["destino"] == "contato@clinica.com.br" and r["payloads"][0]["assunto"]


def test_preparar_envio_com_ambos_gera_um_payload_por_canal_sem_duplicar():
    with DbTemp():
        engine, lead_id = criar_lead(telefone=CELULAR, email="contato@clinica.com.br")
        fake = FakeAI("Texto")
        with mock.patch.object(outreach, "ai", fake), sem_rede():
            r = engine.preparar_envio(lead_id, "Clínica", QUAL)
        assert r["status"] == "ready" and r["situacao"] == TELEFONE_E_EMAIL
        assert [p["canal"] for p in r["payloads"]] == ["whatsapp", "email"] == r["canais"]
        assert [p["destino"] for p in r["payloads"]] == [CELULAR, "contato@clinica.com.br"]
        assert len(fake.prompts) == 2 and "whatsapp" in fake.prompts[0] and "email" in fake.prompts[1]
        assert all(p["sent"] is False for p in r["payloads"])


def test_preparar_envio_usa_mensagem_pronta_e_anexa_link_uma_vez():
    with DbTemp():
        engine, lead_id = criar_lead(telefone=CELULAR, email="contato@clinica.com.br")
        fake = FakeAI()
        with mock.patch.object(outreach, "ai", fake):
            r = engine.preparar_envio(lead_id, "Clínica", QUAL, mensagem="Mensagem pronta", link_prototipo="https://x.vercel.app")
            ja_tem = engine.preparar_envio(lead_id, "Clínica", QUAL, mensagem="Veja https://x.vercel.app", link_prototipo="https://x.vercel.app")
        assert fake.prompts == []  # mensagem pronta: nenhuma chamada de IA
        assert all(p["mensagem"] == "Mensagem pronta\n\nVeja o protótipo: https://x.vercel.app" for p in r["payloads"])
        assert all(p["mensagem"].count("https://x.vercel.app") == 1 for p in ja_tem["payloads"])
        assert all(p["usou_fallback"] is False for p in r["payloads"])


def test_preparar_envio_com_ia_fora_do_ar_usa_template_e_informa():
    with DbTemp():
        engine, lead_id = criar_lead(telefone=CELULAR)
        with mock.patch.object(outreach, "ai", FakeAI(erro=AIRequestError("fora do ar"))):
            r = engine.preparar_envio(lead_id, "Clínica", QUAL)
        payload = r["payloads"][0]
        assert payload["usou_fallback"] is True and "Clínica" in payload["mensagem"] and payload["mensagem"].strip()


def test_preparar_envio_bloqueia_lead_perdido():
    with DbTemp():
        engine, lead_id = criar_lead(telefone=CELULAR, email="contato@clinica.com.br", status="LOST")
        fake = FakeAI()
        with mock.patch.object(outreach, "ai", fake):
            r = engine.preparar_envio(lead_id, "Clínica", QUAL)
        assert r["status"] == "blocked" and r["sent"] is False and "payloads" not in r
        assert fake.prompts == []


def test_preparar_envio_lead_inexistente_e_no_contact():
    with DbTemp():
        engine, _ = criar_lead()
        with mock.patch.object(outreach, "ai", FakeAI()):
            assert engine.preparar_envio(9999, "X", QUAL)["status"] == "no_contact"


def test_preparar_envio_nao_altera_contatos_nem_grava_nada():
    with DbTemp():
        engine, lead_id = criar_lead(telefone="(11) 97585-9568", email="Contato@Clinica.com.br")  # valores "sujos" de propósito
        antes = snapshot()
        with mock.patch.object(outreach, "ai", FakeAI()):
            r = engine.preparar_envio(lead_id, "Clínica", QUAL)
        assert snapshot() == antes  # contatos guardados continuam como estavam; nenhuma linha em outreach
        assert antes[1] == 0
        assert [p["destino"] for p in r["payloads"]] == [CELULAR, "contato@clinica.com.br"]  # só o payload é normalizado


def test_analisar_lead_le_do_banco():
    with DbTemp():
        engine, lead_id = criar_lead(telefone=FIXO, email="contato@clinica.com.br")
        assert engine.analisar_lead(lead_id)["situacao"] == TELEFONE_E_EMAIL
        assert engine.analisar_lead(lead_id)["canais"] == ["email"]
        assert engine.analisar_lead(9999)["situacao"] == SEM_CONTATO


# ---------------------------------------------------------------- dispatch não finge que enviou

def test_dispatch_registra_rascunho_e_nunca_sent():
    with DbTemp() as db:
        engine, lead_id = criar_lead(telefone=CELULAR)
        with mock.patch.object(outreach, "ai", FakeAI("Msg")), sem_rede():
            r = engine.dispatch(lead_id, "Clínica", QUAL, canal="whatsapp")
        assert r["status"] == "success" and r["sent"] is False and r["message"] == "Msg"
        with sqlite3.connect(db.path) as conn:
            linhas = conn.execute("SELECT canal, mensagem, status FROM outreach").fetchall()
        assert linhas == [("WHATSAPP", "Msg", "DRAFT")]


def test_migracao_legada_nao_marca_mensagem_antiga_como_enviada():
    with DbTemp() as db:
        with sqlite3.connect(db.path) as conn:
            conn.executescript("""
                CREATE TABLE leads (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, url TEXT UNIQUE, descricao TEXT,
                    nicho TEXT, cidade TEXT, status TEXT, score INTEGER, motivos_score TEXT, vercel_url TEXT,
                    design_brief TEXT, outreach_message TEXT, criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                INSERT INTO leads (nome, url, descricao, nicho, cidade, status, score, motivos_score, vercel_url, design_brief, outreach_message)
                VALUES ('Legado', 'https://legado.com.br/', 'd', 'n', 'c', 'DEPLOYED', 10, 'm', 'https://l.vercel.app', 'brief', 'msg antiga');
            """)
        database.init_db()
        with sqlite3.connect(db.path) as conn:
            assert conn.execute("SELECT mensagem, status FROM outreach").fetchall() == [("msg antiga", "DRAFT")]


def test_codigo_de_outreach_nao_grava_status_sent():
    for caminho in ("src/outreach.py", "src/database.py"):
        with open(os.path.join(ROOT_DIR, caminho), encoding="utf-8") as f:
            fonte = f.read()
        assert "'SENT'" not in fonte and '"SENT"' not in fonte, caminho


def test_app_mostra_a_situacao_de_contato_no_crm():
    with open(os.path.join(ROOT_DIR, "app.py"), encoding="utf-8") as f:
        fonte = f.read()
    assert "from outreach import analisar_contatos" in fonte
    assert 'df_crm["contato"]' in fonte and '"contato", "vercel_url"' in fonte


# ---------------------------------------------------------------- runner (sem depender do pytest)

if __name__ == "__main__":
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = 0
    print("=== Testes: preparação de contato do outreach ===\n")
    for nome, fn in testes:
        try:
            fn()
            print(f"✓ {nome}")
        except Exception as e:
            falhas += 1
            print(f"✗ {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    sys.exit(1 if falhas else 0)
