"""Lightweight, privacy-safe runtime telemetry for local operation and testing."""
from __future__ import annotations

import os
import statistics
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import psutil


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round(value: float | None, digits: int = 1) -> float | None:
    return round(value, digits) if value is not None else None


class MetricsCollector:
    """Stores a bounded diagnostic window; never stores transcript or document text."""

    def __init__(self, max_events: int = 250):
        self.started = time.monotonic()
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.model_load_ms: dict[str, float] = {}
        self._lock = threading.Lock()
        self._process = psutil.Process(os.getpid())
        self._process.cpu_percent(None)
        psutil.cpu_percent(None)
        self._gpu_cache: tuple[float, dict[str, Any] | None] = (0, None)

    def record(self, category: str, name: str, duration_ms: float, ok: bool = True, **values: Any) -> None:
        event = {"timestamp": _utc_now(), "category": category, "name": name,
                 "duration_ms": _round(duration_ms), "ok": ok, **values}
        with self._lock:
            self.events.append(event)

    def set_model_load(self, component: str, duration_ms: float, ok: bool) -> None:
        self.model_load_ms[component] = _round(duration_ms)
        self.record("startup", component, duration_ms, ok)

    def reset(self) -> None:
        with self._lock:
            self.events.clear()

    @staticmethod
    def _percentile(values: list[float], fraction: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
        return _round(ordered[index])

    def _gpu(self) -> dict[str, Any] | None:
        cached_at, cached = self._gpu_cache
        if time.monotonic() - cached_at < 1.5:
            return cached
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2, check=True, creationflags=flags,
            )
            fields = [item.strip() for item in result.stdout.splitlines()[0].split(",")]
            gpu = {"name": fields[0], "utilization_percent": float(fields[1]),
                   "memory_used_mb": float(fields[2]), "memory_total_mb": float(fields[3]),
                   "memory_percent": _round(float(fields[2]) / max(float(fields[3]), 1) * 100),
                   "temperature_c": float(fields[4]), "power_w": float(fields[5])}
        except Exception:
            gpu = None
        self._gpu_cache = (time.monotonic(), gpu)
        return gpu

    def snapshot(self, components: dict[str, bool], component_errors: dict[str, str]) -> dict[str, Any]:
        memory = psutil.virtual_memory()
        process_memory = self._process.memory_info()
        with self._lock:
            events = list(self.events)
        http_events = [e for e in events if e["category"] == "http"]
        pipelines = [e for e in events if e["category"] in {"roleplay", "transcription", "tts"}]
        durations = [float(e["duration_ms"]) for e in http_events]
        errors = [e for e in http_events if not e["ok"]]
        roleplays = [e for e in events if e["category"] == "roleplay"]
        latest_roleplay = dict(roleplays[-1]) if roleplays else None
        if latest_roleplay:
            correlation_id = latest_roleplay.get("correlation_id")
            matching_tts = next(
                (e for e in reversed(events) if e["category"] == "tts" and e.get("correlation_id") == correlation_id),
                None,
            )
            if matching_tts:
                latest_roleplay.update({
                    "tts_ms": matching_tts.get("duration_ms"),
                    "tts_first_audio_ms": matching_tts.get("first_audio_ms"),
                    "audio_seconds": matching_tts.get("audio_seconds"),
                    "tts_chunks": matching_tts.get("chunks"),
                    "tts_realtime_factor": matching_tts.get("tts_realtime_factor"),
                    "tts_ok": matching_tts.get("ok"),
                    "first_audio_total_ms": _round((0 if matching_tts.get("overlaps_response") else float(latest_roleplay.get("response_ready_ms", 0))) + float(matching_tts.get("first_audio_ms") or 0)),
                    "full_pipeline_ms": _round((0 if matching_tts.get("overlaps_response") else float(latest_roleplay.get("response_ready_ms", 0))) + float(matching_tts.get("duration_ms") or 0)),
                })
        return {
            "timestamp": _utc_now(),
            "uptime_seconds": _round(time.monotonic() - self.started),
            "system": {
                "cpu_percent": _round(psutil.cpu_percent(None)),
                "ram_used_gb": _round(memory.used / 1024 ** 3, 2),
                "ram_total_gb": _round(memory.total / 1024 ** 3, 2),
                "ram_percent": _round(memory.percent),
                "process_rss_mb": _round(process_memory.rss / 1024 ** 2),
                "process_cpu_percent": _round(self._process.cpu_percent(None)),
                "process_threads": self._process.num_threads(),
                "gpu": self._gpu(),
            },
            "components": {name: {"ready": ready, "load_ms": self.model_load_ms.get(name),
                                   "error": component_errors.get(name)} for name, ready in components.items()},
            "http": {"requests": len(http_events), "errors": len(errors),
                     "error_rate_percent": _round(len(errors) / max(len(http_events), 1) * 100),
                     "mean_ms": _round(statistics.fmean(durations)) if durations else None,
                     "p50_ms": self._percentile(durations, .50), "p95_ms": self._percentile(durations, .95)},
            "pipeline": {"runs": len(pipelines), "latest_roleplay": latest_roleplay},
            "recent": list(reversed(events[-30:])),
        }
