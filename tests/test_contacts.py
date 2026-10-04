"""
Testes da captura de contatos (telefone/e-mail) dos leads.

Sem rede real (requests.get e DDGS são substituídos por fakes), sem API de IA, sem deploy, sem envio
de mensagens e sem tocar no leads.db real (database.DB_PATH aponta para um SQLite temporário).
Roda com `python tests/test_contacts.py` ou com pytest.
"""
import os
import sqlite3
import sys
import tempfile
from unittest import mock

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))
sys.path.insert(0, ROOT_DIR)

import requests

import contact_extractor as ce
import database
import lead_scraper
import outreach

CELULAR = "+5511975859568"
FIXO = "+551140123456"


# ---------------------------------------------------------------- helpers

class DbTemp:
    """Aponta database.DB_PATH para um arquivo temporário (nunca o leads.db real)."""
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "teste.db")
        self._patch = mock.patch.object(database, "DB_PATH", self.path)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()


def colunas(path, tabela="leads"):
    with sqlite3.connect(path) as conn:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")]


class Resp:
    def __init__(self, text="", status=200, url="https://site.com.br/"):
        self.text, self.status_code, self.url = text, status, url


def pagina(corpo):
    return f"<html><body>{corpo}</body></html>"


# ---------------------------------------------------------------- normalização de telefone

def test_telefone_formatos_validos_viram_e164():
    casos = {
        "(11) 97585-9568": CELULAR,
        "11 97585-9568": CELULAR,
        "+55 11 97585-9568": CELULAR,
        "5511975859568": CELULAR,
        "011 97585-9568": CELULAR,
        "(11) 4012-3456": FIXO,
        "+55 (55) 3025-1234": "+555530251234",  # DDD 55 não é confundido com o código do país
    }
    for bruto, esperado in casos.items():
        assert ce.normalizar_telefone_br(bruto) == esperado, bruto


def test_telefone_lixo_e_rejeitado():
    for bruto in ["", "abc", "0800 123 4567", "12345-678", "(00) 1234-5678", "(11) 1234-5678",
                  "(11) 99999-9999", "(11) 8888-7777", "123.456.789-01", "12.345.678/0001-90"]:
        assert ce.normalizar_telefone_br(bruto) == "", bruto


def test_eh_celular():
    assert ce.eh_celular_br("(11) 97585-9568") is True
    assert ce.eh_celular_br("(11) 4012-3456") is False
    assert ce.eh_celular_br("") is False
    assert ce.eh_celular_br("lixo") is False


# ---------------------------------------------------------------- normalização de e-mail

def test_email_normaliza_e_rejeita_lixo():
    assert ce.normalizar_email("  Contato@Site.COM.br. ") == "contato@site.com.br"
    for ruim in ["", "sem-arroba", "logo@2x.png", "foto@banner.jpg", "noreply@site.com.br",
                 "seuemail@seudominio.com.br", "nome@example.com", "abc@o123.ingest.sentry.io", "a..b@site.com"]:
        assert ce.normalizar_email(ruim) == "", ruim


# ---------------------------------------------------------------- extração do HTML

def test_extrai_de_links_tel_mailto_e_whatsapp_preferindo_celular():
    html = pagina(
        '<a href="tel:+55 (11) 4012-3456">Ligue</a>'
        '<a href="https://wa.me/5511975859568?text=Oi">Zap</a>'
        '<a href="mailto:Contato@Site.com.br?subject=Oi">E-mail</a>'
    )
    assert ce.extrair_contatos_do_html(html, "https://www.site.com.br/") == {"telefone": CELULAR, "email": "contato@site.com.br"}


def test_extrai_do_texto_visivel():
    html = pagina("<p>Telefone: (11) 4012-3456 | WhatsApp 11 97585-9568</p><p>E-mail: contato@dominio-real.com.br</p>")
    assert ce.extrair_contatos_do_html(html, "https://dominio-real.com.br") == {"telefone": CELULAR, "email": "contato@dominio-real.com.br"}


def test_usa_fixo_quando_nao_ha_celular():
    html = pagina("<p>Fone (11) 4012-3456</p>")
    assert ce.extrair_contatos_do_html(html, "https://x.com.br")["telefone"] == FIXO


def test_mesmo_numero_em_formatos_diferentes_nao_duplica():
    assert ce._sem_duplicados([ce.normalizar_telefone_br(t) for t in ["tel:11975859568"[4:], "(11) 97585-9568", "+55 11 97585-9568"]]) == [CELULAR]


def test_numeros_que_nao_sao_telefone_sao_ignorados():
    html = pagina("<p>CNPJ 12.345.678/0001-90 CEP 12345-678 CPF 123.456.789-01 em 02/10/2026 22:55 "
                  "ID 1790985600 anos 2024 2025 2026</p>")
    assert ce.extrair_contatos_do_html(html, "https://x.com.br") == {"telefone": "", "email": ""}


def test_scripts_e_estilos_sao_ignorados():
    html = '<html><head><script>var t="(11) 97585-9568"; var e="a@dominio.com.br";</script><style>.a{}</style></head><body>oi</body></html>'
    assert ce.extrair_contatos_do_html(html, "https://dominio.com.br") == {"telefone": "", "email": ""}


def test_email_do_dominio_do_site_vence_gmail_e_agencia_e_lixo_e_ignorado():
    html = pagina("<p>clinicax@gmail.com | contato@clinica.com.br | dev@agenciaweb.com.br | logo@2x.png | noreply@clinica.com.br</p>")
    assert ce.extrair_contatos_do_html(html, "https://www.clinica.com.br/")["email"] == "contato@clinica.com.br"


def test_gmail_so_e_aceito_sem_email_proprio_e_email_de_agencia_nunca():
    so_gmail = pagina("<p>clinicax@gmail.com e dev@agenciaweb.com.br</p>")
    assert ce.extrair_contatos_do_html(so_gmail, "https://clinica.com.br")["email"] == "clinicax@gmail.com"
    so_agencia = pagina("<p>dev@agenciaweb.com.br</p>")
    assert ce.extrair_contatos_do_html(so_agencia, "https://clinica.com.br")["email"] == ""


def test_html_vazio_ou_sem_contato_nao_inventa_nada():
    for html in ["", None, pagina("<p>Bem-vindo ao nosso site</p>")]:
        assert ce.extrair_contatos_do_html(html, "https://x.com.br") == {"telefone": "", "email": ""}


# ---------------------------------------------------------------- busca no site (rede mockada)

def test_busca_na_home_faz_uma_requisicao_quando_acha_tudo():
    home = pagina('<a href="tel:11975859568">x</a><a href="mailto:contato@site.com.br">y</a>')
    with mock.patch.object(ce.requests, "get", side_effect=[Resp(home)]) as get:
        assert ce.buscar_contatos_do_site("https://site.com.br/") == {"telefone": CELULAR, "email": "contato@site.com.br"}
    assert get.call_count == 1


def test_busca_segue_uma_pagina_de_contato_do_mesmo_dominio():
    home = pagina('<a href="/contato">Fale conosco</a>')
    contato = pagina("<p>Fale: (11) 97585-9568 contato@site.com.br</p>")
    with mock.patch.object(ce.requests, "get", side_effect=[Resp(home), Resp(contato, url="https://site.com.br/contato")]) as get:
        assert ce.buscar_contatos_do_site("https://site.com.br/") == {"telefone": CELULAR, "email": "contato@site.com.br"}
    assert get.call_count == 2
    assert get.call_args_list[1].args[0] == "https://site.com.br/contato"


def test_busca_mescla_home_e_pagina_de_contato():
    home = pagina('<a href="/contato">Contato</a><p>(11) 97585-9568</p>')
    contato = pagina("<p>contato@site.com.br</p>")
    with mock.patch.object(ce.requests, "get", side_effect=[Resp(home), Resp(contato, url="https://site.com.br/contato")]):
        assert ce.buscar_contatos_do_site("https://site.com.br/") == {"telefone": CELULAR, "email": "contato@site.com.br"}


def test_busca_nao_segue_contato_de_outro_dominio():
    home = pagina('<a href="https://outro.com/contato">Contato</a>')
    with mock.patch.object(ce.requests, "get", side_effect=[Resp(home)]) as get:
        assert ce.buscar_contatos_do_site("https://site.com.br/") == {"telefone": "", "email": ""}
    assert get.call_count == 1


def test_busca_com_falha_de_rede_ou_status_ruim_devolve_vazio():
    vazio = {"telefone": "", "email": ""}
    with mock.patch.object(ce.requests, "get", side_effect=requests.ConnectionError("fora")):
        assert ce.buscar_contatos_do_site("https://site.com.br/") == vazio
    with mock.patch.object(ce.requests, "get", side_effect=[Resp("<p>(11) 97585-9568</p>", status=404)]):
        assert ce.buscar_contatos_do_site("https://site.com.br/") == vazio


# ---------------------------------------------------------------- schema / migração

# Schema EXATO do leads.db atual (antes das colunas de contato)
SCHEMA_ATUAL_SEM_CONTATO = """
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, url TEXT UNIQUE, descricao TEXT, nicho TEXT, cidade TEXT,
    status TEXT DEFAULT 'NEW', score INTEGER DEFAULT 0, motivos_score TEXT DEFAULT '', fonte TEXT DEFAULT '',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP, atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE audits (id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, score INTEGER, motivos TEXT);
CREATE TABLE outreach (id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, canal TEXT, mensagem TEXT, status TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, slug TEXT, vercel_url TEXT,
    design_brief TEXT, status TEXT, criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TRIGGER update_leads_atualizado_em AFTER UPDATE ON leads
BEGIN UPDATE leads SET atualizado_em = CURRENT_TIMESTAMP WHERE id = NEW.id; END;
"""


def test_migracao_preserva_leads_existentes_e_e_idempotente():
    with DbTemp() as db:
        with sqlite3.connect(db.path) as conn:
            conn.executescript(SCHEMA_ATUAL_SEM_CONTATO)
            conn.execute("INSERT INTO leads (nome, url, descricao, nicho, cidade, status, score, motivos_score) "
                         "VALUES ('Advocacia Rossi', 'https://rossi.adv.br/', 'desc', 'Advogados', 'Braganca', 'DEPLOYED', 44, 'Lento')")
            conn.execute("INSERT INTO projects (lead_id, vercel_url, status) VALUES (1, 'https://rossi.vercel.app', 'COMPLETED')")
            conn.execute("INSERT INTO audits (lead_id, score, motivos) VALUES (1, 44, 'Lento')")
        assert "telefone" not in colunas(db.path)

        database.init_db()
        database.init_db()  # rodar de novo não pode quebrar nem duplicar colunas

        assert colunas(db.path).count("telefone") == 1 and colunas(db.path).count("email") == 1
        lead = database.get_lead_by_url("https://rossi.adv.br/")
        assert (lead["nome"], lead["status"], lead["score"], lead["motivos_score"]) == ("Advocacia Rossi", "DEPLOYED", 44, "Lento")
        assert lead["telefone"] == "" and lead["email"] == ""
        todos = database.get_all_leads()
        assert len(todos) == 1 and todos[0]["vercel_url"] == "https://rossi.vercel.app"
        with sqlite3.connect(db.path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM audits").fetchone()[0] == 1


def test_banco_novo_ja_nasce_com_as_colunas():
    with DbTemp() as db:
        database.init_db()
        assert {"telefone", "email"} <= set(colunas(db.path))


def test_migracao_do_schema_legado_continua_funcionando():
    with DbTemp() as db:
        with sqlite3.connect(db.path) as conn:
            conn.executescript("""
                CREATE TABLE leads (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, url TEXT UNIQUE, descricao TEXT,
                    nicho TEXT, cidade TEXT, status TEXT, score INTEGER, motivos_score TEXT, vercel_url TEXT,
                    design_brief TEXT, outreach_message TEXT, criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                INSERT INTO leads (nome, url, descricao, nicho, cidade, status, score, motivos_score, vercel_url, design_brief, outreach_message)
                VALUES ('Legado', 'https://legado.com.br/', 'd', 'n', 'c', 'DEPLOYED', 10, 'm', 'https://l.vercel.app', 'brief', 'msg');
            """)
        database.init_db()
        lead = database.get_lead_by_url("https://legado.com.br/")
        assert lead["nome"] == "Legado" and lead["telefone"] == "" and lead["email"] == ""
        assert {"telefone", "email"} <= set(colunas(db.path))
        assert database.get_all_leads()[0]["vercel_url"] == "https://l.vercel.app"


# ---------------------------------------------------------------- persistência

def test_update_lead_contacts_preenche_vazio_e_nunca_sobrescreve_nem_apaga():
    with DbTemp():
        database.init_db()
        url = "https://a.com.br/"
        database.insert_lead("A", url, "d", "n", "c")

        database.update_lead_contacts(url, CELULAR, "")
        lead = database.get_lead_by_url(url)
        assert (lead["telefone"], lead["email"]) == (CELULAR, "")

        database.update_lead_contacts(url, FIXO, "contato@a.com.br")  # telefone já existe: mantém
        lead = database.get_lead_by_url(url)
        assert (lead["telefone"], lead["email"]) == (CELULAR, "contato@a.com.br")

        database.update_lead_contacts(url, "", "")  # vazio nunca apaga
        lead = database.get_lead_by_url(url)
        assert (lead["telefone"], lead["email"]) == (CELULAR, "contato@a.com.br")


def test_get_leads_sem_contato():
    with DbTemp():
        database.init_db()
        database.insert_lead("Com", "https://com.com.br/", "d", "n", "c")
        database.insert_lead("Sem", "https://sem.com.br/", "d", "n", "c")
        database.update_lead_contacts("https://com.com.br/", "", "x@com.com.br")
        assert [l["nome"] for l in database.get_leads_sem_contato()] == ["Sem"]


# ---------------------------------------------------------------- discovery

def fake_ddgs(resultados):
    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def text(self, termo, max_results=5):
            return list(resultados)
    return FakeDDGS


def resultado(url, titulo="Clínica Boa - Home"):
    return {"href": url, "title": titulo, "body": "descrição"}


def rodar_discovery(resultados, contatos):
    fetch = mock.Mock(side_effect=contatos) if isinstance(contatos, Exception) else mock.Mock(return_value=contatos)
    with mock.patch.object(lead_scraper, "DDGS", fake_ddgs(resultados)), \
         mock.patch.object(lead_scraper, "buscar_contatos_do_site", fetch):
        lead_scraper.buscar_empresas("Clinica", "SP", max_resultados=5)
    return fetch


def test_discovery_salva_lead_com_contatos_e_nao_busca_em_dominio_banido():
    with DbTemp():
        fetch = rodar_discovery(
            [resultado("https://clinica.com.br/"), resultado("https://instagram.com/clinica")],
            {"telefone": CELULAR, "email": "contato@clinica.com.br"},
        )
        lead = database.get_lead_by_url("https://clinica.com.br/")
        assert (lead["telefone"], lead["email"]) == (CELULAR, "contato@clinica.com.br")
        assert fetch.call_count == 1
        assert database.get_lead_by_url("https://instagram.com/clinica") is None


def test_discovery_sem_contato_encontrado_mantem_campos_vazios():
    with DbTemp():
        rodar_discovery([resultado("https://clinica.com.br/")], {"telefone": "", "email": ""})
        lead = database.get_lead_by_url("https://clinica.com.br/")
        assert lead is not None and lead["telefone"] == "" and lead["email"] == ""


def test_discovery_nao_refaz_busca_nem_sobrescreve_lead_que_ja_tem_contato():
    with DbTemp():
        database.init_db()
        database.insert_lead("Clínica", "https://clinica.com.br/", "d", "n", "c")
        database.update_lead_contacts("https://clinica.com.br/", FIXO, "")
        fetch = rodar_discovery([resultado("https://clinica.com.br/")], {"telefone": CELULAR, "email": "novo@clinica.com.br"})
        assert fetch.call_count == 0
        lead = database.get_lead_by_url("https://clinica.com.br/")
        assert (lead["telefone"], lead["email"]) == (FIXO, "")


def test_discovery_busca_contato_de_lead_existente_que_nao_tem_nenhum():
    with DbTemp():
        database.init_db()
        database.insert_lead("Clínica", "https://clinica.com.br/", "d", "n", "c")
        fetch = rodar_discovery([resultado("https://clinica.com.br/")], {"telefone": CELULAR, "email": ""})
        assert fetch.call_count == 1
        assert database.get_lead_by_url("https://clinica.com.br/")["telefone"] == CELULAR


def test_discovery_nao_quebra_quando_a_busca_de_contato_falha():
    with DbTemp():
        rodar_discovery([resultado("https://a.com.br/"), resultado("https://b.com.br/")], RuntimeError("boom"))
        assert database.get_lead_by_url("https://a.com.br/") is not None
        assert database.get_lead_by_url("https://b.com.br/") is not None


def test_backfill_enriquece_so_leads_sem_contato():
    with DbTemp():
        database.init_db()
        for nome in ("a", "b", "c"):
            database.insert_lead(nome, f"https://{nome}.com.br/", "d", "n", "c")
        database.update_lead_contacts("https://c.com.br/", FIXO, "")

        def fake_busca(url):
            return {"telefone": CELULAR, "email": ""} if url == "https://a.com.br/" else {"telefone": "", "email": ""}

        with mock.patch.object(lead_scraper, "buscar_contatos_do_site", side_effect=fake_busca) as fetch:
            assert lead_scraper.enriquecer_contatos_pendentes() == 1
        assert fetch.call_count == 2  # c já tem contato e não é consultado
        assert database.get_lead_by_url("https://a.com.br/")["telefone"] == CELULAR
        assert database.get_lead_by_url("https://b.com.br/")["telefone"] == ""
        assert database.get_lead_by_url("https://c.com.br/")["telefone"] == FIXO


# ---------------------------------------------------------------- preparação do outreach

def test_canais_disponiveis():
    assert outreach.canais_disponiveis({"telefone": CELULAR, "email": "a@b.com.br"}) == ["whatsapp", "email"]
    assert outreach.canais_disponiveis({"telefone": CELULAR, "email": ""}) == ["whatsapp"]
    assert outreach.canais_disponiveis({"telefone": FIXO, "email": "a@b.com.br"}) == ["email"]
    assert outreach.canais_disponiveis({"telefone": FIXO, "email": ""}) == []
    assert outreach.canais_disponiveis({}) == []
    assert outreach.canais_disponiveis({"telefone": None, "email": None}) == []


def test_outreach_get_contacts_le_do_banco_sem_enviar_nada():
    with DbTemp() as db:
        database.init_db()
        database.insert_lead("A", "https://a.com.br/", "d", "n", "c")
        database.insert_lead("B", "https://b.com.br/", "d", "n", "c")
        database.update_lead_contacts("https://a.com.br/", CELULAR, "contato@a.com.br")
        engine = outreach.OutreachEngine(db.path)
        id_a = database.get_lead_by_url("https://a.com.br/")["id"]
        id_b = database.get_lead_by_url("https://b.com.br/")["id"]
        assert engine.get_contacts(id_a) == {"telefone": CELULAR, "email": "contato@a.com.br"}
        assert engine.get_contacts(id_b) == {"telefone": "", "email": ""}
        assert engine.get_contacts(9999) == {"telefone": "", "email": ""}
        assert outreach.canais_disponiveis(engine.get_contacts(id_a)) == ["whatsapp", "email"]
        with sqlite3.connect(db.path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM outreach").fetchone()[0] == 0


# ---------------------------------------------------------------- runner (sem depender do pytest)

if __name__ == "__main__":
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = 0
    print("=== Testes: captura de contatos ===\n")
    for nome, fn in testes:
        try:
            fn()
            print(f"✓ {nome}")
        except Exception as e:
            falhas += 1
            print(f"✗ {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    sys.exit(1 if falhas else 0)
