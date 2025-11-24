from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import uuid

from google.adk.runners import Runner
from google.genai import types
from google.adk.sessions import InMemorySessionService
import os

from .agent import order_agent

router = APIRouter(tags=["orders"])

stateless_session_service = InMemorySessionService()

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
    body = await raw_request.body()
    print(f"[ORDERS A2A] Raw request body: {body.decode()}")
    
    try:
        body_dict = await raw_request.json()
        request = A2ARequest(**body_dict)
        message = request.params.message
    except Exception as e:
        print(f"[ORDERS A2A] Failed to parse request: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    
    try:
        session_id = str(uuid.uuid4())
        print(f"[ORDERS A2A] Processing with temporary session: {session_id}")

        await stateless_session_service.create_session(
            app_name="agents",
            user_id="default_user",
            session_id=session_id
        )

        runner = Runner(
            agent=order_agent,
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
                    # Check for normal text response
                    if hasattr(part, 'text') and part.text:
                        result_text += part.text
                        print(f"[ORDERS A2A] Got text response (length {len(part.text)})")
                    # Capture function response as fallback
                    elif hasattr(part, 'function_response') and part.function_response:
                        print(f"[ORDERS A2A] Found function_response: {type(part.function_response)}")
                        print(f"[ORDERS A2A] function_response attributes: {dir(part.function_response)}")
                        print(f"[ORDERS A2A] function_response dict: {part.function_response.__dict__ if hasattr(part.function_response, '__dict__') else 'N/A'}")
                        
                        # Try multiple ways to extract the response
                        if hasattr(part.function_response, 'response'):
                            print(f"[ORDERS A2A] Has response attribute: {part.function_response.response}")
                            function_response_text = str(part.function_response.response)
                        elif hasattr(part.function_response, 'content'):
                            print(f"[ORDERS A2A] Has content attribute: {part.function_response.content}")
                            function_response_text = str(part.function_response.content)
        
        # If no text response was generated, use the function response directly
        if not result_text and function_response_text:
            result_text = function_response_text
            print(f"[ORDERS A2A] Using function response as final output (length {len(result_text)})")
        
        print(f"[ORDERS A2A] Total events: {event_count}, result length: {len(result_text)}")
        
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
        print(f"[ORDERS A2A] Response structure: {json.dumps(response, indent=2)[:500]}...")
        print(f"[ORDERS A2A] Sending response")
        return response
    except Exception as e:
        print(f"Order Agent Error: {e}")
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
