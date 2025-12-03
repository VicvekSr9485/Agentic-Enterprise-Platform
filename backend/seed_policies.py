#!/usr/bin/env python3
"""
Seed Policy Documents with Embeddings
======================================
Populates the policy_documents vector collection with demo company policies.
"""

import os
import sys
from dotenv import load_dotenv
import vecs
from google import genai

load_dotenv()

POLICIES = [
    {
        "id": "pol-001",
        "filename": "return_policy.pdf",
        "category": "customer_service",
        "title": "Product Return Policy",
        "content": """Our return policy allows customers to return products within 30 days of purchase. 
Electronics must be returned within 14 days and cannot be opened. All returns require original 
receipt and packaging. Refunds are processed within 5-7 business days to the original payment method.
Restocking fee of 15% applies to opened electronics. Custom or personalized items cannot be returned.
For warranty issues, refer to manufacturer warranty policy."""
    },
    {
        "id": "pol-002",
        "filename": "shipping_policy.pdf",
        "category": "customer_service",
        "title": "Shipping and Delivery Policy",
        "content": """We offer free standard shipping on orders over $100. Standard shipping takes 5-7 business days.
Express shipping is available for $15 (2-3 days) and overnight shipping for $30 (next business day).
International shipping available to select countries with customs duties paid by customer.
Tracking numbers provided for all shipments. Address changes must be requested within 2 hours of order placement."""
    },
    {
        "id": "pol-003",
        "filename": "warranty_policy.pdf",
        "category": "customer_service",
        "title": "Product Warranty Policy",
        "content": """All products come with a 1-year manufacturer warranty covering defects in materials and workmanship.
Extended warranty available for purchase at checkout (2-year or 3-year options). 
Warranty does not cover normal wear and tear, misuse, or accidental damage.
Claims must be filed within warranty period with proof of purchase. Return shipping for warranty claims is free.
Warranty replacement or repair determined by manufacturer."""
    },
    {
        "id": "pol-004",
        "filename": "privacy_policy.pdf",
        "category": "compliance",
        "title": "Customer Privacy Policy",
        "content": """We collect customer information including name, email, address, and payment details for order processing.
Data is encrypted using industry-standard AES-256 encryption and stored securely on SOC 2 compliant servers.
We do not sell customer data to third parties. Limited data sharing with shipping partners for fulfillment only.
Customers can request data deletion at any time by contacting privacy@company.com. GDPR and CCPA compliant.
Cookies used for analytics and shopping cart functionality - see cookie policy for details."""
    },
    {
        "id": "pol-005",
        "filename": "pto_policy.pdf",
        "category": "human_resources",
        "title": "Paid Time Off Policy",
        "content": """Full-time employees accrue 15 days paid vacation per year (prorated for partial years based on start date).
10 sick days provided annually, not prorated. Unused vacation can be rolled over up to 5 days to following year.
Vacation requests require 2 weeks advance notice for approval by manager. Sick leave does not require advance notice
but must be reported by start of business day. Vacation days can be used in half-day increments. 
Sick days cannot be cashed out. Upon termination, unused vacation days are paid out at current salary rate."""
    },
    {
        "id": "pol-006",
        "filename": "remote_work_policy.pdf",
        "category": "human_resources",
        "title": "Remote Work Policy",
        "content": """Employees may work remotely up to 3 days per week with direct manager approval. 
Full remote work available for positions approved by department head and HR. Remote employees must maintain
reliable high-speed internet connection (minimum 25 Mbps) and be available during core hours 10am-3pm EST.
Home office stipend of $500 provided annually for equipment (desk, chair, monitor). Company laptop required
for all remote work. Personal devices not permitted for company work. Monthly virtual team meetings mandatory."""
    },
    {
        "id": "pol-007",
        "filename": "data_security_policy.pdf",
        "category": "compliance",
        "title": "Data Security and IT Policy",
        "content": """All employee devices must have encrypted hard drives (BitLocker/FileVault) and up-to-date antivirus software.
Multi-factor authentication (MFA) required for all company systems including email, Slack, and database access.
Passwords must be minimum 12 characters with uppercase, lowercase, numbers, and special characters. No password reuse.
Annual security awareness training completion required by January 31st. Report security incidents or phishing attempts
to security@company.com within 1 hour of discovery. USB drives must be encrypted. No personal cloud storage for company data."""
    },
    {
        "id": "pol-008",
        "filename": "code_of_conduct.pdf",
        "category": "compliance",
        "title": "Employee Code of Conduct",
        "content": """Employees must maintain professional conduct at all times in workplace and company-sponsored events.
Harassment, discrimination, or retaliation of any kind is strictly prohibited and will result in immediate 
disciplinary action up to and including termination. All conflicts of interest must be disclosed to HR and manager.
Confidential company information including financials, customer data, and trade secrets must not be shared externally.
Social media posts should not reference company matters without PR approval. Violations can be anonymously reported 
to ethics hotline 1-800-ETHICS-1. Zero tolerance for theft, fraud, or violence."""
    },
    {
        "id": "pol-009",
        "filename": "expense_reimbursement.pdf",
        "category": "human_resources",
        "title": "Expense Reimbursement Policy",
        "content": """Business expenses require pre-approval from manager for amounts over $500. Submit expense reports
within 30 days of expense date with itemized receipts. Reimbursement processed within 2 pay cycles.
Approved expenses include: client meals (up to $75/person), travel, accommodation, and necessary supplies.
Alcohol reimbursement limited to client entertainment only. Mileage reimbursed at IRS standard rate ($0.67/mile).
Flight bookings must be economy class unless flight exceeds 5 hours. Hotel rate not to exceed $200/night in standard markets."""
    },
    {
        "id": "pol-010",
        "filename": "equipment_policy.pdf",
        "category": "human_resources",
        "title": "Company Equipment Policy",
        "content": """All company-issued equipment (laptops, phones, monitors) remains company property and must be returned
upon termination or when replaced. Equipment damage must be reported to IT immediately. Loss or theft must be
reported to IT and security within 24 hours. Personal use of company equipment permitted during non-work hours
but subject to monitoring. No illegal content or activity. Software installations require IT approval.
Equipment upgrades available every 3 years or as needed for performance. Return damaged equipment for disposal,
do not throw away due to data security requirements."""
    }
]

def seed_policies():
    """Insert policy documents with embeddings into vector database"""
    
    print("🔌 Connecting to Supabase...")
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("❌ Error: SUPABASE_DB_URL not set in environment")
        sys.exit(1)
    
    vx = vecs.create_client(db_url)
    
    print("📚 Creating/getting policy_documents collection...")
    docs = vx.get_or_create_collection(name="policy_documents", dimension=768)
    
    print("🤖 Initializing embedding model...")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY not set in environment")
        sys.exit(1)
    
    client = genai.Client(api_key=api_key)
    
    print(f"\n📝 Inserting {len(POLICIES)} policy documents...\n")
    
    records = []
    for i, policy in enumerate(POLICIES, 1):
        print(f"  [{i}/{len(POLICIES)}] Embedding: {policy['title']}")
        
        try:
            response = client.models.embed_content(
                model="text-embedding-004",
                contents=policy['content']
            )
            embedding = response.embeddings[0].values
            
            records.append((
                policy['id'],
                embedding,
                {
                    "filename": policy['filename'],
                    "category": policy['category'],
                    "title": policy['title'],
                    "content": policy['content']
                }
            ))
            
            print(f"      ✓ Embedded ({len(embedding)} dimensions)")
            
        except Exception as e:
            print(f"      ❌ Error embedding policy: {e}")
            continue
    
    if not records:
        print("\n❌ No policies were successfully embedded")
        sys.exit(1)
    
    print(f"\n💾 Upserting {len(records)} records to vector database...")
    try:
        docs.upsert(records=records)
        print("✅ Successfully inserted policy documents!")
        
        print("\n🔍 Creating vector index...")
        docs.create_index()
        print("✅ Index created!")
        
        print("\n🧪 Testing vector search with sample query...")
        test_embedding = client.models.embed_content(
            model="text-embedding-004",
            contents="What is the return policy for electronics?"
        ).embeddings[0].values
        
        results = docs.query(
            data=test_embedding,
            limit=2,
            include_value=True,
            include_metadata=True
        )
        
        if results:
            print(f"✅ Found {len(results)} relevant policies:")
            for result in results:
                print(f"   - {result[2]['title']}")
        else:
            print("⚠️  No results found in test query")
        
        print(f"\n🎉 Policy database seeded successfully with {len(records)} documents!")
        print(f"📊 Collection: policy_documents (768-dim vectors)")
        
    except Exception as e:
        print(f"\n❌ Error inserting records: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("  Policy Documents Vector Database Seeder")
    print("=" * 60)
    seed_policies()
