from typing import Optional, Dict
from pydantic import BaseModel
from datetime import datetime

class PendingApproval(BaseModel):
    """Represents a pending HITL approval"""
    session_id: str
    agent_name: str  # Which agent needs approval
    action_type: str  # "email_send", "data_delete", etc.
    draft_content: str  # The thing being approved
    created_at: datetime
    metadata: Dict = {}

class HITLManager:
    """Manages HITL approval workflows"""
    
    def __init__(self):
        self._pending_approvals: Dict[str, PendingApproval] = {}
    
    def create_approval(self, session_id: str, agent_name: str, 
                       action_type: str, draft_content: str, 
                       metadata: Dict = None) -> str:
        """
        Register a pending approval request.
        
        Returns:
            approval_id: Unique identifier for this approval
        """
        approval_id = f"{session_id}_{action_type}_{datetime.now().timestamp()}"
        
        self._pending_approvals[approval_id] = PendingApproval(
            session_id=session_id,
            agent_name=agent_name,
            action_type=action_type,
            draft_content=draft_content,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        
        return approval_id
    
    def get_pending_approval(self, session_id: str) -> Optional[PendingApproval]:
        """Get the most recent pending approval for a session"""
        for approval_id, approval in self._pending_approvals.items():
            if approval.session_id == session_id:
                return approval
        return None
    
    def approve(self, session_id: str) -> Optional[PendingApproval]:
        """Mark approval as approved and return it"""
        approval = self.get_pending_approval(session_id)
        if approval:
            approval_id = [k for k, v in self._pending_approvals.items() 
                          if v.session_id == session_id][0]
            del self._pending_approvals[approval_id]
        return approval
    
    def reject(self, session_id: str) -> Optional[PendingApproval]:
        """Mark approval as rejected and return it"""
        approval = self.get_pending_approval(session_id)
        if approval:
            approval_id = [k for k, v in self._pending_approvals.items() 
                          if v.session_id == session_id][0]
            del self._pending_approvals[approval_id]
        return approval
    
    def has_pending_approval(self, session_id: str) -> bool:
        """Check if session has a pending approval"""
        return self.get_pending_approval(session_id) is not None

hitl_manager = HITLManager()
