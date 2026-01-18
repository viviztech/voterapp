import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import time
from extract_voters import process_document
from init_db import init_db

# Page config
st.set_page_config(
    page_title="Voter Roll Analytics",
    page_icon="🗳️",
    layout="wide"
)

DB_PATH = 'voter_data.db'
UPLOAD_DIR = 'uploads'

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Upload & Extract", "Analytics Dashboard"])

st.sidebar.divider()
if st.sidebar.button("🗑️ Reset Database", type="secondary"):
    try:
        init_db()
        st.sidebar.success("Database has been cleared!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to reset: {e}")

def get_connection():
    return sqlite3.connect(DB_PATH)

if page == "Upload & Extract":
    st.title("📄 Upload Documents")
    st.write("Upload the electoral roll PDF or Image (JPG, PNG) to extract voter information using local AI.")
    
    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "jpg", "jpeg", "png", "webp"])
    
    if uploaded_file is not None:
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Saved file to {file_path}")
        
        if st.button("Start Extraction"):
            st.warning("⚠️ This process depends on your local GPU/CPU and may take time.")
            
            # Initialize DB if needed (or reset)
            # init_db() # Optional: Uncomment to reset DB on new upload
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Run extraction
            with st.spinner("Initializing AI and Reading Document..."):
                # We need a wrapper to update Streamlit UI from the generator
                def update_progress(current, total, msg):
                    if total > 0:
                        percent = int((current / total) * 100)
                    else:
                        percent = 0
                    progress_bar.progress(percent)
                    status_text.text(msg)
                
                # Iterate through the generator
                for status in process_document(file_path, progress_callback=update_progress):
                    if "Error" in status:
                        st.error(status)
                    else:
                        print(status) # Log to console
                
                st.success("Extraction Complete! Go to Analytics Dashboard to view results.")

if page == "Analytics Dashboard":
    st.title("📊 Voter Analytics")
    
    if not os.path.exists(DB_PATH):
        st.error("Database not found. Please upload and extract data first.")
    else:
        conn = get_connection()
        
        # 1. Headline Stats
        col1, col2, col3 = st.columns(3)
        
        try:
            total_voters = pd.read_sql("SELECT COUNT(*) FROM voters", conn).iloc[0,0]
            total_booths = pd.read_sql("SELECT COUNT(*) FROM polling_stations", conn).iloc[0,0]
            
            col1.metric("Total Voters", total_voters)
            col2.metric("Polling Stations", total_booths)
            
            # 2. Gender Distribution
            df_gender = pd.read_sql("SELECT gender, COUNT(*) as count FROM voters GROUP BY gender", conn)
            
            # 3. Gen Z Stats
            df_genz = pd.read_sql("SELECT COUNT(*) as count FROM voters WHERE age >= 18 AND age <= 29", conn)
            genz_count = df_genz.iloc[0,0]
            genz_percent = (genz_count / total_voters * 100) if total_voters > 0 else 0
            
            col3.metric("Gen Z Voters (18-29)", f"{genz_count} ({genz_percent:.1f}%)")
            
            st.divider()
            
            # Charts Row 1
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("Gender Distribution")
                if not df_gender.empty:
                    fig_gender = px.pie(df_gender, values='count', names='gender', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                    st.plotly_chart(fig_gender, use_container_width=True)
                else:
                    st.info("No data available.")

            with c2:
                st.subheader("Age Distribution")
                df_age = pd.read_sql("SELECT age FROM voters WHERE age > 0", conn) # Filter valid ages
                if not df_age.empty:
                    fig_age = px.histogram(df_age, x="age", nbins=20, title="Voter Age Histogram", color_discrete_sequence=['#636EFA'])
                    st.plotly_chart(fig_age, use_container_width=True)
                else:
                    st.info("No data available.")
            
            # Data Table
            st.subheader("Voter Data Preview")
            df_voters = pd.read_sql("SELECT epic_number, name, relation_name, age, gender, house_number FROM voters LIMIT 100", conn)
            st.dataframe(df_voters, use_container_width=True)
            
            # Download
            st.subheader("Download Data")
            if st.button("Prepare CSV"):
                full_df = pd.read_sql("SELECT * FROM voters", conn)
                csv = full_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download Full Voter List (CSV)",
                    csv,
                    "voter_list.csv",
                    "text/csv",
                    key='download-csv'
                )
                
        except Exception as e:
            st.error(f"Error loading analytics: {e}")
        finally:
            conn.close()
