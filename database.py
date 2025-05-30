import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import uuid
import threading

class DatabaseService:
    """Simple synchronous database service that works reliably"""
    
    def __init__(self, database_url: str = "leads.db"):
        self.database_url = database_url
        self._initialized = False
        self._lock = threading.Lock()
    
    def get_connection(self):
        """Get a connection with proper settings"""
        conn = sqlite3.connect(self.database_url, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def execute_query(self, query: str, params: tuple = (), fetch: str = None):
        """Execute query synchronously"""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                if fetch == 'one':
                    result = cursor.fetchone()
                    return dict(result) if result else None
                elif fetch == 'all':
                    return [dict(row) for row in cursor.fetchall()]
                else:
                    conn.commit()
                    return cursor.rowcount
    
    def init_database(self):
        """Initialize database synchronously"""
        if self._initialized:
            return
            
        print("🔧 Initializing database...")
        
        # Create tables one by one
        tables = [
            '''CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                stripe_customer_id TEXT UNIQUE,
                stripe_subscription_id TEXT,
                plan TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                api_key TEXT UNIQUE NOT NULL,
                leads_limit INTEGER NOT NULL,
                leads_used_this_month INTEGER DEFAULT 0,
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                email TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                company TEXT,
                phone TEXT,
                source TEXT,
                qualification_score INTEGER DEFAULT 0,
                qualification_stage TEXT DEFAULT 'new',
                conversation_data TEXT DEFAULT '[]',
                webhook_sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS analytics (
                id TEXT PRIMARY KEY,
                customer_id TEXT,
                event_type TEXT NOT NULL,
                data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS zapier_webhooks (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                webhook_url TEXT NOT NULL,
                events TEXT NOT NULL,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS support_tickets (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS promo_codes (
                id TEXT PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                trial_days INTEGER NOT NULL DEFAULT 30,
                plan_override TEXT,
                max_uses INTEGER,
                current_uses INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                description TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        
        # Create indexes
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_leads_customer_id ON leads(customer_id)',
            'CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)',
            'CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)',
            'CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)'
        ]
        
        try:
            # Execute all table creation
            for i, table_sql in enumerate(tables):
                self.execute_query(table_sql)
                print(f"✅ Created table {i+1}/{len(tables)}")
            
            # Create indexes
            for i, index_sql in enumerate(indexes):
                self.execute_query(index_sql)
                print(f"✅ Created index {i+1}/{len(indexes)}")
            
            self._initialized = True
            print("✅ Database initialized successfully")
            
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            raise
    
    # Wrapper methods to make them async-compatible
    async def async_execute_query(self, query: str, params: tuple = (), fetch: str = None):
        """Async wrapper for execute_query"""
        return self.execute_query(query, params, fetch)
    
    async def create_customer(self, customer_data: Dict[str, Any]) -> str:
        """Create a new customer"""
        customer_id = str(uuid.uuid4())
        self.execute_query('''
            INSERT INTO customers (
                id, email, stripe_customer_id, stripe_subscription_id, 
                plan, api_key, leads_limit, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            customer_id, customer_data['email'], customer_data.get('stripe_customer_id'),
            customer_data.get('stripe_subscription_id'), customer_data['plan'],
            customer_data['api_key'], customer_data['leads_limit'], 'active',
            datetime.now(), datetime.now()
        ))
        return customer_id
    
    async def get_customer_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get customer by API key"""
        return self.execute_query(
            "SELECT * FROM customers WHERE api_key = ? AND status = 'active'",
            (api_key,),
            fetch='one'
        )
    
    async def create_lead(self, lead_data: Dict[str, Any]) -> str:
        """Create a new lead"""
        lead_id = str(uuid.uuid4())
        self.execute_query('''
            INSERT INTO leads (
                id, customer_id, email, first_name, last_name, 
                company, phone, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lead_id, lead_data['customer_id'], lead_data['email'],
            lead_data.get('first_name'), lead_data.get('last_name'),
            lead_data.get('company'), lead_data.get('phone'),
            lead_data.get('source', 'api'), datetime.now(), datetime.now()
        ))
        return lead_id
    
    async def get_leads(self, customer_id: str, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Get leads for a customer"""
        return self.execute_query('''
            SELECT * FROM leads WHERE customer_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        ''', (customer_id, limit, skip), fetch='all') or []
    
    async def update_customer_usage(self, customer_id: str):
        """Increment customer's lead usage counter"""
        self.execute_query('''
            UPDATE customers 
            SET leads_used_this_month = leads_used_this_month + 1, updated_at = ?
            WHERE id = ?
        ''', (datetime.now(), customer_id))
    
    async def set_customer_password(self, api_key: str, password_hash: str):
        """Set customer password hash"""
        self.execute_query('''
            UPDATE customers 
            SET password_hash = ?, updated_at = ?
            WHERE api_key = ?
        ''', (password_hash, datetime.now(), api_key))
    
    async def log_analytics_event(self, customer_id: str, event_type: str, data: Dict[str, Any]):
        """Log an analytics event"""
        self.execute_query('''
            INSERT INTO analytics (id, customer_id, event_type, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), customer_id, event_type, 
            json.dumps(data), datetime.now()
        ))

# Global instance
db_service = DatabaseService()
