"""
Regressão: um pipeline que falha (retorna None) NÃO pode mover o lead para DEPLOYED.
Deploy com sucesso move para DEPLOYED, nunca para CONTACTED.

Usa um SQLite temporário (database.DB_PATH é substituído) e substitui executar_pipeline_completo
por um fake: sem API, sem deploy, sem envio de mensagens, sem tocar no leads.db real.
Roda com `python tests/test_pipeline_status.py` ou com pytest.
"""
import inspect
import os
import sys
import tempfile
from unittest import mock

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))
sys.path.insert(0, ROOT_DIR)

import database
import main

URL = "http://lead-teste-status.invalid"


class DbTemporario:
    """Banco isolado com um lead QUALIFIED."""
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(database, "DB_PATH", os.path.join(self._tmp.name, "teste.db"))
        self._patch.start()
        database.init_db()
        database.insert_lead("Lead Teste", URL, "desc", "Advocacia", "Curitiba")
        database.update_lead_status(URL, "QUALIFIED")
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._tmp.cleanup()


def rodar(retorno_pipeline=None, erro=None):
    fake = mock.Mock(return_value=retorno_pipeline, side_effect=erro)
    with mock.patch.object(main, "executar_pipeline_completo", fake):
        resultado = main.executar_pipeline_e_atualizar_status("Lead Teste", "Advocacia", "Curitiba", URL)
    return resultado, fake


def projeto_vercel_url():
    leads = [l for l in database.get_all_leads() if l["url"] == URL]
    return leads[0]["vercel_url"]


def test_falha_do_pipeline_nao_move_para_deployed():
    with DbTemporario():
        resultado, fake = rodar(retorno_pipeline=None)
        assert resultado is None
        fake.assert_called_once()
        status = database.get_lead_by_url(URL)["status"]
        assert status == "QUALIFIED"
        assert status != "DEPLOYED"
        assert not projeto_vercel_url()


def test_excecao_no_pipeline_nao_move_para_deployed():
    with DbTemporario():
        try:
            rodar(erro=RuntimeError("falha simulada"))
        except RuntimeError:
            pass
        else:
            raise AssertionError("a exceção deveria propagar")
        status = database.get_lead_by_url(URL)["status"]
        assert status == "QUALIFIED"
        assert status != "DEPLOYED"


def test_sucesso_move_para_deployed_e_grava_link():
    with DbTemporario():
        resultado, _ = rodar(retorno_pipeline="https://lead-teste.vercel.app")
        assert resultado == "https://lead-teste.vercel.app"
        status = database.get_lead_by_url(URL)["status"]
        assert status == "DEPLOYED"
        assert status != "CONTACTED"
        assert projeto_vercel_url() == "https://lead-teste.vercel.app"


def test_helper_pos_deploy_usa_deployed_e_nao_contacted():
    with open(os.path.join(ROOT_DIR, "main.py"), encoding="utf-8") as f:
        fonte = inspect.getsource(main.executar_pipeline_e_atualizar_status)
    assert '"DEPLOYED"' in fonte
    assert '"CONTACTED"' not in fonte


def test_app_usa_o_helper_e_nao_chama_o_pipeline_cru():
    with open(os.path.join(ROOT_DIR, "app.py"), encoding="utf-8") as f:
        fonte = f.read()
    assert "executar_pipeline_e_atualizar_status(" in fonte
    assert "executar_pipeline_completo" not in fonte


if __name__ == "__main__":
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = 0
    print("=== Testes: status do lead após o pipeline ===\n")
    for nome, fn in testes:
        try:
            fn()
            print(f"✓ {nome}")
        except Exception as e:
            falhas += 1
            print(f"✗ {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    sys.exit(1 if falhas else 0)
