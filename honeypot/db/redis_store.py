"""
ScamBait-X V2 - Redis Session Store
Real-time session caching and pub/sub for live updates
"""

import json
import os
from typing import Optional, Dict, Any, List
from datetime import timedelta

try:
    import redis.asyncio as redis
except ImportError:
    redis = None


class RedisStore:
    """
    Redis-based session store for:
    - Session state caching
    - Real-time entity tracking
    - Pub/sub for live dashboard updates
    """
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: Optional[redis.Redis] = None
        self._pubsub = None
    
    async def connect(self) -> bool:
        """Connect to Redis."""
        if redis is None:
            print("⚠️  Redis not installed, using in-memory fallback")
            return False
        
        try:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            await self._client.ping()
            print("✅ Redis connected")
            return True
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")
            self._client = None
            return False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
    
    @property
    def is_connected(self) -> bool:
        return self._client is not None
    
    # ==================== Session Operations ====================
    
    async def save_session(self, session_id: str, data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Save session data with TTL (default 1 hour)."""
        if not self._client:
            return False
        
        key = f"session:{session_id}"
        try:
            await self._client.setex(key, ttl, json.dumps(data, default=str))
            return True
        except Exception as e:
            print(f"Redis save error: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        if not self._client:
            return None
        
        key = f"session:{session_id}"
        try:
            data = await self._client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session data."""
        if not self._client:
            return False
        
        try:
            await self._client.delete(f"session:{session_id}")
            return True
        except Exception:
            return False
    
    async def extend_session_ttl(self, session_id: str, ttl: int = 3600) -> bool:
        """Extend session TTL."""
        if not self._client:
            return False
        
        try:
            await self._client.expire(f"session:{session_id}", ttl)
            return True
        except Exception:
            return False
    
    # ==================== Entity Tracking ====================
    
    async def add_entity(self, session_id: str, entity_type: str, value: str) -> int:
        """Add entity to session's entity set. Returns count."""
        if not self._client:
            return 0
        
        key = f"entities:{session_id}:{entity_type}"
        try:
            await self._client.sadd(key, value)
            await self._client.expire(key, 3600)  # 1 hour TTL
            return await self._client.scard(key)
        except Exception:
            return 0
    
    async def get_entities(self, session_id: str, entity_type: str) -> List[str]:
        """Get all entities of a type for session."""
        if not self._client:
            return []
        
        key = f"entities:{session_id}:{entity_type}"
        try:
            return list(await self._client.smembers(key))
        except Exception:
            return []
    
    async def get_all_entities(self, session_id: str) -> Dict[str, List[str]]:
        """Get all entities for session grouped by type."""
        entity_types = ["upi", "phone", "bank", "crypto", "url", "email"]
        result = {}
        for entity_type in entity_types:
            entities = await self.get_entities(session_id, entity_type)
            if entities:
                result[entity_type] = entities
        return result
    
    # ==================== Pub/Sub for Live Dashboard ====================
    
    async def publish_event(self, channel: str, event: Dict[str, Any]) -> bool:
        """Publish event to channel."""
        if not self._client:
            return False
        
        try:
            await self._client.publish(channel, json.dumps(event, default=str))
            return True
        except Exception:
            return False
    
    async def publish_session_update(self, session_id: str, event_type: str, data: Dict[str, Any]):
        """Publish session update for dashboard."""
        event = {
            "session_id": session_id,
            "type": event_type,
            "data": data
        }
        await self.publish_event("scambait:sessions", event)
    
    async def publish_entity_found(self, session_id: str, entity_type: str, value: str):
        """Publish new entity discovery."""
        await self.publish_event("scambait:entities", {
            "session_id": session_id,
            "entity_type": entity_type,
            "value": value
        })
    
    # ==================== Metrics ====================
    
    async def increment_metric(self, metric: str, amount: int = 1) -> int:
        """Increment a metric counter."""
        if not self._client:
            return 0
        
        try:
            return await self._client.incrby(f"metric:{metric}", amount)
        except Exception:
            return 0
    
    async def get_metrics(self) -> Dict[str, int]:
        """Get all metrics."""
        if not self._client:
            return {}
        
        try:
            keys = await self._client.keys("metric:*")
            metrics = {}
            for key in keys:
                value = await self._client.get(key)
                metric_name = key.replace("metric:", "")
                metrics[metric_name] = int(value) if value else 0
            return metrics
        except Exception:
            return {}


# Singleton instance
redis_store = RedisStore()


async def get_redis() -> RedisStore:
    """Get Redis store instance."""
    if not redis_store.is_connected:
        await redis_store.connect()
    return redis_store
