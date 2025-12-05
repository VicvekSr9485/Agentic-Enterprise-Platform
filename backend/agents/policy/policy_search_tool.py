import os
from typing import List
import vecs
from google import genai
from dotenv import load_dotenv

load_dotenv()


def search_policy_documents(query: str) -> str:
    """
    Function tool for searching policy documents.
    This is the tool that will be registered with the agent.
    
    Args:
        query: The search query
        
    Returns:
        str: Policy search results
    """
    import vecs
    from google import genai
    import os
    
    try:
        # Validate environment variables
        db_url = os.getenv("SUPABASE_DB_URL")
        api_key = os.getenv("GOOGLE_API_KEY")
        
        if not db_url:
            return "Policy search is temporarily unavailable. Database connection not configured."
        
        if not api_key:
            return "Policy search is temporarily unavailable. API key not configured."
        
        # Connect to vector database
        vx_client = vecs.create_client(db_url)
        docs = vx_client.get_or_create_collection(
            name="policy_documents", 
            dimension=768
        )
        
        # Generate query embedding
        genai_client = genai.Client(api_key=api_key)
        embedding_response = genai_client.models.embed_content(
            model="text-embedding-004",
            contents=query
        )
        
        if not embedding_response or not embedding_response.embeddings:
            return "Unable to process search query. Please try rephrasing."
        
        embedding = embedding_response.embeddings[0].values
        
        # Perform vector search
        results = docs.query(
            data=embedding,
            limit=3,
            include_value=True,
            include_metadata=True
        )
        
        if not results:
            return "No policies found matching your query. Try using different keywords or ask about available policy categories."
        
        # Format results
        formatted_results = []
        for result in results:
            metadata = result[2] if len(result) > 2 else {}
            content = metadata.get('content', 'No content available')
            
            formatted_results.append(
                f"**{metadata.get('title', 'Company Policy')}**\n"
                f"Source: {metadata.get('filename', 'Internal Document')}\n"
                f"Category: {metadata.get('category', 'General')}\n\n"
                f"{content}\n"
            )
        
        return "\n---\n\n".join(formatted_results)
        
    except ConnectionError:
        return "Unable to connect to policy database. Please try again later."
    except TimeoutError:
        return "Policy search timed out. Please try again."
    except Exception:
        return "An error occurred while searching policies. Please contact support if this persists."
