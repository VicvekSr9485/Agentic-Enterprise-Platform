# Enterprise Agents Platform

A production-ready Level 3 Modular Monolith Agent Swarm built with Google Agent Development Kit (ADK). This platform provides intelligent business workflow automation through specialized AI agents that communicate via the Agent-to-Agent (A2A) Protocol.

## Architecture Overview

The platform implements a hierarchical agent architecture with one orchestrator coordinating five specialized worker agents:

- **Orchestrator Agent**: Intelligent routing, multi-agent coordination, and context management with memory
- **Inventory Agent**: Product database queries, stock levels, pricing, and availability checks
- **Policy Agent**: RAG-powered policy document search, compliance verification, and regulatory guidance
- **Analytics Agent**: Business intelligence, trend analysis, sales forecasting, and performance reporting
- **Order Management Agent**: Purchase order creation, supplier management, procurement automation, and reorder recommendations
- **Notification Agent**: Email drafting and sending with Human-in-the-Loop (HITL) approval workflow

### Key Features

- **A2A Protocol**: All agents communicate via standardized Agent-to-Agent protocol
- **Session Persistence**: Conversation history maintained across sessions using SQLite
- **Memory Management**: Orchestrator maintains global context for improved coordination
- **HITL Workflow**: Critical actions require human approval before execution
- **Intent Classification**: LLM-based routing with 10-second timeout for reliability
- **Multi-Agent Coordination**: Sequential, parallel, iterative, and conditional execution strategies
- **Observability**: Comprehensive logging, metrics tracking, and error handling
- **Production Ready**: Rate limiting, health checks, CORS configuration, and structured error responses

## Technology Stack

### Backend
- **Framework**: FastAPI 0.115+
- **AI/ML**: Google Generative AI (Gemini 2.5 Flash Lite)
- **Agent Framework**: Google ADK (Agent Development Kit)
- **Database**: PostgreSQL (Supabase) for inventory/orders, SQLite for sessions
- **API Protocol**: A2A (Agent-to-Agent) via HTTP/JSON
- **Observability**: Structured logging, OpenTelemetry support

### Frontend
- **Framework**: React 18 with Vite
- **Styling**: Tailwind CSS with custom gradients
- **UI Components**: Custom-built responsive components
- **State Management**: React Hooks
- **Build Tool**: Vite for fast development and optimized production builds

## Quick Start with Docker

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Supabase account (for database)
- Google AI API key

### Environment Configuration

1. Create a `.env` file in the `backend/` directory:

```bash
# AI Configuration
GOOGLE_API_KEY=your_google_api_key_here

# Database Configuration
SUPABASE_DB_URL=postgresql://user:password@host:5432/dbname
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
SESSION_DB_URL=sqlite:///./sessions.db

# Server Configuration
BASE_URL=http://localhost:8000
PORT=8000
HOST=0.0.0.0
LOG_LEVEL=INFO

# Email Configuration (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com

# Feature Flags
ENABLE_HITL=true
ENABLE_SESSION_PERSISTENCE=true
ENABLE_MEMORY=true
ENABLE_RETRY_LOGIC=true
ENABLE_RATE_LIMITING=true

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Observability (Optional)
ENABLE_OTEL=false
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=enterprise-agents-platform
```

### Running with Docker

Build and start all services:

```bash
docker-compose up --build
```

Or run in detached mode:

```bash
docker-compose up -d
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Stopping Services

```bash
docker-compose down
```

To remove volumes as well:

```bash
docker-compose down -v
```

## Manual Installation

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables (see `.env` example above)

5. Initialize database:
```bash
python seed_inventory.py  # Seeds sample inventory data
```

6. Start the server:
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm run dev
```

4. Build for production:
```bash
npm run build
```

5. Preview production build:
```bash
npm run preview
```

## API Documentation

### Orchestrator Endpoints

- `POST /orchestrator/chat` - Main chat interface with intent classification and agent routing
- `GET /orchestrator/metrics` - Agent performance metrics and statistics

### Agent Endpoints

Each agent exposes:
- `POST /{agent}/a2a/interact` - A2A interaction endpoint
- `GET /{agent}/.well-known/agent.json` - Agent card for discovery
- `GET /{agent}/health` - Health check endpoint

Available agents: `/inventory`, `/policy`, `/analytics`, `/orders`, `/notification`

### System Endpoints

- `GET /` - Platform status overview
- `GET /health` - Kubernetes-style health check
- `GET /ready` - Readiness probe
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Agent Capabilities

### Inventory Agent
- Query products by name, SKU, or category
- Get all product categories with counts
- Find low-stock products below threshold
- Real-time stock level checks

### Policy Agent
- Semantic search across policy documents
- Return policy verification
- HR policy lookups
- Compliance and regulatory guidance

### Analytics Agent
- Inventory trend analysis (fast/slow movers)
- Inventory valuation with category breakdowns
- Sales forecasting and demand prediction
- Performance reporting and KPI generation
- Category comparison analysis
- Anomaly detection in stock levels and pricing

### Order Management Agent
- Purchase order creation with auto-calculated totals
- Supplier catalog queries
- Order status tracking with delivery estimates
- Intelligent reorder recommendations
- Supplier compliance validation
- Economic Order Quantity (EOQ) calculations

### Notification Agent
- Email drafting with context awareness
- HITL approval workflow for all sends
- Template-based email generation
- Rate limiting and safety checks

## Multi-Agent Workflows

The orchestrator supports complex workflows across multiple agents:

### Example: Complete Procurement Workflow
```
User: "Analyze inventory trends, recommend what to reorder, and email the purchase recommendations to procurement@company.com"

Orchestrator coordinates:
1. Analytics Agent: Analyzes trends and identifies low-stock items
2. Order Agent: Generates reorder recommendations with costs
3. Notification Agent: Drafts email with HITL approval
4. Returns: Comprehensive response with approval prompt
```

### Example: Data-Driven Decision Making
```
User: "Compare pump vs valve categories, forecast demand for PUMP-001, and create a purchase order if needed"

Orchestrator coordinates:
1. Analytics Agent: Compares categories and forecasts demand
2. Order Agent: Calculates optimal order quantity
3. Order Agent: Creates purchase order draft
4. Returns: Complete analysis with actionable PO
```

## Development

### Backend Development

Run tests:
```bash
pytest
```

Code formatting:
```bash
black .
```

Linting:
```bash
pylint backend/
```

### Frontend Development

Run linter:
```bash
npm run lint
```

Format code:
```bash
npm run format
```

Type checking (if TypeScript):
```bash
npm run type-check
```

## Production Deployment

### Backend Deployment Checklist

- Set `ENVIRONMENT=production` in `.env`
- Use production database credentials
- Configure proper CORS origins
- Enable rate limiting with appropriate limits
- Set up log aggregation (e.g., CloudWatch, Datadog)
- Configure health check endpoints for load balancer
- Use secrets manager for sensitive credentials
- Enable OpenTelemetry for observability
- Set up SSL/TLS certificates
- Configure firewall rules and IP whitelisting

### Frontend Deployment Checklist

- Build optimized production bundle: `npm run build`
- Serve static files via CDN (e.g., CloudFront, Vercel)
- Configure proper API base URL
- Enable HTTPS
- Set up caching headers
- Configure CSP (Content Security Policy)
- Enable compression (gzip/brotli)
- Set up monitoring and error tracking (e.g., Sentry)

### Docker Production Deployment

1. Build production images:
```bash
docker-compose build
```

2. Tag and push to registry:
```bash
docker tag enterprise-agents-platform-backend:latest your-registry/backend:latest
docker tag enterprise-agents-platform-frontend:latest your-registry/frontend:latest
docker push your-registry/backend:latest
docker push your-registry/frontend:latest
```

3. Deploy to orchestration platform (Kubernetes, ECS, etc.)

## Monitoring and Observability

### Health Checks

- Backend: `GET /health` - Returns system metrics (CPU, memory)
- Frontend: Health check via root path
- Individual agent health: `GET /{agent}/health`

### Metrics

Access orchestrator metrics:
```bash
curl http://localhost:8000/orchestrator/metrics
```

Returns:
- Success rate per agent
- Average latency
- Error counts and types
- Total requests processed

### Logs

Structured JSON logging enabled by default. Configure log level via `LOG_LEVEL` environment variable:
- `DEBUG`: Verbose logging including tool calls
- `INFO`: Standard operational logging
- `WARNING`: Warning messages and recoverable errors
- `ERROR`: Error conditions
- `CRITICAL`: Critical failures

## Troubleshooting

### Common Issues

**Database Connection Timeout**
- Verify `SUPABASE_DB_URL` is correct
- Check IP whitelist in Supabase dashboard
- Ensure database is not paused

**Agent Not Responding**
- Check agent health endpoint: `GET /{agent}/health`
- Verify API key is valid: `GOOGLE_API_KEY`
- Review logs for specific error messages

**HITL Approval Not Working**
- Ensure `ENABLE_HITL=true` in environment
- Check session persistence is enabled
- Verify session ID consistency across requests

**Frontend Cannot Connect to Backend**
- Verify CORS origins in backend `.env`
- Check backend is running on correct port
- Ensure API base URL is configured correctly in frontend

## License

Proprietary - All rights reserved

## Support

For issues, questions, or feature requests, please contact the development team or open an issue in the project repository.

## Acknowledgments

Built with Google Agent Development Kit (ADK) and powered by Gemini 2.5 Flash Lite models.
