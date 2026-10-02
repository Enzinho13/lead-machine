import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()

from main import executar_pipeline_completo

print("=== TEST PIPELINE (WITHOUT DEPLOY) ===")
# We will mock fazer_deploy_site to avoid actually deploying to Vercel during test
import deployer
deployer.fazer_deploy_site = lambda slug: f"https://mocked-deploy-{slug}.vercel.app"

# Executing pipeline for a fictional law firm
url_online = executar_pipeline_completo(
    nome_bruto="Silva & Santos Advocacia",
    nicho="Escritório de Advocacia Empresarial",
    cidade="Curitiba",
    url_lead="https://this-is-a-fake-test-url-12345.com"
)

print(f"Generated site URL: {url_online}")
