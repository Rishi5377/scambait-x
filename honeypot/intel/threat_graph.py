"""
ScamBait-X V2 - Threat Intelligence Graph
NetworkX-based threat graph for IOC correlation
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import json

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    nx = None


@dataclass
class ThreatNode:
    """Node in the threat graph."""
    node_type: str  # 'upi', 'phone', 'bank', 'session', 'scammer', 'campaign'
    value: str
    metadata: Dict[str, Any] = None


@dataclass
class ThreatEdge:
    """Edge in the threat graph."""
    source: ThreatNode
    target: ThreatNode
    relationship: str  # 'linked_to', 'used_by', 'same_campaign', 'co_occurred'
    weight: float = 1.0


class ThreatGraph:
    """
    NetworkX-based threat intelligence graph.
    Connects IOCs to find patterns and campaigns.
    """
    
    def __init__(self):
        if not HAS_NETWORKX:
            self._graph = None
            print("⚠️  NetworkX not available, threat graph disabled")
        else:
            self._graph = nx.DiGraph()
    
    def is_available(self) -> bool:
        return HAS_NETWORKX and self._graph is not None
    
    def add_node(
        self, 
        node_type: str, 
        value: str, 
        **metadata
    ) -> str:
        """Add node to graph. Returns node_id."""
        if not self._graph:
            return ""
        
        node_id = f"{node_type}:{value}"
        self._graph.add_node(node_id, type=node_type, value=value, **metadata)
        return node_id
    
    def add_edge(
        self,
        source_type: str,
        source_value: str,
        target_type: str,
        target_value: str,
        relationship: str,
        weight: float = 1.0,
        **metadata
    ) -> bool:
        """Add edge between nodes."""
        if not self._graph:
            return False
        
        src_id = f"{source_type}:{source_value}"
        tgt_id = f"{target_type}:{target_value}"
        
        # Ensure nodes exist
        if src_id not in self._graph:
            self.add_node(source_type, source_value)
        if tgt_id not in self._graph:
            self.add_node(target_type, target_value)
        
        # Add or update edge
        if self._graph.has_edge(src_id, tgt_id):
            # Increase weight for existing edge
            self._graph[src_id][tgt_id]["weight"] += weight
        else:
            self._graph.add_edge(
                src_id, tgt_id, 
                relationship=relationship, 
                weight=weight,
                **metadata
            )
        
        return True
    
    def add_session_entities(
        self,
        session_id: str,
        entities: Dict[str, List[str]]
    ):
        """
        Add all entities from a session to graph.
        Links entities that co-occurred in same session.
        """
        if not self._graph:
            return
        
        # Add session node
        self.add_node("session", session_id)
        
        all_entity_ids = []
        
        # Add entity nodes and link to session
        for entity_type, values in entities.items():
            for value in values:
                entity_id = self.add_node(entity_type, value)
                all_entity_ids.append(entity_id)
                
                self.add_edge(
                    "session", session_id,
                    entity_type, value,
                    "extracted"
                )
        
        # Link entities that co-occurred
        for i, id1 in enumerate(all_entity_ids):
            for id2 in all_entity_ids[i+1:]:
                type1 = id1.split(":")[0]
                val1 = id1.split(":", 1)[1]
                type2 = id2.split(":")[0]
                val2 = id2.split(":", 1)[1]
                
                self.add_edge(
                    type1, val1,
                    type2, val2,
                    "co_occurred",
                    weight=0.5
                )
    
    def find_connected_entities(
        self, 
        entity_type: str, 
        entity_value: str,
        max_depth: int = 2
    ) -> Dict[str, List[str]]:
        """Find all entities connected to given entity within depth."""
        if not self._graph:
            return {}
        
        node_id = f"{entity_type}:{entity_value}"
        if node_id not in self._graph:
            return {}
        
        connected = {}
        
        # BFS to find connected nodes
        visited = {node_id}
        queue = [(node_id, 0)]
        
        while queue:
            current, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            # Get neighbors
            neighbors = list(self._graph.successors(current)) + \
                       list(self._graph.predecessors(current))
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))
                    
                    # Parse node info
                    parts = neighbor.split(":", 1)
                    if len(parts) == 2:
                        ntype, nvalue = parts
                        if ntype not in connected:
                            connected[ntype] = []
                        connected[ntype].append(nvalue)
        
        return connected
    
    def find_campaigns(self, min_shared_entities: int = 2) -> List[Dict[str, Any]]:
        """
        Identify potential scam campaigns by clustering sessions
        that share multiple entities.
        """
        if not self._graph:
            return []
        
        # Get all session nodes
        sessions = [n for n, d in self._graph.nodes(data=True) if d.get("type") == "session"]
        
        campaigns = []
        processed = set()
        
        for session in sessions:
            if session in processed:
                continue
            
            # Find sessions with shared entities
            session_entities = self.get_session_entities(session.split(":", 1)[1])
            related_sessions = [session]
            
            for other_session in sessions:
                if other_session == session or other_session in processed:
                    continue
                
                other_entities = self.get_session_entities(other_session.split(":", 1)[1])
                
                # Count shared entities
                shared = 0
                for etype, values in session_entities.items():
                    other_values = other_entities.get(etype, [])
                    shared += len(set(values) & set(other_values))
                
                if shared >= min_shared_entities:
                    related_sessions.append(other_session)
            
            if len(related_sessions) > 1:
                # Found a campaign
                campaign_entities = {}
                for rs in related_sessions:
                    entities = self.get_session_entities(rs.split(":", 1)[1])
                    for etype, values in entities.items():
                        if etype not in campaign_entities:
                            campaign_entities[etype] = set()
                        campaign_entities[etype].update(values)
                
                campaigns.append({
                    "sessions": [s.split(":", 1)[1] for s in related_sessions],
                    "session_count": len(related_sessions),
                    "shared_entities": {k: list(v) for k, v in campaign_entities.items()}
                })
                
                processed.update(related_sessions)
        
        return campaigns
    
    def get_session_entities(self, session_id: str) -> Dict[str, List[str]]:
        """Get all entities linked to a session."""
        if not self._graph:
            return {}
        
        node_id = f"session:{session_id}"
        if node_id not in self._graph:
            return {}
        
        entities = {}
        for neighbor in self._graph.successors(node_id):
            parts = neighbor.split(":", 1)
            if len(parts) == 2:
                etype, value = parts
                if etype != "session":
                    if etype not in entities:
                        entities[etype] = []
                    entities[etype].append(value)
        
        return entities
    
    def get_top_iocs(self, entity_type: str, top_k: int = 10) -> List[Tuple[str, int]]:
        """Get most connected IOCs of a type."""
        if not self._graph:
            return []
        
        nodes = [
            (n, self._graph.degree(n)) 
            for n, d in self._graph.nodes(data=True) 
            if d.get("type") == entity_type
        ]
        
        nodes.sort(key=lambda x: x[1], reverse=True)
        
        return [(n.split(":", 1)[1], deg) for n, deg in nodes[:top_k]]
    
    def get_stats(self) -> Dict[str, int]:
        """Get graph statistics."""
        if not self._graph:
            return {"available": False}
        
        return {
            "available": True,
            "total_nodes": self._graph.number_of_nodes(),
            "total_edges": self._graph.number_of_edges(),
            "sessions": len([n for n, d in self._graph.nodes(data=True) if d.get("type") == "session"]),
            "unique_iocs": len([n for n, d in self._graph.nodes(data=True) if d.get("type") != "session"]),
        }
    
    def export_to_json(self) -> Dict[str, Any]:
        """Export graph to JSON for visualization."""
        if not self._graph:
            return {"nodes": [], "edges": []}
        
        nodes = []
        for node_id, data in self._graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "type": data.get("type"),
                "value": data.get("value"),
                "degree": self._graph.degree(node_id)
            })
        
        edges = []
        for src, tgt, data in self._graph.edges(data=True):
            edges.append({
                "source": src,
                "target": tgt,
                "relationship": data.get("relationship"),
                "weight": data.get("weight", 1)
            })
        
        return {"nodes": nodes, "edges": edges}


# Singleton instance
threat_graph = ThreatGraph()


def get_threat_graph() -> ThreatGraph:
    """Get threat graph instance."""
    return threat_graph
