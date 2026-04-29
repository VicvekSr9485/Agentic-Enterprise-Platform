from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import uuid

from google.adk.runners import Runner
from google.genai import types
from google.adk.sessions import InMemorySessionService
import os

from .agent import create_order_agent
from shared.logging_utils import get_logger

logger = get_logger("agents.orders.routes")
router = APIRouter(tags=["orders"])

stateless_session_service = InMemorySessionService()
_order_agent = None


def _get_order_agent():
    global _order_agent
    if _order_agent is None:
        _order_agent = create_order_agent()
    return _order_agent

class A2APart(BaseModel):
    kind: str
    text: Optional[str] = None

class A2AMessage(BaseModel):
    kind: str
    messageId: str
    role: str
    parts: List[A2APart]
    taskId: Optional[str] = None
    contextId: Optional[str] = None

class A2AConfiguration(BaseModel):
    acceptedOutputModes: List[str] = []
    blocking: bool = True

class A2AParams(BaseModel):
    configuration: A2AConfiguration
    message: A2AMessage

class A2ARequest(BaseModel):
    id: str
    jsonrpc: str
    method: str
    params: A2AParams

@router.post("/a2a/interact")
async def handle_task(raw_request: Request):
    try:
        body_dict = await raw_request.json()
        request = A2ARequest(**body_dict)
        message = request.params.message
    except Exception as e:
        logger.warning("orders_a2a_parse_failed", error=str(e))
        raise HTTPException(status_code=422, detail=str(e))

    try:
        session_id = str(uuid.uuid4())
        logger.info("orders_a2a_start", session_id=session_id)

        await stateless_session_service.create_session(
            app_name="agents",
            user_id="default_user",
            session_id=session_id
        )

        runner = Runner(
            agent=_get_order_agent(),
            app_name="agents",
            session_service=stateless_session_service
        )

        text_parts = []
        for part in message.parts:
            if part.kind == "text" and part.text:
                text_parts.append(types.Part(text=part.text))

        message_content = types.Content(
            role=message.role,
            parts=text_parts
        )

        events_async = runner.run_async(
            user_id="default_user",
            session_id=session_id,
            new_message=message_content
        )
        
        result_text = ""
        event_count = 0
        function_response_text = ""
        async for event in events_async:
            event_count += 1
            if event.content and event.content.parts:
                for idx, part in enumerate(event.content.parts):
                    if hasattr(part, 'text') and part.text:
                        result_text += part.text
                    elif hasattr(part, 'function_response') and part.function_response:
                        response_data = getattr(part.function_response, 'response', None) \
                            or getattr(part.function_response, 'content', None)
                        # Skip tool-error envelopes — the agent will retry; we don't
                        # want "missing mandatory parameter" to leak to the user.
                        if isinstance(response_data, dict) and "error" in response_data:
                            continue
                        if response_data is not None:
                            function_response_text = str(response_data)

        if not result_text and function_response_text:
            result_text = function_response_text

        if not result_text:
            result_text = "No information found."
            logger.warning("orders_a2a_empty_result", session_id=session_id)

        logger.info("orders_a2a_complete", session_id=session_id, events=event_count, chars=len(result_text))

        return {
            "id": request.id,
            "jsonrpc": "2.0",
            "result": {
                "kind": "message",
                "messageId": str(uuid.uuid4()),
                "role": "agent",
                "parts": [{"kind": "text", "text": result_text}]
            }
        }
    except Exception as e:
        logger.error("orders_agent_error", error=str(e), exc_info=True)
        return {
            "id": request.id,
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

@router.get("/.well-known/agent-card.json")
async def get_agent_card():
    """
    A2A Protocol: Agent Card endpoint
    """
    card_path = os.path.join(os.path.dirname(__file__), "agent.json")
    with open(card_path, "r") as f:
        return json.load(f)

@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "agent": "order_specialist"}
