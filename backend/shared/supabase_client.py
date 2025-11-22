"""
Supabase REST API client for reliable database access.

This module provides a wrapper around Supabase's REST API (PostgREST)
for querying and manipulating data. Using REST API instead of direct
PostgreSQL connections provides better reliability and follows Supabase
best practices.
"""

import os
import requests
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class SupabaseClient:
    """Client for interacting with Supabase REST API."""
    
    def __init__(self):
        """Initialize Supabase client with environment credentials."""
        self.base_url = os.getenv("SUPABASE_URL")
        self.api_key = os.getenv("SUPABASE_KEY")
        
        if not self.base_url or not self.api_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set in environment variables"
            )
        
        self.rest_url = f"{self.base_url}/rest/v1"
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    def query(
        self,
        table: str,
        select: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query data from a Supabase table.
        
        Args:
            table: Table name to query
            select: Columns to select (default: "*")
            filters: Dictionary of column filters (e.g., {"category": "eq.Equipment"})
            order: Column to order by (e.g., "quantity.desc")
            limit: Maximum number of rows to return
            offset: Number of rows to skip
            
        Returns:
            List of rows as dictionaries
            
        Raises:
            requests.HTTPError: If the request fails
        """
        url = f"{self.rest_url}/{table}"
        params = {"select": select}
        
        if filters:
            params.update(filters)
        
        if order:
            params["order"] = order
        
        if limit:
            params["limit"] = str(limit)
        
        if offset:
            params["offset"] = str(offset)
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Supabase query failed: {str(e)}")
    
    def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a single row into a table.
        
        Args:
            table: Table name
            data: Row data as dictionary
            
        Returns:
            Inserted row with generated fields
        """
        url = f"{self.rest_url}/{table}"
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result[0] if result else data
        except requests.RequestException as e:
            raise Exception(f"Supabase insert failed: {str(e)}")
    
    def insert_many(self, table: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Insert multiple rows into a table.
        
        Args:
            table: Table name
            data: List of row dictionaries
            
        Returns:
            List of inserted rows
        """
        url = f"{self.rest_url}/{table}"
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Supabase bulk insert failed: {str(e)}")
    
    def update(
        self,
        table: str,
        filters: Dict[str, Any],
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Update rows in a table matching filters.
        
        Args:
            table: Table name
            filters: Dictionary of column filters
            data: New values to set
            
        Returns:
            List of updated rows
        """
        url = f"{self.rest_url}/{table}"
        
        try:
            response = requests.patch(
                url,
                headers=self.headers,
                params=filters,
                json=data,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Supabase update failed: {str(e)}")
    
    def delete(self, table: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Delete rows from a table matching filters.
        
        Args:
            table: Table name
            filters: Dictionary of column filters
            
        Returns:
            List of deleted rows
        """
        url = f"{self.rest_url}/{table}"
        
        try:
            response = requests.delete(
                url,
                headers=self.headers,
                params=filters,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Supabase delete failed: {str(e)}")
    
    def rpc(self, function_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Call a Postgres function via RPC.
        
        Args:
            function_name: Name of the function to call
            params: Function parameters
            
        Returns:
            Function result
        """
        url = f"{self.rest_url}/rpc/{function_name}"
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=params or {},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Supabase RPC failed: {str(e)}")


# Global client instance
_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Get or create the global Supabase client instance."""
    global _client
    if _client is None:
        _client = SupabaseClient()
    return _client
