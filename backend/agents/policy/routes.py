import json
import os
import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agents.policy.agent import create_policy_agent
from shared.logging_utils import get_logger

logger = get_logger("agents.policy.routes")
router = APIRouter()

stateless_session_service = InMemorySessionService()
_policy_agent = None


def _get_policy_agent():
    global _policy_agent
    if _policy_agent is None:
        _policy_agent = create_policy_agent()
    return _policy_agent


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
async def handle_task(request: A2ARequest):
    message = request.params.message
    try:
        session_id = str(uuid.uuid4())
        logger.info("policy_a2a_start", session_id=session_id)

        await stateless_session_service.create_session(
            app_name="agents",
            user_id="default_user",
            session_id=session_id
        )

        runner = Runner(
            agent=_get_policy_agent(),
            app_name="agents",
            session_service=stateless_session_service
        )

        text_parts = []
        for part in message.parts:
            if part.kind == "text" and part.text:
                text_parts.append(types.Part(text=part.text))

        message_content = types.Content(role=message.role, parts=text_parts)

        events_async = runner.run_async(
            user_id="default_user",
            session_id=session_id,
            new_message=message_content
        )

        result_text = ""
        async for event in events_async:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        result_text += part.text

        logger.info("policy_a2a_complete", session_id=session_id, chars=len(result_text))

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
        logger.error("policy_agent_error", error=str(e), exc_info=True)
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
