"""
Testes do tratamento de erros da camada de IA.

Sem rede, sem GEMINI_API_KEY, sem tocar no leads.db real, sem deploy e sem envio de mensagens:
tudo usa fakes. Roda com `python tests/test_ai_error_handling.py` ou com pytest.
"""
import os
import sqlite3
import sys
import tempfile
from unittest import mock

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))
sys.path.insert(0, ROOT_DIR)

from google.genai import errors as genai_errors

import ai_service
from ai_service import (
    AIService, GeminiProvider, AIError, AIConfigError, AIRequestError, AIResponseError,
)
import design_director
import seo_optimizer
import outreach
import qa_engine


# ---------------------------------------------------------------- fakes

class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.prompt_feedback = None


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes):
        self.models = FakeModels(outcomes)


def provider_with(outcomes):
    provider = GeminiProvider("chave-falsa")
    provider._client = FakeClient(outcomes)
    return provider


def api_error(cls, code):
    return cls(code, {"error": {"code": code, "message": "falha simulada", "status": "TESTE"}})


class FakeAI:
    """Substitui o singleton `ai` dentro dos módulos que dependem da IA."""
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def generate_structured(self, prompt, schema_hint=None, **kwargs):
        if self.error:
            raise self.error
        return self.result

    def generate_text(self, prompt, **kwargs):
        if self.error:
            raise self.error
        return self.result


def raises(exc_type, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except exc_type as e:
        return e
    raise AssertionError(f"esperava {exc_type.__name__}, mas nada foi levantado")


# ---------------------------------------------------------------- AIService / GeminiProvider

def test_texto_sucesso():
    provider = provider_with([FakeResponse("  Olá  ")])
    assert provider.generate_text("p", "m", 0.5) == "Olá"


def test_texto_vazio_vira_erro_e_nao_string_vazia():
    for texto in ("", "   ", None):
        provider = provider_with([FakeResponse(texto)])
        raises(AIResponseError, provider.generate_text, "p", "m", 0.5)


def test_structured_sucesso_e_json_com_cerca_markdown():
    assert provider_with([FakeResponse('{"a": 1}')]).generate_structured("p", None, "m", 0.1) == {"a": 1}
    cercado = '```json\n{"a": 2}\n```'
    assert provider_with([FakeResponse(cercado)]).generate_structured("p", None, "m", 0.1) == {"a": 2}


def test_structured_invalido_vazio_ou_nao_objeto_vira_erro_e_nao_dict_vazio():
    for texto in ("não é json", "{}", "[1, 2]", "", None):
        provider = provider_with([FakeResponse(texto)])
        raises(AIResponseError, provider.generate_structured, "p", None, "m", 0.1)


def test_retry_em_erro_transitorio_depois_sucesso():
    provider = provider_with([api_error(genai_errors.ServerError, 503), api_error(genai_errors.ClientError, 429), FakeResponse("ok")])
    with mock.patch("ai_service.time.sleep") as sleep:
        assert provider.generate_text("p", "m", 0.5) == "ok"
    assert provider._client.models.calls == 3
    assert sleep.call_count == 2


def test_retry_esgotado_levanta_erro_de_requisicao():
    provider = provider_with([api_error(genai_errors.ServerError, 500)] * 3)
    with mock.patch("ai_service.time.sleep"):
        erro = raises(AIRequestError, provider.generate_text, "p", "m", 0.5)
    assert provider._client.models.calls == 3
    assert erro.status_code == 500 and erro.retryable is True


def test_erro_permanente_nao_e_repetido():
    provider = provider_with([api_error(genai_errors.ClientError, 401)])
    with mock.patch("ai_service.time.sleep") as sleep:
        erro = raises(AIRequestError, provider.generate_text, "p", "m", 0.5)
    assert provider._client.models.calls == 1
    assert sleep.call_count == 0
    assert erro.status_code == 401 and erro.retryable is False


def test_sem_api_key_levanta_config_error_sem_retry():
    provider = GeminiProvider(None)
    with mock.patch("ai_service.time.sleep") as sleep:
        raises(AIConfigError, provider.generate_text, "p", "m", 0.5)
        raises(AIConfigError, provider.generate_structured, "p", None, "m", 0.1)
    assert sleep.call_count == 0


def test_aiservice_propaga_falha_em_vez_de_mascarar():
    class ProviderQuebrado:
        def generate_text(self, *a, **k):
            raise AIRequestError("fora do ar", status_code=503, retryable=True)

        def generate_structured(self, *a, **k):
            raise AIResponseError("json ruim")

    service = AIService(provider=ProviderQuebrado())
    raises(AIRequestError, service.generate_text, "p")
    raises(AIResponseError, service.generate_structured, "p")


def test_aiservice_sucesso_usa_modelo_padrao():
    vistos = {}

    class ProviderOk:
        def generate_text(self, prompt, model, temperature):
            vistos["model"] = model
            return "texto"

        def generate_structured(self, prompt, schema, model, temperature):
            return {"k": "v"}

    service = AIService(provider=ProviderOk())
    assert service.generate_text("p") == "texto"
    assert service.generate_structured("p") == {"k": "v"}
    assert vistos["model"] == "gemini-3.8-flash"


# ---------------------------------------------------------------- Design Director

LEAD = {"nome": "Silva & Santos", "nicho": "Advocacia", "cidade": "Curitiba"}


def design_valido():
    return {
        "nome_limpo": "Silva & Santos",
        "design_brief": "editorial",
        "theme": {"primary_color": "#111", "font_heading": "Playfair Display", "font_body": "Inter"},
        "layout": [{"type": "HeroEditorial", "props": {"title": "T", "subtitle": "S"}}],
    }


def test_design_director_resposta_valida_e_devolvida_sem_flag():
    with mock.patch.object(design_director, "ai", FakeAI(result=design_valido())):
        resultado = design_director.DesignDirector().generate_design(LEAD, {})
    assert "ai_fallback" not in resultado
    assert resultado["layout"][0]["type"] == "HeroEditorial"


def test_design_director_falha_da_ia_usa_fallback_marcado_e_sem_email_inventado():
    with mock.patch.object(design_director, "ai", FakeAI(error=AIRequestError("fora do ar"))):
        resultado = design_director.DesignDirector().generate_design(LEAD, {})
    assert resultado["ai_fallback"] is True
    assert resultado["layout"], "o fallback deve continuar existindo"
    assert "contato@" not in str(resultado) and "@" not in str(resultado["layout"])


def test_design_director_resposta_invalida_cai_no_fallback():
    invalidas = [
        {"nome_limpo": "X", "layout": []},
        {"nome_limpo": "X", "layout": "texto"},
        {"nome_limpo": "X", "layout": [{"props": {}}]},
        {"nome_limpo": "X", "layout": [{"type": "HeroMinimalist", "props": "x"}]},
        {"nome_limpo": "  ", "layout": [{"type": "HeroMinimalist", "props": {}}]},
        {"nome_limpo": "X", "theme": "azul", "layout": [{"type": "HeroMinimalist", "props": {}}]},
    ]
    for resposta in invalidas:
        with mock.patch.object(design_director, "ai", FakeAI(result=resposta)):
            resultado = design_director.DesignDirector().generate_design(LEAD, {})
        assert resultado["ai_fallback"] is True, resposta


def test_design_director_nao_engole_bug_que_nao_e_erro_de_ia():
    with mock.patch.object(design_director, "ai", FakeAI(error=KeyError("bug"))):
        raises(KeyError, design_director.DesignDirector().generate_design, LEAD, {})


# ---------------------------------------------------------------- SEO

def seo_valido():
    return {
        "meta_title": "Silva & Santos | Advocacia em Curitiba",
        "meta_description": "Descrição com CTA.",
        "keywords": ["advocacia"],
        "schema_json": {},
    }


def test_seo_resposta_valida_completa_schema_e_nao_tem_flag():
    with mock.patch.object(seo_optimizer, "ai", FakeAI(result=seo_valido())):
        resultado = seo_optimizer.otimizar_seo(LEAD, {"nome_limpo": "Silva & Santos"})
    assert "ai_fallback" not in resultado
    assert resultado["schema_json"]["@context"] == "https://schema.org"
    assert resultado["schema_json"]["address"]["addressLocality"] == "Curitiba"


def test_seo_falha_da_ia_usa_fallback_seguro_marcado():
    with mock.patch.object(seo_optimizer, "ai", FakeAI(error=AIResponseError("vazio"))):
        resultado = seo_optimizer.otimizar_seo(LEAD, {"nome_limpo": "Silva & Santos"})
    assert resultado["ai_fallback"] is True
    assert resultado["meta_title"] == "Silva & Santos | Advocacia em Curitiba"
    assert resultado["schema_json"]["@type"] == "LocalBusiness"


def test_seo_resposta_incompleta_cai_no_fallback():
    incompletas = [
        {"meta_title": "só título"},
        {**seo_valido(), "meta_description": ""},
        {**seo_valido(), "schema_json": "texto"},
        {**seo_valido(), "keywords": "a, b"},
    ]
    for resposta in incompletas:
        with mock.patch.object(seo_optimizer, "ai", FakeAI(result=resposta)):
            resultado = seo_optimizer.otimizar_seo(LEAD, {"nome_limpo": "Silva & Santos"})
        assert resultado["ai_fallback"] is True, resposta


# ---------------------------------------------------------------- Outreach

QUAL = {"factors": ["Site lento (5.0s)", "Sem HTTPS"], "opportunities": [], "motivos": ""}


def test_outreach_sucesso_usa_texto_da_ia():
    engine = outreach.OutreachEngine(":memory:")
    with mock.patch.object(outreach, "ai", FakeAI(result="Mensagem da IA")):
        assert engine.generate_message_with_status("Empresa X", QUAL) == ("Mensagem da IA", False)
        assert engine.generate_message("Empresa X", QUAL) == "Mensagem da IA"


def test_outreach_falha_da_ia_usa_template_com_dados_reais_e_informa():
    engine = outreach.OutreachEngine(":memory:")
    with mock.patch.object(outreach, "ai", FakeAI(error=AIRequestError("fora do ar"))):
        texto, usou_fallback = engine.generate_message_with_status("Empresa X", QUAL)
        assert engine.generate_message("Empresa X", QUAL) == texto
    assert usou_fallback is True
    assert "Empresa X" in texto and "Site lento (5.0s)" in texto
    assert texto.strip(), "nunca pode ser mensagem vazia"


def test_outreach_dispatch_informa_used_fallback_e_grava_mensagem_nao_vazia():
    outreach._rate_limits.clear()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "teste.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE leads (id INTEGER PRIMARY KEY, status TEXT)")
            conn.execute("CREATE TABLE outreach (id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, canal TEXT, mensagem TEXT, status TEXT)")
            conn.execute("INSERT INTO leads (id, status) VALUES (1, 'QUALIFIED')")
        engine = outreach.OutreachEngine(db_path)
        with mock.patch.object(outreach, "ai", FakeAI(error=AIResponseError("vazio"))):
            resultado = engine.dispatch(1, "Empresa X", QUAL, canal="whatsapp")
        assert resultado["status"] == "success" and resultado["used_fallback"] is True
        with sqlite3.connect(db_path) as conn:
            mensagem = conn.execute("SELECT mensagem FROM outreach WHERE lead_id = 1").fetchone()[0]
        assert mensagem and "Empresa X" in mensagem
    outreach._rate_limits.clear()


# ---------------------------------------------------------------- QA (auto-fix por IA)

def test_qa_auto_fix_nao_sobrescreve_o_html_quando_a_ia_falha():
    with tempfile.TemporaryDirectory() as tmp:
        engine = qa_engine.QAEngine("site-de-teste")
        engine.base_path = tmp
        engine.html_path = os.path.join(tmp, "index.html")
        original = "<html><head></head><body><h1>Oi</h1></body></html>"
        with open(engine.html_path, "w", encoding="utf-8") as f:
            f.write(original)
        erros = engine.run_checks()
        assert erros, "o HTML de teste precisa ter erros para acionar o auto-fix"
        with mock.patch.object(qa_engine, "ai", FakeAI(error=AIRequestError("fora do ar"))):
            assert engine.auto_fix(erros) is False
        with open(engine.html_path, encoding="utf-8") as f:
            assert f.read() == original


# ---------------------------------------------------------------- Pipeline (guarda do ai_fallback)

def test_pipeline_cancela_sem_gerar_nem_publicar_quando_design_director_cai_no_fallback():
    import main  # import tardio: carrega todos os módulos do pipeline

    class DirectorEmFallback:
        def generate_design(self, lead_data, dados_auditoria):
            return {"ai_fallback": True, "nome_limpo": "Silva", "layout": [{"type": "HeroMinimalist", "props": {}}]}

    chamadas = []
    with mock.patch.object(main, "auditar_site_lead", return_value={"status": "Sucesso"}), \
         mock.patch.object(main, "DesignDirector", DirectorEmFallback), \
         mock.patch.object(main, "otimizar_seo", side_effect=lambda *a, **k: chamadas.append("seo")), \
         mock.patch.object(main, "gerar_site_cliente", side_effect=lambda *a, **k: chamadas.append("gerar")), \
         mock.patch.object(main, "executar_qa", side_effect=lambda *a, **k: chamadas.append("qa")), \
         mock.patch.object(main, "fazer_deploy_site", side_effect=lambda *a, **k: chamadas.append("deploy")):
        resultado = main.executar_pipeline_completo("Silva", "Advocacia", "Curitiba", "https://exemplo.invalid")
    assert resultado is None
    assert chamadas == [], f"nada deveria ter sido chamado, mas foi: {chamadas}"


# ---------------------------------------------------------------- runner (sem depender do pytest)

if __name__ == "__main__":
    testes = [(nome, fn) for nome, fn in sorted(globals().items()) if nome.startswith("test_") and callable(fn)]
    falhas = 0
    print("=== Testes: tratamento de erros da camada de IA ===\n")
    for nome, fn in testes:
        try:
            fn()
            print(f"✓ {nome}")
        except Exception as e:
            falhas += 1
            print(f"✗ {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    sys.exit(1 if falhas else 0)
