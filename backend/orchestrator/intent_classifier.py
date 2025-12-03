from typing import List, Dict, Optional
from pydantic import BaseModel
import json


class AgentIntent(BaseModel):
    """Represents an agent that should be invoked"""
    agent_name: str
    targeted_prompt: str 
    reason: str


class IntentClassification(BaseModel):
    """Result of intent classification"""
    agents_needed: List[AgentIntent]
    requires_coordination: bool  
    user_intent_summary: str 


INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for an enterprise agent orchestration system.

Available agents:
1. **inventory_specialist** - Queries product inventory database by name, SKU, or category (NOT price filtering)
2. **policy_expert** - Searches company policy documents (returns, HR policies, compliance, regulations)
3. **analytics_specialist** - Business intelligence, analytics, AND PRICE FILTERING (trends, forecasts, reports, products under/over/between price ranges)
4. **order_specialist** - Order management and procurement (purchase orders, suppliers, reorders, tracking)
5. **notification_specialist** - Drafts and sends emails with human approval workflow

Analyze the user's request and determine:
1. Which agent(s) need to be involved
2. What specific question/task each agent should handle
3. Whether coordination between agents is needed

Rules:
- If user asks about inventory by name/SKU/category → use inventory_specialist
- If user asks about PRICE filtering ("under $X", "over $Y", "between $A-$B") → use analytics_specialist
- If user asks about QUANTITY filtering ("below X units", "less than Y", "under Z stock") → use analytics_specialist
- If user asks about policies/rules/compliance → use policy_expert
- If user asks about policies/rules/compliance (EXCEPT supplier compliance) → use policy_expert
- If user asks about orders/purchase/suppliers/reorder/procurement OR supplier compliance → use order_specialist
- If user asks to draft/send/email/notify → use notification_specialist
- If user asks multiple things (e.g., "analyze trends AND email results") → use multiple agents with coordination
- If tasks are INDEPENDENT (e.g., "Stock of X and Policy for Y") → set "requires_coordination": false
- Create targeted, specific prompts for each agent (don't pass the full user query if it contains tasks for other agents)
- For follow-up questions with pronouns (it, them, that, which), maintain the domain from previous context

CRITICAL: For ANY price-based filtering queries ("products under $50", "items over $100", "products between $20-$80"), 
ALWAYS use analytics_specialist, NEVER inventory_specialist.

CRITICAL: "Supplier compliance" queries MUST go to order_specialist, NOT policy_expert.

USER REQUEST: {user_prompt}

Respond with a JSON object following this schema:
{{
  "agents_needed": [
    {{
      "agent_name": "inventory_specialist" | "policy_expert" | "analytics_specialist" | "order_specialist" | "notification_specialist",
      "targeted_prompt": "Specific question for this agent",
      "reason": "Why this agent is needed"
    }}
  ],
  "requires_coordination": true | false,
  "user_intent_summary": "Brief summary of what user wants"
}}

Examples:

User: "How many pumps do we have?"
Response:
{{
  "agents_needed": [
    {{"agent_name": "inventory_specialist", "targeted_prompt": "How many pumps are in stock?", "reason": "User needs inventory data"}}
  ],
  "requires_coordination": false,
  "user_intent_summary": "Check pump inventory quantity"
}}

User: "Check pump inventory and draft an email to sales about it"
Response:
{{
  "agents_needed": [
    {{"agent_name": "inventory_specialist", "targeted_prompt": "What pumps do we have in stock? Include quantities, SKUs, and prices.", "reason": "Need inventory data for email"}},
    {{"agent_name": "notification_specialist", "targeted_prompt": "Draft an email to sales@company.com summarizing the pump inventory data", "reason": "User wants to email the results"}}
  ],
  "requires_coordination": true,
  "user_intent_summary": "Get pump inventory and email summary to sales"
}}

User: "What's our return policy for electronics and how many valves are in warehouse B?"
Response:
{{
  "agents_needed": [
    {{"agent_name": "policy_expert", "targeted_prompt": "What is the return policy for electronics?", "reason": "User needs policy information"}},
    {{"agent_name": "inventory_specialist", "targeted_prompt": "How many valves are in warehouse B?", "reason": "User needs inventory data"}}
  ],
  "requires_coordination": false,
  "user_intent_summary": "Get electronics return policy and valve inventory from warehouse B"
}}

User: "Show me products under $50 and send me a notification"
Response:
{{
  "agents_needed": [
    {{"agent_name": "analytics_specialist", "targeted_prompt": "Filter and show all products under $50. Include product name, SKU, price, stock quantity, and category.", "reason": "User needs price-based filtering which only analytics can do"}},
    {{"agent_name": "notification_specialist", "targeted_prompt": "Draft an email notification with the list of products under $50", "reason": "User wants email notification with the results"}}
  ],
  "requires_coordination": true,
  "user_intent_summary": "Filter products by price (under $50) and send email notification"
}}

User: "Draft an email to orders@acme.com asking for a quote on 100 units of PUMP-001"
Response:
{{
  "agents_needed": [
    {{"agent_name": "notification_specialist", "targeted_prompt": "Draft an email to orders@acme.com asking for a quote on 100 units of PUMP-001", "reason": "User wants to compose an email requesting a quote"}}
  ],
  "requires_coordination": false,
  "user_intent_summary": "Draft quote request email"
}}

Now classify this request and respond with ONLY the JSON object (no other text before or after):"""


def parse_intent_from_llm_response(response_text: str) -> Optional[IntentClassification]:
    """
    Parse LLM response into IntentClassification object.
    
    Args:
        response_text: Raw text response from LLM
        
    Returns:
        IntentClassification object or None if parsing fails
    """
    try:
        text = response_text.strip()

        if "```json" in text:
            text = text[text.index("```json") + 7:]
        elif "```" in text:
            text = text[text.index("```") + 3:]
        
        if not text.startswith("{"):
            json_start = text.find("{")
            if json_start != -1:
                text = text[json_start:]

        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
     
        if not text.endswith("}"):
            brace_count = 0
            last_valid_pos = -1
            for i, char in enumerate(text):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        last_valid_pos = i
                        break
            
            if last_valid_pos != -1:
                text = text[:last_valid_pos + 1]
            else:
                text += '"' * text.count('"') % 2
                text += "}" * text.count("{") - text.count("}")
        
        data = json.loads(text)
        
        return IntentClassification(**data)
    except Exception as e:
        print(f"[INTENT CLASSIFIER] Failed to parse LLM response: {e}")
        print(f"[INTENT CLASSIFIER] Raw response: {response_text[:500]}")
        return None
