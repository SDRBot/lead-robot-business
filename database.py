import sqlite3
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

class DatabaseService:
    """Improved database service with connection pooling"""
    
    def __init__(self, database_url: str = "leads.db"):
        self.database_url = database_url
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialized = False
    
    @asynccontextmanager
    async def get_connection(self):
        """Async context manager for database connections"""
        loop = asyncio.get_event_loop()
        
        def get_conn():
            conn = sqlite3.connect(self.database_url)
            conn.row_factory = sqlite3.Row
            return conn
        
        conn = await loop.run_in_executor(self.executor, get_conn)
        try:
            yield conn
        finally:
            await loop.run_in_executor(self.executor, conn.close)
    
    async def execute_query(self, query: str, params: tuple = (), fetch: str = None):
        """Execute query with connection pooling"""
        async with self.get_connection() as conn:
            loop = asyncio.get_event_loop()
            
            def execute():
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
            
            return await loop.run_in_executor(self.executor, execute)
    
    async def init_database(self):
        """Initialize database with indexes"""
        if self._initialized:
            return
            
        # Create customers table
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS customers (
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
            )
        ''')
        
        # Create leads table
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS leads (
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
            )
        ''')
        
        # Create analytics table (from your original app.py)
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS analytics (
                id TEXT PRIMARY KEY,
                customer_id TEXT,
                event_type TEXT NOT NULL,
                data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Create zapier webhooks table
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS zapier_webhooks (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                webhook_url TEXT NOT NULL,
                events TEXT NOT NULL,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        await self.execute_query('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add indexes for performance
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_leads_customer_id ON leads(customer_id)')
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)')
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at)')
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)')
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)')
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_zapier_webhooks_customer_id ON zapier_webhooks(customer_id)')
        
        self._initialized = True
        print("✅ Database initialized with performance indexes")
    
    async def create_customer(self, customer_data: Dict[str, Any]) -> str:
        """Create a new customer"""
        customer_id = str(uuid.uuid4())
        await self.execute_query('''
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
        return await self.execute_query(
            "SELECT * FROM customers WHERE api_key = ? AND status = 'active'",
            (api_key,),
            fetch='one'
        )
    
    async def get_customer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get customer by email"""
        return await self.execute_query(
            "SELECT * FROM customers WHERE email = ? AND status = 'active'",
            (email,),
            fetch='one'
        )
    
    async def create_lead(self, lead_data: Dict[str, Any]) -> str:
        """Create a new lead"""
        lead_id = str(uuid.uuid4())
        await self.execute_query('''
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
        return await self.execute_query('''
            SELECT * FROM leads WHERE customer_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        ''', (customer_id, limit, skip), fetch='all')
    
    async def update_customer_usage(self, customer_id: str):
        """Increment customer's lead usage counter"""
        await self.execute_query('''
            UPDATE customers 
            SET leads_used_this_month = leads_used_this_month + 1, updated_at = ?
            WHERE id = ?
        ''', (datetime.now(), customer_id))
    
    async def set_customer_password(self, api_key: str, password_hash: str):
        """Set customer password hash"""
        await self.execute_query('''
            UPDATE customers 
            SET password_hash = ?, updated_at = ?
            WHERE api_key = ?
        ''', (password_hash, datetime.now(), api_key))
    
    async def log_analytics_event(self, customer_id: str, event_type: str, data: Dict[str, Any]):
        """Log an analytics event"""
        await self.execute_query('''
            INSERT INTO analytics (id, customer_id, event_type, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), customer_id, event_type, 
            json.dumps(data), datetime.now()
        ))

# Global instance
db_service = DatabaseService()
