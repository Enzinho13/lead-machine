
import sys
import os
import json

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "..", "src"))

from ai_service import ai
from seo_optimizer import otimizar_seo

def test_ai_service():
    print("Testing AI Service...")
    res = ai.generate_text("Hello, say 'Test OK'")
    assert "Test OK" in res
    print("✓ AI generate_text passed")
    
    struct = ai.generate_structured("Return a JSON with key 'status' value 'ready'", schema_hint={"type":"object", "properties":{"status":{"type":"string"}}})
    assert struct.get("status") == "ready"
    print("✓ AI generate_structured passed")

def test_seo_optimizer():
    print("Testing SEO Optimizer...")
    lead = {"nome": "Padaria Silva", "nicho": "Padaria", "cidade": "São Paulo"}
    design = {"nome_limpo": "Silva Bakery", "design_brief": "Modern bakery with rustic touch."}
    
    seo = otimizar_seo(lead, design)
    assert "meta_title" in seo
    assert "meta_description" in seo
    assert "schema_json" in seo
    assert "@context" in seo["schema_json"]
    print("✓ SEO Optimizer passed")

if __name__ == "__main__":
    try:
        test_ai_service()
        test_seo_optimizer()
        print("\n=== NEW MODULES TESTS PASSED ===")
    except Exception as e:
        print(f"\nFAIL: {e}")
        sys.exit(1)
