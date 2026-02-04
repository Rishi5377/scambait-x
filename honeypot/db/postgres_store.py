"""
ScamBait-X V2 - PostgreSQL Intelligence Store
Persistent storage for sessions, entities, and threat intelligence
"""

import os
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

try:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from sqlalchemy import text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class PostgresStore:
    """
    PostgreSQL store for persistent intelligence data:
    - Session history
    - Extracted entities
    - Scammer profiles
    - Threat graph edges
    """
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", 
            "postgresql+asyncpg://scambait:scambait123@localhost:5432/scambait"
        )
        self._engine = None
        self._session_factory = None
    
    async def connect(self) -> bool:
        """Connect to PostgreSQL."""
        if not HAS_SQLALCHEMY:
            print("⚠️  SQLAlchemy not installed, using in-memory fallback")
            return False
        
        try:
            self._engine = create_async_engine(self.database_url, echo=False)
            self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
            
            # Test connection
            async with self._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            print("✅ PostgreSQL connected")
            return True
        except Exception as e:
            print(f"⚠️  PostgreSQL connection failed: {e}")
            self._engine = None
            return False
    
    async def disconnect(self):
        """Disconnect from PostgreSQL."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
    
    @property
    def is_connected(self) -> bool:
        return self._engine is not None
    
    def _get_session(self) -> AsyncSession:
        if not self._session_factory:
            raise RuntimeError("Not connected to PostgreSQL")
        return self._session_factory()
    
    # ==================== Session Operations ====================
    
    async def save_session(
        self,
        session_id: UUID,
        persona_id: str,
        mode: str = "patience",
        turn_count: int = 0,
        scam_type: str = None,
        scam_confidence: float = None,
        threat_level: str = None
    ) -> bool:
        """Save or update session."""
        if not self._engine:
            return False
        
        try:
            async with self._get_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO sessions (id, persona_id, current_mode, turn_count, 
                                            scam_type, scam_confidence, threat_level)
                        VALUES (:id, :persona_id, :mode, :turn_count, 
                                :scam_type, :scam_confidence, :threat_level)
                        ON CONFLICT (id) DO UPDATE SET
                            current_mode = :mode,
                            turn_count = :turn_count,
                            scam_type = COALESCE(:scam_type, sessions.scam_type),
                            scam_confidence = COALESCE(:scam_confidence, sessions.scam_confidence),
                            threat_level = COALESCE(:threat_level, sessions.threat_level)
                    """),
                    {
                        "id": str(session_id),
                        "persona_id": persona_id,
                        "mode": mode,
                        "turn_count": turn_count,
                        "scam_type": scam_type,
                        "scam_confidence": scam_confidence,
                        "threat_level": threat_level
                    }
                )
                await session.commit()
                return True
        except Exception as e:
            print(f"PostgreSQL save session error: {e}")
            return False
    
    async def end_session(self, session_id: UUID) -> bool:
        """Mark session as ended."""
        if not self._engine:
            return False
        
        try:
            async with self._get_session() as session:
                await session.execute(
                    text("UPDATE sessions SET ended_at = NOW() WHERE id = :id"),
                    {"id": str(session_id)}
                )
                await session.commit()
                return True
        except Exception:
            return False
    
    # ==================== Message Operations ====================
    
    async def save_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        raw_content: str = None
    ) -> bool:
        """Save message to session."""
        if not self._engine:
            return False
        
        try:
            async with self._get_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO messages (session_id, role, content, raw_content)
                        VALUES (:session_id, :role, :content, :raw_content)
                    """),
                    {
                        "session_id": str(session_id),
                        "role": role,
                        "content": content,
                        "raw_content": raw_content
                    }
                )
                await session.commit()
                return True
        except Exception as e:
            print(f"PostgreSQL save message error: {e}")
            return False
    
    async def get_messages(self, session_id: UUID) -> List[Dict[str, Any]]:
        """Get all messages for session."""
        if not self._engine:
            return []
        
        try:
            async with self._get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT role, content, timestamp 
                        FROM messages 
                        WHERE session_id = :session_id 
                        ORDER BY timestamp
                    """),
                    {"session_id": str(session_id)}
                )
                return [
                    {"role": row[0], "content": row[1], "timestamp": row[2]}
                    for row in result.fetchall()
                ]
        except Exception:
            return []
    
    # ==================== Entity Operations ====================
    
    async def save_entity(
        self,
        session_id: UUID,
        entity_type: str,
        value: str,
        normalized_value: str = None
    ) -> bool:
        """Save extracted entity."""
        if not self._engine:
            return False
        
        normalized = normalized_value or value.lower().strip()
        
        try:
            async with self._get_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO entities (session_id, entity_type, value, normalized_value)
                        VALUES (:session_id, :entity_type, :value, :normalized_value)
                        ON CONFLICT (session_id, entity_type, normalized_value) DO NOTHING
                    """),
                    {
                        "session_id": str(session_id),
                        "entity_type": entity_type,
                        "value": value,
                        "normalized_value": normalized
                    }
                )
                await session.commit()
                return True
        except Exception as e:
            print(f"PostgreSQL save entity error: {e}")
            return False
    
    async def get_entities_by_type(self, entity_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all entities of a type across sessions."""
        if not self._engine:
            return []
        
        try:
            async with self._get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT DISTINCT normalized_value, value, COUNT(*) as occurrences
                        FROM entities 
                        WHERE entity_type = :entity_type
                        GROUP BY normalized_value, value
                        ORDER BY occurrences DESC
                        LIMIT :limit
                    """),
                    {"entity_type": entity_type, "limit": limit}
                )
                return [
                    {"normalized": row[0], "value": row[1], "occurrences": row[2]}
                    for row in result.fetchall()
                ]
        except Exception:
            return []
    
    # ==================== Threat Graph Operations ====================
    
    async def add_threat_edge(
        self,
        source_type: str,
        source_value: str,
        target_type: str,
        target_value: str,
        relationship: str,
        session_id: UUID = None,
        weight: float = 1.0
    ) -> bool:
        """Add edge to threat graph."""
        if not self._engine:
            return False
        
        try:
            async with self._get_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO threat_edges 
                        (source_type, source_value, target_type, target_value, 
                         relationship, session_id, weight)
                        VALUES (:src_type, :src_val, :tgt_type, :tgt_val, 
                                :rel, :session_id, :weight)
                    """),
                    {
                        "src_type": source_type,
                        "src_val": source_value,
                        "tgt_type": target_type,
                        "tgt_val": target_value,
                        "rel": relationship,
                        "session_id": str(session_id) if session_id else None,
                        "weight": weight
                    }
                )
                await session.commit()
                return True
        except Exception:
            return False
    
    async def get_threat_graph_data(self) -> Dict[str, Any]:
        """Get all edges for building NetworkX graph."""
        if not self._engine:
            return {"nodes": [], "edges": []}
        
        try:
            async with self._get_session() as session:
                result = await session.execute(
                    text("""
                        SELECT source_type, source_value, target_type, target_value, 
                               relationship, weight
                        FROM threat_edges
                    """)
                )
                
                nodes = set()
                edges = []
                
                for row in result.fetchall():
                    src = f"{row[0]}:{row[1]}"
                    tgt = f"{row[2]}:{row[3]}"
                    nodes.add(src)
                    nodes.add(tgt)
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "relationship": row[4],
                        "weight": row[5]
                    })
                
                return {
                    "nodes": list(nodes),
                    "edges": edges
                }
        except Exception:
            return {"nodes": [], "edges": []}
    
    # ==================== Intelligence Reports ====================
    
    async def save_report(self, session_id: UUID, report_data: Dict[str, Any], threat_level: str) -> bool:
        """Save intelligence report."""
        if not self._engine:
            return False
        
        import json
        
        try:
            async with self._get_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO intelligence_reports (session_id, report_data, threat_level)
                        VALUES (:session_id, :report_data, :threat_level)
                    """),
                    {
                        "session_id": str(session_id),
                        "report_data": json.dumps(report_data, default=str),
                        "threat_level": threat_level
                    }
                )
                await session.commit()
                return True
        except Exception:
            return False
    
    # ==================== Statistics ====================
    
    async def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        if not self._engine:
            return {}
        
        try:
            async with self._get_session() as session:
                stats = {}
                
                # Count sessions
                result = await session.execute(text("SELECT COUNT(*) FROM sessions"))
                stats["total_sessions"] = result.scalar()
                
                # Count entities
                result = await session.execute(text("SELECT COUNT(*) FROM entities"))
                stats["total_entities"] = result.scalar()
                
                # Count by entity type
                result = await session.execute(
                    text("SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type")
                )
                for row in result.fetchall():
                    stats[f"entities_{row[0]}"] = row[1]
                
                return stats
        except Exception:
            return {}


# Singleton instance
postgres_store = PostgresStore()


async def get_postgres() -> PostgresStore:
    """Get PostgreSQL store instance."""
    if not postgres_store.is_connected:
        await postgres_store.connect()
    return postgres_store
