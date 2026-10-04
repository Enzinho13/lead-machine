"""
Contact Extractor — encontra telefone e e-mail PÚBLICOS no próprio site do lead.

Só extrai o que está publicado na página (links tel:/mailto:/WhatsApp e texto visível).
Nunca inventa contato: sem evidência, o campo fica vazio.
Nada aqui envia mensagem; só lê e normaliza dados.
"""
import re
from urllib.parse import urlparse, urljoin, unquote, parse_qs

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"}
TIMEOUT = 8
MAX_HTML_CHARS = 1_000_000

# ---------------------------------------------------------------- telefone (Brasil)

_DDDS_VALIDOS = set(
    "11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 "
    "41 42 43 44 45 46 47 48 49 51 53 54 55 61 62 63 64 65 66 67 68 69 "
    "71 73 74 75 77 79 81 82 83 84 85 86 87 88 89 91 92 93 94 95 96 97 98 99".split()
)

# Exige formatação (parênteses, separador ou +55): número solto de 10-11 dígitos pode ser CPF/ID.
_TELEFONE_TEXTO = re.compile(
    r"(?<!\d)(?<!\d[./\-])"
    r"(?:\+?55[\s.\-]?)?"
    r"(?:\(\s*0?\d{2}\s*\)|0?\d{2})[\s.\-]?"
    r"9?\d{4}[\s.\-]?\d{4}"
    r"(?!\d)(?![./\-]\d)"
)


def normalizar_telefone_br(raw: str) -> str:
    """Devolve '+55DDDNÚMERO' (E.164) ou '' se não for um telefone brasileiro plausível."""
    digitos = re.sub(r"\D", "", raw or "")
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if digitos.startswith("55") and len(digitos) in (12, 13):
        nacional = digitos[2:]
    elif digitos.startswith("0") and len(digitos) in (11, 12):
        nacional = digitos[1:]
    elif len(digitos) in (10, 11):
        nacional = digitos
    else:
        return ""

    ddd, assinante = nacional[:2], nacional[2:]
    if ddd not in _DDDS_VALIDOS or len(set(assinante)) == 1:
        return ""
    celular = len(assinante) == 9 and assinante[0] == "9"
    fixo = len(assinante) == 8 and assinante[0] in "2345"
    if not (celular or fixo):
        return ""
    return f"+55{ddd}{assinante}"


def eh_celular_br(telefone: str) -> bool:
    """True para celular (9 dígitos): é o que permite WhatsApp. Fixo e vazio dão False."""
    t = normalizar_telefone_br(telefone)
    return len(t) == 14 and t[5] == "9"


def _telefones_dos_links(soup) -> list:
    achados = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        baixo = href.lower()
        if baixo.startswith("tel:"):
            achados.append(re.split(r"[;,]", unquote(href[4:]))[0])
        elif "wa.me/" in baixo or "whatsapp.com/send" in baixo:
            url = urlparse(href)
            candidato = parse_qs(url.query).get("phone", [""])[0] or url.path.strip("/")
            if re.fullmatch(r"\+?\d{10,15}", candidato):
                achados.append(candidato)
    return achados


# ---------------------------------------------------------------- e-mail

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,24}")
_EXTENSOES_ARQUIVO = {"png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js", "ico", "woff", "woff2"}
_DOMINIOS_FALSOS = {
    "example.com", "example.org", "email.com", "domain.com", "dominio.com", "seudominio.com",
    "seudominio.com.br", "seusite.com", "seusite.com.br", "meusite.com.br", "site.com",
    "sentry.io", "wixpress.com",
}
_USUARIOS_FALSOS = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "seuemail", "seu-email",
    "seunome", "email", "nome", "exemplo", "usuario", "name", "user",
}
# Fora do domínio do próprio site, só aceitamos e-mail de provedor gratuito (negócio pequeno no Gmail etc.).
# E-mail de outro domínio costuma ser da agência que fez o site, não do lead.
_PROVEDORES_GRATUITOS = {
    "gmail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com", "yahoo.com.br",
    "uol.com.br", "bol.com.br", "terra.com.br", "icloud.com", "ig.com.br",
}


def normalizar_email(raw: str) -> str:
    """Devolve o e-mail em minúsculas ou '' se for inválido, placeholder, nome de arquivo ou no-reply."""
    email = (raw or "").strip().strip(".,;:<>()[]\"'").lower()
    if not _EMAIL.fullmatch(email) or len(email) > 254 or ".." in email:
        return ""
    usuario, dominio = email.rsplit("@", 1)
    if len(usuario) > 64 or usuario.startswith(".") or usuario.endswith(".") or usuario in _USUARIOS_FALSOS:
        return ""
    if dominio.rsplit(".", 1)[-1] in _EXTENSOES_ARQUIVO:
        return ""
    if any(dominio == d or dominio.endswith("." + d) for d in _DOMINIOS_FALSOS):
        return ""
    return email


def _dominio_base(url: str) -> str:
    host = urlparse(url if "//" in url else "//" + url).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _escolher_email(candidatos: list, url: str) -> str:
    base = _dominio_base(url)
    dominios = [(e, e.rsplit("@", 1)[1]) for e in candidatos]
    for email, dominio in dominios:
        if base and (dominio == base or base.endswith("." + dominio) or dominio.endswith("." + base)):
            return email
    for email, dominio in dominios:
        if dominio in _PROVEDORES_GRATUITOS:
            return email
    return ""


def _emails_dos_links(soup) -> list:
    achados = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            achados.extend(unquote(href[7:]).split("?")[0].split(","))
    return achados


# ---------------------------------------------------------------- extração

def _sem_duplicados(itens: list) -> list:
    return list(dict.fromkeys(i for i in itens if i))


def extrair_contatos_do_html(html: str, url: str = "") -> dict:
    """Extrai o melhor telefone e e-mail de um HTML. Campo sem evidência fica ''."""
    soup = BeautifulSoup(html or "", "html.parser")
    telefones_brutos = _telefones_dos_links(soup)
    emails_brutos = _emails_dos_links(soup)

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    texto = soup.get_text(" ", strip=True)
    telefones_brutos += [m.group() for m in _TELEFONE_TEXTO.finditer(texto) if not m.group().isdigit()]
    emails_brutos += _EMAIL.findall(texto)

    telefones = _sem_duplicados([normalizar_telefone_br(t) for t in telefones_brutos])
    emails = _sem_duplicados([normalizar_email(e) for e in emails_brutos])

    celulares = [t for t in telefones if eh_celular_br(t)]
    telefone = (celulares or telefones or [""])[0]
    return {"telefone": telefone, "email": _escolher_email(emails, url)}


# ---------------------------------------------------------------- rede (somente leitura)

def _baixar_html(url: str) -> tuple:
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException:
        return "", url
    if res.status_code != 200:
        return "", url
    return res.text[:MAX_HTML_CHARS], res.url


def _achar_pagina_contato(html: str, url: str) -> str:
    """Primeiro link de 'contato' do MESMO domínio (nunca segue links para outros sites)."""
    base = _dominio_base(url)
    atual = url.split("#")[0]
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        alvo = (a["href"] + " " + a.get_text(" ", strip=True)).lower()
        if not any(p in alvo for p in ("contat", "contact", "fale-conosco", "fale conosco")):
            continue
        destino = urljoin(url, a["href"].strip()).split("#")[0]
        if urlparse(destino).scheme in ("http", "https") and _dominio_base(destino) == base and destino != atual:
            return destino
    return ""


def buscar_contatos_do_site(url: str) -> dict:
    """Busca na página do lead e, se faltar algum contato, em UMA página de contato do mesmo domínio."""
    html, url_final = _baixar_html(url)
    if not html:
        return {"telefone": "", "email": ""}
    contatos = extrair_contatos_do_html(html, url_final)
    if not (contatos["telefone"] and contatos["email"]):
        pagina = _achar_pagina_contato(html, url_final)
        if pagina:
            html2, url2 = _baixar_html(pagina)
            if html2:
                extra = extrair_contatos_do_html(html2, url2)
                contatos = {campo: contatos[campo] or extra[campo] for campo in contatos}
    return contatos
