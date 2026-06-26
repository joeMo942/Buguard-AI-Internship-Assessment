from functools import lru_cache
import hashlib
import json
from datetime import datetime, timedelta

class LLMCache:
    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def _key(self, chain_name: str, inputs: dict) -> str:
        raw = json.dumps({"chain": chain_name, **inputs}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()
    
    def get(self, chain_name: str, inputs: dict):
        key = self._key(chain_name, inputs)
        entry = self._cache.get(key)
        if entry and datetime.utcnow() - entry["ts"] < self._ttl:
            return entry["value"]
        return None
    
    def set(self, chain_name: str, inputs: dict, value):
        key = self._key(chain_name, inputs)
        self._cache[key] = {"value": value, "ts": datetime.utcnow()}

llm_cache = LLMCache()
