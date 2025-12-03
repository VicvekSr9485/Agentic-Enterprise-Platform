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

router = APIRouter()

stateless_session_service = InMemorySessionService()
inventory_agent = create_inventory_agent()

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
    print(f"[INVENTORY A2A] Raw request body: {body.decode()}")
    
    try:
        body_dict = await raw_request.json()
        request = A2ARequest(**body_dict)
        message = request.params.message
    except Exception as e:
        print(f"[INVENTORY A2A] Failed to parse request: {e}")
        print(f"[INVENTORY A2A] Body dict: {body_dict if 'body_dict' in locals() else 'failed to get JSON'}")
        raise HTTPException(status_code=422, detail=str(e))
    
    try:
        session_id = str(uuid.uuid4())
        print(f"[INVENTORY A2A] Processing with temporary session: {session_id}")

        await stateless_session_service.create_session(
            app_name="agents",
            user_id="default_user",
            session_id=session_id
        )

        runner = Runner(
            agent=inventory_agent,
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
            print(f"[INVENTORY DEBUG] Event: type={type(event)}, author={event.author}")
            if event.content:
                parts = event.content.parts or []
                print(f"[INVENTORY DEBUG] Content parts: {len(parts)}")
                for part in parts:
                    print(f"[INVENTORY DEBUG] Part: text={part.text[:50] if part.text else 'None'}, function_call={part.function_call is not None}")
                    
                    # Handle text parts
                    if part.text:
                        result_text += part.text
                    
                    # Handle function_response parts (tool outputs)
                    # Sometimes the model returns the tool output as part of the event stream
                    if hasattr(part, 'function_response') and part.function_response:
                        print(f"[INVENTORY A2A] Found function_response: {type(part.function_response)}")
                        try:
                            # Extract response from function_response
                            # It might be in 'response' dict or 'result' field
                            response_data = part.function_response.response
                            if response_data:
                                if isinstance(response_data, dict) and 'result' in response_data:
                                    result_text += str(response_data['result'])
                                else:
                                    result_text += str(response_data)
                        except Exception as e:
                            print(f"[INVENTORY A2A] Error parsing function_response: {e}")
        
        if not result_text:
            print("[INVENTORY DEBUG] WARNING: Result text is empty!")
        
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
        print(f"[INVENTORY A2A] Sending response: {json.dumps(response)}")
        return response
    except Exception as e:
        print(f"Inventory Agent Error: {e}")
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
    """A2A Protocol: Agent Card endpoint"""
    card_path = os.path.join(os.path.dirname(__file__), "agent.json")
    with open(card_path, "r") as f:
        return json.load(f)