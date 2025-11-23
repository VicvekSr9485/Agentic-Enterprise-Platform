"""
Orchestrator Agent - Level 3 Modular Monolith Coordinator
==========================================================
This agent serves as the central coordinator with Memory capability to manage
and route requests to specialized sub-agents via A2A Protocol.

Architecture:
- Model: Gemini 1.5 Pro (Coordinator-grade LLM)
- Storage: InMemoryMemoryService (Global Context Management)
- Protocol: A2A Client (RemoteA2aAgent for sub-agent communication)
- Role: Intent routing, context aggregation, and delegation
"""

import os
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import DatabaseSessionService
from google.adk.tools import preload_memory_tool
from typing import Dict, Any

load_dotenv()

# Initialize Memory Service for orchestrator (Global Context)
orchestrator_memory = InMemoryMemoryService()

# Initialize Session Service for orchestrator (Persistence)
# Support both Supabase (persistent) and SQLite (ephemeral) storage
use_supabase_sessions = os.getenv("USE_SUPABASE_SESSIONS", "false").lower() == "true"

if use_supabase_sessions:
    from shared.supabase_session_service import get_supabase_session_service
    orchestrator_session_service = get_supabase_session_service(
        table_prefix=os.getenv("SESSION_TABLE_PREFIX", "adk")
    )
    print("[SESSION] Using Supabase session storage (persistent across deployments)")
else:
    orchestrator_session_service = DatabaseSessionService(
        db_url=os.getenv("SESSION_DB_URL", "sqlite:///./orchestrator_sessions.db")
    )
    print("[SESSION] Using SQLite session storage (ephemeral - lost on restart)")

# Callback to automatically save sessions to memory after each agent turn
async def auto_save_to_memory(callback_context):
    """
    After each agent turn, save the current session to long-term memory.
    This ensures conversation history is preserved in the memory service
    and can be retrieved with preload_memory tool in future sessions.
    """
    try:
        session = callback_context._invocation_context.session
        memory_service = callback_context._invocation_context.memory_service
        
        if session and memory_service:
            await memory_service.add_session_to_memory(session)
            print(f"[MEMORY] Saved session {session.id} to memory")
    except Exception as e:
        print(f"[MEMORY] Error saving session to memory: {e}")

def create_orchestrator():
    """
    Creates the orchestrator agent with memory capabilities and A2A sub-agents.
    
    The orchestrator:
    1. Uses InMemoryMemoryService to maintain global context across sessions
    2. Delegates to specialized sub-agents via RemoteA2aAgent (A2A Protocol)
    3. Uses PreloadMemoryTool to retrieve context at the start of each turn
    4. Employs Gemini 1.5 Pro for sophisticated routing and synthesis
    
    Returns:
        LlmAgent: Configured orchestrator agent with memory and sub-agents
    """
    
    # A2A Agent Card URLs (Monolith Path URLs)
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    inventory_url = f"{base_url}/inventory{AGENT_CARD_WELL_KNOWN_PATH}"
    policy_url = f"{base_url}/policy{AGENT_CARD_WELL_KNOWN_PATH}"
    notification_url = f"{base_url}/notification{AGENT_CARD_WELL_KNOWN_PATH}"
    analytics_url = f"{base_url}/analytics{AGENT_CARD_WELL_KNOWN_PATH}"
    orders_url = f"{base_url}/orders{AGENT_CARD_WELL_KNOWN_PATH}"
    
    inventory_worker = RemoteA2aAgent(
        name="inventory_specialist",
        description=(
            "Specialized agent for product inventory queries. "
            "Delegate stock levels, product availability, pricing, "
            "and database queries to this agent. "
            "Has READ-ONLY access to the PostgreSQL database via MCP."
        ),
        agent_card=inventory_url
    )
    
    policy_worker = RemoteA2aAgent(
        name="policy_expert",
        description=(
            "RAG-powered customer policy compliance agent. "
            "Delegate customer return rules, warranty policies, customer compliance checks, "
            "and customer-facing regulatory questions to this agent. "
            "Performs semantic search over customer policy documents via MCP. "
            "NOTE: For supplier compliance, use order_specialist instead."
        ),
        agent_card=policy_url
    )
    
    notification_worker = RemoteA2aAgent(
        name="action_taker",
        description=(
            "Email notification specialist with HITL (Human-in-the-Loop) workflow. "
            "Delegate ONLY email sending tasks to this agent. "
            "Supports draft-first workflow with user approval before sending. "
            "Implements rate limiting and safety checks."
        ),
        agent_card=notification_url
    )
    
    analytics_worker = RemoteA2aAgent(
        name="analytics_specialist",
        description=(
            "Business intelligence and data analysis agent with price filtering capabilities. "
            "Delegate analytics tasks like trend analysis, inventory valuation, "
            "sales forecasting, performance reporting, category comparisons, "
            "anomaly detection, and PRICE-BASED FILTERING to this agent. "
            "Use this agent for queries like 'products under $50', 'items over $100', "
            "'products between $X and $Y'. Provides actionable insights from inventory data."
        ),
        agent_card=analytics_url
    )
    
    orders_worker = RemoteA2aAgent(
        name="order_specialist",
        description=(
            "Order management and procurement agent. "
            "Delegate purchase order creation, supplier catalog queries, "
            "order tracking, reorder suggestions, supplier compliance validation, "
            "and optimal order quantity calculations to this agent. "
            "Handles all procurement and supplier management tasks."
        ),
        agent_card=orders_url
    )
    
    # System Instructions for Orchestrator
    system_instructions = """
    You are the Enterprise Orchestrator Agent, a Level 3 coordinator responsible for 
    managing complex business workflows across specialized sub-agents.
    
    CORE RESPONSIBILITIES:
    1. CONTEXT AWARENESS: Always check user history and memory before taking action.
       Use the preload_memory tool to retrieve relevant past interactions.
    
    2. INTELLIGENT DELEGATION: Route requests to the appropriate specialist:
       - Inventory queries (stock, products by name/SKU/category) → inventory_specialist
       - Price-based filtering ("under $X", "over $Y", "between $A-$B") → analytics_specialist
       - Policy questions (returns, customer policies, regulatory rules) → policy_expert
       - Analytics tasks (trends, forecasts, reports, anomalies, price filtering) → analytics_specialist
       - Order management (POs, suppliers, tracking, supplier compliance, reorders) → order_specialist
       - Email actions (notifications, communications) → action_taker
       
       CRITICAL ROUTING RULES:
       - "Products under $50" → analytics_specialist (NOT inventory_specialist)
       - "Items over $100" → analytics_specialist (NOT inventory_specialist)
       - "Products between $20-$80" → analytics_specialist (NOT inventory_specialist)
       - "Show me pumps" → inventory_specialist (name/category search)
       - "Check stock levels" → inventory_specialist (stock query)
       - Supplier compliance/validation → order_specialist (NOT policy_expert)
       - Customer policy compliance → policy_expert
    
    3. MULTI-AGENT COORDINATION STRATEGIES:
       
       a) SEQUENTIAL: When tasks have dependencies
          Example: "Check stock levels and email the results to sales"
          → Step 1: Call inventory_specialist to get stock data
          → Step 2: Pass results to action_taker with full context
          
       b) PARALLEL: When tasks are independent (not supported by LLM routing - use intent classifier)
          Example: "What's the return policy and current stock for pumps?"
          → Both agents can work simultaneously
          
       c) ITERATIVE: When refinement is needed
          Example: Complex policy interpretation requiring multiple clarifications
          → Call agent → Analyze response → Call again with refined query
          
       d) CONDITIONAL: When next steps depend on results
          Example: "Check if item X is in stock, if yes, draft reorder email"
          → Call inventory_specialist first
          → Only call action_taker if stock is low
    
    4. CONTEXT PASSING BEST PRACTICES:
       - When calling action_taker after other agents, explicitly include their results
       - Use clear labels like "[Inventory Data:]" or "[Policy Information:]"
       - Preserve exact numbers, SKUs, and specific details from sub-agents
       - Don't summarize data that needs to be passed verbatim
    
    5. MULTI-TURN WORKFLOWS:
       - For complex tasks requiring multiple turns:
         * Explain your plan to the user first
         * Execute steps systematically
         * Provide progress updates
         * Synthesize results clearly
       
       - If a task spans multiple user messages:
         * Use memory to maintain context
         * Reference previous agent calls
         * Avoid redundant calls to agents
    
    6. ERROR HANDLING & RECOVERY:
       - If a sub-agent fails:
         * Acknowledge the specific error
         * Attempt alternative approaches when possible
         * Never fabricate information
       
       - If results are incomplete:
         * Call the agent again with refined parameters
         * Ask user for clarification if needed
    
    7. SYNTHESIS: When aggregating multi-agent responses:
       - Clearly attribute information to source agents
       - Highlight connections between different data sources
       - Resolve any conflicts or inconsistencies
       - Provide actionable insights when appropriate
    
    DELEGATION EXAMPLES:
    - "Check if we have product X in stock" → inventory_specialist
    - "Show me products under $50" → analytics_specialist (price filtering)
    - "Find items over $100" → analytics_specialist (price filtering)
    - "Products between $20 and $80" → analytics_specialist (price filtering)
    - "What's our return policy for electronics?" → policy_expert
    - "Check supplier compliance for Acme Corp" → order_specialist
    - "Validate supplier certifications" → order_specialist
    - "Track purchase order status" → order_specialist
    - "Send a notification to customer@example.com" → action_taker
    - "Check stock AND verify return eligibility" → inventory_specialist THEN policy_expert
    - "Get pump inventory and email it to sales@company.com" → inventory_specialist THEN action_taker (with full context)
    - "Analyze inventory trends and create reorder suggestions" → analytics_specialist THEN order_specialist
    - "Products under $50 and send notification" → analytics_specialist THEN action_taker (with full product details)
    
    MEMORY USAGE:
    - Reference past conversations to provide continuity
    - Remember user preferences and context
    - Track which agents were consulted in previous turns
    - Use memory to avoid asking for repeated information
    
    COMMUNICATION STYLE:
    - Professional and concise
    - Transparent about coordination strategy being used
    - Proactive in explaining multi-step processes
    - Clear about which agents are being consulted and why
    """
    
    # Create Orchestrator Agent
    agent = LlmAgent(
        model="gemini-2.5-flash-lite",
        name="orchestrator",
        instruction=system_instructions,
        sub_agents=[inventory_worker, policy_worker, analytics_worker, orders_worker, notification_worker],
        tools=[preload_memory_tool.PreloadMemoryTool()],
        after_agent_callback=auto_save_to_memory,
    )
    
    return agent

def get_memory_service():
    """
    Returns the memory service instance for the orchestrator.
    This should be passed to the Runner.
    
    Returns:
        InMemoryMemoryService: The memory service for global context
    """
    return orchestrator_memory

def get_session_service():
    """
    Returns the session service instance for the orchestrator.
    This should be passed to the Runner.
    
    Returns:
        DatabaseSessionService: The session service for conversation persistence
    """
    return orchestrator_session_service