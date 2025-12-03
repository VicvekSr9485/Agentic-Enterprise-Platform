#!/usr/bin/env python3
"""
Quick validation script to check if the platform is ready to run.
"""

import os
import sys
from pathlib import Path

def check_env_var(var_name, required=True):
    """Check if an environment variable is set."""
    value = os.getenv(var_name)
    if value and value.strip():
        return True, "✅"
    elif required:
        return False, "❌ MISSING"
    else:
        return False, "⚠️  Optional"

def main():
    print("=" * 80)
    print("🔍 Enterprise Agents Platform - Configuration Validator")
    print("="  * 80)
    print()
    
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        print(f"✅ Environment file found: {env_path}")
        from dotenv import load_dotenv
        load_dotenv(env_path)
    else:
        print(f"❌ Environment file not found: {env_path}")
        return False
    
    print()
    print("=" * 80)
    print("Required Configuration:")
    print("=" * 80)
    
    required_vars = {
        "GOOGLE_API_KEY": "Google AI API Key",
        "SUPABASE_DB_URL": "Supabase Database URL",
        "SUPABASE_URL": "Supabase Project URL",
        "SUPABASE_KEY": "Supabase Service Key",
    }
    
    all_required_set = True
    for var, description in required_vars.items():
        status, icon = check_env_var(var, required=True)
        print(f"{icon} {var:25} - {description}")
        if not status:
            all_required_set = False
    
    print()
    print("=" * 80)
    print("SMTP Configuration (for Notification Agent):")
    print("=" * 80)
    
    smtp_vars = {
        "SMTP_HOST": "SMTP Server Host",
        "SMTP_PORT": "SMTP Server Port",
        "SMTP_USER": "SMTP Username",
        "SMTP_PASSWORD": "SMTP Password",
        "FROM_EMAIL": "From Email Address",
    }
    
    smtp_configured = True
    for var, description in smtp_vars.items():
        status, icon = check_env_var(var, required=False)
        print(f"{icon} {var:25} - {description}")
        if not status:
            smtp_configured = False
    
    print()
    print("=" * 80)
    print("Optional Configuration:")
    print("=" * 80)
    
    optional_vars = {
        "SESSION_DB_URL": "Session Storage Database",
        "BASE_URL": "Base URL for A2A Protocol",
        "PORT": "Server Port",
        "LOG_LEVEL": "Logging Level",
        "ENABLE_OTEL": "OpenTelemetry Enabled",
    }
    
    for var, description in optional_vars.items():
        status, icon = check_env_var(var, required=False)
        value = os.getenv(var, "Not set")
        print(f"{icon} {var:25} - {description:30} (Current: {value})")
    
    print()
    print("=" * 80)
    print("Summary:")
    print("=" * 80)
    
    if all_required_set:
        print("✅ All required configuration is set")
    else:
        print("❌ Some required configuration is missing")
        print("   Please update your .env file with the missing values")
        return False
    
    if not smtp_configured:
        print("⚠️  SMTP configuration incomplete - Notification Agent won't work")
        print("   For Gmail, generate an App Password at:")
        print("   https://support.google.com/accounts/answer/185833")
    else:
        print("✅ SMTP configuration complete")
    
    print()
    print("=" * 80)
    print("Database Status:")
    print("=" * 80)
    
    try:
        import psycopg2
        db_url = os.getenv("SUPABASE_DB_URL")
        if db_url:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            # Check tables
            cur.execute("SELECT COUNT(*) FROM inventory")
            inventory_count = cur.fetchone()[0]
            print(f"✅ Inventory table: {inventory_count} products")
            
            cur.execute("SELECT COUNT(*) FROM policy_documents")
            policy_count = cur.fetchone()[0]
            print(f"✅ Policy documents table: {policy_count} documents")
            
            cur.close()
            conn.close()
        else:
            print("⚠️  Database URL not configured")
    except Exception as e:
        print(f"⚠️  Could not connect to database: {str(e)}")
    
    print()
    print("=" * 80)
    print("🎉 Validation Complete!")
    print("=" * 80)
    
    if all_required_set:
        print()
        print("Your platform is ready to start!")
        print()
        print("Run: python main.py")
        print()
        if not smtp_configured:
            print("Note: Notification agent will have limited functionality without SMTP")
    
    return all_required_set

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
