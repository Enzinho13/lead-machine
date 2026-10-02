import sqlite3
import os

# Descobre a pasta raiz do projeto automaticamente
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
    
    # Adiciona colunas novas automaticamente sem quebrar a tabela atual
    for col in ["score INTEGER DEFAULT 0", "motivos_score TEXT DEFAULT ''", "vercel_url TEXT DEFAULT ''"]:
        try:
            c.execute(f"ALTER TABLE leads ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass # Coluna já existe
            
    conn.commit()
    conn.close()

def insert_lead(nome, url, descricao, nicho, cidade):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO leads (nome, url, descricao, nicho, cidade, status, score, motivos_score, vercel_url)
            VALUES (?, ?, ?, ?, ?, 'NEW', 0, '', '')
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

# Agora esta função guarda o link da vercel
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