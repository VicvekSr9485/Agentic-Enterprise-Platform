import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import math

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.supabase_client import get_supabase_client


def create_purchase_order(supplier: str, items: str, delivery_date: str) -> str:
    """
    Create a purchase order with auto-calculated totals.
    
    Args:
        supplier: Supplier name or ID
        items: JSON string with items array [{"sku": "...", "quantity": ...}]
        delivery_date: Expected delivery date (YYYY-MM-DD format)
        
    Returns:
        Formatted purchase order
    """
    try:
        try:
            items_list = json.loads(items)
        except json.JSONDecodeError:
            return "Error: Items must be valid JSON array with format [{'sku': '...', 'quantity': ...}]"
        
        client = get_supabase_client()
        
        po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{hash(supplier) % 10000:04d}"
        order_items = []
        total_amount = 0
        
        for item in items_list:
            sku = item.get("sku")
            quantity = item.get("quantity", 0)
            
            if not sku or quantity <= 0:
                continue
            
            results = client.query(
                "inventory",
                select="name,price,category",
                filters={"sku": f"ilike.{sku}"}
            )
            
            if results:
                product = results[0]
                price = float(product['price'])
                line_total = price * quantity
                total_amount += line_total
                
                order_items.append({
                    "sku": sku,
                    "name": product['name'],
                    "quantity": quantity,
                    "unit_price": price,
                    "line_total": line_total,
                    "category": product['category']
                })
        
        if not order_items:
            return "Error: No valid items found for purchase order. Check SKUs and quantities."
        
        output = []
        output.append(f"PURCHASE ORDER: {po_number}")
        output.append(f"{'=' * 70}")
        output.append(f"Supplier: {supplier}")
        output.append(f"Order Date: {datetime.now().strftime('%Y-%m-%d')}")
        output.append(f"Expected Delivery: {delivery_date}")
        output.append(f"Status: DRAFT")
        output.append("")
        output.append("ITEMS:")
        output.append(f"{'SKU':<15} {'Name':<30} {'Qty':>6} {'Price':>10} {'Total':>12}")
        output.append("-" * 70)
        
        for item in order_items:
            output.append(
                f"{item['sku']:<15} {item['name']:<30} {item['quantity']:>6} "
                f"${item['unit_price']:>9.2f} ${item['line_total']:>11.2f}"
            )
        
        output.append("-" * 70)
        output.append(f"{'TOTAL AMOUNT':<53} ${total_amount:>15.2f}")
        output.append("")
        output.append("Notes:")
        output.append(f"  - This is a draft purchase order and requires approval")
        output.append(f"  - Total items: {len(order_items)}")
        output.append(f"  - Payment terms: Net 30")
        output.append(f"  - Shipping: To be determined")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error creating purchase order: {str(e)}"


def check_supplier_catalog(supplier_name: str, product_type: Optional[str] = None) -> str:
    """
    Query vendor availability and pricing from inventory.
    
    Args:
        supplier_name: Supplier name to query
        product_type: Optional product category filter
        
    Returns:
        Formatted supplier catalog information
    """
    try:
        client = get_supabase_client()
        
        if product_type:
            results = client.query(
                "inventory",
                select="name,sku,quantity,price,category,location",
                filters={"category": f"ilike.{product_type}"},
                order="price.asc",
                limit=20
            )
        else:
            results = client.query(
                "inventory",
                select="name,sku,quantity,price,category,location",
                order="category.asc,price.asc",
                limit=20
            )
        
        if not results:
            return f"No products found{f' in category {product_type}' if product_type else ''} for supplier {supplier_name}."
        
        categories = {}
        for item in results:
            cat = item['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        output = []
        output.append(f"SUPPLIER CATALOG: {supplier_name}")
        output.append(f"{'=' * 70}")
        if product_type:
            output.append(f"Product Category: {product_type}")
        output.append(f"Total Items: {len(results)}")
        output.append("")
        
        for category, items in sorted(categories.items()):
            output.append(f"Category: {category}")
            output.append(f"{'-' * 70}")
            for item in items:
                output.append(f"  {item['name']} (SKU: {item['sku']})")
                output.append(f"    Price: ${float(item['price']):.2f} | Stock: {item['quantity']} units | Location: {item['location']}")
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error checking supplier catalog: {str(e)}"


def track_order_status(po_number: str) -> str:
    """
    Track purchase order status and delivery information.
    
    Args:
        po_number: Purchase order number to track
        
    Returns:
        Formatted order tracking information
    """
    try:
        client = get_supabase_client()
        
        # Query purchase order with supplier information
        po_results = client.query(
            "purchase_orders",
            select="*",
            filters={"po_number": f"eq.{po_number}"}
        )
        
        if not po_results:
            return f"Purchase order '{po_number}' not found in the system."
        
        po = po_results[0]
        
        # Get supplier details
        supplier_results = client.query(
            "suppliers",
            select="name,contact_email,contact_phone",
            filters={"supplier_id": f"eq.{po['supplier_id']}"}
        )
        
        supplier_name = supplier_results[0]['name'] if supplier_results else "Unknown Supplier"
        
        output = []
        output.append(f"ORDER TRACKING: {po_number}")
        output.append(f"{'=' * 70}")
        output.append(f"Status: {po['status'].upper()}")
        output.append(f"Supplier: {supplier_name}")
        output.append(f"Order Date: {po['order_date']}")
        output.append(f"Expected Delivery: {po['delivery_date']}")
        
        if po.get('tracking_number'):
            output.append(f"Tracking Number: {po['tracking_number']}")
        
        output.append("")
        output.append("Order Items:")
        items = po['items'] if isinstance(po['items'], list) else []
        for item in items:
            output.append(f"  - {item.get('name', 'N/A')} (SKU: {item.get('sku', 'N/A')})")
            output.append(f"    Quantity: {item.get('quantity', 0)} @ ${item.get('unit_price', 0):.2f}")
        
        output.append("")
        output.append(f"Order Total: ${float(po['total_amount']):.2f}")
        
        if po.get('notes'):
            output.append(f"\nNotes: {po['notes']}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error tracking order: {str(e)}"


def get_reorder_suggestions(threshold: int = 10) -> str:
    """
    Generate reorder recommendations based on stock levels.
    
    Args:
        threshold: Stock level threshold to trigger reorder suggestion
        
    Returns:
        Formatted reorder recommendations
    """
    try:
        client = get_supabase_client()
        
        results = client.query(
            "inventory",
            select="name,sku,quantity,price,category",
            filters={"quantity": f"lt.{threshold}"},
            order="quantity.asc"
        )
        
        if not results:
            return f"No products below reorder threshold of {threshold} units. All stock levels are adequate."
        
        categories = {}
        total_reorder_cost = 0
        
        for item in results:
            cat = item['category']
            if cat not in categories:
                categories[cat] = []
            
            # Calculate suggested order quantity (2x threshold)
            suggested_qty = threshold * 2
            reorder_cost = suggested_qty * float(item['price'])
            total_reorder_cost += reorder_cost
            
            categories[cat].append({
                **item,
                "suggested_qty": suggested_qty,
                "reorder_cost": reorder_cost
            })
        
        output = []
        output.append(f"REORDER RECOMMENDATIONS")
        output.append(f"{'=' * 70}")
        output.append(f"Threshold: {threshold} units")
        output.append(f"Total Products Needing Reorder: {len(results)}")
        output.append(f"Estimated Total Cost: ${total_reorder_cost:,.2f}")
        output.append("")
        
        for category, items in sorted(categories.items()):
            output.append(f"Category: {category} ({len(items)} items)")
            output.append(f"{'-' * 70}")
            for item in items:
                output.append(f"  {item['name']} (SKU: {item['sku']})")
                output.append(f"    Current Stock: {item['quantity']} units")
                output.append(f"    Suggested Order: {item['suggested_qty']} units")
                output.append(f"    Unit Price: ${float(item['price']):.2f}")
                output.append(f"    Reorder Cost: ${item['reorder_cost']:,.2f}")
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error generating reorder suggestions: {str(e)}"


def validate_supplier_compliance(supplier_id: str) -> str:
    """
    Check supplier compliance status and certifications.
    
    Args:
        supplier_id: Supplier ID or name to validate
        
    Returns:
        Formatted compliance report
    """
    try:
        client = get_supabase_client()
        
        # Try to find supplier by ID or name
        filters = {}
        if supplier_id.isdigit():
            filters = {"supplier_id": f"eq.{supplier_id}"}
        elif supplier_id.startswith('SUP-'):
            # Handle potential SUP- prefix if used in future or legacy
            clean_id = supplier_id.replace('SUP-', '')
            if clean_id.isdigit():
                filters = {"supplier_id": f"eq.{clean_id}"}
            else:
                filters = {"supplier_id": f"eq.{supplier_id}"}
        else:
            filters = {"name": f"ilike.*{supplier_id}*"}
        
        supplier_results = client.query(
            "suppliers",
            select="*",
            filters=filters
        )
        
        if not supplier_results:
            return f"Supplier '{supplier_id}' not found in the system."
        
        supplier = supplier_results[0]
        
        output = []
        output.append(f"SUPPLIER COMPLIANCE VALIDATION: {supplier['name']}")
        output.append(f"{'=' * 70}")
        output.append(f"Supplier ID: {supplier['supplier_id']}")
        output.append(f"Compliance Status: {supplier['compliance_status'].upper()}")
        output.append(f"Rating: {float(supplier['rating']):.1f}/5.0")
        output.append("")
        
        # Last audit information
        if supplier.get('last_audit_date'):
            output.append(f"Last Audit: {supplier['last_audit_date']}")
            from datetime import datetime, date
            try:
                audit_date = datetime.strptime(supplier['last_audit_date'], '%Y-%m-%d').date()
                days_since = (date.today() - audit_date).days
                output.append(f"Days Since Audit: {days_since}")
                
                if days_since > 365:
                    output.append("⚠️  WARNING: Audit is overdue (>365 days)")
                elif days_since > 180:
                    output.append("ℹ️  NOTE: Audit should be scheduled soon (>180 days)")
            except:
                pass
        else:
            output.append("Last Audit: No audit on record")
            output.append("⚠️  WARNING: No compliance audit found")
        
        output.append("")
        
        # Certifications
        certifications = supplier.get('certifications', [])
        if certifications and isinstance(certifications, list) and len(certifications) > 0:
            output.append("Certifications:")
            for cert in certifications:
                output.append(f"  ✓ {cert}")
        else:
            output.append("Certifications: None on record")
            output.append("⚠️  WARNING: No certifications found")
        
        output.append("")
        output.append("Contact Information:")
        output.append(f"  Email: {supplier.get('contact_email', 'N/A')}")
        output.append(f"  Phone: {supplier.get('contact_phone', 'N/A')}")
        output.append(f"  Address: {supplier.get('address', 'N/A')}")
        
        # Compliance recommendation
        output.append("")
        if supplier['compliance_status'] == 'active' and supplier['rating'] >= 4.0:
            output.append("✓ RECOMMENDATION: Supplier meets compliance requirements")
        elif supplier['compliance_status'] == 'under_review':
            output.append("⚠️  RECOMMENDATION: Supplier under review - use caution for new orders")
        else:
            output.append("❌ RECOMMENDATION: Compliance issues detected - review required")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error validating supplier compliance: {str(e)}"


def calculate_optimal_order_quantity(sku: str) -> str:
    """
    Calculate Economic Order Quantity (EOQ) for optimal purchasing.
    
    Args:
        sku: Product SKU to calculate EOQ for
        
    Returns:
        Formatted EOQ calculation
    """
    try:
        client = get_supabase_client()
        
        results = client.query(
            "inventory",
            select="name,sku,quantity,price,category",
            filters={"sku": f"ilike.{sku}"}
        )
        
        if not results:
            return f"Product with SKU '{sku}' not found."
        
        item = results[0]
        current_stock = item['quantity']
        unit_cost = float(item['price'])
        
        # EOQ formula: sqrt((2 * annual_demand * order_cost) / holding_cost_per_unit)
        # Assumptions for calculation:
        estimated_annual_demand = max(current_stock * 12, 100)  # Estimate based on current stock
        order_cost = 50  # Fixed cost per order
        holding_cost_rate = 0.25  # 25% of unit cost per year
        holding_cost_per_unit = unit_cost * holding_cost_rate
        
        if holding_cost_per_unit > 0:
            eoq = math.sqrt((2 * estimated_annual_demand * order_cost) / holding_cost_per_unit)
            eoq = int(eoq)
        else:
            eoq = estimated_annual_demand // 12  # Fallback: monthly demand
        
        orders_per_year = estimated_annual_demand / eoq if eoq > 0 else 12
        total_ordering_cost = orders_per_year * order_cost
        avg_inventory = eoq / 2
        total_holding_cost = avg_inventory * holding_cost_per_unit
        total_cost = total_ordering_cost + total_holding_cost
        
        output = []
        output.append(f"ECONOMIC ORDER QUANTITY (EOQ) ANALYSIS")
        output.append(f"{'=' * 70}")
        output.append(f"Product: {item['name']} (SKU: {item['sku']})")
        output.append(f"Category: {item['category']}")
        output.append("")
        output.append("Current Situation:")
        output.append(f"  Current Stock: {current_stock} units")
        output.append(f"  Unit Cost: ${unit_cost:.2f}")
        output.append("")
        output.append("Assumptions:")
        output.append(f"  Estimated Annual Demand: {estimated_annual_demand:,.0f} units")
        output.append(f"  Order Cost: ${order_cost:.2f} per order")
        output.append(f"  Holding Cost Rate: {holding_cost_rate*100:.0f}% per year")
        output.append(f"  Holding Cost per Unit: ${holding_cost_per_unit:.2f}/year")
        output.append("")
        output.append("Optimal Order Strategy:")
        output.append(f"  Economic Order Quantity: {eoq} units")
        output.append(f"  Orders per Year: {orders_per_year:.1f}")
        output.append(f"  Days Between Orders: {365/orders_per_year:.0f} days")
        output.append("")
        output.append("Cost Analysis:")
        output.append(f"  Total Ordering Cost: ${total_ordering_cost:.2f}/year")
        output.append(f"  Total Holding Cost: ${total_holding_cost:.2f}/year")
        output.append(f"  Total Inventory Cost: ${total_cost:.2f}/year")
        output.append("")
        output.append("Recommendation:")
        if current_stock < eoq / 2:
            output.append(f" Current stock is below optimal level. Order {eoq} units.")
        elif current_stock > eoq * 2:
            output.append(f"  Current stock is above optimal level. Consider reducing next order.")
        else:
            output.append(f"  ✓ Stock level is within optimal range. Next order: {eoq} units.")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error calculating EOQ: {str(e)}"


def find_supplier_for_product(product_name_or_sku: str) -> str:
    """
    Find suppliers who provide a specific product based on purchase history.
    
    Args:
        product_name_or_sku: Product name or SKU to search for
        
    Returns:
        Formatted list of suppliers who have supplied this product
    """
    try:
        client = get_supabase_client()
        
        # 1. Identify the SKU
        sku = product_name_or_sku
        product_name = product_name_or_sku
        
        # Try to find product in inventory to get exact SKU and Name
        # Using a broad search first
        inventory_results = client.query(
            "inventory",
            select="name,sku",
            filters={
                "sku": f"ilike.{product_name_or_sku}"
            },
            limit=1
        )
        
        if not inventory_results:
             inventory_results = client.query(
                "inventory",
                select="name,sku",
                filters={
                    "name": f"ilike.%{product_name_or_sku}%"
                },
                limit=1
            )
        
        if inventory_results:
            sku = inventory_results[0]['sku']
            product_name = inventory_results[0]['name']
        
        # 2. Find Purchase Orders containing this SKU
        # Fetch recent POs and filter in Python to avoid complex JSONB query syntax issues
        po_results = client.query(
            "purchase_orders",
            select="supplier_id,items,order_date",
            order="order_date.desc",
            limit=50
        )
        
        supplier_ids = set()
        supplier_history = {} # supplier_id -> {last_price, last_date, total_supplied}
        
        for po in po_results:
            items = po.get('items', [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except:
                    continue
            
            for item in items:
                if item.get('sku') == sku:
                    sup_id = po['supplier_id']
                    supplier_ids.add(sup_id)
                    
                    if sup_id not in supplier_history:
                        supplier_history[sup_id] = {
                            'last_price': item.get('unit_price', 0),
                            'last_date': po['order_date'],
                            'total_supplied': 0
                        }
                    
                    supplier_history[sup_id]['total_supplied'] += item.get('quantity', 0)
                    # Update to most recent date/price if this PO is newer
                    if po['order_date'] > supplier_history[sup_id]['last_date']:
                         supplier_history[sup_id]['last_date'] = po['order_date']
                         supplier_history[sup_id]['last_price'] = item.get('unit_price', 0)

        if not supplier_ids:
            return f"No purchase history found for product '{product_name}' (SKU: {sku}). Cannot identify supplier."
            
        # 3. Get Supplier Details
        suppliers_info = []
        for sup_id in supplier_ids:
            sup_results = client.query(
                "suppliers",
                select="name,supplier_id,compliance_status,rating",
                filters={"supplier_id": f"eq.{sup_id}"}
            )
            if sup_results:
                sup = sup_results[0]
                hist = supplier_history.get(sup_id, {})
                suppliers_info.append({
                    **sup,
                    **hist
                })
        
        # Format Output
        output = []
        output.append(f"SUPPLIERS FOR: {product_name}")
        output.append(f"SKU: {sku}")
        output.append(f"{'=' * 70}")
        
        for sup in suppliers_info:
            output.append(f"Supplier: {sup['name']}")
            output.append(f"  ID: {sup['supplier_id']}")
            output.append(f"  Compliance: {sup['compliance_status'].upper()}")
            output.append(f"  Rating: {sup['rating']}/5.0")
            output.append(f"  Last Supplied: {sup.get('last_date', 'N/A')}")
            output.append(f"  Last Price: ${sup.get('last_price', 0):.2f}")
            output.append(f"  Total Supplied: {sup.get('total_supplied', 0)} units")
            output.append("-" * 30)
            
        return "\n".join(output)

    except Exception as e:
        return f"Error finding supplier: {str(e)}"
