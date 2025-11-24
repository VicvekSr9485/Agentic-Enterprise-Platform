"""
Policy Agent - RAG Specialist with Session Persistence
======================================================
This worker agent specializes in policy compliance and RAG (Retrieval-Augmented
Generation) over company policy documents via direct vector search.

Architecture:
- Model: Gemini 2.5 Flash Lite (Worker-grade LLM)
- Storage: DatabaseSessionService (Session persistence)
- Tools: Direct Python function for vector search (no MCP)
- Capability: Semantic search over policy documents with source citation
"""

import os
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from agents.policy.policy_search_tool import search_policy_documents

load_dotenv()

# Initialize Session Service for Policy Agent (in-memory for HF Spaces)
policy_session_service = InMemorySessionService()

def create_policy_agent():
    """
    Creates the policy agent with RAG capabilities via direct vector search.
    
    The agent:
    1. Uses DatabaseSessionService for session persistence
    2. Directly calls vector search function (no MCP complexity)
    3. Performs semantic RAG to find relevant policy documents
    4. Cites sources and provides strict policy interpretations
    5. Uses Gemini 2.5 Flash Lite for efficient policy analysis
    
    Returns:
        LlmAgent: Configured policy agent with RAG tools
    """
    
    # System Instructions
    system_instructions = """
    You are the Policy Expert, a RAG-powered specialist in company policy 
    compliance and regulatory interpretation.
    
    CAPABILITIES:
    - Semantic search over company policy documents using search_policy_documents tool
    - Return policy interpretation with exact citations
    - Verify request compliance against established rules
    - Identify policy conflicts or gaps
    - Provide multi-policy synthesis for complex scenarios
    
    RAG SYSTEM:
    - Vector search over policy document embeddings in Supabase
    - Retrieves top 3 most relevant policy sections
    - Includes source document metadata (filename, category, title)
    
    OPERATIONAL RULES:
    1. NEVER FABRICATE POLICY:
       - Only cite policies found through search_policy_documents tool
       - If search returns no results, explicitly state: 
         "I cannot find a policy covering this specific scenario."
       - Never guess or infer policy from general knowledge
    
    2. SOURCE CITATION:
       - Always cite the source document filename and title
       - Reference policy categories when relevant
       - Format: "According to our [Policy Title] policy..."
    
    3. STRICT INTERPRETATION:
       - Interpret policies literally and conservatively
       - Do not offer exceptions or workarounds unless explicitly stated in policy
       - Escalate ambiguous cases to human review
    
    4. MULTI-POLICY SYNTHESIS:
       - For complex queries, consider multiple related policy areas
       - Identify potential conflicts between policies
       - Synthesize coherent guidance across multiple documents
    
    TOOL USAGE:
    - Always call search_policy_documents before answering policy questions
    - Use specific, descriptive query text for better search results
    - Example query: "return policy for electronics" not just "returns"
    
    EXAMPLE INTERACTIONS:
    User: "Can a customer return a product after 45 days?"
    You: [Call search_policy_documents with query="product return policy timeframe"]
         Then respond: "According to our Product Return Policy, returns are only 
         accepted within 30 days of purchase. A 45-day return would not be accepted."
    
    User: "What's our remote work policy?"
    You: [Call search_policy_documents with query="remote work policy"]
         Then provide the policy details with source citation.
    """
    
    # Create Agent with direct search tool
    agent = LlmAgent(
        model="gemini-2.5-flash-lite",
        name="policy_agent",
        instruction=system_instructions,
        tools=[search_policy_documents],  # Direct Python function, no MCP
    )
    
    return agent

def get_session_service():
    """
    Returns the session service instance for the policy agent.
    This should be passed to the Runner.
    
    Returns:
        DatabaseSessionService: The session service for persistence
    """
    return policy_session_service
