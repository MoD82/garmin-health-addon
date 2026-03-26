import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.config import load_config  # Top-level Import (Module-Caching-sicher)


def test_load_config_defaults():
    """Lädt Config mit leerer options.json → alle Defaults greifen."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        tmp_path = Path(f.name)
    with patch("src.config.OPTIONS_PATH", tmp_path):
        config = load_config()
    assert config.openai_model == "gpt-4o"
    assert config.analysis_time == "08:00"
    assert config.timezone == "Europe/Berlin"
    assert config.retry_count == 3


def test_load_config_override():
    """Überschreibt einzelne Werte aus options.json."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"analysis_time": "09:00", "retry_count": 5}, f)
        tmp_path = Path(f.name)
    with patch("src.config.OPTIONS_PATH", tmp_path):
        config = load_config()
    assert config.analysis_time == "09:00"
    assert config.retry_count == 5
    assert config.openai_model == "gpt-4o"  # default bleibt


def test_load_config_missing_file():
    """Fehlende options.json → Config mit allen Defaults."""
    with patch("src.config.OPTIONS_PATH", Path("/nonexistent/options.json")):
        config = load_config()
    assert config.timezone == "Europe/Berlin"
