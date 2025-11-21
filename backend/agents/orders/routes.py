from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from .agent import order_agent

router = APIRouter(prefix="/orders", tags=["orders"])

class A2AInteractRequest(BaseModel):
    prompt: str
    session_id: str
    context: Optional[Dict[str, Any]] = {}

class A2AInteractResponse(BaseModel):
    response: str
    session_id: str
    error: Optional[str] = None

@router.post("/a2a/interact")
async def a2a_interact(request: A2AInteractRequest):
    """
    A2A endpoint for order management agent interaction.
    """
    try:
        result = await order_agent.generate_turn_streaming(
            prompt=request.prompt,
            session_id=request.session_id,
            app_name="agents",
            user_id="default_user"
        )
        
        response_text = ""
        async for chunk in result:
            if hasattr(chunk, 'text'):
                response_text += chunk.text
        
        return A2AInteractResponse(
            response=response_text.strip(),
            session_id=request.session_id
        )
        
    except Exception as e:
        print(f"[ORDER AGENT] Error: {e}")
        return A2AInteractResponse(
            response=f"I encountered an error: {str(e)}",
            session_id=request.session_id,
            error=str(e)
        )

@router.get("/.well-known/agent.json")
async def get_agent_card():
    """
    Agent card endpoint for A2A discovery.
    """
    return {
        "name": "order_specialist",
        "description": "Order management and procurement agent specialized in purchase orders, supplier management, order tracking, and reorder recommendations",
        "capabilities": [
            "purchase_order_creation",
            "supplier_catalog_query",
            "order_status_tracking",
            "reorder_recommendations",
            "supplier_compliance_validation",
            "optimal_order_quantity_calculation"
        ],
        "version": "1.0.0",
        "endpoints": {
            "interact": "/orders/a2a/interact"
        }
    }

@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "agent": "order_specialist"}
