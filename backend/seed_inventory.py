#!/usr/bin/env python3
"""
Seed Inventory Database with Demo Products
===========================================
Populates the PostgreSQL inventory table with sample product data.
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

# Sample inventory data
PRODUCTS = [
    {
        "product_id": 1,
        "name": "Industrial Water Pump Model A",
        "sku": "PUMP-001",
        "quantity": 50,
        "price": 299.99,
        "category": "Equipment",
        "location": "Warehouse A"
    },
    {
        "product_id": 2,
        "name": "Industrial Water Pump Model B",
        "sku": "PUMP-002",
        "quantity": 30,
        "price": 399.99,
        "category": "Equipment",
        "location": "Warehouse A"
    },
    {
        "product_id": 3,
        "name": "Safety Relief Valve",
        "sku": "VALVE-001",
        "quantity": 100,
        "price": 49.99,
        "category": "Parts",
        "location": "Warehouse B"
    },
    {
        "product_id": 4,
        "name": "Pressure Control Valve",
        "sku": "VALVE-002",
        "quantity": 75,
        "price": 89.99,
        "category": "Parts",
        "location": "Warehouse B"
    },
    {
        "product_id": 5,
        "name": "Electronic Control Panel",
        "sku": "CTRL-001",
        "quantity": 25,
        "price": 899.99,
        "category": "Electronics",
        "location": "Warehouse C"
    },
    {
        "product_id": 6,
        "name": "Temperature Sensor",
        "sku": "SENS-001",
        "quantity": 200,
        "price": 25.99,
        "category": "Electronics",
        "location": "Warehouse C"
    },
    {
        "product_id": 7,
        "name": "Motor Oil 5L",
        "sku": "OIL-001",
        "quantity": 150,
        "price": 39.99,
        "category": "Consumables",
        "location": "Warehouse D"
    },
    {
        "product_id": 8,
        "name": "Replacement Filter Kit",
        "sku": "FILT-001",
        "quantity": 120,
        "price": 15.99,
        "category": "Parts",
        "location": "Warehouse D"
    }
]

def seed_inventory():
    """Insert inventory products into PostgreSQL database"""
    
    print("Connecting to Supabase PostgreSQL...")
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("Error: SUPABASE_DB_URL not set in environment")
        sys.exit(1)
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        print("📊 Creating inventory table if not exists...")
        
        # Create inventory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                product_id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                sku VARCHAR(50) UNIQUE NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                price DECIMAL(10, 2) NOT NULL,
                category VARCHAR(100),
                location VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print(f"\n📝 Inserting {len(PRODUCTS)} products...\n")
        
        # Clear existing data
        cursor.execute("DELETE FROM inventory")
        
        # Prepare data for batch insert
        values = [
            (
                p["product_id"],
                p["name"],
                p["sku"],
                p["quantity"],
                p["price"],
                p["category"],
                p["location"]
            )
            for p in PRODUCTS
        ]
        
        # Batch insert
        execute_values(
            cursor,
            """
            INSERT INTO inventory 
                (product_id, name, sku, quantity, price, category, location)
            VALUES %s
            ON CONFLICT (product_id) 
            DO UPDATE SET
                name = EXCLUDED.name,
                sku = EXCLUDED.sku,
                quantity = EXCLUDED.quantity,
                price = EXCLUDED.price,
                category = EXCLUDED.category,
                location = EXCLUDED.location,
                updated_at = CURRENT_TIMESTAMP
            """,
            values
        )
        
        # Commit transaction
        conn.commit()
        
        # Verify insertion
        cursor.execute("SELECT COUNT(*) FROM inventory")
        count = cursor.fetchone()[0]
        
        print(f"Successfully inserted {count} products!")
        
        print("\nSample inventory:")
        cursor.execute("""
            SELECT name, sku, quantity, price, category 
            FROM inventory 
            LIMIT 3
        """)
        
        for row in cursor.fetchall():
            print(f"   - {row[0]} ({row[1]}): {row[2]} units @ ${row[3]}")
        
        # Close connections
        cursor.close()
        conn.close()
        
        print(f"\nInventory database seeded successfully!")
        print(f"Total products: {count}")
        
    except Exception as e:
        print(f"\nError seeding inventory: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("  Inventory Database Seeder")
    print("=" * 60)
    seed_inventory()
