"""
Orquestrador do motor automático — um lead por vez, sem Streamlit.

Etapas: DISCOVERY → ENRICHMENT → AUDIT → QUALIFICATION → GENERATION → QA → DEPLOY → OUTREACH DRAFT

Reusa as funções já existentes. Não envia mensagem. O status de contato comercial não é atribuído aqui.
Preparado para um scheduler/worker chamar process_lead / process_next_lead.

Robustez (SQLite, sem infraestrutura externa):
- LEASE com ownership: cada aquisição gera um token único (acquire_lease). Só quem tem o token renova,
  libera ou registra o desfecho do lead. Lease de worker morto/lento expira (CLAIM_TTL_SECONDS) e outro
  worker pode assumir; o token antigo perde a autoridade;
- heartbeat: LeaseHeartbeat renova o lease enquanto o lead é processado e é checado entre as etapas;
  quem perde o lease aborta (LEASE) sem tocar no que é do novo dono;
- retry controlado: cada aquisição conta uma tentativa; até MAX_ATTEMPTS, com backoff entre tentativas;
- recuperação: falha em qualquer etapa nunca deixa o lead preso em AUDITING;
- idempotência: lead já concluído não refaz trabalho (auditoria salva é reaproveitada, DEPLOYED retoma
  só o rascunho, rascunhos são atualizados e não duplicados).
"""
import logging
import os
import sys
import threading
import uuid
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from auditor import auditar_site_lead
from ai_qualifier import qualificar_lead_com_ia
from database import (
    acquire_lease,
    exhaust_lead,
    get_all_leads,
    get_lead_by_url,
    get_lead_with_audit,
    get_next_lead,
    mark_lead_failure,
    mark_lead_success,
    owns_lease,
    release_lead,
    renew_lease,
    save_audit,
    update_lead_score,
    update_lead_status,
)
from deployer import fazer_deploy_site
from design_director import DesignDirector
from lead_scraper import _enriquecer_contatos, buscar_empresas
from qa_engine import executar_qa
from seo_optimizer import otimizar_seo
from site_generator import gerar_site_cliente

from main import criar_slug_seguro, preparar_outreach_do_lead

logger = logging.getLogger(__name__)

STAGES = (
    "DISCOVERY",
    "ENRICHMENT",
    "AUDIT",
    "QUALIFICATION",
    "GENERATION",
    "QA",
    "DEPLOY",
    "OUTREACH_DRAFT",
)

PROCESSABLE_STATUSES = ("NEW", "DISCOVERED", "AUDITED", "QUALIFIED")
QUALIFY_PRIORITIES = ("high", "medium")

CLAIM_TTL_SECONDS = 900        # duração do lease; o heartbeat o renova enquanto o worker está vivo
MAX_ATTEMPTS = 3               # tentativas por lead (cada aquisição conta uma); depois o worker desiste
RETRY_BACKOFF_SECONDS = 300    # espera entre tentativas: backoff * nº de tentativas


class LeaseLost(Exception):
    """Este worker perdeu o lease do lead (expirou e outro worker assumiu): deve parar sem escrever mais nada."""


class LeaseHeartbeat:
    """Renova o lease em segundo plano enquanto o bloco `with` estiver ativo (reutilizável por qualquer worker).

    - a cada `interval` segundos (padrão ttl/3) renova o lease com o token do dono;
    - se a renovação falhar por perda de ownership, marca `lost`;
    - check() renova na hora e levanta LeaseLost se o lease foi perdido (chamar entre as etapas).
    Erros transitórios do SQLite (ex.: banco ocupado) não contam como perda: tenta de novo no próximo ciclo.
    """

    def __init__(self, url: str, token: str, ttl_seconds: float = CLAIM_TTL_SECONDS, interval: float | None = None):
        self.url, self.token, self.ttl = url, token, ttl_seconds
        self.interval = interval if interval is not None else max(ttl_seconds / 3.0, 0.05)
        self.lost = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check(self) -> None:
        if self.lost.is_set() or not renew_lease(self.url, self.token, self.ttl):
            self.lost.set()
            raise LeaseLost(f"lease perdido: {self.url}")

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                if not renew_lease(self.url, self.token, self.ttl):
                    self.lost.set()
                    return
            except Exception:
                logger.warning("[ORCH] heartbeat: falha transitória ao renovar o lease", exc_info=True)

    def __enter__(self) -> "LeaseHeartbeat":
        self._thread = threading.Thread(target=self._run, name="lease-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


def _checar(lease: "LeaseHeartbeat | None") -> None:
    """Confirma (e renova) o lease entre etapas. Fica fora dos try/except das etapas para LeaseLost subir."""
    if lease is not None:
        lease.check()


def _stage(name: str, ok: bool, **extra: Any) -> dict:
    return {"stage": name, "ok": ok, **extra}


def _result(url, stages, stopped_at=None, ok=False, **extra) -> dict:
    lead = get_lead_by_url(url) if url else None
    status = lead["status"] if lead else None
    return {
        "ok": ok,
        "url": url,
        "stopped_at": stopped_at,
        "lead_status": status,
        "stages": stages,
        **extra,
    }


def _lease_perdido(url: str) -> dict:
    return _result(url, [_stage("LEASE", False, reason="lease_lost")], stopped_at="LEASE", lease_lost=True)


def _gravar_auditoria(lead: dict, resultado: dict) -> None:
    checks = resultado.get("checks") or {}
    save_audit(lead["id"], {
        "score": resultado.get("score", 0),
        "motivos": resultado.get("motivos", ""),
        "performance_time": (checks.get("performance") or {}).get("load_time", 0),
        "has_https": (checks.get("security") or {}).get("has_https", False),
        "has_viewport": (checks.get("mobile") or {}).get("has_viewport", False),
        "has_h1": (checks.get("seo") or {}).get("has_h1", False),
        "textos_principais": resultado.get("textos_principais", ""),
        "cor_detectada": resultado.get("cor_detectada", ""),
        "raw_data": resultado,
    })
    update_lead_score(lead["url"], resultado.get("score", 0), resultado.get("motivos", ""))


def _auditoria_salva(lead: dict) -> dict | None:
    """Última auditoria BEM-SUCEDIDA já gravada para o lead (evita auditar de novo e duplicar linhas)."""
    audit = ((get_lead_with_audit(lead["id"]) or {}).get("audit")) or {}
    bruto = audit.get("raw_data")
    if isinstance(bruto, dict) and bruto.get("status") == "Sucesso":
        return bruto
    return None


def run_discovery(nicho: str, cidade: str, max_resultados: int = 5) -> dict:
    """Discovery em lote (reusa buscar_empresas). Independente do processamento de um lead."""
    antes = {lead["url"] for lead in get_all_leads()}
    buscar_empresas(nicho, cidade, max_resultados=max_resultados)
    novos = [lead for lead in get_all_leads() if lead["url"] not in antes]
    return {
        "ok": True,
        "stage": "DISCOVERY",
        "count": len(novos),
        "urls": [lead["url"] for lead in novos],
    }


def next_lead(now: float | None = None) -> dict | None:
    """Próximo lead elegível para o worker (um por vez).

    Só devolve lead sem lease ativo, com tentativas restantes e fora do backoff, então um lead que
    falhou não volta em loop. AUDITING só aparece aqui quando não há lease ativo (worker morto):
    é a recuperação de lead preso. Quem tem menos tentativas vem primeiro.
    """
    return get_next_lead(PROCESSABLE_STATUSES + ("AUDITING",), max_attempts=MAX_ATTEMPTS, now=now)


def process_next_lead(now: float | None = None) -> dict | None:
    lead = next_lead(now=now)
    if not lead:
        return None
    return process_lead(lead["url"])


def _erro_do_resultado(resultado: dict) -> str:
    falha = next((s for s in reversed(resultado["stages"]) if not s["ok"]), {})
    motivo = falha.get("reason") or falha.get("audit_status") or "falha"
    return f"{resultado.get('stopped_at')}: {motivo}"


def _finalizar(url: str, status_inicial: str, resultado: dict, token: str) -> None:
    """Pós-processamento com o lease em mãos: recupera status e registra o desfecho (só vale para o dono)."""
    atual = get_lead_by_url(url) or {}
    if atual.get("status") == "AUDITING":  # nunca deixar o lead preso em AUDITING
        update_lead_status(url, "NEW" if status_inicial == "AUDITING" else status_inicial)
    if resultado["ok"]:
        mark_lead_success(url, token=token)
    elif resultado.get("terminal"):
        exhaust_lead(url, resultado["terminal"], MAX_ATTEMPTS, token=token)
    else:
        mark_lead_failure(url, _erro_do_resultado(resultado), RETRY_BACKOFF_SECONDS, token=token)


def process_lead(url: str, worker_id: str | None = None, claim_ttl: float = CLAIM_TTL_SECONDS,
                 max_attempts: int = MAX_ATTEMPTS) -> dict:
    """Processa um lead com lease exclusivo no SQLite. Não depende do Streamlit. Não envia outreach.

    Idempotente (retoma de onde parou), com tentativas limitadas. O lease é renovado enquanto o worker
    trabalha e liberado (só com o token do dono) em sucesso, falha ou exceção. Se o lease for perdido,
    o worker aborta sem alterar o que pertence ao novo dono.
    """
    lead = get_lead_by_url(url)
    if not lead:
        return _result(url, [_stage("DISCOVERY", False, reason="lead_not_found")], stopped_at="DISCOVERY")

    worker = worker_id or f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    token = acquire_lease(url, worker, claim_ttl, max_attempts)
    if token is None:
        atual = get_lead_by_url(url) or {}
        motivo = "retries_exhausted" if (atual.get("attempts") or 0) >= max_attempts else "already_claimed"
        return _result(url, [_stage("CLAIM", False, reason=motivo)], stopped_at="CLAIM")

    status_inicial = lead["status"]
    try:
        with LeaseHeartbeat(url, token, claim_ttl) as lease:
            try:
                resultado = _process_claimed(url, lead, lease)
            except LeaseLost:
                logger.warning(f"[ORCH] lease perdido durante o processamento de {url}: abortando sem alterar o lead")
                return _lease_perdido(url)
            except Exception as e:
                logger.exception("[ORCH] erro inesperado")
                resultado = _result(url, [_stage("UNEXPECTED", False, reason=str(e))], stopped_at="UNEXPECTED")
        if not owns_lease(url, token):  # outro worker assumiu no fim: não registra desfecho por cima
            return _lease_perdido(url)
        _finalizar(url, status_inicial, resultado, token)
        resultado["lead_status"] = (get_lead_by_url(url) or {}).get("status")
        return resultado
    finally:
        release_lead(url, token)


def _retomar_lead_deployed(url: str, lead: dict, stages: list, lease: "LeaseHeartbeat | None" = None) -> dict:
    """Lead já publicado: não refaz geração/QA/deploy; só completa o rascunho de outreach se faltar."""
    linha = next((row for row in get_all_leads() if row["url"] == url), {})
    vercel_url = linha.get("vercel_url") or ""
    if linha.get("outreach_message") and not lead.get("last_error"):
        stages.append(_stage("DEPLOY", True, skipped=True, vercel_url=vercel_url))
        stages.append(_stage("OUTREACH_DRAFT", True, skipped=True, sent=False))
        return _result(url, stages, ok=True, already_done=True)
    if not vercel_url:
        stages.append(_stage("DEPLOY", False, reason="missing_vercel_url"))
        return _result(url, stages, stopped_at="DEPLOY")
    stages.append(_stage("DEPLOY", True, skipped=True, vercel_url=vercel_url))
    _checar(lease)
    try:
        outreach = preparar_outreach_do_lead(
            url, lead.get("nome") or "", _auditoria_salva(lead) or {}, vercel_url, linha.get("design_brief") or "",
        )
        stages.append(_stage(
            "OUTREACH_DRAFT", True,
            outreach_status=outreach.get("status"),
            sent=bool(outreach.get("sent")),
        ))
    except Exception as e:
        logger.exception("[ORCH] OUTREACH_DRAFT falhou (site já publicado)")
        stages.append(_stage("OUTREACH_DRAFT", False, reason=str(e), sent=False))
        return _result(url, stages, stopped_at="OUTREACH_DRAFT")
    return _result(url, stages, ok=True, resumed=True)


def _process_claimed(url: str, lead: dict, lease: "LeaseHeartbeat | None" = None) -> dict:
    """Executa o fluxo de um lead cujo lease JÁ pertence a este worker (checado entre as etapas)."""
    stages: list[dict] = [_stage("DISCOVERY", True)]
    token = lease.token if lease is not None else None

    if lead["status"] == "DEPLOYED":
        return _retomar_lead_deployed(url, lead, stages, lease)

    _checar(lease)
    if lead.get("telefone") or lead.get("email"):
        stages.append(_stage("ENRICHMENT", True, found_contact=True, skipped=True))
    else:
        try:
            found = _enriquecer_contatos(url)
            stages.append(_stage("ENRICHMENT", True, found_contact=bool(found)))
        except Exception as e:
            logger.exception("[ORCH] ENRICHMENT falhou")
            stages.append(_stage("ENRICHMENT", False, reason=str(e)))
            return _result(url, stages, stopped_at="ENRICHMENT")

    _checar(lease)
    dados_auditoria = _auditoria_salva(lead) if lead["status"] in ("AUDITED", "QUALIFIED") else None
    if dados_auditoria is not None:
        stages.append(_stage("AUDIT", True, score=dados_auditoria.get("score"), reused=True))
    else:
        try:
            update_lead_status(url, "AUDITING")
            dados_auditoria = auditar_site_lead(url)
            lead = get_lead_by_url(url)
            _gravar_auditoria(lead, dados_auditoria)
            if dados_auditoria.get("status") != "Sucesso":
                stages.append(_stage("AUDIT", False, audit_status=dados_auditoria.get("status")))
                return _result(url, stages, stopped_at="AUDIT")
            stages.append(_stage("AUDIT", True, score=dados_auditoria.get("score")))
        except Exception as e:
            logger.exception("[ORCH] AUDIT falhou")
            stages.append(_stage("AUDIT", False, reason=str(e)))
            return _result(url, stages, stopped_at="AUDIT")

    _checar(lease)
    try:
        qualificacao = qualificar_lead_com_ia({"auditoria": dados_auditoria})
        if qualificacao.get("priority") not in QUALIFY_PRIORITIES:
            stages.append(_stage(
                "QUALIFICATION", True, qualified=False, priority=qualificacao.get("priority"),
            ))
            # Resultado final (não é falha): o worker não deve pegar este lead de novo
            return _result(url, stages, stopped_at="QUALIFICATION", terminal="not_qualified")
        update_lead_status(url, "QUALIFIED")
        stages.append(_stage(
            "QUALIFICATION", True, qualified=True, priority=qualificacao.get("priority"),
        ))
    except Exception as e:
        logger.exception("[ORCH] QUALIFICATION falhou")
        stages.append(_stage("QUALIFICATION", False, reason=str(e)))
        return _result(url, stages, stopped_at="QUALIFICATION")

    lead = get_lead_by_url(url)
    nome = lead.get("nome") or ""
    nicho = lead.get("nicho") or "Negócio"
    cidade = lead.get("cidade") or "Brasil"
    lead_data = {"nome": nome, "nicho": nicho, "cidade": cidade, "url": url}

    _checar(lease)
    try:
        dados_ia = DesignDirector().generate_design(lead_data, dados_auditoria)
        if dados_ia.get("ai_fallback"):
            stages.append(_stage("GENERATION", False, reason="ai_fallback"))
            return _result(url, stages, stopped_at="GENERATION")
        nome_limpo = dados_ia.get("nome_limpo", nome[:30])
        slug = criar_slug_seguro(nome_limpo)
        dados_seo = otimizar_seo(lead_data, dados_ia)
        gerar_site_cliente({
            "slug": slug,
            "title": nome_limpo,
            "theme": dados_ia.get("theme", {
                "font_heading": "serif", "font_body": "sans-serif", "primary_color": "#000000",
            }),
            "layout": dados_ia.get("layout", []),
            "seo": dados_seo,
        })
        stages.append(_stage("GENERATION", True, slug=slug))
    except Exception as e:
        logger.exception("[ORCH] GENERATION falhou")
        stages.append(_stage("GENERATION", False, reason=str(e)))
        return _result(url, stages, stopped_at="GENERATION")

    _checar(lease)
    try:
        if not executar_qa(slug):
            stages.append(_stage("QA", False, reason="qa_failed"))
            return _result(url, stages, stopped_at="QA")
        stages.append(_stage("QA", True, slug=slug))
    except Exception as e:
        logger.exception("[ORCH] QA falhou")
        stages.append(_stage("QA", False, reason=str(e)))
        return _result(url, stages, stopped_at="QA")

    _checar(lease)  # último ponto antes do deploy (irreversível): só publica quem ainda é o dono
    try:
        url_online = fazer_deploy_site(slug)
        if not url_online:
            stages.append(_stage("DEPLOY", False, reason="deploy_failed"))
            return _result(url, stages, stopped_at="DEPLOY")
        update_lead_status(url, "DEPLOYED", vercel_url=url_online)
        # Deploy feito: se o processo cair antes do rascunho, o lead fica retomável (só o outreach)
        mark_lead_failure(url, "outreach_pending", 0, token=token)
        stages.append(_stage("DEPLOY", True, vercel_url=url_online))
    except Exception as e:
        logger.exception("[ORCH] DEPLOY falhou")
        stages.append(_stage("DEPLOY", False, reason=str(e)))
        return _result(url, stages, stopped_at="DEPLOY")

    _checar(lease)
    try:
        outreach = preparar_outreach_do_lead(
            url, nome_limpo, dados_auditoria, url_online, dados_ia.get("design_brief", ""),
        )
        stages.append(_stage(
            "OUTREACH_DRAFT", True,
            outreach_status=outreach.get("status"),
            sent=bool(outreach.get("sent")),
        ))
    except Exception as e:
        logger.exception("[ORCH] OUTREACH_DRAFT falhou (site já publicado)")
        stages.append(_stage("OUTREACH_DRAFT", False, reason=str(e), sent=False))
        return _result(url, stages, stopped_at="OUTREACH_DRAFT", ok=False)

    return _result(url, stages, ok=True)
