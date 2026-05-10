import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.audio_analyzer import _analyze_fallback as audio_fallback
from services.video_analyzer import _analyze_fallback as video_fallback


def test_audio_fallback_exposes_proxy_fields():
    result = audio_fallback(b"x" * 20000)
    assert result["metrics_source"] == "heuristic"
    assert "hesitation_count" in result
    assert "tone_proxy" in result


def test_video_fallback_exposes_proxy_fields():
    result = video_fallback(b"x" * 500000, False)
    assert result["metrics_source"] == "heuristic"
    assert "face_presence_score" in result
    assert "nervousness_score" in result
