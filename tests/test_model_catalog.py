import pytest
from pathlib import Path
from skybrain.engine.model_catalog import ModelCatalog, MODEL_PRESETS, DEFAULT_PRESET_KEY


def test_catalog_paths_and_defaults(tmp_path):
    models_dir = tmp_path / "models"
    home_dir = tmp_path / "home"
    catalog = ModelCatalog(models_dir=models_dir, home_dir=home_dir)

    # 1. Defaults
    assert catalog.get_active_key() == DEFAULT_PRESET_KEY
    assert not catalog.is_installed()

    # 2. List presets
    presets = catalog.list_models()
    assert len(presets) >= 2
    keys = [p["key"] for p in presets]
    assert "gemma-4-e4b" in keys
    assert "gemma-2-2b" in keys

    # 3. Switch active key
    catalog.set_active_key("gemma-2-2b")
    assert catalog.get_active_key() == "gemma-2-2b"


def test_catalog_installed_check(tmp_path):
    models_dir = tmp_path / "models"
    home_dir = tmp_path / "home"
    catalog = ModelCatalog(models_dir=models_dir, home_dir=home_dir)

    path = catalog.get_model_path("gemma-4-e4b")
    with open(path, "wb") as f:
        f.seek(101 * 1024 * 1024 - 1)
        f.write(b"\0")

    assert catalog.is_installed("gemma-4-e4b")



def test_ensure_model_ready_when_installed(tmp_path):
    models_dir = tmp_path / "models"
    home_dir = tmp_path / "home"
    catalog = ModelCatalog(models_dir=models_dir, home_dir=home_dir)

    path = catalog.get_model_path("gemma-4-e4b")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.seek(101 * 1024 * 1024 - 1)
        f.write(b"\0")

    result_path = catalog.ensure_model_ready("gemma-4-e4b")
    assert result_path == path
    assert catalog.is_installed("gemma-4-e4b")


def test_corporate_ssl_and_proxy_settings(tmp_path, monkeypatch):
    from skybrain.core.config import SkyBrainSettings
    import ssl

    # 1. Custom CA bundle test
    fake_ca = tmp_path / "corp_ca.pem"
    fake_ca.write_text("-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----")

    monkeypatch.setenv("SKYBRAIN_CA_BUNDLE", str(fake_ca))
    monkeypatch.setenv("SKYBRAIN_HTTPS_PROXY", "http://proxy.corp.internal:8080")
    monkeypatch.setenv("SKYBRAIN_SSL_VERIFY", "true")

    s = SkyBrainSettings()
    assert s.https_proxy == "http://proxy.corp.internal:8080"
    proxy_handler = s.get_proxy_handler()
    assert proxy_handler is not None

    # 2. Insecure mode test
    s.ssl_verify = False
    insecure_ctx = s.get_ssl_context()
    assert insecure_ctx is not None
    assert insecure_ctx.check_hostname is False
    assert insecure_ctx.verify_mode == ssl.CERT_NONE


def test_download_ssl_mitm_auto_fallback(tmp_path, monkeypatch):
    """Verifies that download automatically recovers when SSL verification fails due to corporate MITM."""
    import io
    import urllib.error
    from unittest.mock import patch, MagicMock

    catalog = ModelCatalog(models_dir=tmp_path / "models", home_dir=tmp_path / "home")

    # Simulate: 1st call fails with SSLCertVerificationError, 2nd call (unverified) succeeds
    first_call = True

    def mock_urlopen(req, context=None):
        nonlocal first_call
        if first_call:
            first_call = False
            raise urllib.error.URLError("certificate verify failed: self-signed certificate in certificate chain")

        # Fallback response
        resp = MagicMock()
        resp.headers = {"content-length": "100"}
        resp.read.side_effect = [b"A" * 100, b""]
        resp.close.return_value = None
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        # Trigger download with fallback
        target = catalog.download("gemma-2-2b")
        assert target.exists()
        assert target.stat().st_size == 100


