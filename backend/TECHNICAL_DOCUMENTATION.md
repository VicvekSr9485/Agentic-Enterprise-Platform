# Enterprise Agents Platform - Backend Technical Documentation

**Version:** 1.0.0  
**Last Updated:** November 21, 2025  
**Architecture:** Modular Monolith with A2A Protocol

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture & Design Decisions](#architecture--design-decisions)
4. [Agent Ecosystem](#agent-ecosystem)
5. [Orchestration Layer](#orchestration-layer)
6. [Data Flow & Communication](#data-flow--communication)
7. [Human-in-the-Loop (HITL) System](#human-in-the-loop-hitl-system)
8. [Observability & Metrics](#observability--metrics)
9. [Testing & Validation](#testing--validation)
10. [Configuration & Environment](#configuration--environment)
11. [API Reference](#api-reference)
12. [Performance Characteristics](#performance-characteristics)
13. [Production Considerations](#production-considerations)

---

## System Overview

The Enterprise Agents Platform is a production-ready AI agent orchestration system built on the **Agent-to-Agent (A2A) Protocol**. It enables intelligent coordination of multiple specialized AI agents to accomplish complex, multi-step tasks requiring data retrieval, policy enforcement, and human approval workflows.

### Key Capabilities

- **Intelligent Intent Classification**: LLM-powered routing to appropriate specialized agents
- **Multi-Agent Coordination**: Sequential and parallel execution strategies with context enrichment
- **Human-in-the-Loop**: Secure approval workflows for high-stakes actions (email sending, data modifications)
- **Production Observability**: Real-time metrics, latency tracking, and error monitoring
- **Graceful Degradation**: Retry logic, timeout handling, and error recovery mechanisms

### Design Philosophy

1. **Agent Specialization**: Each agent handles a specific domain (inventory, policy, notifications)
2. **Context Propagation**: Rich context passed between agents for informed decision-making
3. **Deterministic Behavior**: Predictable workflows with clear audit trails
4. **Developer Experience**: Clean abstractions, comprehensive logging, easy debugging

---

## Technology Stack

### Core Framework
- **FastAPI** (0.115.5): High-performance async web framework
- **Uvicorn** (0.32.1): ASGI server with uvloop for production performance
- **Python 3.12**: Modern Python features (type hints, async/await, pattern matching)

### AI & Agent Framework
- **Google ADK (Agent Development Kit)**: Production agent framework with A2A protocol support
  - `google.adk.runners.Runner`: Agent execution runtime
  - `google.adk.sessions.InMemorySessionService`: Session state management
  - `google.adk.agents.RemoteA2aAgent`: Cross-agent communication primitives
- **Google Generative AI SDK** (0.8.3): LLM integration for Gemini models
  - Model: `gemini-2.0-flash-exp` (orchestrator, intent classification)
  - Model: `gemini-2.5-flash-lite` (specialized agents)

### Database & Storage
- **Supabase (PostgreSQL)**: Structured data storage with pgvector extension
  - Inventory management
  - Vector embeddings for semantic policy search
  - Session persistence (optional)
- **In-Memory Sessions**: Fast stateless operation for development

### Communication & Utilities
- **HTTPX** (0.27.2): Modern async HTTP client for A2A calls
- **Pydantic** (2.10.3): Runtime type validation and data modeling
- **python-dotenv** (1.0.1): Environment configuration management
- **SMTP (smtplib)**: Email delivery (Gmail SMTP by default)

### Development Tools
- **structlog**: Structured logging for production observability
- **psutil**: System resource monitoring
- **typing-extensions**: Advanced type hints for better IDE support

---

## Architecture & Design Decisions

### 1. Custom Tools vs Model Context Protocol (MCP)

**Decision**: Use custom-defined Python functions instead of MCP servers for agent tools

**Background**: Model Context Protocol (MCP) is a standardized way to expose tools and resources to AI agents through a client-server architecture. While MCP provides excellent interoperability and standardization, we encountered significant performance bottlenecks in production scenarios.

**MCP Bottlenecks Identified**:

1. **Process Isolation Overhead**
   - MCP servers run as separate processes with stdio transport
   - Each tool call requires IPC (Inter-Process Communication)
   - Added 200-500ms latency per tool invocation
   - Example: `mcp_server.py` for notification agent added ~400ms overhead

2. **Serialization Costs**
   - All data must be JSON-serialized for transport
   - Large inventory results (80+ items) caused 100-200ms serialization delay
   - Double serialization: Agent→MCP server→Database

3. **Session Management Complexity**
   - MCP requires separate session tracking per server
   - Difficult to share context between agent and tools
   - Additional memory overhead for each MCP server instance

4. **Development Friction**
   - Separate debugging for MCP server vs agent logic
   - Complex error propagation across process boundaries
   - Harder to trace execution flow in logs

**Performance Comparison** (Inventory Query):
```
With MCP Server:     6.2 seconds total
├─ Agent processing: 1.5s
├─ MCP transport:    0.4s
├─ Tool execution:   3.8s
└─ Response format:  0.5s

With Direct Tools:   4.7 seconds total
├─ Agent processing: 1.5s
├─ Tool execution:   2.9s
└─ Response format:  0.3s

Improvement: 24% faster (1.5s saved)
```

**Our Approach**: Direct Python Function Tools
```python
# agents/inventory/inventory_query_tool.py
def search_inventory(query: str, category: str = None) -> str:
    """Direct database query - no IPC overhead"""
    conn = get_supabase_connection()
    results = conn.from_('inventory').select('*').ilike('name', f'%{query}%').execute()
    return format_results(results)

# agents/inventory/agent.py
from inventory_query_tool import search_inventory

inventory_agent = Agent(
    model="gemini-2.5-flash-lite",
    tools=[search_inventory]  # Direct function reference
)
```

**Benefits of Direct Tools**:
- **24% faster execution**: No IPC or serialization overhead
- **Simpler debugging**: Single process, unified stack traces
- **Better observability**: Direct function calls appear in profiling
- **Easier testing**: Standard Python unit tests
- **Lower latency**: Sub-50ms tool invocation vs 200-500ms with MCP

**When MCP Makes Sense**:
- Cross-language tool integration (Node.js tools from Python agents)
- External service tools that must run in isolation
- Third-party tool marketplaces
- Multi-tenant systems requiring process isolation

**Trade-offs Accepted**:
- Less interoperability (tools tied to Python runtime)
- No standardized tool discovery protocol
- Cannot easily share tools across different language runtimes

**Conclusion**: For this monolithic Python backend with performance requirements, direct Python tools provide the best balance of simplicity, performance, and maintainability. MCP server implementations were maintain (`mcp_server.py` files) for future interoperability needs but use direct tools in production.

---

### 2. Modular Monolith Architecture

**Decision**: Single deployable service with clear module boundaries

**Rationale**:
- **Simplicity**: Easier to develop, test, and deploy than microservices
- **Performance**: No network overhead between modules
- **Flexibility**: Can split into microservices later if needed
- **Developer Velocity**: Faster iteration during development phase

**Structure**:
```
backend/
├── main.py                    # FastAPI application entry point
├── orchestrator/              # Coordination & routing logic
│   ├── agent.py              # Orchestrator agent definition
│   ├── routes.py             # HTTP endpoints & coordination logic
│   ├── intent_classifier.py  # LLM-based intent routing
│   └── hitl_manager.py       # Human approval workflows
├── agents/                    # Specialized agent implementations
│   ├── inventory/            # Product data retrieval
│   │   ├── agent.py         # Agent with direct tools
│   │   ├── inventory_query_tool.py  # Direct Python function
│   │  
│   ├── policy/               # Policy document search
│   │   ├── agent.py
│   │   ├── policy_search_tool.py
│   │   └── mcp_server.py    # MCP implementation (unused in prod)
│   └── notification/         # Email drafting & sending
│       ├── agent.py
│       ├── email_draft_tool.py
│       └── mcp_server.py    # MCP implementation (unused in prod)
└── shared/                    # Cross-cutting concerns
    ├── agent_metrics.py      # Observability metrics
    └── supabase_client.py    # Database connection
```

**Note on MCP Files**: The `mcp_server.py` files are maintained for potential future use cases requiring process isolation or cross-language interoperability, but production deployments use direct Python tools for optimal performance.

---

### 3. Agent-to-Agent (A2A) Protocol

**Decision**: Standardized JSON-RPC 2.0 communication between agents

**Rationale**:
- **Interoperability**: Agents can be implemented in any language
- **Testability**: Easy to mock and test agent interactions
- **Versioning**: Clear contract evolution path
- **Debugging**: Human-readable JSON messages in logs

**Protocol Example**:
```json
{
  "id": "uuid-v4",
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "configuration": {
      "acceptedOutputModes": [],
      "blocking": true
    },
    "message": {
      "kind": "message",
      "messageId": "uuid-v4",
      "role": "user",
      "parts": [
        {"kind": "text", "text": "What pumps do we have?"}
      ]
    }
  }
}
```

**Response Format**:
```json
{
  "id": "uuid-v4",
  "jsonrpc": "2.0",
  "result": {
    "kind": "message",
    "messageId": "uuid-v4",
    "role": "agent",
    "parts": [
      {"kind": "text", "text": "Found 2 pumps..."}
    ]
  }
}
```

### 4. Intent Classification Strategy

**Decision**: LLM-powered intent classification instead of rule-based routing

**Rationale**:
- **Flexibility**: Handles natural language variations
- **Maintainability**: No complex rule maintenance
- **Context-Aware**: Understands user intent holistically
- **Extensibility**: Easy to add new agent types

**Implementation**:
```python
# orchestrator/intent_classifier.py
INTENT_CLASSIFICATION_PROMPT = """
Analyze this user query and determine:
1. Which specialized agents are needed (inventory, policy, notification)
2. Specific prompts for each agent
3. Whether agents need sequential coordination
4. Reasoning for each decision

Output JSON with: summary, agents_needed[], requires_coordination
"""
```

**Classification Output**:
- `summary`: High-level task description
- `agents_needed`: List of `{agent_name, targeted_prompt, reason}`
- `requires_coordination`: Boolean for sequential vs parallel execution

### 5. Multi-Agent Coordination Modes

**Decision**: Support both sequential and parallel execution patterns

**Sequential Mode** (requires_coordination=true):
- Used when later agents need data from earlier agents
- Example: Inventory retrieval → Email drafting (needs inventory data)
- Executes agents in order, passing context forward

**Parallel Mode** (requires_coordination=false):
- Used when agents work independently
- Example: Inventory query + Policy lookup (unrelated tasks)
- Executes via `asyncio.gather()` for speed

**Context Enrichment**:
```python
# Sequential: Build enriched prompt for notification agent
enriched_prompt = f"{notification_prompt}\n\n"
enriched_prompt += "[Context from other agents:]\n"
for block in data_blocks:
    enriched_prompt += f"[{block['agent'].title()}:]\n{block['content']}\n\n"
```

### 6. Human-in-the-Loop (HITL) Design

**Decision**: Orchestrator-managed approval state with stateful sessions

**Rationale**:
- **Security**: High-stakes actions require human verification
- **Auditability**: Clear approval trail
- **User Control**: Explicit opt-in for dangerous operations
- **Simplicity**: Agent agents don't need HITL logic

**Workflow**:
1. Agent returns action requiring approval (e.g., email draft)
2. Orchestrator stores pending action in session
3. Response includes `pending_approval=true, approval_type="email_send"`
4. User replies "yes" or "no"
5. Orchestrator executes or cancels based on approval

**Supported Actions**:
- `email_send`: Draft email approval
- `data_modification`: Database changes (future)
- `external_api_call`: Third-party integrations (future)

### 7. Error Handling & Resilience

**Decision**: Multi-layer error handling with graceful degradation

**Retry Logic**:
```python
async def call_a2a(url: str, prompt: str, retry_count: int = 2):
    for attempt in range(retry_count + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                return sanitize(response)
        except Exception as e:
            if attempt < retry_count:
                await asyncio.sleep(1)  # Exponential backoff possible
            else:
                raise
```

**Timeout Handling**:
- Intent classification: 10 second timeout
- A2A calls: 30 second timeout
- Background tasks: No timeout (handled by process manager)

**Error Recovery**:
- Failed agent calls don't crash orchestrator
- Partial results returned to user with error context
- Metrics track error rates per agent

---

## Agent Ecosystem

### Orchestrator Agent

**Purpose**: Intelligent routing, coordination, and HITL management

**Capabilities**:
- Intent classification using Gemini 2.0 Flash
- Multi-agent workflow orchestration
- Context enrichment and propagation
- Approval workflow management
- Session state tracking

**Configuration**:
```json
{
  "name": "orchestrator",
  "model": "gemini-2.0-flash-exp",
  "generation_config": {
    "temperature": 0.2,
    "max_output_tokens": 8192
  }
}
```

**System Instructions**:
- 4 coordination strategies (SEQUENTIAL, PARALLEL, ITERATIVE, CONDITIONAL)
- Context passing best practices
- Multi-turn conversation guidelines
- Error handling & recovery procedures

**Key Methods**:
- `POST /orchestrator/chat`: Main user interaction endpoint
- `GET /orchestrator/metrics`: Observability metrics
- `GET /orchestrator/health`: Health check

### Inventory Agent

**Purpose**: Product inventory querying and reporting

**Data Source**: Supabase PostgreSQL with product catalog

**Capabilities**:
- Natural language product queries
- Stock level reporting
- Price and availability checks
- Category and location filtering

**Tool**: `inventory_query_tool.py`
```python
def search_inventory(query: str, category: str = None) -> str:
    # Build dynamic SQL with ILIKE patterns
    # Support: "pumps", "valve model X", "electronics in warehouse A"
    # Returns formatted inventory report
```

**Database Schema**:
```sql
CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    sku TEXT UNIQUE NOT NULL,
    category TEXT,
    price DECIMAL(10,2),
    stock_quantity INTEGER DEFAULT 0,
    location TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Example Query → Response**:
- Input: "What pumps do we have in stock?"
- SQL: `SELECT * FROM inventory WHERE name ILIKE '%pump%'`
- Output: Formatted list with SKU, stock, price, location

**Configuration**:
```json
{
  "model": "gemini-2.5-flash-lite",
  "temperature": 0.1,
  "tools": ["inventory_query_tool"]
}
```

### Policy Agent

**Purpose**: Company policy document search and retrieval

**Data Source**: Supabase with pgvector for semantic search

**Capabilities**:
- Semantic policy search using embeddings
- Multi-document retrieval
- Context-aware policy matching
- Fallback to keyword search

**Tool**: `policy_search_tool.py`
```python
async def semantic_policy_search(query: str, top_k: int = 3) -> str:
    # Generate query embedding
    embedding = await generate_embedding(query)
    
    # Vector similarity search
    results = await supabase.rpc(
        'match_policy_documents',
        {'query_embedding': embedding, 'match_count': top_k}
    )
    
    # Format with source attribution
    return format_policy_results(results)
```

**Database Schema**:
```sql
CREATE TABLE policy_documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON policy_documents 
USING ivfflat (embedding vector_cosine_ops);
```

**Embedding Model**: `text-embedding-004` (768 dimensions)

**Search Strategy**:
1. Generate query embedding
2. Cosine similarity search in vector space
3. Return top 3 most relevant documents
4. Fallback to full-text search if no results

**Configuration**:
```json
{
  "model": "gemini-2.5-flash-lite",
  "temperature": 0.0,
  "tools": ["policy_search_tool"]
}
```

### Notification Agent

**Purpose**: Email drafting and delivery with HITL approval

**Capabilities**:
- Context-aware email composition
- Professional formatting (plain text + HTML)
- Inventory data parsing and table generation
- Policy information formatting
- SMTP email delivery
- Draft→Approval→Send workflow

**Tools**:
- `email_draft_tool.py`: Composition and sending logic
- `compose_email_from_context()`: Intelligent email generation
- `send_email()`: SMTP delivery

**Email Composition Pipeline**:
```python
def compose_email_from_context(recipient, purpose, context_data):
    # 1. Sanitize and parse context
    cleaned_lines = _sanitize_context(context_data)
    
    # 2. Extract structured data
    inventory_items = _parse_inventory(cleaned_lines)
    
    # 3. Generate subject with metrics
    # Example: "Inventory Update – 80 Units (2 Models) | Est. Value $26,999.20"
    
    # 4. Build professional body
    # - Greeting
    # - Executive summary with metrics
    # - Stock health assessment
    # - Detailed item breakdown
    # - Supplemental context
    # - Call to action
    # - Signature
    
    # 5. Generate HTML variant
    
    # 6. Return draft with approval prompt
    return draft_email(to, subject, body)
```

**Inventory Parsing**:
```python
def _parse_inventory(lines: list[str]) -> list[dict]:
    # Multi-line format support:
    # "**Industrial Water Pump Model A** (SKU: PUMP-001)"
    # "Stock: 50 units"
    # "Price: $299.99"
    
    # Returns: [
    #   {"name": "...", "sku": "...", "qty": 50, "price": 299.99, "ext": 14999.50}
    # ]
```

**Email Formatting Features**:
- Dynamic subject lines with metrics
- Stock health assessments ("healthy" vs "low threshold")
- Calculated extended values (qty × price)
- Professional tone and structure
- HTML variant for rich formatting
- Proper quote escaping and sanitization

**SMTP Configuration**:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-specific-password
FROM_EMAIL=your-email@gmail.com
```

**Configuration**:
```json
{
  "model": "gemini-2.5-flash-lite",
  "temperature": 0.3,
  "tools": ["compose_email_from_context", "send_email"]
}
```

---

## Orchestration Layer

### Intent Classification

**File**: `orchestrator/intent_classifier.py`

**Process**:
1. User query received via `/orchestrator/chat`
2. Query passed to Gemini 2.0 Flash with classification prompt
3. LLM analyzes intent and returns structured JSON
4. Pydantic models validate response structure
5. Orchestrator uses classification to route requests

**Classification Models**:
```python
class AgentIntent(BaseModel):
    agent_name: str           # "inventory_specialist", "policy_expert", etc.
    targeted_prompt: str      # Specific query for this agent
    reason: str              # Why this agent is needed

class IntentClassification(BaseModel):
    summary: str             # High-level task description
    agents_needed: list[AgentIntent]
    requires_coordination: bool  # Sequential vs parallel
```

**Example Classification**:
```json
{
  "summary": "Get pump inventory and draft email to vicveksr@gmail.com",
  "agents_needed": [
    {
      "agent_name": "inventory_specialist",
      "targeted_prompt": "What is the current inventory for pumps?",
      "reason": "User needs pump inventory data"
    },
    {
      "agent_name": "notification_specialist",
      "targeted_prompt": "Draft email to vicveksr@gmail.com with inventory summary",
      "reason": "User wants to send email with data"
    }
  ],
  "requires_coordination": true
}
```

**Timeout Handling**:
```python
result = await asyncio.wait_for(
    asyncio.to_thread(generate_content_sync, prompt),
    timeout=10.0
)
```

### Coordination Strategies

**File**: `orchestrator/routes.py`

#### Sequential Execution
```python
if intent_classification.requires_coordination:
    print("[ORCHESTRATOR] Using SEQUENTIAL execution")
    
    # Execute all data agents first
    for agent_intent in agents_needed:
        if agent_intent.agent_name not in ["notification", "notification_specialist"]:
            result = await call_a2a(endpoint, agent_intent.targeted_prompt)
            data_blocks.append({
                "agent": agent_intent.agent_name,
                "content": result,
                "reason": agent_intent.reason,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    # Then call notification with enriched context
    if notification_task:
        enriched_prompt = build_enriched_prompt(notification_task, data_blocks)
        result = await call_a2a(notification_endpoint, enriched_prompt)
```

#### Parallel Execution
```python
else:
    print("[ORCHESTRATOR] Executing N agents in PARALLEL")
    
    tasks = [
        call_a2a(endpoints[agent.agent_name], agent.targeted_prompt)
        for agent in non_notification_agents
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            data_blocks.append({"agent": agents[i].agent_name, "error": str(result)})
        else:
            data_blocks.append({"agent": agents[i].agent_name, "content": result})
```

### Context Enrichment

**Purpose**: Pass data from earlier agents to later agents

**Format**:
```
Draft an email to vicveksr@gmail.com with a summary.

[Context from other agents:]
[Inventory Specialist:]
Found 2 product(s) matching 'pump'. Total quantity: 80 units.

- **Industrial Water Pump Model A** (SKU: PUMP-001)
  - Stock: 50 units
  - Price: $299.99
  - Category: Equipment
  - Location: Warehouse A

[Policy Expert:]
The return policy for equipment states that all company-issued 
equipment must be returned upon termination of employment...
```

**Benefits**:
- Notification agent has full context for email composition
- No need for agents to query each other directly
- Clear audit trail of information flow
- Supports complex multi-agent workflows

### Response Sanitization

**Purpose**: Clean agent responses before passing to next agent

**Implementation**:
```python
def _sanitize(text: str) -> str:
    # Remove common LLM refusals
    patterns = [
        "i cannot provide information",
        "i do not have access",
        "outside of my",
        "i cannot draft",
        "please contact"
    ]
    
    lines = []
    for ln in text.splitlines():
        if not any(p in ln.lower() for p in patterns):
            lines.append(ln)
    
    result = "\n".join(lines).strip()
    
    # Strip wrapping quotes from JSON-escaped responses
    if result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    
    return result
```

**Handles**:
- LLM refusal messages
- Unnecessary politeness
- JSON escaping artifacts
- Empty lines and whitespace

---

## Human-in-the-Loop (HITL) System

**File**: `orchestrator/hitl_manager.py`

### Architecture

**Session-Based State Management**:
```python
class HITLManager:
    def __init__(self):
        self.pending_approvals: Dict[str, PendingApproval] = {}
    
    def request_approval(self, session_id, action_type, action_data):
        self.pending_approvals[session_id] = PendingApproval(
            action_type=action_type,
            action_data=action_data,
            timestamp=datetime.utcnow()
        )
    
    def get_pending_approval(self, session_id):
        return self.pending_approvals.get(session_id)
    
    def clear_approval(self, session_id):
        del self.pending_approvals[session_id]
```

### Approval Workflow

**1. Agent Returns Draft**:
```python
# In notification agent
draft = compose_email_from_context(recipient, purpose, context)
return draft  # Contains approval instructions
```

**2. Orchestrator Detects HITL Need**:
```python
# In orchestrator routes
if "Reply 'yes' to approve" in response_text:
    hitl_manager.request_approval(
        session_id,
        action_type="email_send",
        action_data={
            "recipient": extract_recipient(response_text),
            "draft": response_text
        }
    )
    
    return {
        "response": response_text,
        "pending_approval": True,
        "approval_type": "email_send"
    }
```

**3. User Approves/Rejects**:
```python
# Next chat message in same session
if prompt.lower() in ["yes", "approve", "send"]:
    approval = hitl_manager.get_pending_approval(session_id)
    
    if approval.action_type == "email_send":
        # Execute the action
        result = send_email(approval.action_data)
        hitl_manager.clear_approval(session_id)
        return f"Approved! {result}"

elif prompt.lower() in ["no", "reject", "cancel"]:
    hitl_manager.clear_approval(session_id)
    return "Cancelled. The action was not executed."
```

### Security Considerations

**Session Isolation**: Each session has independent approval state

**Timeout**: Approvals expire after configurable duration (default: 30 minutes)

**Audit Trail**: All approval requests and responses logged

**Type Safety**: Action types validated via enum

---

## Observability & Metrics

**File**: `shared/agent_metrics.py`

### Agent Metrics System

**Purpose**: Track agent performance, reliability, and usage patterns

**Metrics Tracked**:
```python
class AgentMetrics:
    def __init__(self):
        self.agent_stats = defaultdict(lambda: {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_latency_ms": 0.0,
            "total_tokens": 0,
            "errors": []
        })
    
    def record_agent_call(
        self,
        agent_name: str,
        session_id: str,
        success: bool,
        latency_ms: float,
        token_count: int = 0,
        error: str = None
    ):
        stats = self.agent_stats[agent_name]
        stats["total_calls"] += 1
        
        if success:
            stats["successful_calls"] += 1
        else:
            stats["failed_calls"] += 1
            if error:
                stats["errors"].append({
                    "session_id": session_id,
                    "error": error,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        stats["total_latency_ms"] += latency_ms
        stats["total_tokens"] += token_count
```

**Derived Metrics**:
```python
def get_agent_stats(self, agent_name: str) -> dict:
    stats = self.agent_stats[agent_name]
    total = stats["total_calls"]
    
    return {
        "total_calls": total,
        "successful_calls": stats["successful_calls"],
        "failed_calls": stats["failed_calls"],
        "success_rate": stats["successful_calls"] / total if total > 0 else 0,
        "avg_latency_ms": stats["total_latency_ms"] / total if total > 0 else 0,
        "avg_tokens_per_call": stats["total_tokens"] / total if total > 0 else 0,
        "errors": stats["errors"][-10:]  # Last 10 errors
    }
```

**Metrics Endpoint**:
```http
GET /orchestrator/metrics

Response:
{
  "timestamp": "2025-11-21T12:33:49.505159",
  "agents": {
    "inventory_specialist": {
      "total_calls": 5,
      "successful_calls": 5,
      "failed_calls": 0,
      "success_rate": 1.0,
      "avg_latency_ms": 4735.23,
      "avg_tokens_per_call": 0,
      "errors": []
    },
    "policy_expert": {
      "total_calls": 3,
      "successful_calls": 3,
      "failed_calls": 0,
      "success_rate": 1.0,
      "avg_latency_ms": 8850.53,
      "avg_tokens_per_call": 0,
      "errors": []
    }
  }
}
```

### Logging Strategy

**Structured Logging**:
```python
import structlog

logger = structlog.get_logger()

# Contextual logs
logger.info(
    "agent_called",
    agent_name="inventory_specialist",
    session_id=session_id,
    latency_ms=latency,
    success=True
)
```

**Log Levels**:
- `DEBUG`: Detailed execution traces
- `INFO`: Agent calls, user interactions, approvals
- `WARNING`: Configuration issues, fallbacks
- `ERROR`: Agent failures, network errors, timeouts

**Log Output**:
```
2025-11-21T12:21:04.123456Z [info] agent_called agent_name=inventory_specialist session_id=test-123 latency_ms=4156.2 success=true
2025-11-21T12:21:08.987654Z [info] agent_called agent_name=notification_specialist session_id=test-123 latency_ms=3421.5 success=true
2025-11-21T12:21:09.012345Z [info] hitl_approval_requested session_id=test-123 action_type=email_send
```

### Health Check

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-21T12:33:49Z",
  "version": "1.0.0",
  "agents": {
    "orchestrator": "operational",
    "inventory": "operational",
    "policy": "operational",
    "notification": "operational"
  },
  "database": {
    "supabase": "connected"
  },
  "system": {
    "cpu_percent": 6.1,
    "memory_percent": 58.2
  }
}
```

---

## Testing & Validation

### Unit Tests

**File**: `test_runner.py`

**Coverage**:
- Intent classification parsing
- Agent response sanitization
- Email composition logic
- Inventory parsing (multi-line format)
- HITL workflow state transitions
- Metrics calculation

**Example Test**:
```python
def test_inventory_parsing():
    lines = [
        "**Industrial Water Pump Model A** (SKU: PUMP-001)",
        "Stock: 50 units",
        "Price: $299.99"
    ]
    
    result = _parse_inventory(lines)
    
    assert len(result) == 1
    assert result[0]["name"] == "Industrial Water Pump Model A"
    assert result[0]["sku"] == "PUMP-001"
    assert result[0]["qty"] == 50
    assert result[0]["price"] == 299.99
    assert result[0]["ext"] == 14999.50
```

### Integration Tests

**Single-Agent Workflow**:
```bash
# Test inventory retrieval
curl -X POST http://localhost:8000/orchestrator/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-1", "prompt": "What pumps do we have?"}'

# Expected: Inventory list with 2 pump models
```

**Multi-Agent Sequential Workflow**:
```bash
# Test inventory → email coordination
curl -X POST http://localhost:8000/orchestrator/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-2", "prompt": "Get pump inventory and draft email to test@example.com"}'

# Expected: pending_approval=true, draft email with inventory data
```

**HITL Approval Workflow**:
```bash
# Step 1: Get draft
curl -X POST http://localhost:8000/orchestrator/chat \
  -d '{"session_id": "test-3", "prompt": "Draft email..."}'

# Step 2: Approve
curl -X POST http://localhost:8000/orchestrator/chat \
  -d '{"session_id": "test-3", "prompt": "yes"}'

# Expected: "Approved! Email sent successfully"
```

**Multi-Agent Parallel Workflow**:
```bash
# Test independent queries
curl -X POST http://localhost:8000/orchestrator/chat \
  -d '{"session_id": "test-4", "prompt": "What pumps do we have and what is the return policy?"}'

# Expected: Both inventory and policy data in response
```

### Performance Testing

**Latency Benchmarks** (Average over 10 runs):
- Single-agent query: ~5-6 seconds
- Sequential 2-agent: ~12-15 seconds
- Parallel 2-agent: ~8-10 seconds
- Intent classification: ~2-3 seconds

**Load Testing**:
```bash
# 10 concurrent requests
ab -n 100 -c 10 -p payload.json -T application/json \
  http://localhost:8000/orchestrator/chat
```

**Expected Throughput**: ~10 requests/second (limited by LLM API)

### Validation Scripts

**Configuration Validation**:
```bash
python validate_config.py

# Checks:
# - Environment variables set
# - Database connectivity
# - SMTP credentials valid
# - Agent configurations parseable
```

**Database Seeding**:
```bash
# Seed inventory
python seed_inventory.py

# Seed policies
python seed_policies.py
```

---

## Configuration & Environment

### Environment Variables

**Required**:
```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_DB_URL=postgresql://postgres:[password]@db.xxx.supabase.co:5432/postgres

# Google AI
GOOGLE_API_KEY=your-gemini-api-key

# SMTP (Email)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-specific-password
FROM_EMAIL=your-email@gmail.com
```

**Optional**:
```env
# Server
HOST=0.0.0.0
PORT=8000

# Features
ENABLE_HITL=true
ENABLE_MEMORY=true
SESSION_PERSISTENCE=true

# Branding
COMPANY_NAME=Company
EMAIL_SIGNATURE=Best regards\nCompany
```

### Agent Configurations

**Format**: `agent.json` in each agent directory

**Example** (`agents/inventory/agent.json`):
```json
{
  "name": "inventory_specialist",
  "description": "Retrieves product inventory data from the database",
  "model": "gemini-2.5-flash-lite",
  "temperature": 0.1,
  "max_output_tokens": 2048,
  "tools": ["inventory_query_tool"],
  "capabilities": [
    "product_search",
    "stock_lookup",
    "price_inquiry",
    "location_filtering"
  ]
}
```

### Database Schema

**Inventory Table**:
```sql
CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    sku TEXT UNIQUE NOT NULL,
    category TEXT,
    price DECIMAL(10,2),
    stock_quantity INTEGER DEFAULT 0,
    location TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_inventory_name ON inventory(name);
CREATE INDEX idx_inventory_category ON inventory(category);
CREATE INDEX idx_inventory_sku ON inventory(sku);
```

**Policy Documents Table**:
```sql
CREATE TABLE policy_documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    metadata JSONB DEFAULT '{}',
    document_type TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_policy_embedding ON policy_documents 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX idx_policy_title ON policy_documents(title);
```

---

## API Reference

### Orchestrator Endpoints

#### Chat Endpoint
```http
POST /orchestrator/chat
Content-Type: application/json

{
  "session_id": "unique-session-id",
  "prompt": "What pumps do we have in stock?"
}

Response:
{
  "response": "We have two types of industrial water pumps...",
  "session_id": "unique-session-id",
  "trace_id": "success",
  "pending_approval": false,
  "approval_type": null
}
```

**With HITL**:
```http
Response:
{
  "response": "[DRAFT EMAIL]\nGenerated: 2025-11-21...",
  "session_id": "unique-session-id",
  "trace_id": "success",
  "pending_approval": true,
  "approval_type": "email_send"
}
```

#### Metrics Endpoint
```http
GET /orchestrator/metrics

Response:
{
  "timestamp": "2025-11-21T12:33:49.505159",
  "agents": {
    "inventory_specialist": {...},
    "policy_expert": {...},
    "notification_specialist": {...}
  }
}
```

#### Health Endpoint
```http
GET /health

Response:
{
  "status": "healthy",
  "timestamp": "2025-11-21T12:33:49Z",
  "agents": {...},
  "database": {...},
  "system": {...}
}
```

### Agent A2A Endpoints

**All agents expose**:
```http
POST /{agent_name}/a2a/interact
Content-Type: application/json

{
  "id": "uuid-v4",
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "configuration": {"acceptedOutputModes": [], "blocking": true},
    "message": {
      "kind": "message",
      "messageId": "uuid-v4",
      "role": "user",
      "parts": [{"kind": "text", "text": "query"}]
    }
  }
}
```

**Agent Endpoints**:
- `POST /inventory/a2a/interact`
- `POST /policy/a2a/interact`
- `POST /notification/a2a/interact`

---

## Performance Characteristics

### Latency Breakdown

**Single-Agent Query** (~5-6 seconds):
- Intent classification: 2-3s
- Agent processing: 2-3s
- Network overhead: <500ms

**Sequential Multi-Agent** (~12-15 seconds):
- Intent classification: 2-3s
- First agent: 4-5s
- Second agent: 4-5s
- Context enrichment: <500ms

**Parallel Multi-Agent** (~8-10 seconds):
- Intent classification: 2-3s
- Agents (parallel): 5-6s (longest agent wins)
- Result aggregation: <500ms

### Throughput

**Concurrent Requests**: 10-20 requests/second
- Limited by: LLM API rate limits
- Bottleneck: Gemini API calls
- Mitigation: Request queuing, caching (future)

**Database Performance**:
- Inventory queries: <100ms
- Policy vector search: <500ms
- Session operations: <50ms

### Resource Usage

**Memory**: 150-250 MB baseline
- Per session: ~5-10 MB
- Max concurrent sessions: 1000+

**CPU**: Low (<10% idle, <30% under load)
- Async I/O minimizes CPU usage
- Most time spent waiting for LLM API

**Network**: ~10-50 KB per request
- Inbound: User queries (small)
- Outbound: LLM API calls (larger)

---

## Production Considerations

### Deployment Checklist

**Infrastructure**:
- [ ] Provision PostgreSQL database (Supabase recommended)
- [ ] Configure vector extension (pgvector)
- [ ] Set up SMTP relay (Gmail, SendGrid, etc.)
- [ ] Obtain Gemini API key with sufficient quota
- [ ] Configure environment variables
- [ ] Set up process manager (systemd, PM2, Docker)

**Security**:
- [ ] Use app-specific SMTP passwords
- [ ] Rotate API keys regularly
- [ ] Enable HTTPS for all endpoints
- [ ] Implement rate limiting
- [ ] Add authentication middleware
- [ ] Sanitize all user inputs
- [ ] Enable CORS appropriately

**Monitoring**:
- [ ] Set up application logging (e.g., CloudWatch, Datadog)
- [ ] Configure metrics collection
- [ ] Set up alerting (latency spikes, error rates)
- [ ] Enable health check monitoring
- [ ] Track API quota usage

**Scaling**:
- [ ] Horizontal scaling: Multiple instances behind load balancer
- [ ] Database: Read replicas for inventory/policy queries
- [ ] Caching: Redis for frequent queries
- [ ] Queue: Celery/RQ for background tasks

### Error Handling Best Practices

**Circuit Breaker Pattern**:
```python
# Future enhancement
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
```

**Graceful Degradation**:
- If inventory agent fails → Return cached data or graceful error
- If policy agent fails → Fall back to keyword search
- If notification agent fails → Queue for retry

**Retry Strategies**:
- Exponential backoff: 1s, 2s, 4s, 8s
- Max retries: 3 attempts
- Retry only on transient errors (network, timeout)
- Don't retry on validation errors

### Maintenance

**Regular Tasks**:
- Weekly: Review error logs and metrics
- Monthly: Analyze agent performance trends
- Quarterly: Update dependencies and models
- Annually: Audit security configurations

**Database Maintenance**:
```sql
-- Vacuum and analyze
VACUUM ANALYZE inventory;
VACUUM ANALYZE policy_documents;

-- Rebuild vector index
REINDEX INDEX idx_policy_embedding;

-- Archive old sessions
DELETE FROM sessions WHERE created_at < NOW() - INTERVAL '30 days';
```

**Model Updates**:
- Monitor Gemini model releases
- Test new models in staging environment
- Gradual rollout with A/B testing
- Monitor latency and quality metrics

---

## Appendix

### Glossary

- **A2A Protocol**: Agent-to-Agent communication standard (JSON-RPC 2.0)
- **ADK**: Agent Development Kit (Google's framework)
- **HITL**: Human-in-the-Loop (approval workflows)
- **Intent Classification**: LLM-powered query routing
- **Context Enrichment**: Passing data between agents
- **pgvector**: PostgreSQL extension for vector similarity search

### Related Documentation

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [A2A Protocol Specification](https://google.github.io/adk-docs/a2a/intro/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Vector Documentation](https://supabase.com/docs/guides/ai)

### Troubleshooting

**Issue**: "Intent classification timeout"
- **Cause**: Gemini API slow or unavailable
- **Solution**: Check API quota, increase timeout, add retry logic

**Issue**: "Empty agent response"
- **Cause**: Agent tool failure or database connection issue
- **Solution**: Check logs, verify database connectivity, test agent in isolation

**Issue**: "Email not sending"
- **Cause**: SMTP credentials invalid or network blocked
- **Solution**: Verify SMTP settings, check firewall, use app-specific password

**Issue**: "High latency on parallel execution"
- **Cause**: One slow agent blocking completion
- **Solution**: Add per-agent timeouts, implement circuit breakers

---

## Changelog

### Version 1.0.0 (2025-11-21)
- Initial production release
- Multi-agent coordination with sequential and parallel modes
- HITL approval workflows
- Agent metrics and observability
- Comprehensive email composition with inventory parsing
- Policy semantic search with pgvector
- Retry logic and timeout handling
- Production-ready error handling and logging

---

**Document Prepared By**: Olamide Oso 
**Last Review Date**: November 21, 2025  
**Next Review Date**: -
