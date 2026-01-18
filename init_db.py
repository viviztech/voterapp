import sqlite3

def init_db():
    conn = sqlite3.connect('voter_data.db')
    c = conn.cursor()

    # Drop tables if they exist to reset
    c.execute('DROP TABLE IF EXISTS voters')
    c.execute('DROP TABLE IF EXISTS polling_stations')
    c.execute('DROP TABLE IF EXISTS extraction_logs')

    # Create polling_stations table
    c.execute('''
        CREATE TABLE polling_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booth_no VARCHAR(50),
            part_no VARCHAR(50),
            section_no VARCHAR(50),
            location_name TEXT,
            assembly_constituency TEXT,
            UNIQUE(part_no, section_no)
        )
    ''')

    # Create voters table
    c.execute('''
        CREATE TABLE voters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_number VARCHAR(20) UNIQUE,
            name TEXT,
            relation_type VARCHAR(10),
            relation_name TEXT,
            house_number TEXT,
            age INTEGER,
            gender VARCHAR(10),
            polling_station_id INTEGER,
            raw_text TEXT,
            FOREIGN KEY (polling_station_id) REFERENCES polling_stations(id)
        )
    ''')

    # Create logs table
    c.execute('''
        CREATE TABLE extraction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_number INTEGER,
            status VARCHAR(20),
            error_message TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully: voter_data.db")

if __name__ == '__main__':
    init_db()
