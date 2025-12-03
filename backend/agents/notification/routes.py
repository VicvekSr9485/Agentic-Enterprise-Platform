import os
import json
import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agents.notification.agent import create_notification_agent
from agents.notification.email_draft_tool import compose_email_from_context
import re

router = APIRouter()

stateless_session_service = InMemorySessionService()
notification_agent = create_notification_agent()

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
        print(f"[NOTIFICATION A2A] Processing with temporary session: {session_id}")
        
        full_prompt = ""
        for part in message.parts:
            if part.kind == "text" and part.text:
                full_prompt += part.text + "\n"
        
        print(f"[NOTIFICATION A2A] Received prompt ({len(full_prompt)} chars): {full_prompt[:200]}...")
        
        context_match = re.search(r'\[Context from other agents:\]\s*(.*)', full_prompt, re.DOTALL | re.IGNORECASE)
        
        if context_match:
            context_data = context_match.group(1).strip()
            print(f"[NOTIFICATION A2A] Detected context data ({len(context_data)} chars)")
            
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, full_prompt)
            
            if email_match:
                recipient = email_match.group(0)
                print(f"[NOTIFICATION A2A] Auto-detected recipient: {recipient}")
                
                purpose_keywords = {
                    'policy': ['policy', 'policies', 'return', 'refund', 'warranty', 'rules', 'guidelines', 'terms', 'conditions'],
                    'inventory': ['inventory', 'stock', 'products', 'items', 'supplies', 'pump', 'valve'],
                    'summary': ['summary', 'report', 'overview', 'update']
                }
                
                purpose = "status update"
                prompt_lower = full_prompt.lower()
                context_lower = context_data.lower() if context_data else ""
                combined = prompt_lower + " " + context_lower
                
                for category, keywords in purpose_keywords.items():
                    if any(kw in combined for kw in keywords):
                        purpose = f"{category}"
                        break
                
                print(f"[NOTIFICATION A2A] Auto-detected purpose: {purpose}")
                
                try:
                    draft = compose_email_from_context(recipient, purpose, context_data)
                    print(f"[NOTIFICATION A2A] Successfully composed email draft ({len(draft)} chars)")
                    
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
                    print(f"[NOTIFICATION A2A] Error composing email: {compose_error}")
            else:
                print(f"[NOTIFICATION A2A] No email recipient found in prompt")
        else:
            print(f"[NOTIFICATION A2A] No context detected, using LLM for generation")
        
        await stateless_session_service.create_session(
            app_name="agents",
            user_id="default_user",
            session_id=session_id
        )
        
        runner = Runner(
            agent=notification_agent,
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
        function_results = []
        async for event in events_async:
            event_count += 1
            print(f"[NOTIFICATION A2A] Event {event_count}: author={event.author if hasattr(event, 'author') else 'unknown'}")
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        result_text += part.text
                        print(f"[NOTIFICATION A2A] Added text: {part.text[:200]}...")
                    elif hasattr(part, 'function_response') and part.function_response:
                        print(f"[NOTIFICATION A2A] Function response detected: {part.function_response}")
                        if hasattr(part.function_response, 'response'):
                            func_result = str(part.function_response.response)
                            function_results.append(func_result)
                            print(f"[NOTIFICATION A2A] Function result: {func_result[:300]}...")
                    elif hasattr(part, 'function_call') and part.function_call:
                        print(f"[NOTIFICATION A2A] Function call detected: {part.function_call}")
        
        # If we have function results but no text, use the function results
        if function_results and not result_text:
            result_text = "\n\n".join(function_results)
            print(f"[NOTIFICATION A2A] Using function results as response")
        
        print(f"[NOTIFICATION A2A] Final result_text length: {len(result_text)}")
        print(f"[NOTIFICATION A2A] Final result_text: {result_text[:500]}...")
        
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
        import traceback
        traceback.print_exc()
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