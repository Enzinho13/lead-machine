"""
QA Engine — Validates generated sites before deployment.
Implements automatic fixing of detected HTML/SEO/Accessibility issues.
"""
import os
import re
import logging
from bs4 import BeautifulSoup

from ai_service import ai

logger = logging.getLogger(__name__)


class QAEngine:
    def __init__(self, slug: str):
        self.slug = slug
        self.base_path = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
            "clientes_gerados",
            slug,
        )
        self.html_path = os.path.join(self.base_path, "index.html")
        self.html_content = ""
        self.soup = None

    def _load(self) -> bool:
        if not os.path.exists(self.html_path):
            logger.error(f"QA: Arquivo não encontrado - {self.html_path}")
            return False
        with open(self.html_path, "r", encoding="utf-8") as f:
            self.html_content = f.read()
            self.soup = BeautifulSoup(self.html_content, "html.parser")
        return True

    def _save(self):
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write(str(self.soup))

    def run_checks(self) -> list:
        """Run all QA checks and return a list of errors."""
        errors = []
        if not self._load():
            return ["Arquivo HTML inexistente."]

        # 1. Basic HTML Structure
        if not self.soup.find("html"):
            errors.append("Falta a tag <html> principal.")
        if not self.soup.find("head"):
            errors.append("Falta a tag <head>.")
        if not self.soup.find("body"):
            errors.append("Falta a tag <body>.")

        # 2. SEO Basics
        title = self.soup.find("title")
        if not title or not title.get_text(strip=True):
            errors.append("Falta tag <title> ou está vazia.")
        
        meta_desc = self.soup.find("meta", attrs={"name": "description"})
        if not meta_desc or not meta_desc.get("content", "").strip():
            errors.append("Falta meta description.")

        h1s = self.soup.find_all("h1")
        if len(h1s) == 0:
            errors.append("Falta tag <h1> na página.")
        elif len(h1s) > 1:
            errors.append("Múltiplas tags <h1> encontradas (deve haver apenas uma).")

        # 3. Accessibility
        html_tag = self.soup.find("html")
        if html_tag and not html_tag.get("lang"):
            errors.append("Tag <html> sem atributo 'lang'.")

        for img in self.soup.find_all("img"):
            if not img.get("alt"):
                errors.append(f"Imagem sem atributo alt: {img.get('src', 'desconhecida')}")

        # 4. Mobile Responsiveness
        viewport = self.soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            errors.append("Falta meta viewport para responsividade mobile.")

        # 5. Links
        for a in self.soup.find_all("a"):
            href = a.get("href")
            if not href or href.strip() == "":
                errors.append("Link vazio (href) encontrado.")

        return errors

    def auto_fix(self, errors: list, max_retries: int = 2) -> bool:
        """Attempt to automatically fix errors using AI."""
        if not errors:
            return True

        logger.info(f"QA: Encontrados {len(errors)} erros no site {self.slug}. Iniciando Auto-Fix...")
        
        for attempt in range(max_retries):
            prompt = f"""
            Você é um QA Engineer focado em HTML.
            O código HTML abaixo possui os seguintes erros:
            {chr(10).join(f'- {e}' for e in errors)}
            
            Corrija TODOS os erros diretamente no código HTML fornecido.
            REGRAS:
            1. Mantenha as classes Tailwind originais.
            2. Não altere o design ou textos (exceto para adicionar atributos faltando como alt ou lang).
            3. Para links vazios, use href="#".
            4. Se faltar meta description, infira uma curta baseada no conteúdo.
            5. Retorne APENAS o código HTML completo e corrigido, sem markdown extra (sem ```html).
            
            HTML ATUAL:
            {self.html_content}
            """
            
            try:
                fixed_html = ai.generate_text(prompt, temperature=0.2)
                # Cleanup markdown formatting if AI still outputs it
                if fixed_html.startswith("```html"):
                    fixed_html = fixed_html[7:]
                if fixed_html.endswith("```"):
                    fixed_html = fixed_html[:-3]
                
                self.html_content = fixed_html.strip()
                self.soup = BeautifulSoup(self.html_content, "html.parser")
                self._save()
                
                # Re-run checks
                errors = self.run_checks()
                if not errors:
                    logger.info("QA: Todos os erros corrigidos com sucesso!")
                    return True
                else:
                    logger.warning(f"QA: Auto-Fix tentativa {attempt+1} falhou. Restam erros: {errors}")
            except Exception as e:
                logger.error(f"QA: Falha ao chamar AI para Auto-Fix: {e}")
                return False
                
        return False


def executar_qa(slug: str) -> bool:
    """Entry point for QA pipeline."""
    engine = QAEngine(slug)
    errors = engine.run_checks()
    if not errors:
        logger.info(f"QA: Site {slug} passou em todos os testes.")
        return True
    
    return engine.auto_fix(errors)
