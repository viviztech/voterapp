import os
import sqlite3
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuration
# Default to local SQLite if no connection string is provided
DEFAULT_DB_URL = "sqlite:///voter_data.db"

def get_db_url():
    """
    Retrieves the database URL from Streamlit secrets (Cloud) or Environment (Docker) 
    or defaults to local SQLite.
    """
    # 1. Try Streamlit Secrets (for Community Cloud)
    if hasattr(st, "secrets") and "connections" in st.secrets and "voter_db" in st.secrets["connections"]:
        # Construct URL from parts if needed, or use a direct URL if stored
        # Typically Supabase provides a full postgres:// string which works with sqlalchemy
        # But we need to handle specific format: postgresql://...
        secret_conf = st.secrets["connections"]["voter_db"]
        if "url" in secret_conf:
            return secret_conf["url"]
        
        # Fallback to constructing from parts (typical Streamlit config)
        return f"postgresql://{secret_conf['username']}:{secret_conf['password']}@{secret_conf['host']}:{secret_conf['port']}/{secret_conf['database']}"

    # 2. Try Environment Variable (For Docker/Local override)
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    
    # 3. Default to Local SQLite
    return DEFAULT_DB_URL

def get_engine():
    url = get_db_url()
    # Simple workaround for Render/Supabase using 'postgres://' which SQLAlchemy deprecated
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    return create_engine(url)

def run_query(query, params=None):
    """
    Helper to run a query regardless of backend. 
    Returns list of dicts for SELECT, or commits for INSERT/UPDATE.
    """
    engine = get_engine()
    with engine.connect() as conn:
        if params is None:
            params = {}
            
        result = conn.execute(text(query), params)
        
        if query.strip().upper().startswith("SELECT"):
            # Return row mappings
            return [dict(row) for row in result.mappings()]
        else:
            conn.commit()
            return None
