from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from .agent import analytics_agent

router = APIRouter(prefix="/analytics", tags=["analytics"])

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
    A2A endpoint for analytics agent interaction.
    """
    try:
        result = await analytics_agent.generate_turn_streaming(
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
        print(f"[ANALYTICS AGENT] Error: {e}")
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
        "name": "analytics_specialist",
        "description": "Business intelligence and data analysis agent specialized in inventory analytics, trends, forecasting, and performance reporting",
        "capabilities": [
            "inventory_trend_analysis",
            "inventory_value_calculation",
            "sales_forecasting",
            "performance_reporting",
            "category_comparison",
            "anomaly_detection"
        ],
        "version": "1.0.0",
        "endpoints": {
            "interact": "/analytics/a2a/interact"
        }
    }

@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "agent": "analytics_specialist"}
