import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

def query_inventory(search_term: str) -> str:
    """
    Search inventory database for products matching the search term.
    
    Args:
        search_term: Product name, SKU, or category to search for
        
    Returns:
        Formatted string with product information
    """
    try:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: SUPABASE_DB_URL environment variable not configured. Please set it in your .env file."
        
        print(f"[INVENTORY TOOL] Connecting to database...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        print(f"[INVENTORY TOOL] Connected successfully, searching for: '{search_term}'")
        
        term = (search_term or "").strip().lower()
        patterns = set()
        if term:
            patterns.add(f"%{term}%")
            if term.endswith("s") and len(term) > 1:
                singular = term[:-1]
                patterns.add(f"%{singular}%")
            for tok in term.split():
                if tok:
                    patterns.add(f"%{tok}%")
                    if tok.endswith("s") and len(tok) > 1:
                        patterns.add(f"%{tok[:-1]}%")

        if not patterns:
            patterns.add("%%")

        col_exprs = [
            sql.SQL("LOWER(name) LIKE %s"),
            sql.SQL("LOWER(sku) LIKE %s"),
            sql.SQL("LOWER(category) LIKE %s"),
        ]
        per_col_groups = []
        for col_sql in col_exprs:
            group = sql.SQL(" OR ").join([col_sql] * len(patterns))
            per_col_groups.append(sql.SQL("(") + group + sql.SQL(")"))
        where_clause = sql.SQL(" OR ").join(per_col_groups)

        query = sql.SQL(
            """
            SELECT name, sku, quantity, price, category, location
            FROM inventory
            WHERE {where}
            ORDER BY quantity DESC
            LIMIT 10
            """
        ).format(where=where_clause)

        params = []
        for _ in col_exprs:
            params.extend(list(patterns))
        
        print(f"[INVENTORY TOOL] Executing query with {len(params)} parameters...")
        cur.execute(query, params)
        
        results = cur.fetchall()
        print(f"[INVENTORY TOOL] Found {len(results)} results")
        cur.close()
        conn.close()
        
        if not results:
            return f"No products found matching '{search_term}'. Try a different search term or check spelling."
        
        output = []
        total_quantity = 0
        
        for row in results:
            name, sku, quantity, price, category, location = row
            output.append(f"- **{name}** (SKU: {sku})")
            output.append(f"  - Stock: {quantity} units")
            output.append(f"  - Price: ${price:.2f}")
            output.append(f"  - Category: {category}")
            output.append(f"  - Location: {location}")
            output.append("")
            total_quantity += quantity
        
        summary = f"Found {len(results)} product(s) matching '{search_term}'. Total quantity: {total_quantity} units.\n\n"
        return summary + "\n".join(output)
        
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        print(f"[INVENTORY TOOL] Database connection error: {error_msg}")
        return f"Database connection error: Unable to connect to inventory database. Please check SUPABASE_DB_URL configuration. Details: {error_msg}"
    except psycopg2.Error as e:
        error_msg = str(e)
        print(f"[INVENTORY TOOL] Database query error: {error_msg}")
        return f"Database query error: {error_msg}"
    except Exception as e:
        error_msg = str(e)
        print(f"[INVENTORY TOOL] Unexpected error: {error_msg}")
        return f"Unexpected error while querying inventory: {error_msg}"


def get_all_categories() -> str:
    """
    Get list of all product categories in inventory.
    
    Returns:
        Formatted string with category list
    """
    try:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: Database connection not configured"
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT category, COUNT(*) as product_count, SUM(quantity) as total_units
            FROM inventory
            GROUP BY category
            ORDER BY category
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return "No categories found in inventory."
        
        output = ["**Inventory Categories:**\n"]
        for category, count, total in results:
            output.append(f"- {category}: {count} product(s), {total} total units")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Database error: {str(e)}"


def get_low_stock_products(threshold: int = 20) -> str:
    """
    Get products with stock levels below the threshold.
    
    Args:
        threshold: Minimum stock level (default: 20)
        
    Returns:
        Formatted string with low-stock products
    """
    try:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: Database connection not configured"
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT name, sku, quantity, category
            FROM inventory
            WHERE quantity < %s
            ORDER BY quantity ASC
        """, (threshold,))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return f"No products with stock below {threshold} units. All inventory levels are healthy."
        
        output = [f"**Low Stock Alert** (below {threshold} units):\n"]
        for name, sku, quantity, category in results:
            output.append(f"- {name} (SKU: {sku}): {quantity} units - Category: {category}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Database error: {str(e)}"
