"""
Seed suppliers and purchase_orders tables in Supabase
"""
import os
from datetime import datetime, timedelta
from shared.supabase_client import get_supabase_client
from dotenv import load_dotenv

load_dotenv()


def create_tables_via_sql():
    """
    SQL statements to create tables in Supabase SQL Editor
    """
    sql = """
-- Create suppliers table
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    address TEXT,
    compliance_status VARCHAR(50) DEFAULT 'active',
    last_audit_date DATE,
    certifications JSONB DEFAULT '[]'::jsonb,
    rating DECIMAL(3,2) DEFAULT 5.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create purchase_orders table
CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id SERIAL PRIMARY KEY,
    po_number VARCHAR(100) UNIQUE NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(supplier_id),
    order_date DATE NOT NULL,
    delivery_date DATE,
    status VARCHAR(50) DEFAULT 'draft',
    items JSONB NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    tax DECIMAL(12,2) DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    notes TEXT,
    tracking_number VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(po_number);
CREATE INDEX IF NOT EXISTS idx_supplier_id ON purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status);
"""
    print("=" * 70)
    print("SQL TO RUN IN SUPABASE SQL EDITOR:")
    print("=" * 70)
    print(sql)
    print("\n" + "=" * 70)
    print("After running the SQL above, press Enter to continue with seeding...")
    input()


def seed_suppliers():
    """Seed suppliers table with sample data"""
    client = get_supabase_client()
    
    suppliers_data = [
        {
            "name": "Acme Industrial Supplies",
            "contact_email": "orders@acmeindustrial.com",
            "contact_phone": "+1-555-0100",
            "address": "123 Industry Blvd, Manufacturing City, MC 12345",
            "compliance_status": "active",
            "last_audit_date": (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"),
            "certifications": ["ISO-9001", "ISO-14001"],
            "rating": 4.8
        },
        {
            "name": "Global Parts Distributor",
            "contact_email": "sales@globalparts.com",
            "contact_phone": "+1-555-0200",
            "address": "456 Commerce St, Trade Town, TT 67890",
            "compliance_status": "active",
            "last_audit_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "certifications": ["ISO-9001"],
            "rating": 4.5
        },
        {
            "name": "Premium Equipment Co",
            "contact_email": "contact@premiumequip.com",
            "contact_phone": "+1-555-0300",
            "address": "789 Equipment Way, Quality City, QC 11111",
            "compliance_status": "active",
            "last_audit_date": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
            "certifications": ["ISO-9001", "CE-Certified"],
            "rating": 4.9
        },
        {
            "name": "Budget Supplies Inc",
            "contact_email": "info@budgetsupplies.com",
            "contact_phone": "+1-555-0400",
            "address": "321 Value Ave, Savings City, SC 22222",
            "compliance_status": "under_review",
            "last_audit_date": (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d"),
            "certifications": [],
            "rating": 3.5
        }
    ]
    
    print("\nSeeding suppliers table...")
    try:
        result = client.insert_many("suppliers", suppliers_data)
        print(f"✅ Successfully inserted {len(result)} suppliers")
        return result
    except Exception as e:
        print(f"❌ Error seeding suppliers: {e}")
        return []


def seed_purchase_orders(suppliers):
    """Seed purchase_orders table with sample data"""
    if not suppliers:
        print("⚠️  No suppliers found, skipping purchase orders")
        return
    
    client = get_supabase_client()
    
    # Create sample purchase orders
    orders_data = [
        {
            "po_number": "PO-20251101-0001",
            "supplier_id": suppliers[0]["supplier_id"],
            "order_date": (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"),
            "delivery_date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
            "status": "delivered",
            "items": [
                {"sku": "PUMP-001", "name": "Industrial Water Pump Model A", "quantity": 20, "unit_price": 299.99},
                {"sku": "VALVE-001", "name": "Safety Relief Valve", "quantity": 50, "unit_price": 49.99}
            ],
            "subtotal": 8499.30,
            "tax": 679.94,
            "total_amount": 9179.24,
            "tracking_number": "TRK-1234567890",
            "notes": "Delivered on time, all items inspected"
        },
        {
            "po_number": "PO-20251110-0002",
            "supplier_id": suppliers[1]["supplier_id"],
            "order_date": (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"),
            "delivery_date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "status": "shipped",
            "items": [
                {"sku": "FILT-001", "name": "Replacement Filter Kit", "quantity": 100, "unit_price": 15.99}
            ],
            "subtotal": 1599.00,
            "tax": 127.92,
            "total_amount": 1726.92,
            "tracking_number": "TRK-9876543210",
            "notes": "In transit, expected delivery Nov 24"
        },
        {
            "po_number": "PO-20251118-0003",
            "supplier_id": suppliers[2]["supplier_id"],
            "order_date": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
            "delivery_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "status": "confirmed",
            "items": [
                {"sku": "CTRL-001", "name": "Electronic Control Panel", "quantity": 10, "unit_price": 899.99}
            ],
            "subtotal": 8999.90,
            "tax": 719.99,
            "total_amount": 9719.89,
            "notes": "Awaiting shipment from manufacturer"
        },
        {
            "po_number": "PO-20251122-0004",
            "supplier_id": suppliers[0]["supplier_id"],
            "order_date": datetime.now().strftime("%Y-%m-%d"),
            "delivery_date": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
            "status": "draft",
            "items": [
                {"sku": "SENS-001", "name": "Temperature Sensor", "quantity": 50, "unit_price": 25.99},
                {"sku": "OIL-001", "name": "Motor Oil 5L", "quantity": 30, "unit_price": 39.99}
            ],
            "subtotal": 2499.20,
            "tax": 199.94,
            "total_amount": 2699.14,
            "notes": "Draft order pending approval"
        }
    ]
    
    print("\nSeeding purchase_orders table...")
    try:
        result = client.insert_many("purchase_orders", orders_data)
        print(f"Successfully inserted {len(result)} purchase orders")
        return result
    except Exception as e:
        print(f" Error seeding purchase orders: {e}")
        return []


def main():
    print("=" * 70)
    print("SUPPLIERS & PURCHASE ORDERS SEEDING SCRIPT")
    print("=" * 70)
    
    # Step 1: Show SQL to create tables
    create_tables_via_sql()
    
    # Step 2: Seed suppliers
    suppliers = seed_suppliers()
    
    # Step 3: Seed purchase orders
    if suppliers:
        seed_purchase_orders(suppliers)
    
    print("\n" + "=" * 70)
    print("SEEDING COMPLETE!")
    print("=" * 70)
    print("\nYou can now test:")
    print("  - track_order_status('PO-20251110-0002')")
    print("  - validate_supplier_compliance('1') # Acme Industrial")
    print("=" * 70)


if __name__ == "__main__":
    main()
