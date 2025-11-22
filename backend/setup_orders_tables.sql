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

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(po_number);
CREATE INDEX IF NOT EXISTS idx_supplier_id ON purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_supplier_status ON suppliers(compliance_status);

-- Insert sample suppliers
INSERT INTO suppliers (name, contact_email, contact_phone, address, compliance_status, last_audit_date, certifications, rating)
VALUES 
    ('Acme Industrial Supplies', 'orders@acmeindustrial.com', '+1-555-0100', '123 Industry Blvd, Manufacturing City, MC 12345', 'active', CURRENT_DATE - INTERVAL '45 days', '["ISO-9001", "ISO-14001"]'::jsonb, 4.8),
    ('Global Parts Distributor', 'sales@globalparts.com', '+1-555-0200', '456 Commerce St, Trade Town, TT 67890', 'active', CURRENT_DATE - INTERVAL '30 days', '["ISO-9001"]'::jsonb, 4.5),
    ('Premium Equipment Co', 'contact@premiumequip.com', '+1-555-0300', '789 Equipment Way, Quality City, QC 11111', 'active', CURRENT_DATE - INTERVAL '60 days', '["ISO-9001", "CE-Certified"]'::jsonb, 4.9),
    ('Budget Supplies Inc', 'info@budgetsupplies.com', '+1-555-0400', '321 Value Ave, Savings City, SC 22222', 'under_review', CURRENT_DATE - INTERVAL '120 days', '[]'::jsonb, 3.5);

-- Insert sample purchase orders
INSERT INTO purchase_orders (po_number, supplier_id, order_date, delivery_date, status, items, subtotal, tax, total_amount, tracking_number, notes)
VALUES 
    ('PO-20251101-0001', 1, CURRENT_DATE - INTERVAL '15 days', CURRENT_DATE - INTERVAL '5 days', 'delivered',
     '[{"sku": "PUMP-001", "name": "Industrial Water Pump Model A", "quantity": 20, "unit_price": 299.99}, {"sku": "VALVE-001", "name": "Safety Relief Valve", "quantity": 50, "unit_price": 49.99}]'::jsonb,
     8499.30, 679.94, 9179.24, 'TRK-1234567890', 'Delivered on time, all items inspected'),
    
    ('PO-20251110-0002', 2, CURRENT_DATE - INTERVAL '8 days', CURRENT_DATE + INTERVAL '2 days', 'shipped',
     '[{"sku": "FILT-001", "name": "Replacement Filter Kit", "quantity": 100, "unit_price": 15.99}]'::jsonb,
     1599.00, 127.92, 1726.92, 'TRK-9876543210', 'In transit, expected delivery Nov 24'),
    
    ('PO-20251118-0003', 3, CURRENT_DATE - INTERVAL '3 days', CURRENT_DATE + INTERVAL '7 days', 'confirmed',
     '[{"sku": "CTRL-001", "name": "Electronic Control Panel", "quantity": 10, "unit_price": 899.99}]'::jsonb,
     8999.90, 719.99, 9719.89, NULL, 'Awaiting shipment from manufacturer'),
    
    ('PO-20251122-0004', 1, CURRENT_DATE, CURRENT_DATE + INTERVAL '14 days', 'draft',
     '[{"sku": "SENS-001", "name": "Temperature Sensor", "quantity": 50, "unit_price": 25.99}, {"sku": "OIL-001", "name": "Motor Oil 5L", "quantity": 30, "unit_price": 39.99}]'::jsonb,
     2499.20, 199.94, 2699.14, NULL, 'Draft order pending approval');

-- Verify data
SELECT 'Suppliers created:' as info, COUNT(*) as count FROM suppliers
UNION ALL
SELECT 'Purchase orders created:', COUNT(*) FROM purchase_orders;
