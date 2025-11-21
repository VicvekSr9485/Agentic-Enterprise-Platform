import os
from typing import List
import vecs
from google import genai
from dotenv import load_dotenv

load_dotenv()

class PolicySearchTool:
    def __init__(self):
        self.vx_client = vecs.create_client(os.getenv("SUPABASE_DB_URL"))
        self.docs = self.vx_client.get_or_create_collection(
            name="policy_documents", 
            dimension=768
        )
        self.genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    async def search_policy_documents(self, query: str) -> str:
        """
        Search policy documents using semantic vector search.
        
        Args:
            query: The search query (e.g., "return policy for electronics")
            
        Returns:
            str: Formatted policy documents with sources
        """
        try:
            embedding = self.genai_client.models.embed_content(
                model="text-embedding-004",
                contents=query
            ).embeddings[0].values
            
            results = self.docs.query(
                data=embedding,
                limit=3,
                include_value=True,
                include_metadata=True
            )
            
            if not results:
                return "No specific policies found in the database for this query."
            
            formatted_results = []
            for result in results:
                metadata = result[2]
                content = metadata.get('content', '')
                
                formatted_results.append(
                    f"**{metadata.get('title', 'Unknown Policy')}**\n"
                    f"Source: {metadata.get('filename', 'N/A')}\n"
                    f"Category: {metadata.get('category', 'N/A')}\n\n"
                    f"{content}\n"
                )
            
            return "\n---\n\n".join(formatted_results)
            
        except Exception as e:
            return f"Error searching policies: {str(e)}"


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
        vx_client = vecs.create_client(os.getenv("SUPABASE_DB_URL"))
        docs = vx_client.get_or_create_collection(
            name="policy_documents", 
            dimension=768
        )
        genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        
        embedding = genai_client.models.embed_content(
            model="text-embedding-004",
            contents=query
        ).embeddings[0].values
        
        results = docs.query(
            data=embedding,
            limit=3,
            include_value=True,
            include_metadata=True
        )
        
        if not results:
            return "No specific policies found in the database for this query."
        
        formatted_results = []
        for result in results:
            metadata = result[2]
            content = metadata.get('content', '')
            
            formatted_results.append(
                f"**{metadata.get('title', 'Unknown Policy')}**\n"
                f"Source: {metadata.get('filename', 'N/A')}\n"
                f"Category: {metadata.get('category', 'N/A')}\n\n"
                f"{content}\n"
            )
        
        return "\n---\n\n".join(formatted_results)
        
    except Exception as e:
        return f"Error searching policies: {str(e)}"
