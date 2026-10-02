"""
Website Auditor — Modular audit engine with objective data collection.
Each check module returns (penalty, reason, raw_data).
"""
import requests
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin


class AuditEngine:
    """Core engine that runs modular checks against a URL."""

    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"http://{url}"
        self.soup = None
        self.html = ""
        self.load_time = 0
        self.status_code = 0
        self.headers = {}
        self.final_url = ""

    def fetch(self) -> bool:
        try:
            start = time.time()
            res = requests.get(
                self.url,
                headers={"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"},
                timeout=10,
                allow_redirects=True,
            )
            self.load_time = round(time.time() - start, 2)
            self.status_code = res.status_code
            self.headers = dict(res.headers)
            self.final_url = res.url
            self.html = res.text
            if res.status_code == 200:
                self.soup = BeautifulSoup(res.text, "html.parser")
                return True
        except requests.RequestException:
            pass
        return False

    # --- Performance ---
    def check_performance(self) -> dict:
        result = {"load_time": self.load_time, "penalty": 0, "issue": ""}
        if self.load_time > 4.0:
            result.update(penalty=-30, issue=f"Muito lento ({self.load_time}s)")
        elif self.load_time > 2.0:
            result.update(penalty=-15, issue=f"Lento ({self.load_time}s)")
        elif self.load_time > 1.0:
            result.update(penalty=-5, issue=f"Poderia ser mais rápido ({self.load_time}s)")
        return result

    # --- Security ---
    def check_security(self) -> dict:
        is_https = self.final_url.startswith("https")
        result = {"has_https": is_https, "penalty": 0, "issue": ""}
        if not is_https:
            result.update(penalty=-20, issue="Sem HTTPS")
        return result

    # --- Mobile ---
    def check_mobile(self) -> dict:
        has_viewport = False
        if self.soup:
            has_viewport = bool(self.soup.find("meta", attrs={"name": "viewport"}))
        result = {"has_viewport": has_viewport, "penalty": 0, "issue": ""}
        if not has_viewport:
            result.update(penalty=-25, issue="Sem meta viewport (não otimizado para mobile)")
        return result

    # --- SEO ---
    def check_seo(self) -> dict:
        issues = []
        penalty = 0

        if self.soup:
            # Title
            title_tag = self.soup.find("title")
            has_title = bool(title_tag and title_tag.get_text(strip=True))
            if not has_title:
                penalty -= 10
                issues.append("Sem tag <title>")

            # Meta description
            meta_desc = self.soup.find("meta", attrs={"name": "description"})
            has_meta_desc = bool(meta_desc and meta_desc.get("content", "").strip())
            if not has_meta_desc:
                penalty -= 10
                issues.append("Sem meta description")

            # H1
            h1 = self.soup.find("h1")
            has_h1 = bool(h1)
            if not has_h1:
                penalty -= 10
                issues.append("Sem tag H1")

            # Multiple H1s
            h1_count = len(self.soup.find_all("h1"))
            if h1_count > 1:
                penalty -= 5
                issues.append(f"Múltiplos H1 ({h1_count})")
        else:
            has_title = False
            has_meta_desc = False
            has_h1 = False
            h1_count = 0

        return {
            "has_title": has_title,
            "has_meta_description": has_meta_desc,
            "has_h1": has_h1,
            "h1_count": h1_count if self.soup else 0,
            "penalty": penalty,
            "issues": issues,
        }

    # --- Images ---
    def check_images(self) -> dict:
        if not self.soup:
            return {"total_images": 0, "missing_alt": 0, "penalty": 0, "issue": ""}
        images = self.soup.find_all("img")
        missing_alt = [img.get("src", "?") for img in images if not img.get("alt", "").strip()]
        penalty = 0
        issue = ""
        if len(missing_alt) > 5:
            penalty = -15
            issue = f"{len(missing_alt)} imagens sem alt text"
        elif len(missing_alt) > 0:
            penalty = -5
            issue = f"{len(missing_alt)} imagens sem alt text"
        return {
            "total_images": len(images),
            "missing_alt": len(missing_alt),
            "penalty": penalty,
            "issue": issue,
        }

    # --- Accessibility ---
    def check_accessibility(self) -> dict:
        issues = []
        penalty = 0
        if self.soup:
            # Lang attribute
            html_tag = self.soup.find("html")
            has_lang = bool(html_tag and html_tag.get("lang"))
            if not has_lang:
                penalty -= 5
                issues.append("Sem atributo lang no HTML")

            # Form labels
            inputs = self.soup.find_all("input", {"type": lambda t: t not in ("hidden", "submit", "button")})
            labels = self.soup.find_all("label")
            label_fors = {l.get("for") for l in labels if l.get("for")}
            unlabeled = [i for i in inputs if i.get("id") not in label_fors and not i.get("aria-label")]
            if unlabeled:
                penalty -= 5
                issues.append(f"{len(unlabeled)} campos de formulário sem label")
        else:
            has_lang = False

        return {"has_lang": has_lang, "penalty": penalty, "issues": issues}

    # --- Links ---
    def check_links(self) -> dict:
        if not self.soup:
            return {"total_links": 0, "external_links": 0, "penalty": 0, "issue": ""}
        links = self.soup.find_all("a", href=True)
        parsed = urlparse(self.final_url)
        domain = parsed.netloc
        external = [a["href"] for a in links if urlparse(a["href"]).netloc and urlparse(a["href"]).netloc != domain]
        empty_links = [a for a in links if a["href"] in ("#", "", "javascript:void(0)")]
        penalty = 0
        issue = ""
        if len(empty_links) > 3:
            penalty = -5
            issue = f"{len(empty_links)} links vazios/placeholder"
        return {
            "total_links": len(links),
            "external_links": len(external),
            "empty_links": len(empty_links),
            "penalty": penalty,
            "issue": issue,
        }

    # --- Technology Detection ---
    def check_technology(self) -> dict:
        techs = []
        if not self.html:
            return {"technologies": techs}

        patterns = {
            "WordPress": ["wp-content", "wp-includes"],
            "Wix": ["wix.com", "wixsite"],
            "Squarespace": ["squarespace"],
            "Shopify": ["shopify", "cdn.shopify"],
            "React": ["react", "__next"],
            "Next.js": ["__next", "_next/static"],
            "Vue.js": ["vue.js", "__vue"],
            "Angular": ["ng-version", "angular"],
            "Bootstrap": ["bootstrap"],
            "Tailwind": ["tailwindcss", "tailwind"],
            "jQuery": ["jquery"],
            "Google Analytics": ["google-analytics", "gtag", "googletagmanager"],
            "Google Tag Manager": ["googletagmanager.com/gtm"],
        }

        html_lower = self.html.lower()
        for tech, indicators in patterns.items():
            if any(ind in html_lower for ind in indicators):
                techs.append(tech)

        return {"technologies": techs}

    # --- Content Extraction ---
    def extract_content(self) -> dict:
        if not self.soup:
            return {"textos_principais": "", "cor_detectada": None}
        theme = self.soup.find("meta", attrs={"name": "theme-color"})
        cor = theme["content"] if theme else None
        textos = []
        for tag in ["title", "h1", "h2", "p"]:
            for el in self.soup.find_all(tag, limit=3):
                text = el.get_text(strip=True)
                if len(text) > 10:
                    textos.append(text)
        return {
            "textos_principais": " | ".join(textos)[:2000],
            "cor_detectada": cor,
        }

    def run_full_audit(self) -> dict:
        """Run all checks and produce a structured audit report."""
        checks = {
            "performance": self.check_performance(),
            "security": self.check_security(),
            "mobile": self.check_mobile(),
            "seo": self.check_seo(),
            "images": self.check_images(),
            "accessibility": self.check_accessibility(),
            "links": self.check_links(),
            "technology": self.check_technology(),
            "content": self.extract_content(),
        }

        # Calculate score
        score = 100
        motivos = []
        for name, result in checks.items():
            pen = result.get("penalty", 0)
            if pen < 0:
                score += pen
                issue = result.get("issue") or ", ".join(result.get("issues", []))
                if issue:
                    motivos.append(issue)

        return {
            "status": "Sucesso",
            "url": self.url,
            "final_url": self.final_url,
            "score": max(0, score),
            "motivos": ", ".join(motivos) if motivos else "Nenhum problema crítico",
            "checks": checks,
            "textos_principais": checks["content"]["textos_principais"],
            "cor_detectada": checks["content"]["cor_detectada"],
        }


def auditar_site_lead(url: str) -> dict:
    """Backward-compatible entry point."""
    if not url or not url.startswith("http"):
        return {"status": "Invalido", "score": 0, "motivos": "Sem URL", "textos_principais": "", "checks": {}}

    engine = AuditEngine(url)
    if not engine.fetch():
        return {"status": "Offline", "score": 0, "motivos": "Fora do Ar", "textos_principais": "", "checks": {}}

    return engine.run_full_audit()