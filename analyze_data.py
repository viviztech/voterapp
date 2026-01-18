import sqlite3
import pandas as pd

DB_PATH = 'voter_data.db'

def analyze():
    conn = sqlite3.connect(DB_PATH)
    
    print("--- Voter Roll Analysis ---\n")
    
    # 1. Total Voters
    total = conn.execute("SELECT COUNT(*) FROM voters").fetchone()[0]
    print(f"Total Voters Extracted: {total}")
    
    # 2. Gender Distribution
    print("\nGender Distribution:")
    df_gender = pd.read_sql_query("SELECT gender, COUNT(*) as count FROM voters GROUP BY gender", conn)
    print(df_gender)

    # 3. Age Stats
    print("\nAge Statistics:")
    df_age = pd.read_sql_query("SELECT MIN(age) as min_age, MAX(age) as max_age, AVG(age) as avg_age FROM voters", conn)
    print(df_age)
    
    # 4. Gen Z Analysis (Born ~1997-2008, Ages 18-29 in 2026)
    print("\n--- Gen Z Analysis (Ages 18-29) ---")
    gen_z_stats = pd.read_sql_query('''
        SELECT 
            COUNT(*) as total_gen_z,
            AVG(age) as avg_age,
            SUM(CASE WHEN gender = 'Male' THEN 1 ELSE 0 END) as male_count,
            SUM(CASE WHEN gender = 'Female' THEN 1 ELSE 0 END) as female_count
        FROM voters 
        WHERE age >= 18 AND age <= 29
    ''', conn)
    
    count = gen_z_stats.iloc[0]['total_gen_z']
    if total > 0:
        percent = (count / total) * 100
        print(f"Total Gen Z Voters: {count} ({percent:.2f}%)")
        print(f"Average Age: {gen_z_stats.iloc[0]['avg_age']:.1f}")
        print(f"Gender Split: Male: {gen_z_stats.iloc[0]['male_count']}, Female: {gen_z_stats.iloc[0]['female_count']}")
    
    # 5. Voters per Booth
    print("\nVoters per Polling Station:")
    df_booth = pd.read_sql_query("SELECT polling_station_id, COUNT(*) as count FROM voters GROUP BY polling_station_id", conn)
    print(df_booth)

    conn.close()

if __name__ == "__main__":
    try:
        analyze()
    except Exception as e:
        print(f"Analysis failed (maybe no data yet?): {e}")
        print("Note: Run extract_voters.py first to populate the database.")
