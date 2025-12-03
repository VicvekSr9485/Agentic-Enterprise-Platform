import os
import sys
import logging
from typing import List
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.models import InitializationOptions
import vecs
from google import genai
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='[POLICY MCP] %(message)s',
    stream=sys.stderr
)

load_dotenv()

try:
    vx_client = vecs.create_client(os.getenv("SUPABASE_DB_URL"))
    docs = vx_client.get_or_create_collection(name="policy_documents", dimension=768)
    genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    logging.info("Policy database and embedding client initialized")
except Exception as e:
    logging.error(f"Failed to initialize: {e}")
    raise

app = Server("policy_rag_server")

@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="search_policy_documents",
            description="Searches the internal policy database for relevant rules. Use this for questions about returns, HR, or compliance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g., 'return policy for electronics')"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> List[TextContent]:
    try:
        if name == "search_policy_documents":
            query_text = arguments.get("query", "")
            logging.info(f"Searching policies for: {query_text}")

            embedding = genai_client.models.embed_content(
                model="text-embedding-004",
                contents=query_text
            ).embeddings[0].values

            results = docs.query(
                data=embedding,
                limit=3,
                include_value=True,
                include_metadata=True
            )

            if not results:
                logging.info("No policy documents found, returning default")
                return [TextContent(
                    type="text", 
                    text="No specific policies found in the database. Please check with the policy administrator."
                )]

            context_str = "\n\n".join([
                f"Source: {r[2].get('filename', 'Policy DB')}\nContent: {r[1]}" 
                for r in results
            ])
            
            logging.info(f"Found {len(results)} policy documents")
            return [TextContent(type="text", text=context_str)]

        raise ValueError(f"Tool {name} not found")
    except Exception as e:
        logging.error(f"Error in call_tool: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return [TextContent(
            type="text",
            text=f"Error searching policies: {str(e)}"
        )]

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    import sys
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='[POLICY MCP] %(message)s',
        stream=sys.stderr
    )

    async def main():
        try:
            logging.info("Starting Policy RAG MCP Server")
            async with stdio_server() as (read, write):
                logging.info("MCP Server initialized successfully")
                init_options = InitializationOptions(
                    server_name="policy_rag_server",
                    server_version="1.0.0",
                    capabilities={
                        "tools": {}
                    }
                )
                await app.run(
                    read_stream=read,
                    write_stream=write,
                    initialization_options=init_options
                )
        except Exception as e:
            logging.error(f"MCP Server error: {e}")
            import traceback
            traceback.print_exc(file=sys.stderr)
            raise

    asyncio.run(main())