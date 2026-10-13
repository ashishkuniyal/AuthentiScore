"""
AuthentiScore — Collector Circuit Breaker (B4)
==============================================

Protects collectors from hammering failing upstream platforms.
If a collector experiences 5 consecutive failures within 10 minutes,
its circuit breaker trips to OPEN for 5 minutes (300 seconds),
failing fast to allow immediate fallback to alternative scrapers.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 5
WINDOW_SECONDS = 600       # 10 minutes
COOLDOWN_SECONDS = 300     # 5 minutes


class CircuitBreaker:
    def __init__(self, name: str, threshold: int = FAILURE_THRESHOLD, cooldown: int = COOLDOWN_SECONDS):
        self.name = name
        self.threshold = threshold
        self.cooldown = cooldown
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_failure_time > self.cooldown:
                logger.info("Circuit breaker %s cooling down: OPEN -> HALF_OPEN", self.name)
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self):
        if self.state in ("OPEN", "HALF_OPEN"):
            logger.info("Circuit breaker %s recovered: %s -> CLOSED", self.name, self.state)
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        now = time.time()
        # Reset count if last failure was outside the rolling window
        if now - self.last_failure_time > WINDOW_SECONDS:
            self.failure_count = 0

        self.failure_count += 1
        self.last_failure_time = now

        if self.failure_count >= self.threshold or self.state == "HALF_OPEN":
            logger.warning("Circuit breaker %s tripped! Failure count: %d -> OPEN", self.name, self.failure_count)
            self.state = "OPEN"

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "threshold": self.threshold,
            "cooldown_remaining": max(0.0, round(self.cooldown - (time.time() - self.last_failure_time), 1)) if self.state == "OPEN" else 0.0
        }


# Global registry of collector circuit breakers
_REGISTRY: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    if name not in _REGISTRY:
        _REGISTRY[name] = CircuitBreaker(name)
    return _REGISTRY[name]


def get_all_circuit_breaker_statuses() -> Dict[str, Dict[str, Any]]:
    return {name: cb.get_status() for name, cb in _REGISTRY.items()}
