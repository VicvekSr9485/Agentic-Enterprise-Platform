import json
import os
from fastapi import APIRouter, HTTPException, Request
import uuid
import asyncio
import httpx
from pydantic import BaseModel, Field
from google.adk.runners import Runner
from google.adk.events import Event
from google.genai import types
import google.generativeai as genai
from orchestrator.agent import create_orchestrator, get_memory_service, get_session_service
from orchestrator.hitl_manager import hitl_manager
from orchestrator.intent_classifier import (
    INTENT_CLASSIFICATION_PROMPT,
    parse_intent_from_llm_response
)
from agents.notification.email_draft_tool import send_email
import re
import time

from shared.agent_metrics import agent_metrics
from shared.retry_handler import get_retry_handler, async_retry_with_backoff, RetryConfig
from shared.logging_utils import get_logger, safe_preview
from shared.observability import trace_span

logger = get_logger("orchestrator.routes")

router = APIRouter()

session_service = get_session_service()
memory_service = get_memory_service()
orchestrator_agent = create_orchestrator()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
intent_classifier_model = genai.GenerativeModel("gemini-2.5-flash-lite")

MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "8000"))
MAX_SESSION_ID_CHARS = 128


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=MAX_PROMPT_CHARS)
    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_CHARS)
    context: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str
    session_id: str
    trace_id: str
    pending_approval: bool = False
    approval_type: str | None = None

@router.post("/chat")
async def chat_endpoint(request: ChatRequest, http_request: Request):
    # user_id and request_id are populated by auth + request-id middleware.
    user_id = getattr(http_request.state, "user_id", "default_user")
    request_id = getattr(http_request.state, "request_id", None)
    log = logger.bind(session_id=request.session_id, user_id=user_id, request_id=request_id)

    try:

        user_input_lower = request.prompt.lower().strip()
        pending_approval = hitl_manager.get_pending_approval(request.session_id, user_id=user_id)  # noqa: E501  user_id used after Batch B HITL update
        
        if pending_approval and user_input_lower in ["yes", "approve", "send", "confirm"]:
            approval = hitl_manager.approve(request.session_id, user_id=user_id)

            if approval and approval.action_type == "email_send":
                draft = approval.draft_content

                to_match = re.search(r'To:\s*(.+)', draft)
                subject_match = re.search(r'Subject:\s*(.+)', draft)

                if to_match and subject_match:
                    to_email = to_match.group(1).strip()
                    subject = subject_match.group(1).strip()

                    body_start = draft.find(subject) + len(subject)
                    body_end = draft.find('---')
                    if body_end == -1:
                        body_end = len(draft)
                    body = draft[body_start:body_end].strip()

                    send_result = send_email(to_email, subject, body)

                    return ChatResponse(
                        response=f"Approved! Email sent.\n\n{send_result}\n\n{approval.draft_content}",
                        session_id=request.session_id,
                        trace_id=request_id or "approval_confirmed",
                        pending_approval=False
                    )

            return ChatResponse(
                response=(
                    f"Approved! {approval.action_type} has been executed.\n\n{approval.draft_content}"
                    if approval
                    else "No pending approval was found for this session."
                ),
                session_id=request.session_id,
                trace_id=request_id or "approval_confirmed",
                pending_approval=False
            )

        elif pending_approval and user_input_lower in ["no", "reject", "cancel", "deny"]:
            approval = hitl_manager.reject(request.session_id, user_id=user_id)
            return ChatResponse(
                response=(
                    f"Cancelled. The {approval.action_type} was not executed."
                    if approval
                    else "No pending approval was found for this session."
                ),
                session_id=request.session_id,
                trace_id=request_id or "approval_rejected",
                pending_approval=False
            )
        
        # Handle conversational responses without pending approval
        if not pending_approval and user_input_lower in ["yes", "no", "ok", "okay", "thanks", "thank you", "nope", "yep", "sure", "nah"]:
            conversational_responses = {
                "yes": "Great! How can I help you today?",
                "no": "No problem. Is there anything else I can help you with?",
                "ok": "Understood. What would you like to do next?",
                "okay": "Understood. What would you like to do next?",
                "thanks": "You're welcome! Let me know if you need anything else.",
                "thank you": "You're welcome! Let me know if you need anything else.",
                "nope": "Alright. Feel free to ask if you need anything.",
                "yep": "Great! What can I do for you?",
                "sure": "Perfect! How can I assist you?",
                "nah": "No worries. Let me know if you need help with something."
            }
            return ChatResponse(
                response=conversational_responses.get(user_input_lower, "I'm here to help. What would you like to do?"),
                session_id=request.session_id,
                trace_id=request_id or "conversational_response",
                pending_approval=False
            )
        
        logger.info("intent_classifying", prompt_preview=safe_preview(request.prompt, 80))
        classification_prompt = INTENT_CLASSIFICATION_PROMPT.format(user_prompt=request.prompt)
        
        intent_classification = None
        
        @async_retry_with_backoff(
            config=RetryConfig(max_retries=2, initial_delay=1.0, max_delay=10.0),
            log_func=lambda msg: print(f"[INTENT CLASSIFIER RETRY] {msg}")
        )
        async def classify_intent():
            return await asyncio.to_thread(
                intent_classifier_model.generate_content,
                classification_prompt
            )
        
        try:
            llm_response = await asyncio.wait_for(classify_intent(), timeout=15.0)
            intent_classification = parse_intent_from_llm_response(llm_response.text)

            if intent_classification:
                logger.info(
                    "intent_classified",
                    summary=intent_classification.user_intent_summary,
                    agents=[a.agent_name for a in intent_classification.agents_needed],
                    requires_coordination=intent_classification.requires_coordination,
                )
            else:
                logger.warning("intent_classification_failed_fallback")
                intent_classification = None
        except asyncio.TimeoutError:
            logger.warning("intent_classification_timeout", timeout_seconds=15.0)
            intent_classification = None
        except Exception as e:
            logger.warning("intent_classification_error", error=str(e))
            intent_classification = None
        
        session = None
        try:
            session = await session_service.get_session(
                app_name="agents",
                user_id=user_id,
                session_id=request.session_id
            )
            if session is None:
                raise ValueError("Session returned None")
            logger.info("session_loaded", session_id=session.id, user_id=user_id)
        except Exception:
            logger.info("session_creating", session_id=request.session_id, user_id=user_id)
            session = await session_service.create_session(
                app_name="agents",
                user_id=user_id,
                session_id=request.session_id
            )
            logger.info("session_created", session_id=session.id, user_id=user_id)
        
        async def get_conversation_context() -> str:
            """
            Retrieves recent conversation history from the session and formats it
            for inclusion in sub-agent prompts. This enables context-aware follow-ups.
            """
            try:
                if not session.events or len(session.events) == 0:
                    return ""
                
                recent_events = session.events[-8:] if len(session.events) > 8 else session.events
                
                context_lines = []
                error_patterns = [
                    "no data available",
                    "i am sorry",
                    "encountered an error",
                    "cannot find",
                    "error while",
                    "failed to"
                ]
                
                for event in recent_events:
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                role = "User" if event.author == "user" else "Assistant"
                                text = part.text
                                
                                text_lower = text.lower()
                                is_error = any(pattern in text_lower for pattern in error_patterns)
                                is_empty = len(text.strip()) < 10
                                
                                if not is_error and not is_empty:
                                    text = text[:1500] + "..." if len(text) > 1500 else text
                                    context_lines.append(f"{role}: {text}")
                
                if context_lines:
                    return "\n\n[Previous conversation context:]\n" + "\n".join(context_lines) + "\n[End of context]\n\n"
                return ""
                
            except Exception as e:
                logger.warning("conversation_context_error", error=str(e))
                return ""

        conversation_context = await get_conversation_context()
        if conversation_context:
            log.debug("conversation_context_retrieved", chars=len(conversation_context))
        
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        a2a_endpoints = {
            "inventory": f"{base_url}/inventory/a2a/interact",
            "inventory_specialist": f"{base_url}/inventory/a2a/interact",
            "policy": f"{base_url}/policy/a2a/interact",
            "policy_expert": f"{base_url}/policy/a2a/interact",
            "analytics": f"{base_url}/analytics/a2a/interact",
            "analytics_specialist": f"{base_url}/analytics/a2a/interact",
            "orders": f"{base_url}/orders/a2a/interact",
            "order_specialist": f"{base_url}/orders/a2a/interact",
            "notification": f"{base_url}/notification/a2a/interact",
            "notification_specialist": f"{base_url}/notification/a2a/interact",
        }

        def _sanitize(text: str) -> str:
            """Light cleanup of sub-agent output.

            The previous version filtered any line containing phrases like
            "please contact" or "would you like me to proceed", which struck
            out legitimate replies. We now only strip wrapping quotes — trust
            the agent to produce final text.
            """
            if not text:
                return text
            cleaned = text.strip()
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1]
            if cleaned.startswith("'") and cleaned.endswith("'"):
                cleaned = cleaned[1:-1]
            return cleaned

        retry_config = RetryConfig(
            max_retries=3,
            initial_delay=2.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True
        )
        
        @async_retry_with_backoff(
            config=retry_config,
            log_func=lambda msg: print(f"[ORCHESTRATOR RETRY] {msg}")
        )
        async def call_a2a(url: str, prompt: str) -> str:
            payload = {
                "id": str(uuid.uuid4()),
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "configuration": {"acceptedOutputModes": [], "blocking": True},
                    "message": {
                        "kind": "message",
                        "messageId": str(uuid.uuid4()),
                        "role": "user",
                        "parts": [{"kind": "text", "text": prompt}],
                    },
                },
            }

            with trace_span("a2a.call", url=url, prompt_chars=len(prompt)):
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(url, json=payload)
                    r.raise_for_status()
                    data = r.json()
                
                if "error" in data:
                    error_msg = data["error"].get("message", "Unknown error")
                    if "429" in error_msg or "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
                        raise Exception(f"Rate limit error: {error_msg}")
                    logger.warning("a2a_agent_error", error=error_msg)
                    return f"Error from agent: {error_msg}"

                try:
                    parts = data.get("result", {}).get("parts", [])
                    texts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
                    return _sanitize("\n".join(t for t in texts if t))
                except Exception as e:
                    logger.warning("a2a_response_extract_error", error=str(e))
                    return _sanitize(json.dumps(data))

        used_intelligent_routing = False
        response_text = ""
        event_count = 0

        if intent_classification and intent_classification.agents_needed:
            used_intelligent_routing = True
            log.info(
                "intelligent_routing",
                agent_count=len(intent_classification.agents_needed),
                coordination="sequential" if intent_classification.requires_coordination else "parallel",
            )

            data_blocks = []
            notification_task = None

            if not intent_classification.requires_coordination and len(intent_classification.agents_needed) > 1:
                non_notification_tasks = [a for a in intent_classification.agents_needed if a.agent_name not in ["notification", "notification_specialist"]]

                if len(non_notification_tasks) > 1:
                    log.info("parallel_data_agents", count=len(non_notification_tasks))

                    tasks = []
                    for agent_intent in non_notification_tasks:
                        if agent_intent.agent_name in a2a_endpoints:
                            enriched_prompt = agent_intent.targeted_prompt

                            if conversation_context:
                                enriched_prompt = conversation_context + enriched_prompt
                            tasks.append(call_a2a(a2a_endpoints[agent_intent.agent_name], enriched_prompt))

                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for i, result in enumerate(results):
                            agent_name = non_notification_tasks[i].agent_name
                            if isinstance(result, Exception):
                                log.warning("parallel_task_failed", index=i, error=str(result))
                                data_blocks.append({
                                    "agent": agent_name,
                                    "content": f"Error: {result}",
                                    "reason": non_notification_tasks[i].reason,
                                    "error": True
                                })
                            elif result:
                                data_blocks.append({
                                    "agent": agent_name,
                                    "content": result.strip(),
                                    "reason": non_notification_tasks[i].reason,
                                    "timestamp": __import__('datetime').datetime.utcnow().isoformat()
                                })
                    
                    notification_task = next((a for a in intent_classification.agents_needed if a.agent_name in ["notification", "notification_specialist"]), None)

            if not data_blocks:
                # First, call all data agents (non-notification)
                for agent_intent in intent_classification.agents_needed:
                    agent_name = agent_intent.agent_name
                    if agent_name in ["notification", "notification_specialist"]:
                        notification_task = agent_intent
                        log.info("notification_queued", reason=agent_intent.reason)
                        continue

                    if agent_name in a2a_endpoints:
                        # Always use targeted_prompt from intent classifier — it scopes to one agent.
                        targeted_prompt = agent_intent.targeted_prompt
                        if conversation_context:
                            targeted_prompt = conversation_context + targeted_prompt
                        reason = agent_intent.reason
                        log.info(
                            "a2a_call_start",
                            agent=agent_name,
                            prompt_preview=safe_preview(targeted_prompt, 80),
                            reason=reason,
                        )
                        start_time = time.time()
                        try:
                            result = await call_a2a(a2a_endpoints[agent_name], targeted_prompt)
                            latency_ms = (time.time() - start_time) * 1000

                            if result:
                                log.info("a2a_call_ok", agent=agent_name, chars=len(result), latency_ms=int(latency_ms))
                                data_blocks.append({
                                    "agent": agent_name,
                                    "content": result.strip(),
                                    "reason": reason,
                                    "timestamp": __import__('datetime').datetime.utcnow().isoformat()
                                })
                                agent_metrics.record_agent_call(agent_name, request.session_id, True, latency_ms)
                            else:
                                log.warning("a2a_call_empty", agent=agent_name, latency_ms=int(latency_ms))
                                agent_metrics.record_agent_call(agent_name, request.session_id, False, latency_ms, error="Empty response")
                        except Exception as e:
                            latency_ms = (time.time() - start_time) * 1000
                            log.warning("a2a_call_error", agent=agent_name, error=str(e), latency_ms=int(latency_ms))
                            data_blocks.append({
                                "agent": agent_name,
                                "content": f"Error: {str(e)}",
                                "reason": reason,
                                "error": True
                            })
                            agent_metrics.record_agent_call(agent_name, request.session_id, False, latency_ms, error=str(e))
            log.info("data_blocks_collected", count=len(data_blocks))
            
            if notification_task:
                # Start with conversation context if it exists
                base_prompt = notification_task.targeted_prompt
                
                # When conversation context exists, use original user query
                if conversation_context:
                    base_prompt = request.prompt
                
                if data_blocks:
                    context_parts = []
                    for block in data_blocks:
                        if isinstance(block, dict):
                            agent_label = block.get('agent', 'unknown').replace('_', ' ').title()
                            context_parts.append(f"[{agent_label}:]\n{block.get('content', '')}")
                        else:
                            context_parts.append(str(block))
                    
                    enriched_prompt = f"{base_prompt}\n\n[Context from other agents:]\n" + "\n\n".join(context_parts)

                    if conversation_context:
                        enriched_prompt = conversation_context + enriched_prompt

                    log.info("notification_call", chars=len(enriched_prompt))
                else:
                    enriched_prompt = base_prompt

                    if conversation_context:
                        enriched_prompt = conversation_context + enriched_prompt

                    log.info("notification_call", chars=len(enriched_prompt))

                try:
                    notif_result = await call_a2a(a2a_endpoints["notification"], enriched_prompt)
                    if notif_result:
                        response_text = notif_result.strip()
                    else:
                        response_parts = [block.get('content', '') if isinstance(block, dict) else str(block) for block in data_blocks]
                        response_text = "\n\n".join(response_parts).strip() if data_blocks else "No response from notification agent."
                except Exception as e:
                    log.warning("notification_call_error", error=str(e))
                    # Extract content from data_blocks dictionaries
                    response_parts = [block.get('content', '') if isinstance(block, dict) else str(block) for block in data_blocks]
                    response_text = "\n\n".join(response_parts).strip() if data_blocks else f"Error: {e}"
            else:
                if data_blocks:
                    response_parts = []
                    for block in data_blocks:
                        if isinstance(block, dict):
                            response_parts.append(block.get('content', ''))
                        else:
                            response_parts.append(str(block))
                    response_text = "\n\n".join(response_parts).strip()
                else:
                    response_text = "No data available."
            
            # Store conversation events in session for intelligent routing path
            # This ensures memory persistence even when bypassing Runner
            try:
                # Add user message to session
                user_event = Event(
                    author="user",
                    content=types.Content(
                        role="user",
                        parts=[types.Part(text=request.prompt)]
                    )
                )
                await session_service.append_event(
                    session=session,
                    event=user_event
                )

                agent_event = Event(
                    author="orchestrator",
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text=response_text)]
                    )
                )
                await session_service.append_event(
                    session=session,
                    event=agent_event
                )

                await memory_service.add_session_to_memory(session)
                log.debug("session_persisted", session_id=session.id)

            except Exception as e:
                log.warning("session_persist_error", error=str(e))

        if not used_intelligent_routing:
            runner = Runner(
                agent=orchestrator_agent,
                app_name="agents",
                session_service=session_service,
                memory_service=memory_service
            )

            message_content = types.Content(
                role="user",
                parts=[types.Part(text=request.prompt)]
            )

            log.info("runner_starting")
            events_async = runner.run_async(
                user_id=user_id,
                session_id=request.session_id,
                new_message=message_content
            )
            response_text = ""
            event_count = 0
            async for event in events_async:
                event_count += 1
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text

            log.info("runner_complete", events=event_count, response_chars=len(response_text))
        
        pending_approval = False
        approval_type = None
        response_lower = response_text.lower()
        
        # More precise approval detection: must have explicit approval request phrases
        is_approval_request = (
            ("do you approve" in response_lower or 
             "please reply 'yes' to approve" in response_lower or
             "approve sending" in response_lower or
             "reply 'yes' to approve" in response_lower or
             "approve or reject" in response_lower) and
            ("yes" in response_lower or "no" in response_lower)
        )
        
        has_email_structure = (
            "to:" in response_lower and 
            ("subject:" in response_lower or "body:" in response_lower)
        )
        
        if is_approval_request and has_email_structure:
            pending_approval = True
            
            if has_email_structure or "email" in response_lower:
                approval_type = "email_send"
                
                hitl_manager.create_approval(
                    session_id=request.session_id,
                    agent_name="notification_specialist",
                    action_type="email_send",
                    draft_content=response_text,
                    metadata={"event_count": event_count},
                    user_id=user_id,
                )

        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            trace_id=request_id or "success",
            pending_approval=pending_approval,
            approval_type=approval_type
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "chat_endpoint_error",
            error=str(e),
            error_type=type(e).__name__,
            session_id=getattr(request, "session_id", None),
            prompt_length=len(request.prompt) if hasattr(request, "prompt") else 0,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal error processing chat request")

@router.get("/.well-known/agent-card.json")
async def get_agent_card():
    card_path = os.path.join(os.path.dirname(__file__), "agent.json")
    with open(card_path, "r") as f:
        return json.load(f)

@router.get("/metrics")
async def get_metrics():
    """
    Get agent performance metrics for monitoring and evaluation.
    Returns success rates, latency, and error patterns per agent.
    """
    return {
        "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        "agents": agent_metrics.get_all_stats()
    }