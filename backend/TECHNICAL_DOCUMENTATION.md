# Enterprise Agents Platform - Backend Technical Documentation

**Version:** 1.1.0  
**Last Updated:** November 22, 2025  
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

- **Six Specialized Agents**: Orchestrator + Inventory + Policy + Notification + Analytics + Orders
- **Intelligent Intent Classification**: LLM-powered routing to appropriate specialized agents
- **Multi-Agent Coordination**: Sequential and parallel execution strategies with context enrichment
- **Human-in-the-Loop**: Secure approval workflows for high-stakes actions (email sending, data modifications)
- **Production Observability**: Real-time metrics, latency tracking, and error monitoring
- **Graceful Degradation**: Retry logic, timeout handling, and error recovery mechanisms
- **REST API Integration**: Supabase PostgREST for direct database access without connection pooling issues

### Design Philosophy

1. **Agent Specialization**: Each agent handles a specific domain (inventory, policy, notifications, analytics, orders)
2. **Context Propagation**: Rich context passed between agents for informed decision-making
3. **Deterministic Behavior**: Predictable workflows with clear audit trails
4. **Developer Experience**: Clean abstractions, comprehensive logging, easy debugging
5. **API-First Database Access**: Supabase REST API (PostgREST) for reliable, scalable database operations

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
  - Order tracking and supplier management
  - Session persistence (optional)
- **Supabase REST API (PostgREST)**: HTTP-based database access
  - No connection pooling issues
  - Auto-generated RESTful endpoints
  - Built-in filtering and pagination
  - Row-level security support
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

### 2. Database Access Strategy: Direct PostgreSQL vs REST API

**Decision**: Migrate from direct PostgreSQL connections (psycopg2) to Supabase REST API (PostgREST)

**Background**: The platform initially used direct PostgreSQL connections via psycopg2 for all database operations. During a Supabase maintenance window (Nov 21-23, 2025), we discovered that direct database port access (5432) was restricted while the REST API remained fully operational. This prompted a strategic evaluation of database access patterns.

**Issues with Direct PostgreSQL Connections**:

1. **Connection Pooling Complexity**
   - Required manual connection pool management
   - Connection exhaustion under concurrent load
   - Complex retry logic for connection failures
   - `psycopg2.OperationalError` during maintenance windows

2. **Maintenance Window Impact**
   - Direct port 5432 access blocked during Supabase maintenance
   - Complete service outage for database operations
   - No graceful degradation path
   - Emergency fixes required during critical periods

3. **Deployment Constraints**
   - Firewall rules needed for port 5432
   - SSL/TLS certificate management
   - Connection string security concerns
   - Limited horizontal scaling options

4. **Query Construction**
   - Manual SQL query building
   - Risk of SQL injection if not parameterized
   - Complex filter logic for dynamic queries
   - Limited type safety

**Benefits of Supabase REST API (PostgREST)**:

1. **High Availability**
   - REST API remains operational during maintenance
   - Built-in load balancing and failover
   - No connection pool exhaustion
   - HTTP-level retries and timeouts

2. **Developer Experience**
   ```python
   # Before (psycopg2)
   conn = psycopg2.connect(DATABASE_URL)
   cursor = conn.cursor()
   try:
       cursor.execute("""
           SELECT * FROM inventory 
           WHERE name ILIKE %s AND quantity > %s
           ORDER BY name ASC
           LIMIT 10
       """, (f'%{term}%', threshold))
       results = cursor.fetchall()
   finally:
       cursor.close()
       conn.close()
   
   # After (REST API)
   results = client.query(
       "inventory",
       select="*",
       filters={
           "name": f"ilike.*{term}*",
           "quantity": f"gt.{threshold}"
       },
       order="name.asc",
       limit=10
   )
   ```

3. **Simplified Architecture**
   - No connection pool management
   - Automatic request queuing
   - Built-in timeout handling
   - Stateless HTTP calls

4. **Security & Compliance**
   - Row-level security enforced at API level
   - API keys instead of database credentials
   - Rate limiting built-in
   - Audit logging via HTTP access logs

5. **PostgREST Features**
   - Auto-generated endpoints for all tables
   - Rich filtering syntax (eq, lt, gt, ilike, like, in, not)
   - JSON aggregation and joins
   - Full-text search support
   - Stored procedure execution via /rpc

**REST API Implementation**:

Created `shared/supabase_client.py` with full PostgREST support:

```python
class SupabaseClient:
    def query(self, table, select="*", filters=None, order=None, limit=None):
        """
        Query table with PostgREST filters
        
        Examples:
        - filters={"name": "ilike.*pump*"}  # Case-insensitive search
        - filters={"quantity": "lt.10"}      # Less than 10
        - filters={"status": "eq.active"}    # Exact match
        """
        url = f"{self.base_url}/rest/v1/{table}"
        params = {"select": select}
        
        if filters:
            for key, value in filters.items():
                params[key] = value
        
        if order:
            params["order"] = order
        
        if limit:
            params["limit"] = limit
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def insert(self, table, data):
        """Insert single row with automatic ID generation"""
        url = f"{self.base_url}/rest/v1/{table}"
        headers = {**self.headers, "Prefer": "return=representation"}
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def update(self, table, filters, data):
        """Update rows matching filters"""
        url = f"{self.base_url}/rest/v1/{table}"
        params = filters
        response = requests.patch(url, headers=self.headers, params=params, json=data)
        response.raise_for_status()
        return response.json()
    
    def rpc(self, function_name, params):
        """Call PostgreSQL stored procedures"""
        url = f"{self.base_url}/rest/v1/rpc/{function_name}"
        response = requests.post(url, headers=self.headers, json=params)
        response.raise_for_status()
        return response.json()
```

**Migration Results**:

- **Zero connection failures** post-migration
- **Maintained during maintenance** windows without downtime
- **Simplified codebase**: Removed 200+ lines of connection management code
- **Consistent performance**: 100% success rate on database operations
- **All agents migrated**: Inventory (3 tools), Analytics (6 tools), Orders (6 tools)

**Performance Comparison**:

| Operation | psycopg2 | REST API | Change |
|-----------|----------|----------|--------|
| Simple query | 45ms | 52ms | +7ms (15%) |
| Complex filter | 120ms | 110ms | -10ms (-8%) |
| Bulk insert | 230ms | 250ms | +20ms (9%) |
| Connection setup | 150ms | 0ms | -150ms (eliminated) |

**Trade-offs Accepted**:

- Slight latency increase for simple queries (+7ms average)
- Limited to Supabase/PostgREST ecosystem
- Cannot use PostgreSQL-specific features not exposed via REST API
- Dependency on Supabase service availability

**Conclusion**: The Supabase REST API migration improved system reliability, eliminated connection management complexity, and provided better resilience during maintenance windows. The minimal performance overhead (7-20ms) is acceptable given the operational benefits. This architectural decision prioritizes availability and developer experience over raw performance.

---

### 3. Modular Monolith Architecture

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
│   │   ├── agent.json       # A2A agent card metadata
│   │   ├── routes.py        # A2A interaction endpoint
│   │   └── inventory_query_tool.py  # REST API queries
│   ├── policy/               # Policy document search
│   │   ├── agent.py
│   │   ├── agent.json
│   │   ├── routes.py
│   │   ├── policy_search_tool.py
│   │   └── mcp_server.py    # MCP implementation (unused in prod)
│   ├── notification/         # Email drafting & sending
│   │   ├── agent.py
│   │   ├── agent.json
│   │   ├── routes.py
│   │   ├── email_draft_tool.py
│   │   └── mcp_server.py    # MCP implementation (unused in prod)
│   ├── analytics/            # Business intelligence & reporting
│   │   ├── agent.py
│   │   ├── agent.json
│   │   ├── routes.py
│   │   └── analytics_tools.py  # Trend analysis, forecasting, anomaly detection
│   └── orders/               # Procurement & supplier management
│       ├── agent.py
│       ├── agent.json
│       ├── routes.py
│       └── order_tools.py   # PO creation, tracking, EOQ calculations
└── shared/                    # Cross-cutting concerns
    ├── agent_metrics.py      # Observability metrics
    └── supabase_client.py    # REST API database client
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

### Analytics Agent

**Purpose**: Business intelligence, data analysis, and inventory optimization

**Data Source**: Supabase REST API for inventory queries

**Capabilities**:
- Inventory trend analysis (fast/slow moving products)
- Inventory valuation with category breakdowns
- Sales forecasting with reorder recommendations
- Performance reporting with KPIs
- Category comparison analysis
- Statistical anomaly detection

**Tools**: `analytics_tools.py` (6 functions)

1. **get_inventory_trends(days: int)**
   - Analyzes product turnover patterns
   - Identifies fast movers (>1.5× average) and slow movers (<0.3× average)
   - Calculates mean and median stock levels
   - Returns prioritized recommendations

2. **calculate_inventory_value(category: Optional[str])**
   - Computes total inventory value (quantity × price)
   - Breaks down by category with percentages
   - Lists top 5 items by value
   - Provides executive summary with metrics

3. **generate_sales_forecast(product_sku: str, horizon_days: int)**
   - Generates demand forecasts using EOQ models
   - Calculates reorder points and safety stock
   - Recommends optimal order quantities
   - Estimates next order date

4. **generate_performance_report(metric_type: str, date_range: Optional[str])**
   - Produces comprehensive KPI reports
   - Tracks fill rate, stockout count, turnover ratio
   - Analyzes category distribution
   - Highlights performance trends

5. **compare_categories(category_a: str, category_b: str)**
   - Side-by-side category comparison
   - Metrics: SKU count, total units, inventory value, avg price
   - Percentage differences calculated
   - Strategic recommendations included

6. **detect_inventory_anomalies(metric: str)**
   - Statistical outlier detection using 2σ threshold
   - Analyzes stock levels and pricing
   - Identifies data quality issues
   - Flags items requiring attention

**Example Query → Response**:
- Input: "Analyze pump inventory trends"
- Processing: Fetches all inventory, calculates statistics, identifies outliers
- Output: "Temperature Sensor identified as fast mover (5× avg turnover). Control Panel is slow mover (<0.5× avg). Recommend reviewing pricing strategy."

**Agent Card** (`.well-known/agent-card.json`):
```json
{
  "name": "analytics_specialist",
  "version": "1.0.0",
  "description": "Business intelligence and data analysis agent...",
  "capabilities": {
    "reasoning": "high",
    "tools": ["get_inventory_trends", "calculate_inventory_value", ...]
  },
  "skills": [
    {
      "id": "inventory_trend_analysis",
      "name": "get_inventory_trends",
      "description": "Analyze inventory turnover trends...",
      "tags": ["analytics", "trends", "business-intelligence"]
    },
    ...
  ]
}
```

**Configuration**:
```json
{
  "model": "gemini-2.5-flash-lite",
  "temperature": 0.1,
  "tools": ["get_inventory_trends", "calculate_inventory_value", 
            "generate_sales_forecast", "generate_performance_report",
            "compare_categories", "detect_inventory_anomalies"]
}
```

**Performance**:
- Trend analysis: ~3-4 seconds
- Valuation calculations: ~2-3 seconds
- Anomaly detection: ~4-5 seconds

### Orders Agent

**Purpose**: Procurement management, supplier operations, and order tracking

**Data Source**: Supabase REST API (inventory, suppliers, purchase_orders tables)

**Capabilities**:
- Purchase order creation with automatic calculations
- Supplier catalog queries and product availability
- Order status tracking with delivery information
- Intelligent reorder suggestions based on thresholds
- Supplier compliance validation (certifications, audits, ratings)
- Economic Order Quantity (EOQ) optimization

**Tools**: `order_tools.py` (6 functions)

1. **create_purchase_order(supplier: str, items_json: str, delivery_date: str)**
   - Parses JSON item list (SKU, quantity)
   - Queries inventory for current pricing via REST API
   - Generates unique PO number (PO-YYYYMMDD-XXXX)
   - Calculates line items and totals
   - Returns formatted PO draft for review

2. **check_supplier_catalog(supplier_name: str, product_type: Optional[str])**
   - Filters inventory by supplier name (via ilike search)
   - Optional category filtering
   - Returns product availability, pricing, stock levels
   - Formats as professional catalog listing

3. **track_order_status(po_number: str)**
   - Queries purchase_orders table via REST API
   - Retrieves order status, delivery date, tracking number
   - Joins with suppliers table for vendor details
   - Formats comprehensive tracking report with items and totals

4. **get_reorder_suggestions(threshold: int)**
   - Identifies products below stock threshold
   - Uses REST API with `lt.{threshold}` filter
   - Calculates suggested order quantity (2× current deficit)
   - Prioritizes by stock urgency
   - Returns formatted reorder recommendations

5. **validate_supplier_compliance(supplier_id: str)**
   - Accepts supplier ID or name (flexible search)
   - Retrieves compliance status, last audit date, rating
   - Parses JSONB certifications field
   - Calculates days since last audit
   - Provides compliance recommendations (approve/caution/reject)

6. **calculate_optimal_order_quantity(sku: str)**
   - Implements full EOQ formula: √((2 × D × S) / H)
   - D = estimated annual demand
   - S = fixed ordering cost ($50 default)
   - H = holding cost (25% of unit cost per year)
   - Calculates orders per year, total costs
   - Provides actionable procurement recommendations

**Database Schema Requirements**:

```sql
CREATE TABLE suppliers (
    supplier_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    address TEXT,
    compliance_status VARCHAR(50) DEFAULT 'active',
    last_audit_date DATE,
    certifications JSONB DEFAULT '[]',
    rating DECIMAL(3,2) DEFAULT 5.0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE purchase_orders (
    po_id SERIAL PRIMARY KEY,
    po_number VARCHAR(100) UNIQUE NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(supplier_id),
    order_date DATE NOT NULL,
    delivery_date DATE,
    status VARCHAR(50) DEFAULT 'draft',
    items JSONB NOT NULL,
    subtotal DECIMAL(12,2),
    tax DECIMAL(12,2),
    total_amount DECIMAL(12,2),
    tracking_number VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Example Query → Response**:
- Input: "Track order PO-20251110-0002"
- Processing: REST API query to purchase_orders with filters, join supplier data
- Output: "Order PO-20251110-0002 shipped by Global Parts Distributor, expected Nov 23, tracking TRK-9876543210, 100 units Replacement Filter Kit, total $1,726.92"

**Agent Card** (`.well-known/agent-card.json`):
```json
{
  "name": "order_specialist",
  "version": "1.0.0",
  "description": "Order management and procurement agent...",
  "capabilities": {
    "reasoning": "high",
    "tools": ["create_purchase_order", "check_supplier_catalog", ...]
  },
  "skills": [
    {
      "id": "purchase_order_creation",
      "name": "create_purchase_order",
      "description": "Create purchase orders with supplier and item details...",
      "tags": ["orders", "procurement", "po"]
    },
    ...
  ]
}
```

**Configuration**:
```json
{
  "model": "gemini-2.5-flash-lite",
  "temperature": 0.2,
  "tools": ["create_purchase_order", "check_supplier_catalog",
            "track_order_status", "get_reorder_suggestions",
            "validate_supplier_compliance", "calculate_optimal_order_quantity"]
}
```

**Performance**:
- PO creation: ~3-4 seconds
- Order tracking: ~2-3 seconds  
- EOQ calculations: ~3-4 seconds
- Compliance validation: ~2-3 seconds

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

**Example 2: Analytics with Procurement**
```json
{
  "summary": "Analyze inventory trends and create reorder suggestions",
  "agents_needed": [
    {
      "agent_name": "analytics_specialist",
      "targeted_prompt": "Analyze inventory trends for slow-moving items",
      "reason": "Need to identify products requiring restocking"
    },
    {
      "agent_name": "order_specialist",
      "targeted_prompt": "Generate reorder suggestions for items below threshold 10",
      "reason": "Create actionable procurement recommendations"
    }
  ],
  "requires_coordination": true
}
```

**Example 3: Supplier Compliance Check Before PO**
```json
{
  "summary": "Validate supplier compliance and create purchase order",
  "agents_needed": [
    {
      "agent_name": "order_specialist",
      "targeted_prompt": "Check compliance status for Acme Industrial Supplies",
      "reason": "Verify supplier meets requirements"
    },
    {
      "agent_name": "order_specialist",
      "targeted_prompt": "Create PO for Acme with items: [{\"sku\":\"PUMP-001\",\"quantity\":50}]",
      "reason": "Generate purchase order after compliance verification"
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
    
    # Execute all data agents first (inventory, analytics, orders, policy)
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

[Analytics Specialist:]
Trend Analysis (30 days): PUMP-001 identified as fast-moving item 
(2.5× average turnover). Recommend increasing safety stock to 75 units.

[Orders Specialist:]
Reorder suggestion: Order 25 additional units of PUMP-001 to reach 
optimal stock level. Estimated cost: $7,499.75. Supplier: Acme 
Industrial Supplies (rating: 4.8/5.0, compliant).
```

**Benefits**:
- Notification agent has full context for email composition
- Analytics insights inform procurement decisions
- No need for agents to query each other directly
- Clear audit trail of information flow
- Supports complex multi-agent workflows (6+ agent coordination)

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
- `POST /inventory/a2a/interact` - Inventory queries and stock management
- `POST /policy/a2a/interact` - Policy document retrieval and Q&A
- `POST /notification/a2a/interact` - Email composition and delivery
- `POST /analytics/a2a/interact` - Business intelligence and data analysis
- `POST /orders/a2a/interact` - Procurement and supplier management

**Agent Card Discovery** (A2A Protocol):
- `GET /inventory/.well-known/agent-card.json`
- `GET /policy/.well-known/agent-card.json`
- `GET /notification/.well-known/agent-card.json`
- `GET /analytics/.well-known/agent-card.json`
- `GET /orders/.well-known/agent-card.json`

---

## Performance Characteristics

### Latency Breakdown

**Single-Agent Query** (~4-6 seconds):
- Intent classification: 2-3s
- Agent processing: 2-3s
- Network overhead: <500ms

**Sequential Multi-Agent** (~12-18 seconds):
- Intent classification: 2-3s
- First agent: 4-6s
- Second agent: 4-6s
- Context enrichment: <500ms
- Example: Analytics → Orders coordination

**Parallel Multi-Agent** (~8-10 seconds):
- Intent classification: 2-3s
- Agents (parallel): 5-6s (longest agent wins)
- Result aggregation: <500ms

**Agent-Specific Performance**:
- Inventory queries: 2-3s (simple REST API calls)
- Policy search: 4-5s (vector embeddings + retrieval)
- Notification composition: 3-4s (email drafting)
- Analytics aggregations: 4-7s (complex calculations, trend analysis)
- Orders EOQ calculations: 3-5s (formula-based optimization)

### Throughput

**Concurrent Requests**: 10-20 requests/second (6-agent system)
- Limited by: LLM API rate limits (Gemini)
- Bottleneck: Model API calls (not database)
- Mitigation: Request queuing, response caching (future)

**Database Performance** (Supabase REST API):
- Simple queries: <100ms (inventory, suppliers)
- Complex aggregations: 200-500ms (analytics)
- Vector search: <500ms (policy documents)
- Session operations: <50ms (orchestrator state)
- Write operations: <200ms (purchase orders, audit logs)

**REST API Benefits**:
- No connection pooling overhead
- Automatic HTTP/2 multiplexing
- Built-in request queuing
- Zero maintenance window disruptions

### Resource Usage

**Memory**: 180-300 MB baseline (6-agent system)
- Per session: ~5-10 MB (orchestrator state)
- Per agent instance: ~30-50 MB (model context)
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

### Version 1.1.0 (2025-11-22)
- **Major Architectural Change**: Migrated from psycopg2 to Supabase REST API (PostgREST)
  - Eliminated connection pooling complexity
  - Zero downtime during maintenance windows
  - Simplified deployment architecture
  - Improved developer experience with REST patterns
- **New Analytics Agent**: 6 tools for business intelligence
  - Inventory trend analysis (fast/slow movers)
  - Inventory valuation with category breakdowns
  - Sales forecasting with EOQ recommendations
  - Performance reporting (KPIs, fill rate, turnover)
  - Category comparison analysis
  - Statistical anomaly detection (2σ threshold)
- **New Orders Agent**: 6 tools for procurement management
  - Purchase order creation with automatic calculations
  - Supplier catalog queries
  - Order status tracking with delivery information
  - Intelligent reorder suggestions
  - Supplier compliance validation (certifications, audits)
  - Economic Order Quantity (EOQ) optimization
- **Database Enhancements**:
  - Added `suppliers` table (10 columns, compliance tracking)
  - Added `purchase_orders` table (13 columns, JSONB items)
  - Comprehensive indexes for performance
- **A2A Protocol Compliance**:
  - Fixed agent card endpoints (agent.json → agent-card.json)
  - Updated all agent.json files with complete A2A structure
  - Added skills array with detailed metadata
  - Proper capabilities declaration
- **System Expansion**:
  - Orchestrator now coordinates 5 specialist agents (was 3)
  - Updated intent classification for analytics and orders
  - Enhanced context enrichment for multi-agent workflows
  - Performance characteristics updated for 6-agent system

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
**Last Review Date**: November 22, 2025  
**Next Review Date**: -
