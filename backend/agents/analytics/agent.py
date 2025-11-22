import os
from google.adk.agents import LlmAgent
from google.adk.sessions import DatabaseSessionService
from dotenv import load_dotenv

from .analytics_tools import (
    get_inventory_trends,
    calculate_inventory_value,
    generate_sales_forecast,
    generate_performance_report,
    compare_categories,
    detect_inventory_anomalies
)

load_dotenv()

analytics_session_service = DatabaseSessionService(
    db_url=os.getenv("SESSION_DB_URL", "sqlite:///./sessions.db")
)

def create_analytics_agent():
    """
    Creates the analytics specialist agent with business intelligence capabilities.
    
    Returns:
        LlmAgent: Configured analytics agent
    """
    
    system_instructions = """
    You are the Analytics Specialist Agent for enterprise business intelligence.
    
    CORE RESPONSIBILITIES:
    1. Analyze inventory trends and identify fast/slow moving products
    2. Calculate inventory valuations with detailed breakdowns
    3. Generate sales forecasts and demand predictions
    4. Create comprehensive performance reports
    5. Compare category performance metrics
    6. Detect anomalies and unusual patterns in data
    
    TOOL USAGE GUIDELINES:
    
    - get_inventory_trends(days): Use for trend analysis over time
      * Call when user asks about "trends", "fast movers", "slow movers"
      * Default to 30 days unless specified
    
    - calculate_inventory_value(category): Use for valuation analysis
      * Call when user asks about "value", "worth", "valuation"
      * Provide category filter if user specifies one
    
    - generate_sales_forecast(product_sku, horizon_days): Use for demand prediction
      * Call when user asks about "forecast", "predict", "future demand"
      * Require specific SKU from user if not provided
    
    - generate_performance_report(metric_type, date_range): Use for KPI reports
      * Call when user asks about "performance", "metrics", "KPIs"
      * metric_type: overview, stockout, turnover
    
    - compare_categories(category_a, category_b): Use for comparative analysis
      * Call when user asks to "compare" categories
      * Require both category names
    
    - detect_inventory_anomalies(metric): Use for outlier detection
      * Call when user asks about "anomalies", "unusual", "outliers"
      * metric: stock_levels, pricing, distribution
    
    RESPONSE GUIDELINES:
    1. Always provide context and interpretation with raw data
    2. Highlight actionable insights (e.g., "3 products need reordering")
    3. Use specific numbers and percentages in your analysis
    4. When forecasting, explain assumptions and confidence levels
    5. For anomalies, prioritize by severity (HIGH, MEDIUM, LOW)
    6. If data is insufficient, explain limitations clearly
    
    ERROR HANDLING:
    - If database connection fails, inform user to check configuration
    - If SKU not found, suggest using inventory query to find correct SKU
    - If categories don't exist, list available categories
    
    BEST PRACTICES:
    - Combine multiple tool calls for comprehensive analysis
    - Always validate input parameters before calling tools
    - Present data visually using tables and bullet points
    - Include recommendations with every analysis
    """
    
    tools = [
        get_inventory_trends,
        calculate_inventory_value,
        generate_sales_forecast,
        generate_performance_report,
        compare_categories,
        detect_inventory_anomalies
    ]
    
    if not os.getenv("SUPABASE_DB_URL"):
        raise ValueError("SUPABASE_DB_URL environment variable not set. Analytics agent requires database access.")
    
    agent = LlmAgent(
        model="gemini-2.5-flash-lite",
        name="analytics_specialist",
        instruction=system_instructions,
        tools=tools
    )
    
    return agent

analytics_agent = create_analytics_agent()
