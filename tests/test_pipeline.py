"""
Lead Machine — Test Suite
Tests the core pipeline components.
"""
import sys
import os
import json

ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))
sys.path.insert(0, ROOT_DIR)

from database import init_db, get_all_leads, insert_lead, get_lead_by_url, save_audit, get_leads_by_status, update_lead_score, update_lead_status, save_outreach_data, get_lead_with_audit
from auditor import auditar_site_lead, AuditEngine
from ai_qualifier import qualificar_lead_com_ia
from main import criar_slug_seguro
from deployer import DeploymentService


def test_database():
    """Test database operations."""
    init_db()
    leads = get_all_leads()
    assert isinstance(leads, list), "get_all_leads must return list"

    # Test insert (will skip if URL exists)
    insert_lead("Test Lead", "http://test-unique-12345.com", "Test desc", "Test", "Test City")
    lead = get_lead_by_url("http://test-unique-12345.com")
    assert lead is not None, "insert_lead + get_lead_by_url failed"
    assert lead["nome"] == "Test Lead"
    assert lead["status"] == "NEW"

    # Test score update
    update_lead_score("http://test-unique-12345.com", 42, "Test motivos")
    lead = get_lead_by_url("http://test-unique-12345.com")
    assert lead["score"] == 42
    assert lead["status"] == "AUDITED"

    # Test status update
    update_lead_status("http://test-unique-12345.com", "QUALIFIED")
    lead = get_lead_by_url("http://test-unique-12345.com")
    assert lead["status"] == "QUALIFIED"

    # Test audit save
    audit_data = {
        "score": 75,
        "motivos": "test issue",
        "performance_time": 1.5,
        "has_https": True,
        "has_viewport": True,
        "has_h1": False,
        "textos_principais": "test text",
        "cor_detectada": "#abc",
        "raw_data": {"test": True},
    }
    audit_id = save_audit(lead["id"], audit_data)
    assert audit_id is not None

    # Test lead with audit
    full = get_lead_with_audit(lead["id"])
    assert full is not None
    assert full["audit"] is not None

    # Test by status
    qualified = get_leads_by_status("QUALIFIED")
    assert any(l["url"] == "http://test-unique-12345.com" for l in qualified)

    # Cleanup
    import sqlite3
    from database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM audits WHERE lead_id = ?", (lead["id"],))
    c.execute("DELETE FROM leads WHERE url = ?", ("http://test-unique-12345.com",))
    conn.commit()
    conn.close()

    print("✓ Database tests passed")


def test_auditor():
    """Test auditor with a real URL."""
    # Test invalid URL
    result = auditar_site_lead("")
    assert result["status"] == "Invalido"

    result = auditar_site_lead("not-a-url")
    assert result["status"] == "Invalido"

    # Test offline URL
    result = auditar_site_lead("http://this-domain-does-not-exist-xyz123.com")
    assert result["status"] == "Offline"

    # Test real URL
    result = auditar_site_lead("https://www.google.com")
    assert result["status"] == "Sucesso"
    assert 0 <= result["score"] <= 100
    assert "checks" in result
    assert "performance" in result["checks"]
    assert "seo" in result["checks"]
    assert "security" in result["checks"]

    print("✓ Auditor tests passed")


def test_qualifier():
    """Test lead qualification logic."""
    # Low score = hot lead
    qual = qualificar_lead_com_ia({
        "nome": "Test",
        "url": "http://test.com",
        "auditoria": {
            "score": 30,
            "motivos": "Muito lento, Sem HTTPS",
            "checks": {
                "performance": {"load_time": 5.0},
                "security": {"has_https": False},
                "seo": {"issues": ["Sem H1"]},
                "mobile": {"has_viewport": False},
                "images": {"missing_alt": 3},
                "technology": {"technologies": ["WordPress"]},
            },
        },
    })
    assert qual["qualificacao"] == "Quente"
    assert qual["priority"] == "high"
    assert len(qual["factors"]) > 0
    assert len(qual["opportunities"]) > 0

    # High score = cold lead
    qual2 = qualificar_lead_com_ia({
        "nome": "Good Site",
        "url": "http://good.com",
        "auditoria": {"score": 95, "motivos": "", "checks": {}},
    })
    assert qual2["qualificacao"] == "Frio"
    assert qual2["priority"] == "low"

    print("✓ Qualifier tests passed")


def test_slug():
    """Test slug generation."""
    assert criar_slug_seguro("Advocacia Rossi") == "advocacia-rossi"
    assert criar_slug_seguro("Clínica São Paulo") == "clinica-sao-paulo"
    assert criar_slug_seguro("A & B Associados!!!") == "a-b-associados"
    assert len(criar_slug_seguro("x" * 100)) <= 50

    print("✓ Slug tests passed")


def test_deployer_import():
    """Test deployer can be imported and adapter pattern works."""
    service = DeploymentService()
    assert "vercel" in service.adapters

    # Test with nonexistent folder
    result = service.deploy("nonexistent-folder-12345")
    assert result is None

    print("✓ Deployer tests passed")


if __name__ == "__main__":
    print("=== Lead Machine Test Suite ===\n")
    test_slug()
    test_database()
    test_auditor()
    test_qualifier()
    test_deployer_import()
    print("\n=== ALL TESTS PASSED ===")
