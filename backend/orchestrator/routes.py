import json
import os
from fastapi import APIRouter, HTTPException
import uuid
import asyncio
import httpx
from pydantic import BaseModel
from google.adk.runners import Runner
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

router = APIRouter()

session_service = get_session_service()
memory_service = get_memory_service()
orchestrator_agent = create_orchestrator()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
intent_classifier_model = genai.GenerativeModel("gemini-2.5-flash-lite")

class ChatRequest(BaseModel):
    prompt: str
    session_id: str
    context: dict = {}

class ChatResponse(BaseModel):
    response: str
    session_id: str
    trace_id: str
    pending_approval: bool = False
    approval_type: str | None = None

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        user_input_lower = request.prompt.lower().strip()
        pending_approval = hitl_manager.get_pending_approval(request.session_id)
        
        if pending_approval and user_input_lower in ["yes", "approve", "send", "confirm"]:
            approval = hitl_manager.approve(request.session_id)
            
            if approval.action_type == "email_send":
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
                        trace_id="approval_confirmed",
                        pending_approval=False
                    )
            
            return ChatResponse(
                response=f"Approved! {approval.action_type} has been executed.\n\n{approval.draft_content}",
                session_id=request.session_id,
                trace_id="approval_confirmed",
                pending_approval=False
            )
        
        elif pending_approval and user_input_lower in ["no", "reject", "cancel", "deny"]:
            approval = hitl_manager.reject(request.session_id)
            return ChatResponse(
                response=f"Cancelled. The {approval.action_type} was not executed.",
                session_id=request.session_id,
                trace_id="approval_rejected",
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
                trace_id="conversational_response",
                pending_approval=False
            )
        
        print(f"[ORCHESTRATOR] Classifying intent for: {request.prompt[:100]}...")
        classification_prompt = INTENT_CLASSIFICATION_PROMPT.format(user_prompt=request.prompt)
        
        intent_classification = None
        try:
            llm_response = await asyncio.wait_for(
                asyncio.to_thread(intent_classifier_model.generate_content, classification_prompt),
                timeout=10.0
            )
            intent_classification = parse_intent_from_llm_response(llm_response.text)
            
            if intent_classification:
                print(f"[ORCHESTRATOR] Intent classification:")
                print(f"  - Summary: {intent_classification.user_intent_summary}")
                print(f"  - Agents needed: {[a.agent_name for a in intent_classification.agents_needed]}")
                print(f"  - Coordination required: {intent_classification.requires_coordination}")
                for agent in intent_classification.agents_needed:
                    print(f"  - {agent.agent_name}: {agent.targeted_prompt[:100]}... (Reason: {agent.reason})")
            else:
                print(f"[ORCHESTRATOR] Intent classification failed, falling back to LLM orchestrator")
                intent_classification = None
        except asyncio.TimeoutError:
            print(f"[ORCHESTRATOR] Intent classification timeout (10s), falling back to LLM orchestrator")
            intent_classification = None
        except Exception as e:
            print(f"[ORCHESTRATOR] Intent classification error: {e}, falling back to LLM orchestrator")
            intent_classification = None
        
        session = None
        try:
            session = await session_service.get_session(
                app_name="agents",
                user_id="default_user",
                session_id=request.session_id
            )
            print(f"Found existing session: {request.session_id}")
            print(f"  Session details: app={session.app_name}, user={session.user_id}, id={session.id}")
            
            if hasattr(memory_service, 'get_memory'):
                try:
                    memories = await memory_service.get_memory(
                        app_name="agents",
                        user_id="default_user",
                        session_id=request.session_id
                    )
                    if memories:
                        print(f"  Found {len(memories)} memory entries for context")
                except Exception as mem_err:
                    print(f"  Memory retrieval skipped: {mem_err}")
        except Exception as e:
            print(f"Session not found, creating: {request.session_id} (error: {e})")
            session = await session_service.create_session(
                app_name="agents",
                user_id="default_user",
                session_id=request.session_id
            )
            print(f"Session created: {session.id}")
            print(f"  Session details: app={session.app_name}, user={session.user_id}, id={session.id}")
        
        print(f"Session service DB URL: {session_service._db_url if hasattr(session_service, '_db_url') else 'unknown'}")
        
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
            if not text:
                return text
            lower = text.lower()
            patterns = [
                "i cannot provide information",
                "i do not have access",
                "outside of my",
                "outside my",
                "i cannot check",
                "i cannot draft",
                "i cannot send",
                "limited to my",
                "please contact",
                "please check",
                "would you like me to proceed",
                "however, i",
                "nor can i",
            ]
            lines = []
            for ln in text.splitlines():
                ln_lower = ln.lower()
                if any(p in ln_lower for p in patterns):
                    continue
                if ln_lower.strip().endswith("?") and any(k in ln_lower for k in ["would you", "should i", "proceed"]):
                    continue
                lines.append(ln)
            result = "\n".join([ln for ln in lines if ln.strip()])
            cleaned = result.strip()
            
            # Strip wrapping quotes if present
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1]
            if cleaned.startswith("'") and cleaned.endswith("'"):
                cleaned = cleaned[1:-1]
            
            return cleaned

        async def call_a2a(url: str, prompt: str, retry_count: int = 2) -> str:
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
            
            for attempt in range(retry_count + 1):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        r = await client.post(url, json=payload)
                        r.raise_for_status()
                        data = r.json()
                        try:
                            parts = data.get("result", {}).get("parts", [])
                            texts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
                            return _sanitize("\n".join(t for t in texts if t))
                        except Exception:
                            return _sanitize(json.dumps(data))
                except Exception as e:
                    if attempt < retry_count:
                        print(f"[ORCHESTRATOR] Retry {attempt + 1}/{retry_count} for {url}: {e}")
                        await asyncio.sleep(1)
                    else:
                        raise

        used_intelligent_routing = False
        response_text = ""
        event_count = 0

        if intent_classification and intent_classification.agents_needed:
            used_intelligent_routing = True
            print(f"[ORCHESTRATOR] Using intelligent routing with {len(intent_classification.agents_needed)} agent(s)")
            print(f"[ORCHESTRATOR] Coordination mode: {'SEQUENTIAL' if intent_classification.requires_coordination else 'PARALLEL'}")
            
            data_blocks = []
            notification_task = None
            
            if not intent_classification.requires_coordination and len(intent_classification.agents_needed) > 1:
                non_notification_tasks = [a for a in intent_classification.agents_needed if a.agent_name not in ["notification", "notification_specialist"]]
                
                if len(non_notification_tasks) > 1:
                    print(f"[ORCHESTRATOR] Executing {len(non_notification_tasks)} data agents in PARALLEL")
                    
                    tasks = []
                    for agent_intent in non_notification_tasks:
                        if agent_intent.agent_name in a2a_endpoints:
                            tasks.append(call_a2a(a2a_endpoints[agent_intent.agent_name], agent_intent.targeted_prompt))
                    
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for i, result in enumerate(results):
                            agent_name = non_notification_tasks[i].agent_name
                            if isinstance(result, Exception):
                                print(f"[ORCHESTRATOR] Parallel task {i} failed: {result}")
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
                else:
                    print(f"[ORCHESTRATOR] Only 1 data agent, using standard sequential flow")
            
            if not data_blocks:
                print(f"[ORCHESTRATOR] Using SEQUENTIAL execution")
                
                # First, call all data agents (non-notification)
                for agent_intent in intent_classification.agents_needed:
                    agent_name = agent_intent.agent_name
                    if agent_name in ["notification", "notification_specialist"]:
                        notification_task = agent_intent
                        print(f"[ORCHESTRATOR] Notification task queued: {agent_intent.reason}")
                        continue
                    
                    if agent_name in a2a_endpoints:
                        targeted_prompt = agent_intent.targeted_prompt
                        reason = agent_intent.reason
                        print(f"[ORCHESTRATOR] Calling {agent_name}: {targeted_prompt[:80]}...")
                        print(f"  Reason: {reason}")
                        start_time = time.time()
                        try:
                            result = await call_a2a(a2a_endpoints[agent_name], targeted_prompt)
                            latency_ms = (time.time() - start_time) * 1000
                            
                            if result:
                                print(f"[ORCHESTRATOR] Got {agent_name} response ({len(result)} chars) in {latency_ms:.0f}ms")
                                data_blocks.append({
                                    "agent": agent_name,
                                    "content": result.strip(),
                                    "reason": reason,
                                    "timestamp": __import__('datetime').datetime.utcnow().isoformat()
                                })
                                agent_metrics.record_agent_call(agent_name, request.session_id, True, latency_ms)
                            else:
                                print(f"[ORCHESTRATOR] {agent_name} returned empty response")
                                agent_metrics.record_agent_call(agent_name, request.session_id, False, latency_ms, error="Empty response")
                        except Exception as e:
                            latency_ms = (time.time() - start_time) * 1000
                            print(f"[ORCHESTRATOR] Error calling {agent_name}: {e}")
                            data_blocks.append({
                                "agent": agent_name,
                                "content": f"Error: {str(e)}",
                                "reason": reason,
                                "error": True
                            })
                            agent_metrics.record_agent_call(agent_name, request.session_id, False, latency_ms, error=str(e))
            else:
                # data_blocks already populated from parallel execution
                pass
            
            print(f"[ORCHESTRATOR] Collected {len(data_blocks)} data blocks")
            
            if notification_task:
                if data_blocks:
                    context_parts = []
                    for block in data_blocks:
                        if isinstance(block, dict):
                            agent_label = block.get('agent', 'unknown').replace('_', ' ').title()
                            context_parts.append(f"[{agent_label}:]\n{block.get('content', '')}")
                        else:
                            context_parts.append(str(block))
                    
                    enriched_prompt = f"{notification_task.targeted_prompt}\n\n[Context from other agents:]\n" + "\n\n".join(context_parts)
                    print(f"[ORCHESTRATOR] Calling notification with enriched context ({len(enriched_prompt)} chars)")
                    print(f"[ORCHESTRATOR] Enriched prompt preview: {enriched_prompt[:500]}...")
                else:
                    enriched_prompt = notification_task.targeted_prompt
                    print(f"[ORCHESTRATOR] Calling notification with original prompt (no data context)")
                
                try:
                    notif_result = await call_a2a(a2a_endpoints["notification"], enriched_prompt)
                    if notif_result:
                        response_text = notif_result.strip()
                    else:
                        response_text = "\n\n".join(data_blocks).strip() if data_blocks else "No response from notification agent."
                except Exception as e:
                    print(f"[ORCHESTRATOR] Error calling notification: {e}")
                    response_text = "\n\n".join(data_blocks).strip() if data_blocks else f"Error: {e}"
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

            print(f"Starting run_async for session {request.session_id}")
            events_async = runner.run_async(
                user_id="default_user",
                session_id=request.session_id,
                new_message=message_content
            )
            response_text = ""
            event_count = 0
            async for event in events_async:
                event_count += 1
                print(f"Event {event_count}: author={event.author}")
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text

            print(f"Completed with {event_count} events, response length: {len(response_text)}")
        
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
                    metadata={"timestamp": event_count}
                )
        
        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            trace_id="success",
            pending_approval=pending_approval,
            approval_type=approval_type
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat_endpoint: {e}")
        import traceback
        traceback.print_exc()
        
        error_context = {
            "session_id": request.session_id if hasattr(request, 'session_id') else None,
            "prompt_length": len(request.prompt) if hasattr(request, 'prompt') else 0,
            "error_type": type(e).__name__
        }
        print(f"Error context: {error_context}")
        
        raise HTTPException(status_code=500, detail=str(e))

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