from typing import Dict, Any, Optional
from datetime import datetime
import json

class AgentMetrics:
    """
    Track agent quality metrics following ADK best practices.
    Monitors: latency, success rate, token usage, error patterns.
    """
    
    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}
    
    def record_agent_call(
        self,
        agent_name: str,
        session_id: str,
        success: bool,
        latency_ms: float,
        token_count: Optional[int] = None,
        error: Optional[str] = None
    ):
        """Record metrics for an agent invocation."""
        if agent_name not in self.metrics:
            self.metrics[agent_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_latency_ms": 0,
                "total_tokens": 0,
                "errors": []
            }
        
        agent_metrics = self.metrics[agent_name]
        agent_metrics["total_calls"] += 1
        agent_metrics["total_latency_ms"] += latency_ms
        
        if success:
            agent_metrics["successful_calls"] += 1
        else:
            agent_metrics["failed_calls"] += 1
            if error and len(agent_metrics["errors"]) < 10:
                agent_metrics["errors"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "session_id": session_id,
                    "error": str(error)[:200]
                })
        
        if token_count:
            agent_metrics["total_tokens"] += token_count
    
    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get aggregated statistics for an agent."""
        if agent_name not in self.metrics:
            return {}
        
        metrics = self.metrics[agent_name]
        total_calls = metrics["total_calls"]
        
        if total_calls == 0:
            return metrics
        
        return {
            **metrics,
            "success_rate": metrics["successful_calls"] / total_calls,
            "avg_latency_ms": metrics["total_latency_ms"] / total_calls,
            "avg_tokens_per_call": metrics["total_tokens"] / total_calls if metrics["total_tokens"] > 0 else 0
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all agents."""
        return {
            agent_name: self.get_agent_stats(agent_name)
            for agent_name in self.metrics.keys()
        }

agent_metrics = AgentMetrics()
