"""Tests for arioso.platforms.musicgen (mocked, no GPU needed)."""

from unittest.mock import MagicMock, patch
import pytest

from arioso.platforms.musicgen.config import PLATFORM_CONFIG
from arioso.platforms.musicgen.adapter import Adapter


def test_musicgen_config():
    assert PLATFORM_CONFIG["name"] == "musicgen"
    assert PLATFORM_CONFIG["access_type"] == "python_lib"
    assert PLATFORM_CONFIG["auth"]["type"] == "none"
    assert PLATFORM_CONFIG["output"]["returns"] == "array"
    assert PLATFORM_CONFIG["output"]["sample_rate"] == 32000


def test_musicgen_config_param_map():
    pm = PLATFORM_CONFIG["param_map"]
    assert "prompt" in pm
    assert pm["prompt"]["native_name"] == "descriptions"
    assert pm["duration"]["native_name"] == "duration"
    assert pm["guidance"]["native_name"] == "cfg_coef"


def test_musicgen_config_prompt_coerce():
    coerce = PLATFORM_CONFIG["param_map"]["prompt"]["coerce"]
    assert coerce("jazz piano") == ["jazz piano"]


def test_musicgen_adapter_init():
    adapter = Adapter(PLATFORM_CONFIG)
    assert adapter._model is None
    assert adapter._use_transformers is False


@patch("arioso.platforms.musicgen.adapter.Adapter._ensure_model")
def test_musicgen_generate_audiocraft(mock_ensure):
    """Test generate with mocked audiocraft model."""
    import numpy as np

    adapter = Adapter(PLATFORM_CONFIG)
    adapter._use_transformers = False

    # Mock the audiocraft model
    mock_model = MagicMock()
    mock_model.sample_rate = 32000
    mock_tensor = MagicMock()
    mock_tensor.__getitem__ = MagicMock(
        return_value=MagicMock(
            cpu=MagicMock(return_value=MagicMock(numpy=MagicMock(return_value=np.zeros((1, 256000)))))
        )
    )
    mock_model.generate.return_value = mock_tensor
    adapter._model = mock_model
    adapter._model_name = "facebook/musicgen-small"

    song = adapter.generate("jazz piano", duration=8.0)

    assert song.status == "complete"
    assert song.platform == "musicgen"
    assert song.audio.sample_rate == 32000
    assert song.audio.format == "wav"
    assert song.audio.audio_array is not None
    mock_model.set_generation_params.assert_called_once()
    mock_model.generate.assert_called_once_with(["jazz piano"])


def test_musicgen_supported_affordances():
    supported = PLATFORM_CONFIG["supported_affordances"]
    assert "prompt" in supported
    assert "duration" in supported
    assert "temperature" in supported
    assert "guidance" in supported
