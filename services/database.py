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
            
        # Create tables (keeping your existing schema)
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
        await self.execute_query('''
    ALTER TABLE leads ADD COLUMN webhook_sent BOOLEAN DEFAULT FALSE
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
        
        # Add indexes for performance
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_leads_customer_id ON leads(customer_id)')
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)')
        await self.execute_query('CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)')
        
        self._initialized = True
        print("✅ Database initialized with performance indexes")

# Global instance
db_service = DatabaseService()
