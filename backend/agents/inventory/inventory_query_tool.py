import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.supabase_client import get_supabase_client, sanitize_filter_term
from shared.logging_utils import get_logger

logger = get_logger("agents.inventory.tool")


def query_inventory(search_term: str = "") -> str:
    """
    Search inventory database for products matching the search term.

    Args:
        search_term: Product name, SKU, or category. Empty string returns the
            top items across the catalogue (default), so callers asking for
            "all products" can call this with no argument.

    Returns:
        Formatted string with product information
    """
    try:
        logger.info("inventory_search", term=search_term[:80])
        client = get_supabase_client()

        term = sanitize_filter_term((search_term or "").strip().lower())
        
        # Build PostgREST filters for flexible search
        # PostgREST uses format: column=operator.value
        results = []
        
        if term:
            # Search across name, sku, and category using 'ilike' (case-insensitive LIKE)
            # Try multiple search patterns
            search_patterns = [term]
            
            # Add singular form if term ends with 's'
            if term.endswith("s") and len(term) > 1:
                search_patterns.append(term[:-1])
            
            # Search each pattern
            for pattern in search_patterns:
                try:
                    # Search by name
                    name_results = client.query(
                        "inventory",
                        select="name,sku,quantity,price,category,location",
                        filters={"name": f"ilike.*{pattern}*"},
                        order="quantity.desc",
                        limit=10
                    )
                    results.extend(name_results)
                    
                    # Search by SKU
                    sku_results = client.query(
                        "inventory",
                        select="name,sku,quantity,price,category,location",
                        filters={"sku": f"ilike.*{pattern}*"},
                        order="quantity.desc",
                        limit=10
                    )
                    results.extend(sku_results)
                    
                    # Search by category
                    cat_results = client.query(
                        "inventory",
                        select="name,sku,quantity,price,category,location",
                        filters={"category": f"ilike.*{pattern}*"},
                        order="quantity.desc",
                        limit=10
                    )
                    results.extend(cat_results)
                except Exception as e:
                    logger.warning("inventory_pattern_failed", pattern=pattern, error=str(e))
                    continue
        else:
            # No search term, return all products
            results = client.query(
                "inventory",
                select="name,sku,quantity,price,category,location",
                order="quantity.desc",
                limit=10
            )
        
        # Remove duplicates based on SKU
        seen_skus = set()
        unique_results = []
        for item in results:
            if item['sku'] not in seen_skus:
                seen_skus.add(item['sku'])
                unique_results.append(item)
        
        results = unique_results[:10]  # Limit to top 10

        logger.info("inventory_results", count=len(results))

        if not results:
            return f"No products found matching '{search_term}'. Try a different search term or check spelling."
        
        output = []
        total_quantity = 0
        
        for item in results:
            output.append(f"- **{item['name']}** (SKU: {item['sku']})")
            output.append(f"  - Stock: {item['quantity']} units")
            output.append(f"  - Price: ${float(item['price']):.2f}")
            output.append(f"  - Category: {item['category']}")
            output.append(f"  - Location: {item['location']}")
            output.append("")
            total_quantity += item['quantity']
        
        summary = f"Found {len(results)} product(s) matching '{search_term}'. Total quantity: {total_quantity} units.\n\n"
        return summary + "\n".join(output)
        
    except Exception as e:
        logger.warning("inventory_query_error", error=str(e))
        return f"Error querying inventory: {str(e)}"


def get_all_categories() -> str:
    """
    Get list of all product categories in inventory.
    
    Returns:
        Formatted string with category list
    """
    try:
        client = get_supabase_client()
        
        # Get all products to aggregate by category
        all_products = client.query(
            "inventory",
            select="category,quantity"
        )
        
        if not all_products:
            return "No categories found in inventory."
        
        # Aggregate by category
        category_stats = {}
        for item in all_products:
            cat = item['category']
            if cat not in category_stats:
                category_stats[cat] = {'count': 0, 'total_units': 0}
            category_stats[cat]['count'] += 1
            category_stats[cat]['total_units'] += item['quantity']
        
        # Sort by category name
        sorted_categories = sorted(category_stats.items())
        
        output = ["**Inventory Categories:**\n"]
        for category, stats in sorted_categories:
            output.append(f"- {category}: {stats['count']} product(s), {stats['total_units']} total units")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error retrieving categories: {str(e)}"


def get_low_stock_products(threshold: int = 20) -> str:
    """
    Get products with stock levels below the threshold.
    
    Args:
        threshold: Minimum stock level (default: 20)
        
    Returns:
        Formatted string with low-stock products
    """
    try:
        client = get_supabase_client()
        
        # Query products below threshold using PostgREST filter
        results = client.query(
            "inventory",
            select="name,sku,quantity,category",
            filters={"quantity": f"lt.{threshold}"},
            order="quantity.asc"
        )
        
        if not results:
            return f"No products with stock below {threshold} units. All inventory levels are healthy."
        
        output = [f"**Low Stock Alert** (below {threshold} units):\n"]
        for item in results:
            output.append(f"- {item['name']} (SKU: {item['sku']}): {item['quantity']} units - Category: {item['category']}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error retrieving low stock products: {str(e)}"
