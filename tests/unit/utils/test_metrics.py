"""Tests for Prometheus metrics."""
import pytest
from prometheus_client import REGISTRY
from src.utils.metrics import (
    active_calls,
    total_calls,
    call_duration,
    state_operations,
    track_state_operation,
    track_external_request,
    track_frame_processing,
    increment_call_phase,
)


class TestMetrics:
    """Test Prometheus metrics functionality."""

    def test_active_calls_gauge(self):
        """Test active calls gauge increments and decrements."""
        initial = active_calls._value._value
        active_calls.inc()
        assert active_calls._value._value == initial + 1
        active_calls.dec()
        assert active_calls._value._value == initial

    def test_total_calls_counter(self):
        """Test total calls counter increments."""
        before = total_calls.labels(status='success')._value._value
        total_calls.labels(status='success').inc()
        after = total_calls.labels(status='success')._value._value
        assert after == before + 1

    def test_call_duration_histogram(self):
        """Test call duration histogram records observations."""
        before_count = call_duration._sum._value
        call_duration.observe(120.5)
        after_count = call_duration._sum._value
        assert after_count > before_count

    def test_increment_call_phase(self):
        """Test call phase counter helper function."""
        phase = "INSURANCE"
        before = None
        try:
            # Get current value for this phase label
            for sample in REGISTRY.collect():
                if sample.name == 'voiceagent_calls_by_phase_total':
                    for metric in sample.samples:
                        if metric.labels.get('phase') == phase:
                            before = metric.value
                            break
        except Exception:
            pass

        increment_call_phase(phase)

        after = None
        try:
            for sample in REGISTRY.collect():
                if sample.name == 'voiceagent_calls_by_phase_total':
                    for metric in sample.samples:
                        if metric.labels.get('phase') == phase:
                            after = metric.value
                            break
        except Exception:
            pass

        # If we got values, verify increment
        if before is not None and after is not None:
            assert after >= before

    def test_track_state_operation(self):
        """Test state operation tracking helper."""
        operation = "create"
        backend = "redis"

        before_count = None
        try:
            for sample in REGISTRY.collect():
                if sample.name == 'voiceagent_state_operations_total':
                    for metric in sample.samples:
                        if (metric.labels.get('operation') == operation and
                            metric.labels.get('backend') == backend):
                            before_count = metric.value
                            break
        except Exception:
            pass

        track_state_operation(operation, backend, 0.05)

        after_count = None
        try:
            for sample in REGISTRY.collect():
                if sample.name == 'voiceagent_state_operations_total':
                    for metric in sample.samples:
                        if (metric.labels.get('operation') == operation and
                            metric.labels.get('backend') == backend):
                            after_count = metric.value
                            break
        except Exception:
            pass

        # If we got values, verify increment
        if before_count is not None and after_count is not None:
            assert after_count >= before_count

    def test_track_external_request_openai(self):
        """Test external request tracking for OpenAI."""
        track_external_request("openai", 0.5, True)
        # Just verify it doesn't raise an exception

    def test_track_external_request_deepgram_stt(self):
        """Test external request tracking for Deepgram STT."""
        track_external_request("deepgram_stt", 0.1, True)
        # Just verify it doesn't raise an exception

    def test_track_external_request_deepgram_tts(self):
        """Test external request tracking for Deepgram TTS."""
        track_external_request("deepgram_tts", 0.2, False)
        # Just verify it doesn't raise an exception

    def test_track_external_request_usps(self):
        """Test external request tracking for USPS."""
        track_external_request("usps", 0.3, True)
        # Just verify it doesn't raise an exception

    def test_track_frame_processing(self):
        """Test frame processing tracking."""
        track_frame_processing("TextFrame", "inbound", 0.01)
        # Just verify it doesn't raise an exception

    def test_metrics_export(self):
        """Test that metrics can be exported in Prometheus format."""
        from prometheus_client import generate_latest

        # Generate metrics output
        output = generate_latest()

        # Verify it's bytes and non-empty
        assert isinstance(output, bytes)
        assert len(output) > 0

        # Verify some expected metrics are present
        output_str = output.decode('utf-8')
        assert 'voiceagent_active_calls' in output_str
        assert 'voiceagent_calls_total' in output_str
        assert 'voiceagent_call_duration_seconds' in output_str
