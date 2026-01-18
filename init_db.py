from database import get_engine
from sqlalchemy import text

def init_db():
    engine = get_engine()
    
    print(f"Initializing database using: {engine.url}")

    with engine.connect() as conn:
        # Drop tables if they exist to reset
        conn.execute(text('DROP TABLE IF EXISTS voters'))
        conn.execute(text('DROP TABLE IF EXISTS extraction_logs'))
        # Note: We drop polling_stations last or handle Foreign Keys carefully
        conn.execute(text('DROP TABLE IF EXISTS polling_stations'))

        # Create polling_stations table
        conn.execute(text('''
            CREATE TABLE polling_stations (
                id SERIAL PRIMARY KEY,
                booth_no VARCHAR(50),
                part_no VARCHAR(50),
                section_no VARCHAR(50),
                location_name TEXT,
                assembly_constituency TEXT,
                UNIQUE(part_no, section_no)
            )
        '''.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT" if "sqlite" in str(engine.url) else "SERIAL PRIMARY KEY")))

        # Create voters table
        conn.execute(text('''
            CREATE TABLE voters (
                id SERIAL PRIMARY KEY,
                epic_number VARCHAR(50) UNIQUE,
                name TEXT,
                relation_type VARCHAR(20),
                relation_name TEXT,
                house_number TEXT,
                age INTEGER,
                gender VARCHAR(20),
                polling_station_id INTEGER,
                raw_text TEXT
            )
        '''.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT" if "sqlite" in str(engine.url) else "SERIAL PRIMARY KEY")))
        # Removed Foreign Key constraint for simplicity across DBs, or add it back if strictly needed

        # Create logs table
        conn.execute(text('''
            CREATE TABLE extraction_logs (
                id SERIAL PRIMARY KEY,
                page_number INTEGER,
                status VARCHAR(20),
                error_message TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT" if "sqlite" in str(engine.url) else "SERIAL PRIMARY KEY")))

        conn.commit()
    print("Database initialized successfully.")

if __name__ == '__main__':
    init_db()
