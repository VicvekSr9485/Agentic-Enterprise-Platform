#!/usr/bin/env python3
"""Test script to debug Runner.run() behavior"""

import os
import sys
from dotenv import load_dotenv
from google.genai import types

# Load environment
load_dotenv()

# Import agent
from orchestrator.agent import create_orchestrator, get_session_service, get_memory_service
from google.adk.runners import Runner

print("Creating orchestrator...")
orchestrator_agent = create_orchestrator()
session_service = get_session_service()
memory_service = get_memory_service()

print("Creating runner...")
runner = Runner(
    agent=orchestrator_agent,
    app_name="orchestrator",
    session_service=session_service,
    memory_service=memory_service
)

print("Creating Content object...")
message_content = types.Content(
    role="user",
    parts=[types.Part(text="Hello! What can you help me with?")]
)

print("Running agent...")
events = runner.run(
    user_id="test_user",
    session_id="test_session_debug",
    new_message=message_content
)

print(f"Events type: {type(events)}")
print("Iterating events...")
event_count = 0
for event in events:
    event_count += 1
    print(f"\nEvent {event_count}:")
    print(f"  Author: {event.author}")
    print(f"  Has content: {event.content is not None}")
    if event.content:
        print(f"  Has parts: {event.content.parts is not None}")
        if event.content.parts:
            print(f"  Parts count: {len(event.content.parts)}")
            for i, part in enumerate(event.content.parts):
                if part.text:
                    print(f"  Part {i} text: {part.text[:200]}...")
    print(f"  Turn complete: {event.turn_complete}")
    print(f"  Finish reason: {event.finish_reason}")

print(f"\nTotal events: {event_count}")
