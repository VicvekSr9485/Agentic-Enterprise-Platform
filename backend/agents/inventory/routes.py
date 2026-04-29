import json
import os
import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agents.inventory.agent import create_inventory_agent
from shared.logging_utils import get_logger, safe_preview

logger = get_logger("agents.inventory.routes")
router = APIRouter()

stateless_session_service = InMemorySessionService()
_inventory_agent = None


def _get_inventory_agent():
    """Lazy-init inventory agent so import-time DB checks don't crash boot."""
    global _inventory_agent
    if _inventory_agent is None:
        _inventory_agent = create_inventory_agent()
    return _inventory_agent

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
        logger.warning("inventory_a2a_parse_failed", error=str(e))
        raise HTTPException(status_code=422, detail=str(e))

    try:
        session_id = str(uuid.uuid4())
        logger.info("inventory_a2a_start", session_id=session_id)

        await stateless_session_service.create_session(
            app_name="agents",
            user_id="default_user",
            session_id=session_id
        )

        runner = Runner(
            agent=_get_inventory_agent(),
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
        async for event in events_async:
            if event.content:
                parts = event.content.parts or []
                for part in parts:
                    if part.text:
                        result_text += part.text

                    if hasattr(part, 'function_response') and part.function_response:
                        try:
                            response_data = part.function_response.response
                            if response_data:
                                if isinstance(response_data, dict) and 'result' in response_data:
                                    result_text += str(response_data['result'])
                                else:
                                    result_text += str(response_data)
                        except Exception as e:
                            logger.warning("inventory_function_response_parse_error", error=str(e))

        if not result_text:
            logger.warning("inventory_a2a_empty_result", session_id=session_id)

        response = {
            "id": request.id,
            "jsonrpc": "2.0",
            "result": {
                "kind": "message",
                "messageId": str(uuid.uuid4()),
                "role": "agent",
                "parts": [{"kind": "text", "text": result_text}]
            }
        }
        logger.info("inventory_a2a_complete", session_id=session_id, chars=len(result_text))
        return response
    except Exception as e:
        logger.error("inventory_agent_error", error=str(e), exc_info=True)
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
    """A2A Protocol: Agent Card endpoint"""
    card_path = os.path.join(os.path.dirname(__file__), "agent.json")
    with open(card_path, "r") as f:
        return json.load(f)