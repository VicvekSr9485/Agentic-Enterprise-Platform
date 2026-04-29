import os
import json
import uuid
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agents.notification.agent import create_notification_agent
from agents.notification.email_draft_tool import compose_email_with_html, recipient_allowed
from shared.logging_utils import get_logger, safe_preview

logger = get_logger("agents.notification.routes")
router = APIRouter()

stateless_session_service = InMemorySessionService()
_notification_agent = None


def _get_notification_agent():
    global _notification_agent
    if _notification_agent is None:
        _notification_agent = create_notification_agent()
    return _notification_agent


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
        logger.info("notification_a2a_start", session_id=session_id)

        full_prompt = ""
        for part in message.parts:
            if part.kind == "text" and part.text:
                full_prompt += part.text + "\n"

        logger.debug("notification_prompt", chars=len(full_prompt), preview=safe_preview(full_prompt, 120))

        context_match = re.search(r'\[Context from other agents:\]\s*(.*)', full_prompt, re.DOTALL | re.IGNORECASE)

        if context_match:
            context_data = context_match.group(1).strip()

            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, full_prompt)

            if email_match:
                recipient = email_match.group(0)

                if not recipient_allowed(recipient):
                    logger.warning("notification_recipient_blocked", recipient=recipient)
                    return {
                        "id": request.id,
                        "jsonrpc": "2.0",
                        "result": {
                            "kind": "message",
                            "messageId": str(uuid.uuid4()),
                            "role": "agent",
                            "parts": [{
                                "kind": "text",
                                "text": (
                                    f"Recipient '{recipient}' is not on the configured allowlist. "
                                    "Set EMAIL_ALLOWED_DOMAINS or EMAIL_ALLOWED_RECIPIENTS to permit it."
                                ),
                            }],
                        },
                    }

                purpose_keywords = {
                    'policy': ['policy', 'policies', 'return', 'refund', 'warranty', 'rules', 'guidelines', 'terms', 'conditions'],
                    'inventory': ['inventory', 'stock', 'products', 'items', 'supplies', 'pump', 'valve'],
                    'summary': ['summary', 'report', 'overview', 'update']
                }

                purpose = "status update"
                combined = (full_prompt + " " + context_data).lower()
                for category, keywords in purpose_keywords.items():
                    if any(kw in combined for kw in keywords):
                        purpose = category
                        break

                try:
                    draft, _html = compose_email_with_html(recipient, purpose, context_data)
                    logger.info("notification_draft_composed", session_id=session_id, chars=len(draft))

                    return {
                        "id": request.id,
                        "jsonrpc": "2.0",
                        "result": {
                            "kind": "message",
                            "messageId": str(uuid.uuid4()),
                            "role": "agent",
                            "parts": [{"kind": "text", "text": draft}]
                        }
                    }
                except Exception as compose_error:
                    logger.warning("notification_compose_error", error=str(compose_error))

        await stateless_session_service.create_session(
            app_name="agents",
            user_id="default_user",
            session_id=session_id
        )

        runner = Runner(
            agent=_get_notification_agent(),
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
        function_results = []
        event_count = 0
        async for event in events_async:
            event_count += 1
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        result_text += part.text
                    elif hasattr(part, 'function_response') and part.function_response:
                        response_data = getattr(part.function_response, 'response', None)
                        # Skip tool-error envelopes; the agent will retry.
                        if isinstance(response_data, dict) and "error" in response_data:
                            continue
                        if response_data is not None:
                            function_results.append(str(response_data))

        if function_results and not result_text:
            result_text = "\n\n".join(function_results)

        logger.info("notification_a2a_complete", session_id=session_id, events=event_count, chars=len(result_text))

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
        logger.error("notification_agent_error", error=str(e), exc_info=True)
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
    card_path = os.path.join(os.path.dirname(__file__), "agent.json")
    with open(card_path, "r") as f:
        return json.load(f)
