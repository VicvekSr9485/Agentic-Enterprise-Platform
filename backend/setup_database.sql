
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS inventory (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) UNIQUE NOT NULL,
    quantity INTEGER DEFAULT 0,
    price DECIMAL(10, 2),
    category VARCHAR(100),
    description TEXT,
    location VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert sample inventory data
INSERT INTO inventory (name, sku, quantity, price, category, description, location) VALUES
('Industrial Water Pump Model A', 'PUMP-001', 50, 299.99, 'Equipment', 'High-capacity water pump for industrial use', 'Warehouse A'),
('Industrial Water Pump Model B', 'PUMP-002', 30, 399.99, 'Equipment', 'Heavy-duty water pump with advanced features', 'Warehouse A'),
('Safety Relief Valve', 'VALVE-001', 100, 49.99, 'Parts', 'Standard safety relief valve', 'Warehouse B'),
('Pressure Control Valve', 'VALVE-002', 75, 89.99, 'Parts', 'Pressure regulation valve', 'Warehouse B'),
('Electronic Control Panel', 'CTRL-001', 25, 899.99, 'Electronics', 'Main control panel for pump systems', 'Warehouse C'),
('Temperature Sensor', 'SENS-001', 200, 25.99, 'Electronics', 'Digital temperature sensor', 'Warehouse C'),
('Motor Oil 5L', 'OIL-001', 150, 39.99, 'Consumables', 'Premium motor oil for pumps', 'Warehouse D'),
('Replacement Filter Kit', 'FILT-001', 120, 15.99, 'Parts', 'Standard filter replacement kit', 'Warehouse D')
ON CONFLICT (sku) DO NOTHING;

CREATE TABLE IF NOT EXISTS policy_documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),  -- Using 768 dimensions for text-embedding-004
    category VARCHAR(100),
    version VARCHAR(50),
    filename VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS policy_documents_embedding_idx 
ON policy_documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Insert sample policy documents (without embeddings - will be added by agent)
INSERT INTO policy_documents (title, content, category, version, filename) VALUES
(
    'Return and Refund Policy',
    'RETURN AND REFUND POLICY
    
    1. Return Window
    Customers may return products within 30 days of purchase for a full refund. After 30 days, returns are not accepted unless the product is defective.
    
    2. Condition Requirements
    Products must be returned in their original condition, unused, and in original packaging. Opened or used products may be subject to a 20% restocking fee.
    
    3. Refund Processing
    Refunds are processed within 5-7 business days after receiving the returned item. Refunds are issued to the original payment method.
    
    4. Exceptions
    Custom-ordered items, clearance items, and items marked as final sale are non-returnable.
    
    5. Defective Products
    Defective products can be returned or exchanged at any time with proof of defect. We will cover return shipping costs for defective items.',
    'Customer Service',
    'v2.1',
    'return_policy.txt'
),
(
    'Shipping and Delivery Policy',
    'SHIPPING AND DELIVERY POLICY
    
    1. Processing Time
    Orders are processed within 1-2 business days. Orders placed on weekends or holidays will be processed the next business day.
    
    2. Shipping Methods
    - Standard Shipping (5-7 business days): Free on orders over $100
    - Express Shipping (2-3 business days): $15.99
    - Overnight Shipping (1 business day): $29.99
    
    3. International Shipping
    We ship to most countries worldwide. International shipping times vary by destination (7-21 business days). Customers are responsible for customs duties and import taxes.
    
    4. Tracking
    Tracking information is provided via email once the order ships. Customers can track their orders on our website or the carriers website.
    
    5. Delivery Issues
    If a package is lost or damaged during shipping, please contact us within 48 hours of expected delivery. We will file a claim with the carrier and arrange a replacement or refund.',
    'Operations',
    'v1.3',
    'shipping_policy.txt'
),
(
    'Employee Remote Work Policy',
    'REMOTE WORK POLICY
    
    1. Eligibility
    Full-time employees who have completed their probationary period (90 days) may apply for remote work arrangements. Approval is at managers discretion based on role requirements and performance.
    
    2. Work Hours
    Remote employees must maintain standard business hours (9 AM - 5 PM local time) and be available for meetings and collaboration. Flexible schedules may be approved on a case-by-case basis.
    
    3. Equipment and Technology
    The company provides: laptop, monitor, keyboard, mouse, and necessary software licenses. Employees are responsible for internet connectivity (minimum 50 Mbps required).
    
    4. Communication Requirements
    - Daily check-in with team via Slack or Microsoft Teams
    - Weekly one-on-one meetings with direct manager
    - Response to messages within 2 hours during work hours
    - Camera-on requirement for team meetings
    
    5. Performance Monitoring
    Remote work privilege may be revoked if performance declines or communication standards are not met. Quarterly reviews assess remote work effectiveness.
    
    6. Security Requirements
    - Use of VPN when accessing company systems
    - Secure home office environment
    - No public WiFi for work purposes
    - Compliance with data protection policies',
    'Human Resources',
    'v3.0',
    'remote_work_policy.txt'
),
(
    'Data Privacy and Security Policy',
    'DATA PRIVACY AND SECURITY POLICY
    
    1. Data Collection
    We collect personal information including: name, email, phone number, shipping address, and payment information. Data is collected only when voluntarily provided by customers.
    
    2. Data Usage
    Personal data is used for: order processing, customer service, marketing communications (with consent), and improving our services. We do not sell personal data to third parties.
    
    3. Data Protection
    - All data is encrypted in transit (TLS 1.3) and at rest (AES-256)
    - Access to personal data is restricted to authorized personnel only
    - Regular security audits and penetration testing
    - Compliance with GDPR, CCPA, and other applicable regulations
    
    4. Data Retention
    Customer data is retained for 7 years after last purchase for accounting purposes. Marketing data is retained until consent is withdrawn. Inactive accounts are deleted after 3 years.
    
    5. Customer Rights
    Customers have the right to:
    - Access their personal data
    - Request data correction or deletion
    - Opt-out of marketing communications
    - Export their data in machine-readable format
    - File complaints with data protection authorities
    
    6. Third-Party Services
    We use third-party processors for: payment processing (Stripe), email services (SendGrid), and analytics (Google Analytics). All processors are GDPR-compliant.
    
    7. Breach Notification
    In case of a data breach, affected customers will be notified within 72 hours. We will provide details about the breach and steps being taken to mitigate risks.',
    'Compliance',
    'v4.2',
    'privacy_security_policy.txt'
)
ON CONFLICT DO NOTHING;


-- Inventory search indexes
CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category);
CREATE INDEX IF NOT EXISTS idx_inventory_sku ON inventory(sku);
CREATE INDEX IF NOT EXISTS idx_inventory_name ON inventory(name);

-- Policy search indexes
CREATE INDEX IF NOT EXISTS idx_policy_category ON policy_documents(category);
CREATE INDEX IF NOT EXISTS idx_policy_title ON policy_documents(title);


SELECT COUNT(*) as inventory_count FROM inventory;
SELECT * FROM inventory LIMIT 3;

-- Check policy documents
SELECT COUNT(*) as policy_count FROM policy_documents;
SELECT id, title, category FROM policy_documents;

-- Check extensions
SELECT * FROM pg_extension WHERE extname = 'vector';

COMMENT ON TABLE inventory IS 'Product inventory for Inventory Agent queries';
COMMENT ON TABLE policy_documents IS 'Company policy documents with vector embeddings for RAG-based Policy Agent';
