"""Test configuration."""

from duetto.config import Settings

def test_config_loading():
    # Test defaults
    settings = Settings()
    assert settings.server.port == 8091
    assert settings.tv.threshold_pct == 10.0
    
    # Test nested structure
    assert "NASDAQ:AAPL" in settings.tv.symbols
