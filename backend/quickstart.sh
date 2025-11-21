#!/bin/bash


echo " Starting Enterprise Agents Platform Setup..."
echo ""

if [ ! -f "main.py" ]; then
    echo " Error: Please run this script from the backend directory"
    exit 1
fi

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo "Error: .env file not found in parent directory"
    echo "   Please copy .env.example to .env and configure it"
    exit 1
fi

echo " Environment file found"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo " Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo " Installing Python dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo " Dependencies installed"
else
    echo " Some dependencies may have had issues - check output above"
fi

# Check if Node.js is installed
if command -v npm &> /dev/null; then
    echo " Node.js found"
    
    # Check if MCP PostgreSQL server is installed
    if npm list -g @modelcontextprotocol/server-postgres &> /dev/null; then
        echo " MCP PostgreSQL server already installed"
    else
        echo " Installing MCP PostgreSQL server..."
        npm install -g @modelcontextprotocol/server-postgres
    fi
else
    echo " Node.js not found - MCP PostgreSQL server won't work"
    echo "   Install Node.js from: https://nodejs.org/"
fi

echo ""
echo "=" | tr '\n' '=' | head -c 80
echo ""
echo " Setup Complete!"
echo ""
echo " IMPORTANT: Before starting, make sure you've set your SMTP_PASSWORD in .env"
echo "   For Gmail, use an App Password: https://support.google.com/accounts/answer/185833"
echo ""
echo "To start the platform:"
echo "  python main.py"
echo ""
echo "Or with auto-reload for development:"
echo "  uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "Then visit:"
echo "  http://localhost:8000       - Platform status"
echo "  http://localhost:8000/docs  - API documentation"
echo "  http://localhost:8000/health - Health check"
echo ""
echo "=" | tr '\n' '=' | head -c 80
echo ""
