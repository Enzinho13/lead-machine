"""
Deployer — Handles deployment of generated sites.
Uses adapter pattern for future multi-provider support.
"""
import os
import subprocess
import logging
import shutil

logger = logging.getLogger(__name__)


class DeploymentService:
    """Routes deployment to the appropriate adapter."""

    def __init__(self):
        self.adapters = {"vercel": VercelAdapter()}

    def deploy(self, slug: str, provider: str = "vercel") -> str | None:
        adapter = self.adapters.get(provider)
        if not adapter:
            logger.error(f"Unknown deployment provider: {provider}")
            return None
        return adapter.deploy(slug)


class VercelAdapter:
    """Deploys a static site folder to Vercel via npx."""

    def deploy(self, slug: str) -> str | None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        caminho = os.path.join(base_dir, "clientes_gerados", slug)

        if not os.path.isdir(caminho):
            logger.error(f"Deploy folder not found: {caminho}")
            return None

        # Check npx availability
        if not shutil.which("npx"):
            logger.error("npx not found in PATH. Install Node.js to deploy.")
            return None

        logger.info(f"Deploying {slug} to Vercel...")

        try:
            result = subprocess.run(
                ["npx", "vercel", "deploy", "--prod", "--yes", "--name", slug],
                cwd=caminho,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                url = lines[-1] if lines else None
                if url and url.startswith("http"):
                    logger.info(f"Deploy OK: {url}")
                    return url
                logger.warning(f"Deploy returned success but no URL found in output: {result.stdout}")
                return None
            else:
                logger.error(f"Deploy failed (exit {result.returncode}): {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"Deploy timed out for {slug}")
            return None
        except Exception as e:
            logger.error(f"Deploy error: {e}")
            return None


# Backward-compatible function
def fazer_deploy_site(slug_pasta: str) -> str | None:
    service = DeploymentService()
    return service.deploy(slug_pasta)