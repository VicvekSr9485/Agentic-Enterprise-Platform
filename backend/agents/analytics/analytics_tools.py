import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import statistics

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.supabase_client import get_supabase_client


def get_inventory_trends(days: int = 30) -> str:
    """
    Analyze inventory trends over a time period to identify fast and slow moving products.
    
    Args:
        days: Number of days to analyze (default 30)
        
    Returns:
        Formatted string with trend analysis
    """
    try:
        client = get_supabase_client()
        
        results = client.query(
            "inventory",
            select="name,sku,quantity,price,category",
            order="quantity.desc"
        )
        
        if not results:
            return "No inventory data available for trend analysis."
        
        total_items = len(results)
        quantities = [item['quantity'] for item in results]
        avg_quantity = statistics.mean(quantities)
        median_quantity = statistics.median(quantities)
        
        fast_movers = [item for item in results if item['quantity'] > avg_quantity * 1.5]
        slow_movers = [item for item in results if item['quantity'] < avg_quantity * 0.3]
        
        output = []
        output.append(f"Inventory Trend Analysis (Last {days} days)")
        output.append(f"{'=' * 50}")
        output.append(f"Total Products: {total_items}")
        output.append(f"Average Stock Level: {avg_quantity:.1f} units")
        output.append(f"Median Stock Level: {median_quantity:.1f} units")
        output.append("")
        
        if fast_movers:
            output.append(f"Fast Movers ({len(fast_movers)} products):")
            for item in fast_movers[:5]:
                output.append(f"  - {item['name']} (SKU: {item['sku']})")
                output.append(f"    Stock: {item['quantity']} units | Price: ${float(item['price']):.2f} | Category: {item['category']}")
            output.append("")
        
        if slow_movers:
            output.append(f"Slow Movers ({len(slow_movers)} products):")
            for item in slow_movers[:5]:
                output.append(f"  - {item['name']} (SKU: {item['sku']})")
                output.append(f"    Stock: {item['quantity']} units | Price: ${float(item['price']):.2f} | Category: {item['category']}")
        
        return "\n".join(output)
        
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
        client = get_supabase_client()
        
        if category:
            results = client.query(
                "inventory",
                select="name,sku,quantity,price,category,location",
                filters={"category": f"ilike.{category}"}
            )
        else:
            results = client.query(
                "inventory",
                select="name,sku,quantity,price,category,location"
            )
        
        if not results:
            return f"No inventory found{f' in category {category}' if category else ''}."
        
        # Sort by value (quantity * price)
        results.sort(key=lambda x: x['quantity'] * float(x['price']), reverse=True)
        
        category_values = {}
        total_value = 0
        total_units = 0
        
        for item in results:
            qty = item['quantity']
            price = float(item['price'])
            cat = item['category']
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
            for item in results[:5]:
                value = item['quantity'] * float(item['price'])
                output.append(f"  - {item['name']} (SKU: {item['sku']})")
                output.append(f"    Value: ${value:,.2f} ({item['quantity']} units @ ${float(item['price']):.2f})")
                output.append(f"    Category: {item['category']} | Location: {item['location']}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error calculating inventory value: {str(e)}"


def generate_sales_forecast(product_sku: str, horizon_days: int = 90) -> str:
    """
    Predict future demand for a product based on current stock levels.
    
    Args:
        product_sku: Product SKU to forecast
        horizon_days: Days to forecast ahead
        
    Returns:
        Formatted string with forecast
    """
    try:
        client = get_supabase_client()
        
        results = client.query(
            "inventory",
            select="name,sku,quantity,price,category",
            filters={"sku": f"ilike.{product_sku}"}
        )
        
        if not results:
            return f"Product with SKU '{product_sku}' not found."
        
        item = results[0]
        name = item['name']
        sku = item['sku']
        quantity = item['quantity']
        price = float(item['price'])
        category = item['category']
        
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
        client = get_supabase_client()
        
        results = client.query(
            "inventory",
            select="name,sku,quantity,price,category,location"
        )
        
        if not results:
            return "No inventory data available for performance analysis."
        
        total_items = len(results)
        total_value = sum(item['quantity'] * float(item['price']) for item in results)
        total_units = sum(item['quantity'] for item in results)
        
        low_stock = [item for item in results if item['quantity'] < 10]
        out_of_stock = [item for item in results if item['quantity'] == 0]
        
        categories = {}
        for item in results:
            cat = item['category']
            if cat not in categories:
                categories[cat] = {"count": 0, "value": 0}
            categories[cat]["count"] += 1
            categories[cat]["value"] += item['quantity'] * float(item['price'])
        
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
            for item in low_stock[:3]:
                output.append(f"    - {item['name']} (SKU: {item['sku']}): {item['quantity']} units remaining")
        
        return "\n".join(output)
        
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
        client = get_supabase_client()
        
        # Get all products to filter by category
        all_results = client.query(
            "inventory",
            select="category,quantity,price"
        )
        
        if not all_results:
            return "No inventory data available for comparison."
        
        # Aggregate by category
        data = {}
        for item in all_results:
            cat = item['category'].lower()
            if cat not in data:
                data[cat] = {"count": 0, "units": 0, "value": 0, "prices": []}
            data[cat]["count"] += 1
            data[cat]["units"] += item['quantity']
            data[cat]["value"] += item['quantity'] * float(item['price'])
            data[cat]["prices"].append(float(item['price']))
        
        # Calculate averages
        for cat in data:
            data[cat]["avg_price"] = statistics.mean(data[cat]["prices"]) if data[cat]["prices"] else 0
        
        cat_a_data = data.get(category_a.lower())
        cat_b_data = data.get(category_b.lower())
        
        if not cat_a_data:
            available = list(data.keys())
            return f"Category '{category_a}' not found. Available categories: {', '.join(available)}"
        
        if not cat_b_data:
            available = list(data.keys())
            return f"Category '{category_b}' not found. Available categories: {', '.join(available)}"
        
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
        
    except Exception as e:
        return f"Error comparing categories: {str(e)}"


def detect_inventory_anomalies(metric: str = "stock_levels") -> str:
    """
    Detect unusual patterns in inventory data.
    
    Args:
        metric: Type of anomaly to detect (stock_levels, pricing, distribution)
        
    Returns:
        Formatted anomaly report
    """
    try:
        client = get_supabase_client()
        
        results = client.query(
            "inventory",
            select="name,sku,quantity,price,category,location"
        )
        
        if not results:
            return "No inventory data available for anomaly detection."
        
        quantities = [item['quantity'] for item in results]
        prices = [float(item['price']) for item in results]
        
        avg_qty = statistics.mean(quantities)
        stdev_qty = statistics.stdev(quantities) if len(quantities) > 1 else 0
        
        avg_price = statistics.mean(prices)
        stdev_price = statistics.stdev(prices) if len(prices) > 1 else 0
        
        anomalies = []
        
        for item in results:
            qty = item['quantity']
            price = float(item['price'])
            
            if stdev_qty > 0 and abs(qty - avg_qty) > 2 * stdev_qty:
                anomalies.append({
                    "type": "Unusual Stock Level",
                    "product": item['name'],
                    "sku": item['sku'],
                    "value": qty,
                    "expected": f"{avg_qty:.0f} ± {stdev_qty:.0f}",
                    "severity": "HIGH" if abs(qty - avg_qty) > 3 * stdev_qty else "MEDIUM"
                })
            
            if stdev_price > 0 and abs(price - avg_price) > 2 * stdev_price:
                anomalies.append({
                    "type": "Unusual Pricing",
                    "product": item['name'],
                    "sku": item['sku'],
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
        
    except Exception as e:
        return f"Error detecting anomalies: {str(e)}"
