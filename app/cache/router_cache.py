import hashlib
import json
import re
import logging
import time
import redis
import os

logger = logging.getLogger(__name__)

class RouterCache:
    _instance = None

    @classmethod
    def get(cls) -> redis.Redis:
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=os.environ.get("REDIS_HOST", "redis"),
                port=int(os.environ.get("REDIS_PORT", 6379)),
                db=int(os.environ.get("REDIS_DB", 0)),
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        return cls._instance

    @staticmethod
    def _normalize_prompt(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    @classmethod
    def _hash(cls, text: str) -> str:
        normalized = cls._normalize_prompt(text)
        return hashlib.sha256(normalized.encode()).hexdigest()

    # ── Routing decisions ──

    @classmethod
    def get_routing_decision(cls, prompt: str) -> dict | None:
        key = f"route:{cls._hash(prompt)}"
        try:
            cached = cls.get().get(key)
            return json.loads(cached) if cached else None
        except Exception:
            return None

    @classmethod
    def set_routing_decision(cls, prompt: str, decision: dict, ttl: int = 86400):
        key = f"route:{cls._hash(prompt)}"
        try:
            cls.get().setex(key, ttl, json.dumps(decision))
        except Exception:
            pass

    # ── Response cache (exact match) ──

    @classmethod
    def get_cached_response(cls, prompt: str) -> dict | None:
        key = f"resp:{cls._hash(prompt)}"
        try:
            cached = cls.get().get(key)
            return json.loads(cached) if cached else None
        except Exception:
            return None

    @classmethod
    def set_cached_response(cls, prompt: str, response: dict,
                           model: str, ttl: int = 3600):
        key = f"resp:{cls._hash(prompt)}"
        try:
            cls.get().setex(key, ttl, json.dumps({
                "response": response,
                "model_used": model,
                "cached_at": time.time(),
            }))
        except Exception:
            pass

    # ── Stats ──

    @classmethod
    def increment_stat(cls, stat_name: str):
        try:
            cls.get().hincrby("router:stats", stat_name, 1)
        except Exception:
            pass

    @classmethod
    def get_stats(cls) -> dict:
        try:
            return cls.get().hgetall("router:stats")
        except Exception:
            return {}
