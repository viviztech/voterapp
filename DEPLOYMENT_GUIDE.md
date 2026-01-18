# Deploying to Streamlit Community Cloud

## ⚠️ Critical Limitations
Before you deploy, you must understand two major constraints of the free Streamlit Community Cloud:

1.  **Ephemeral Filesystem**: Changes to local files (like `voter_data.db`) are **NOT saved** permanently. If your app reboots (which happens at least once a day), **you will lose all extracted data**.
2.  **No Local AI**: You **cannot run Ollama** directly on Streamlit Cloud. The cloud machines do not have GPUs and don't allow running background services like simple local Ollama.

---

## ✅ Solution 1: Connect a Persistent Database (Supabase/Postgres)
To save data permanently, you must connect to a cloud database. We recommend **Supabase** (Free Tier available).

### Step 1: Create a Database
1.  Go to [Supabase.com](https://supabase.com) and create a free project.
2.  Go to **Project Settings -> Database -> Connection String**.
3.  Copy the **URI**. It looks like: `postgresql://postgres:[PASSWORD]@db.supabase.co:5432/postgres`

### Step 2: Configure Streamlit
1.  In your GitHub repo, add `psycopg2-binary` to `requirements.txt`.
2.  On Streamlit Cloud dashboard, go to your App Settings -> **Secrets**.
3.  Add your database credentials:
    ```toml
    [connections.voter_db]
    dialect = "postgresql"
    host = "aws-0-us-east-1.pooler.supabase.com"
    port = "5432"
    database = "postgres"
    username = "postgres"
    password = "YOUR_PASSWORD"
    ```

### Step 3: Update Code
You will need to modify `init_db.py`, `app.py`, and `extract_voters.py` to use `st.connection` or `SQLAlchemy` instead of raw `sqlite3`.

---

## 🤖 Solution 2: Remote Ollama Host
Since Ollama can't run on Streamlit Cloud, you must point the app to a remote server where Ollama is running (e.g., your home PC or an AWS EC2 instance).

1.  **Expose your local Ollama**:
    -   Use **ngrok** to expose your local port 11434 to the internet:
        ```bash
        ngrok http 11434
        ```
    -   This gives you a public URL like `https://1234-56-78.ngrok-free.app`.

2.  **Configure Secrets**:
    -   In Streamlit Cloud Secrets:
        ```toml
        OLLAMA_HOST = "https://1234-56-78.ngrok-free.app"
        ```

---

## 🚀 Recommended Deployment Architecture
For a robust production app, we recommend **Self-Hosting** instead of Streamlit Community Cloud, using Docker.

1.  **Rent a GPU Server** (e.g., RunPod, LambdaLabs, or AWS g4dn).
2.  **Run Docker Compose**:
    ```bash
    docker-compose up -d
    ```
    This automatically sets up the App + Database + Local Ollama in one go, bypassing all the limitations above.
