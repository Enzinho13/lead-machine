import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, "leads.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            url TEXT UNIQUE,
            descricao TEXT,
            nicho TEXT,
            cidade TEXT,
            status TEXT DEFAULT 'NEW',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    colunas_novas = [
        "score INTEGER DEFAULT 0",
        "motivos_score TEXT DEFAULT ''",
        "vercel_url TEXT DEFAULT ''",
        "outreach_message TEXT DEFAULT ''",
        "design_brief TEXT DEFAULT ''"
    ]
    
    for col in colunas_novas:
        try:
            c.execute(f"ALTER TABLE leads ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass 
            
    conn.commit()
    conn.close()

def insert_lead(nome, url, descricao, nicho, cidade):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO leads (nome, url, descricao, nicho, cidade, status)
            VALUES (?, ?, ?, ?, ?, 'NEW')
        ''', (nome, url, descricao, nicho, cidade))
        conn.commit()
    except sqlite3.IntegrityError:
        pass 
    finally:
        conn.close()

def get_all_leads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM leads ORDER BY status DESC, score ASC, criado_em DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_lead_status(url, status, vercel_url=''):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE leads SET status = ?, vercel_url = ? WHERE url = ?", (status, vercel_url, url))
    conn.commit()
    conn.close()

def update_lead_score(url, score, motivos):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE leads SET score = ?, motivos_score = ?, status = 'AUDITED' WHERE url = ?", (score, motivos, url))
    conn.commit()
    conn.close()

def save_outreach_data(url, outreach_message, design_brief):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE leads SET outreach_message = ?, design_brief = ? WHERE url = ?", (outreach_message, str(design_brief), url))
    conn.commit()
    conn.close()