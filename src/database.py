import sqlite3
import os
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, "leads.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Check if old schema exists
        c.execute("PRAGMA table_info(leads)")
        columns = [row[1] for row in c.fetchall()]
        
        needs_migration = 'vercel_url' in columns
        
        if needs_migration:
            c.execute("ALTER TABLE leads RENAME TO leads_old")
            
        # Create new tables
        c.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                url TEXT UNIQUE,
                descricao TEXT,
                nicho TEXT,
                cidade TEXT,
                status TEXT DEFAULT 'NEW',
                score INTEGER DEFAULT 0,
                motivos_score TEXT DEFAULT '',
                fonte TEXT DEFAULT '',
                telefone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                score INTEGER,
                motivos TEXT,
                performance_time REAL,
                has_https BOOLEAN,
                has_viewport BOOLEAN,
                has_h1 BOOLEAN,
                textos_principais TEXT,
                cor_detectada TEXT,
                raw_data JSON,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES leads(id)
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS outreach (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                canal TEXT,
                mensagem TEXT,
                status TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES leads(id)
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                slug TEXT,
                vercel_url TEXT,
                design_brief TEXT,
                status TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES leads(id)
            )
        ''')
        
        # Migra bancos existentes: adiciona as colunas de contato sem tocar nos dados atuais
        c.execute("PRAGMA table_info(leads)")
        colunas_leads = {row[1] for row in c.fetchall()}
        for coluna in ("telefone", "email"):
            if coluna not in colunas_leads:
                c.execute(f"ALTER TABLE leads ADD COLUMN {coluna} TEXT DEFAULT ''")

        # Triggers
        c.execute('''
            CREATE TRIGGER IF NOT EXISTS update_leads_atualizado_em 
            AFTER UPDATE ON leads
            BEGIN
                UPDATE leads SET atualizado_em = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        ''')
        
        c.execute('''
            CREATE TRIGGER IF NOT EXISTS update_projects_atualizado_em
            AFTER UPDATE ON projects
            BEGIN
                UPDATE projects SET atualizado_em = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        ''')
        
        if needs_migration:
            # Migrate data
            c.execute("""
                INSERT INTO leads (id, nome, url, descricao, nicho, cidade, status, score, motivos_score, criado_em, atualizado_em)
                SELECT id, nome, url, descricao, nicho, cidade, status, score, motivos_score, criado_em, CURRENT_TIMESTAMP
                FROM leads_old
            """)
            
            # Map old valid statuses? DEPLOYED -> WON or leave as DEPLOYED?
            # Let's map DEPLOYED to WON if valid statuses must be strict. But to be safe, I'll just map DEPLOYED to WON.
            # No, keep the data as is. The prompt just states new requirements for valid lead statuses. I won't change existing status values unless necessary.
            
            c.execute("""
                INSERT INTO projects (lead_id, vercel_url, design_brief, slug, status, criado_em)
                SELECT id, vercel_url, design_brief, '', 'COMPLETED', CURRENT_TIMESTAMP
                FROM leads_old
                WHERE (vercel_url IS NOT NULL AND vercel_url != '') OR (design_brief IS NOT NULL AND design_brief != '')
            """)
            
            c.execute("""
                INSERT INTO outreach (lead_id, canal, mensagem, status, criado_em)
                SELECT id, 'EMAIL', outreach_message, 'DRAFT', CURRENT_TIMESTAMP
                FROM leads_old
                WHERE outreach_message IS NOT NULL AND outreach_message != ''
            """)
            
            c.execute("DROP TABLE leads_old")
            
        conn.commit()

def insert_lead(nome, url, descricao, nicho, cidade):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO leads (nome, url, descricao, nicho, cidade, status)
                VALUES (?, ?, ?, ?, ?, 'NEW')
            ''', (nome, url, descricao, nicho, cidade))
            conn.commit()
        except sqlite3.IntegrityError:
            pass 

def get_all_leads():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT l.*, p.vercel_url, o.mensagem as outreach_message, p.design_brief 
            FROM leads l 
            LEFT JOIN projects p ON p.lead_id = l.id 
            LEFT JOIN outreach o ON o.lead_id = l.id 
            ORDER BY l.status DESC, l.score ASC, l.criado_em DESC
        """)
        rows = c.fetchall()
        return [dict(row) for row in rows]

def update_lead_status(url, status, vercel_url=''):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE leads SET status = ? WHERE url = ?", (status, url))
        
        if vercel_url:
            c.execute("SELECT id FROM leads WHERE url = ?", (url,))
            row = c.fetchone()
            if row:
                lead_id = row[0]
                c.execute("SELECT id FROM projects WHERE lead_id = ?", (lead_id,))
                proj = c.fetchone()
                if proj:
                    c.execute("UPDATE projects SET vercel_url = ? WHERE lead_id = ?", (vercel_url, lead_id))
                else:
                    c.execute("INSERT INTO projects (lead_id, vercel_url) VALUES (?, ?)", (lead_id, vercel_url))
        conn.commit()

def update_lead_contacts(url, telefone='', email=''):
    """Preenche telefone/e-mail só onde o lead ainda não tem valor. Nunca sobrescreve nem apaga."""
    if not telefone and not email:
        return
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE leads SET
                telefone = CASE WHEN COALESCE(telefone, '') = '' THEN ? ELSE telefone END,
                email = CASE WHEN COALESCE(email, '') = '' THEN ? ELSE email END
            WHERE url = ?
        """, (telefone or '', email or '', url))
        conn.commit()

def get_leads_sem_contato():
    """Leads sem telefone E sem e-mail (candidatos a busca/backfill de contato)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM leads WHERE COALESCE(telefone, '') = '' AND COALESCE(email, '') = ''")
        return [dict(row) for row in c.fetchall()]

def update_lead_score(url, score, motivos):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE leads SET score = ?, motivos_score = ?, status = 'AUDITED' WHERE url = ?", (score, motivos, url))
        conn.commit()

def save_outreach_data(url, outreach_message, design_brief):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM leads WHERE url = ?", (url,))
        row = c.fetchone()
        if row:
            lead_id = row[0]
            # Upsert outreach
            c.execute("SELECT id FROM outreach WHERE lead_id = ?", (lead_id,))
            if c.fetchone():
                c.execute("UPDATE outreach SET mensagem = ? WHERE lead_id = ?", (outreach_message, lead_id))
            else:
                c.execute("INSERT INTO outreach (lead_id, canal, mensagem, status) VALUES (?, 'EMAIL', ?, 'DRAFT')", (lead_id, outreach_message))
                
            # Upsert design_brief in projects
            c.execute("SELECT id FROM projects WHERE lead_id = ?", (lead_id,))
            if c.fetchone():
                c.execute("UPDATE projects SET design_brief = ? WHERE lead_id = ?", (str(design_brief), lead_id))
            else:
                c.execute("INSERT INTO projects (lead_id, design_brief) VALUES (?, ?)", (lead_id, str(design_brief)))
        conn.commit()

def save_audit(lead_id, audit_data):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO audits (lead_id, score, motivos, performance_time, has_https, has_viewport, has_h1, textos_principais, cor_detectada, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lead_id,
            audit_data.get('score', 0),
            audit_data.get('motivos', ''),
            audit_data.get('performance_time', 0.0),
            audit_data.get('has_https', False),
            audit_data.get('has_viewport', False),
            audit_data.get('has_h1', False),
            json.dumps(audit_data.get('textos_principais', [])),
            audit_data.get('cor_detectada', ''),
            json.dumps(audit_data.get('raw_data', {}))
        ))
        conn.commit()
        return c.lastrowid

def get_lead_by_url(url):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM leads WHERE url = ?", (url,))
        row = c.fetchone()
        return dict(row) if row else None

def get_lead_by_id(id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM leads WHERE id = ?", (id,))
        row = c.fetchone()
        return dict(row) if row else None

def get_leads_by_status(status):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM leads WHERE status = ?", (status,))
        rows = c.fetchall()
        return [dict(row) for row in rows]

def save_project(lead_id, slug, design_brief):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO projects (lead_id, slug, design_brief, status)
            VALUES (?, ?, ?, 'NEW')
        ''', (lead_id, slug, design_brief))
        conn.commit()
        return c.lastrowid

def update_project_deployment(project_id, vercel_url):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE projects SET vercel_url = ?, status = 'DEPLOYED' WHERE id = ?", (vercel_url, project_id))
        conn.commit()

def get_lead_with_audit(lead_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        lead = c.fetchone()
        if not lead:
            return None
            
        lead_dict = dict(lead)
        c.execute("SELECT * FROM audits WHERE lead_id = ? ORDER BY criado_em DESC LIMIT 1", (lead_id,))
        audit = c.fetchone()
        if audit:
            lead_dict['audit'] = dict(audit)
            if lead_dict['audit'].get('raw_data'):
                try:
                    lead_dict['audit']['raw_data'] = json.loads(lead_dict['audit']['raw_data'])
                except:
                    pass
            if lead_dict['audit'].get('textos_principais'):
                try:
                    lead_dict['audit']['textos_principais'] = json.loads(lead_dict['audit']['textos_principais'])
                except:
                    pass
        else:
            lead_dict['audit'] = None
            
        return lead_dict