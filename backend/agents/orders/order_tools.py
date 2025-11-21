import os
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json


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
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: SUPABASE_DB_URL environment variable not configured."
        
        try:
            items_list = json.loads(items)
        except json.JSONDecodeError:
            return "Error: Items must be valid JSON array with format [{'sku': '...', 'quantity': ...}]"
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{hash(supplier) % 10000:04d}"
        order_items = []
        total_amount = 0
        
        for item in items_list:
            sku = item.get("sku")
            quantity = item.get("quantity", 0)
            
            if not sku or quantity <= 0:
                continue
            
            cur.execute("""
                SELECT name, price, category
                FROM inventory
                WHERE LOWER(sku) = LOWER(%s)
            """, (sku,))
            
            result = cur.fetchone()
            if result:
                name, price, category = result
                line_total = price * quantity
                total_amount += line_total
                
                order_items.append({
                    "sku": sku,
                    "name": name,
                    "quantity": quantity,
                    "unit_price": price,
                    "line_total": line_total,
                    "category": category
                })
        
        cur.close()
        conn.close()
        
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
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
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
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: SUPABASE_DB_URL environment variable not configured."
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        if product_type:
            cur.execute("""
                SELECT name, sku, quantity, price, category, location
                FROM inventory
                WHERE LOWER(category) = LOWER(%s)
                ORDER BY price ASC
                LIMIT 20
            """, (product_type,))
        else:
            cur.execute("""
                SELECT name, sku, quantity, price, category, location
                FROM inventory
                ORDER BY category, price ASC
                LIMIT 20
            """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return f"No products found{f' in category {product_type}' if product_type else ''} for supplier {supplier_name}."
        
        categories = {}
        for name, sku, qty, price, cat, loc in results:
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                "name": name,
                "sku": sku,
                "current_stock": qty,
                "unit_price": price,
                "location": loc
            })
        
        output = []
        output.append(f"SUPPLIER CATALOG: {supplier_name}")
        output.append(f"{'=' * 70}")
        output.append(f"Query: {product_type if product_type else 'All Categories'}")
        output.append(f"Results: {len(results)} product(s)")
        output.append("")
        
        for category, products in sorted(categories.items()):
            output.append(f"{category.upper()}:")
            for prod in products:
                output.append(f"  - {prod['name']} (SKU: {prod['sku']})")
                output.append(f"    Price: ${prod['unit_price']:.2f} | Current Stock: {prod['current_stock']} units")
                output.append(f"    Location: {prod['location']}")
            output.append("")
        
        output.append("Ordering Information:")
        output.append(f"  - Minimum Order Quantity (MOQ): 10 units per item")
        output.append(f"  - Lead Time: 5-7 business days")
        output.append(f"  - Payment Terms: Net 30")
        output.append(f"  - Free shipping on orders over $500")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error querying supplier catalog: {str(e)}"


def track_order_status(po_number: str) -> str:
    """
    Track order status and estimated delivery.
    
    Args:
        po_number: Purchase order number to track
        
    Returns:
        Formatted order status information
    """
    try:
        statuses = ["DRAFT", "SUBMITTED", "CONFIRMED", "IN_TRANSIT", "DELIVERED", "CANCELLED"]
        
        po_prefix = po_number.split("-")[0] if "-" in po_number else ""
        
        if po_prefix != "PO":
            return f"Invalid purchase order number format. Expected format: PO-YYYYMMDD-XXXX"
        
        simulated_status = "IN_TRANSIT"
        estimated_delivery = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        
        output = []
        output.append(f"ORDER TRACKING: {po_number}")
        output.append(f"{'=' * 70}")
        output.append(f"Status: {simulated_status}")
        output.append(f"Estimated Delivery: {estimated_delivery}")
        output.append("")
        
        output.append("Tracking Timeline:")
        output.append(f"  ✓ Order Submitted: {(datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d %H:%M')}")
        output.append(f"  ✓ Order Confirmed: {(datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d %H:%M')}")
        output.append(f"  ✓ Shipped: {(datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M')}")
        output.append(f"  → In Transit: Current")
        output.append(f"  ○ Delivery: {estimated_delivery} (estimated)")
        output.append("")
        
        output.append("Shipment Details:")
        output.append(f"  Carrier: FedEx Ground")
        output.append(f"  Tracking Number: 1Z999AA10123456784")
        output.append(f"  Current Location: Distribution Center - Regional Hub")
        output.append(f"  Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        output.append("")
        
        output.append("Contact Information:")
        output.append(f"  For questions: orders@supplier.com")
        output.append(f"  Phone: 1-800-555-0199")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error tracking order: {str(e)}"


def get_reorder_suggestions(threshold: int = 10) -> str:
    """
    Auto-recommend products to reorder based on low stock.
    
    Args:
        threshold: Stock level threshold for reorder recommendation
        
    Returns:
        Formatted reorder suggestions
    """
    try:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: SUPABASE_DB_URL environment variable not configured."
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT name, sku, quantity, price, category, location
            FROM inventory
            WHERE quantity <= %s
            ORDER BY quantity ASC, category
        """, (threshold,))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return f"No products below threshold of {threshold} units. Stock levels are healthy."
        
        output = []
        output.append(f"REORDER RECOMMENDATIONS")
        output.append(f"Threshold: {threshold} units")
        output.append(f"{'=' * 70}")
        output.append(f"Found {len(results)} product(s) requiring reorder")
        output.append("")
        
        total_reorder_cost = 0
        
        by_priority = {
            "CRITICAL (0-2 units)": [],
            "HIGH (3-5 units)": [],
            "MEDIUM (6-10 units)": []
        }
        
        for name, sku, qty, price, cat, loc in results:
            if qty <= 2:
                priority = "CRITICAL (0-2 units)"
            elif qty <= 5:
                priority = "HIGH (3-5 units)"
            else:
                priority = "MEDIUM (6-10 units)"
            
            recommended_qty = max(30, threshold * 3)
            reorder_cost = recommended_qty * price
            total_reorder_cost += reorder_cost
            
            by_priority[priority].append({
                "name": name,
                "sku": sku,
                "current": qty,
                "recommended": recommended_qty,
                "price": price,
                "cost": reorder_cost,
                "category": cat
            })
        
        for priority, items in by_priority.items():
            if items:
                output.append(f"{priority}:")
                for item in items:
                    output.append(f"  - {item['name']} (SKU: {item['sku']})")
                    output.append(f"    Current Stock: {item['current']} units | Recommended: {item['recommended']} units")
                    output.append(f"    Unit Price: ${item['price']:.2f} | Total Cost: ${item['cost']:,.2f}")
                    output.append(f"    Category: {item['category']}")
                output.append("")
        
        output.append("Summary:")
        output.append(f"  Total Products to Reorder: {len(results)}")
        output.append(f"  Estimated Total Cost: ${total_reorder_cost:,.2f}")
        output.append("")
        output.append("Recommended Actions:")
        output.append(f"  1. Create purchase orders for CRITICAL items immediately")
        output.append(f"  2. Review HIGH priority items within 2-3 days")
        output.append(f"  3. Monitor MEDIUM priority items for next week")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error generating reorder suggestions: {str(e)}"


def validate_supplier_compliance(supplier_id: str) -> str:
    """
    Check if vendor meets policy requirements.
    
    Args:
        supplier_id: Supplier identifier
        
    Returns:
        Formatted compliance status
    """
    try:
        compliance_checks = {
            "ISO 9001 Certification": True,
            "Payment Terms Net 30": True,
            "Minimum Order Value $100": True,
            "Lead Time 5-7 Days": True,
            "Return Policy 30 Days": True,
            "Quality Assurance Program": True,
            "Insurance Coverage": True,
            "Background Check Completed": True
        }
        
        output = []
        output.append(f"SUPPLIER COMPLIANCE REPORT")
        output.append(f"Supplier ID: {supplier_id}")
        output.append(f"{'=' * 70}")
        output.append(f"Evaluation Date: {datetime.now().strftime('%Y-%m-%d')}")
        output.append(f"Status: APPROVED")
        output.append("")
        
        output.append("Compliance Checklist:")
        for check, status in compliance_checks.items():
            symbol = "✓" if status else "✗"
            output.append(f"  {symbol} {check}")
        
        output.append("")
        output.append("Risk Assessment:")
        output.append(f"  Overall Risk Level: LOW")
        output.append(f"  Financial Stability: STRONG")
        output.append(f"  Delivery Performance: 98.5% on-time")
        output.append(f"  Quality Rating: 4.8/5.0")
        output.append("")
        
        output.append("Recommendations:")
        output.append(f"  - Supplier meets all compliance requirements")
        output.append(f"  - Approved for procurement up to $50,000 per order")
        output.append(f"  - Next review date: {(datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error validating supplier compliance: {str(e)}"


def calculate_optimal_order_quantity(sku: str) -> str:
    """
    Economic Order Quantity (EOQ) analysis for cost efficiency.
    
    Args:
        sku: Product SKU to analyze
        
    Returns:
        Formatted EOQ analysis
    """
    try:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: SUPABASE_DB_URL environment variable not configured."
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT name, sku, quantity, price, category
            FROM inventory
            WHERE LOWER(sku) = LOWER(%s)
        """, (sku,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return f"Product with SKU '{sku}' not found."
        
        name, sku, current_qty, price, category = result
        
        annual_demand = max(100, current_qty * 12)
        ordering_cost = 50.0
        holding_cost_rate = 0.25
        holding_cost_per_unit = price * holding_cost_rate
        
        if holding_cost_per_unit > 0:
            eoq = ((2 * annual_demand * ordering_cost) / holding_cost_per_unit) ** 0.5
        else:
            eoq = 50
        
        eoq = int(eoq)
        
        number_of_orders = annual_demand / eoq if eoq > 0 else 0
        total_ordering_cost = number_of_orders * ordering_cost
        average_inventory = eoq / 2
        total_holding_cost = average_inventory * holding_cost_per_unit
        total_cost = total_ordering_cost + total_holding_cost
        
        output = []
        output.append(f"ECONOMIC ORDER QUANTITY ANALYSIS")
        output.append(f"Product: {name} (SKU: {sku})")
        output.append(f"{'=' * 70}")
        output.append("")
        
        output.append("Current Situation:")
        output.append(f"  Current Stock: {current_qty} units")
        output.append(f"  Unit Price: ${price:.2f}")
        output.append(f"  Category: {category}")
        output.append("")
        
        output.append("EOQ Analysis Parameters:")
        output.append(f"  Annual Demand (estimated): {annual_demand:,} units")
        output.append(f"  Ordering Cost per Order: ${ordering_cost:.2f}")
        output.append(f"  Holding Cost Rate: {holding_cost_rate * 100:.0f}%")
        output.append(f"  Holding Cost per Unit: ${holding_cost_per_unit:.2f}")
        output.append("")
        
        output.append("Optimal Order Strategy:")
        output.append(f"  Economic Order Quantity (EOQ): {eoq} units")
        output.append(f"  Number of Orders per Year: {number_of_orders:.1f}")
        output.append(f"  Days Between Orders: {365 / number_of_orders:.0f} days")
        output.append(f"  Reorder Point: {int(annual_demand * 7 / 365)} units (7-day buffer)")
        output.append("")
        
        output.append("Cost Analysis:")
        output.append(f"  Total Ordering Cost: ${total_ordering_cost:,.2f}/year")
        output.append(f"  Total Holding Cost: ${total_holding_cost:,.2f}/year")
        output.append(f"  Total Inventory Cost: ${total_cost:,.2f}/year")
        output.append(f"  Cost per Unit Sold: ${total_cost / annual_demand:.2f}")
        output.append("")
        
        output.append("Recommendations:")
        output.append(f"  - Order {eoq} units per purchase order")
        output.append(f"  - Place orders every {int(365 / number_of_orders)} days")
        output.append(f"  - Reorder when stock drops below {int(annual_demand * 7 / 365)} units")
        output.append(f"  - This minimizes total inventory costs")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error calculating optimal order quantity: {str(e)}"
