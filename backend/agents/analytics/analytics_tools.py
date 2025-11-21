import os
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import statistics


def get_inventory_trends(days: int = 30) -> str:
    """
    Analyze inventory trends over a time period to identify fast and slow moving products.
    
    Args:
        days: Number of days to analyze (default 30)
        
    Returns:
        Formatted string with trend analysis
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
            ORDER BY quantity DESC
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return "No inventory data available for trend analysis."
        
        total_items = len(results)
        quantities = [row[2] for row in results]
        avg_quantity = statistics.mean(quantities)
        median_quantity = statistics.median(quantities)
        
        fast_movers = [row for row in results if row[2] > avg_quantity * 1.5]
        slow_movers = [row for row in results if row[2] < avg_quantity * 0.3]
        
        output = []
        output.append(f"Inventory Trend Analysis (Last {days} days)")
        output.append(f"{'=' * 50}")
        output.append(f"Total Products: {total_items}")
        output.append(f"Average Stock Level: {avg_quantity:.1f} units")
        output.append(f"Median Stock Level: {median_quantity:.1f} units")
        output.append("")
        
        if fast_movers:
            output.append(f"Fast Movers ({len(fast_movers)} products):")
            for name, sku, qty, price, category in fast_movers[:5]:
                output.append(f"  - {name} (SKU: {sku})")
                output.append(f"    Stock: {qty} units | Price: ${price:.2f} | Category: {category}")
            output.append("")
        
        if slow_movers:
            output.append(f"Slow Movers ({len(slow_movers)} products):")
            for name, sku, qty, price, category in slow_movers[:5]:
                output.append(f"  - {name} (SKU: {sku})")
                output.append(f"    Stock: {qty} units | Price: ${price:.2f} | Category: {category}")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error analyzing trends: {str(e)}"


def calculate_inventory_value(category: Optional[str] = None) -> str:
    """
    Calculate total inventory value with detailed breakdown by category.
    
    Args:
        category: Optional category filter
        
    Returns:
        Formatted string with value calculations
    """
    try:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: SUPABASE_DB_URL environment variable not configured."
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        if category:
            cur.execute("""
                SELECT name, sku, quantity, price, category, location
                FROM inventory
                WHERE LOWER(category) = LOWER(%s)
                ORDER BY (quantity * price) DESC
            """, (category,))
        else:
            cur.execute("""
                SELECT name, sku, quantity, price, category, location
                FROM inventory
                ORDER BY (quantity * price) DESC
            """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return f"No inventory found{f' in category {category}' if category else ''}."
        
        category_values = {}
        total_value = 0
        total_units = 0
        
        for name, sku, qty, price, cat, location in results:
            value = qty * price
            total_value += value
            total_units += qty
            
            if cat not in category_values:
                category_values[cat] = {"value": 0, "units": 0, "items": 0}
            category_values[cat]["value"] += value
            category_values[cat]["units"] += qty
            category_values[cat]["items"] += 1
        
        output = []
        output.append(f"Inventory Value Report{f' - {category}' if category else ''}")
        output.append(f"{'=' * 60}")
        output.append(f"Total Inventory Value: ${total_value:,.2f}")
        output.append(f"Total Units: {total_units:,}")
        output.append(f"Average Value per Unit: ${total_value/total_units:.2f}" if total_units > 0 else "")
        output.append("")
        
        output.append("Breakdown by Category:")
        for cat, data in sorted(category_values.items(), key=lambda x: x[1]["value"], reverse=True):
            percentage = (data["value"] / total_value * 100) if total_value > 0 else 0
            output.append(f"  {cat}:")
            output.append(f"    Value: ${data['value']:,.2f} ({percentage:.1f}%)")
            output.append(f"    Units: {data['units']:,} across {data['items']} product(s)")
            output.append("")
        
        if not category:
            output.append("Top 5 Most Valuable Items:")
            for name, sku, qty, price, cat, location in results[:5]:
                value = qty * price
                output.append(f"  - {name} (SKU: {sku})")
                output.append(f"    Value: ${value:,.2f} ({qty} units @ ${price:.2f})")
                output.append(f"    Category: {cat} | Location: {location}")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error calculating inventory value: {str(e)}"


def get_sales_forecast(product_sku: str, horizon_days: int = 90) -> str:
    """
    Predict future demand for a product based on current stock levels.
    
    Args:
        product_sku: Product SKU to forecast
        horizon_days: Days to forecast ahead
        
    Returns:
        Formatted string with forecast
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
        """, (product_sku,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return f"Product with SKU '{product_sku}' not found."
        
        name, sku, quantity, price, category = result
        
        daily_demand_estimate = max(1, quantity // 30)
        days_until_stockout = quantity // daily_demand_estimate if daily_demand_estimate > 0 else 999
        
        reorder_point = daily_demand_estimate * 7
        recommended_order_qty = daily_demand_estimate * 30
        
        output = []
        output.append(f"Sales Forecast - {name} (SKU: {sku})")
        output.append(f"{'=' * 60}")
        output.append(f"Current Stock: {quantity} units")
        output.append(f"Price per Unit: ${price:.2f}")
        output.append(f"Category: {category}")
        output.append("")
        output.append(f"Forecast Horizon: {horizon_days} days")
        output.append(f"Estimated Daily Demand: {daily_demand_estimate} units")
        output.append(f"Days Until Stockout: {days_until_stockout} days")
        output.append("")
        
        if days_until_stockout < 14:
            output.append("⚠️  URGENT: Stock critically low - reorder immediately")
        elif days_until_stockout < 30:
            output.append("⚠️  WARNING: Stock running low - reorder soon")
        else:
            output.append("✓ Stock levels adequate for forecast period")
        
        output.append("")
        output.append("Recommendations:")
        output.append(f"  Reorder Point: {reorder_point} units")
        output.append(f"  Recommended Order Quantity: {recommended_order_qty} units")
        output.append(f"  Estimated Cost: ${recommended_order_qty * price:,.2f}")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error generating forecast: {str(e)}"


def generate_performance_report(metric_type: str = "overview", date_range: int = 30) -> str:
    """
    Generate comprehensive performance metrics report.
    
    Args:
        metric_type: Type of report (overview, stockout, turnover)
        date_range: Days to analyze
        
    Returns:
        Formatted performance report
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
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return "No inventory data available for performance analysis."
        
        total_items = len(results)
        total_value = sum(row[2] * row[3] for row in results)
        total_units = sum(row[2] for row in results)
        
        low_stock = [row for row in results if row[2] < 10]
        out_of_stock = [row for row in results if row[2] == 0]
        
        categories = {}
        for row in results:
            cat = row[4]
            if cat not in categories:
                categories[cat] = {"count": 0, "value": 0}
            categories[cat]["count"] += 1
            categories[cat]["value"] += row[2] * row[3]
        
        output = []
        output.append(f"Performance Report - {metric_type.upper()}")
        output.append(f"Period: Last {date_range} days")
        output.append(f"{'=' * 60}")
        output.append("")
        
        output.append("Key Metrics:")
        output.append(f"  Total SKUs: {total_items}")
        output.append(f"  Total Inventory Value: ${total_value:,.2f}")
        output.append(f"  Total Units in Stock: {total_units:,}")
        output.append(f"  Average Value per SKU: ${total_value/total_items:,.2f}")
        output.append("")
        
        output.append("Stock Health:")
        output.append(f"  Low Stock Items (< 10 units): {len(low_stock)}")
        output.append(f"  Out of Stock Items: {len(out_of_stock)}")
        fill_rate = ((total_items - len(out_of_stock)) / total_items * 100) if total_items > 0 else 0
        output.append(f"  Fill Rate: {fill_rate:.1f}%")
        output.append("")
        
        output.append("Category Distribution:")
        for cat, data in sorted(categories.items(), key=lambda x: x[1]["value"], reverse=True):
            output.append(f"  {cat}: {data['count']} SKUs (${data['value']:,.2f})")
        
        if low_stock:
            output.append("")
            output.append("Action Items:")
            output.append(f"  {len(low_stock)} product(s) need reordering")
            for name, sku, qty, price, cat, loc in low_stock[:3]:
                output.append(f"    - {name} (SKU: {sku}): {qty} units remaining")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error generating report: {str(e)}"


def compare_categories(category_a: str, category_b: str) -> str:
    """
    Compare performance metrics between two product categories.
    
    Args:
        category_a: First category name
        category_b: Second category name
        
    Returns:
        Formatted comparison report
    """
    try:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            return "Error: SUPABASE_DB_URL environment variable not configured."
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT category, COUNT(*), SUM(quantity), SUM(quantity * price), AVG(price)
            FROM inventory
            WHERE LOWER(category) IN (LOWER(%s), LOWER(%s))
            GROUP BY category
        """, (category_a, category_b))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if len(results) < 2:
            return f"Could not find both categories. Available data: {[r[0] for r in results]}"
        
        data = {row[0].lower(): {"count": row[1], "units": row[2], "value": row[3], "avg_price": row[4]} for row in results}
        
        cat_a_data = data.get(category_a.lower())
        cat_b_data = data.get(category_b.lower())
        
        if not cat_a_data or not cat_b_data:
            return "One or both categories not found in inventory."
        
        output = []
        output.append(f"Category Comparison: {category_a} vs {category_b}")
        output.append(f"{'=' * 60}")
        output.append("")
        
        output.append(f"{category_a}:")
        output.append(f"  SKUs: {cat_a_data['count']}")
        output.append(f"  Total Units: {cat_a_data['units']:,}")
        output.append(f"  Total Value: ${cat_a_data['value']:,.2f}")
        output.append(f"  Average Price: ${cat_a_data['avg_price']:.2f}")
        output.append("")
        
        output.append(f"{category_b}:")
        output.append(f"  SKUs: {cat_b_data['count']}")
        output.append(f"  Total Units: {cat_b_data['units']:,}")
        output.append(f"  Total Value: ${cat_b_data['value']:,.2f}")
        output.append(f"  Average Price: ${cat_b_data['avg_price']:.2f}")
        output.append("")
        
        output.append("Comparison:")
        sku_diff = ((cat_a_data['count'] - cat_b_data['count']) / cat_b_data['count'] * 100) if cat_b_data['count'] > 0 else 0
        value_diff = ((cat_a_data['value'] - cat_b_data['value']) / cat_b_data['value'] * 100) if cat_b_data['value'] > 0 else 0
        
        output.append(f"  SKU Difference: {sku_diff:+.1f}%")
        output.append(f"  Value Difference: {value_diff:+.1f}%")
        
        if cat_a_data['value'] > cat_b_data['value']:
            output.append(f"  {category_a} has higher total value")
        else:
            output.append(f"  {category_b} has higher total value")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error comparing categories: {str(e)}"


def detect_anomalies(metric: str = "stock_levels") -> str:
    """
    Detect unusual patterns in inventory data.
    
    Args:
        metric: Type of anomaly to detect (stock_levels, pricing, distribution)
        
    Returns:
        Formatted anomaly report
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
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return "No inventory data available for anomaly detection."
        
        quantities = [row[2] for row in results]
        prices = [row[3] for row in results]
        
        avg_qty = statistics.mean(quantities)
        stdev_qty = statistics.stdev(quantities) if len(quantities) > 1 else 0
        
        avg_price = statistics.mean(prices)
        stdev_price = statistics.stdev(prices) if len(prices) > 1 else 0
        
        anomalies = []
        
        for name, sku, qty, price, cat, loc in results:
            if stdev_qty > 0 and abs(qty - avg_qty) > 2 * stdev_qty:
                anomalies.append({
                    "type": "Unusual Stock Level",
                    "product": name,
                    "sku": sku,
                    "value": qty,
                    "expected": f"{avg_qty:.0f} ± {stdev_qty:.0f}",
                    "severity": "HIGH" if abs(qty - avg_qty) > 3 * stdev_qty else "MEDIUM"
                })
            
            if stdev_price > 0 and abs(price - avg_price) > 2 * stdev_price:
                anomalies.append({
                    "type": "Unusual Pricing",
                    "product": name,
                    "sku": sku,
                    "value": f"${price:.2f}",
                    "expected": f"${avg_price:.2f} ± ${stdev_price:.2f}",
                    "severity": "MEDIUM"
                })
        
        output = []
        output.append(f"Anomaly Detection Report - {metric}")
        output.append(f"{'=' * 60}")
        output.append(f"Analyzed {len(results)} products")
        output.append(f"Found {len(anomalies)} anomalies")
        output.append("")
        
        if anomalies:
            high_severity = [a for a in anomalies if a.get("severity") == "HIGH"]
            if high_severity:
                output.append("HIGH SEVERITY ANOMALIES:")
                for anom in high_severity:
                    output.append(f"  [{anom['type']}] {anom['product']} (SKU: {anom['sku']})")
                    output.append(f"    Actual: {anom['value']} | Expected: {anom['expected']}")
                output.append("")
            
            medium_severity = [a for a in anomalies if a.get("severity") == "MEDIUM"]
            if medium_severity:
                output.append("MEDIUM SEVERITY ANOMALIES:")
                for anom in medium_severity[:5]:
                    output.append(f"  [{anom['type']}] {anom['product']} (SKU: {anom['sku']})")
                    output.append(f"    Actual: {anom['value']} | Expected: {anom['expected']}")
        else:
            output.append("No significant anomalies detected. Inventory patterns are normal.")
        
        return "\n".join(output)
        
    except psycopg2.Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error detecting anomalies: {str(e)}"
