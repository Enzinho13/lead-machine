import sqlite3
import os
import json
import time
import uuid

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
                claimed_by TEXT DEFAULT '',
                claim_token TEXT DEFAULT '',
                claim_expires_at REAL DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                last_error TEXT DEFAULT '',
                retry_after REAL DEFAULT 0,
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

        # Migra bancos existentes: colunas de claim/retry do orquestrador (sem tocar nos dados atuais)
        for coluna, definicao in (
            ("claimed_by", "TEXT DEFAULT ''"), ("claim_token", "TEXT DEFAULT ''"), ("claim_expires_at", "REAL DEFAULT 0"),
            ("attempts", "INTEGER DEFAULT 0"), ("last_error", "TEXT DEFAULT ''"), ("retry_after", "REAL DEFAULT 0"),
        ):
            if coluna not in colunas_leads:
                c.execute(f"ALTER TABLE leads ADD COLUMN {coluna} {definicao}")

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
    """Um registro por lead: projeto e mensagem de outreach vêm da 1ª linha de cada tabela (não duplica o lead)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT l.*, p.vercel_url, o.mensagem as outreach_message, p.design_brief 
            FROM leads l 
            LEFT JOIN projects p ON p.id = (SELECT MIN(id) FROM projects WHERE lead_id = l.id) 
            LEFT JOIN outreach o ON o.id = (SELECT MIN(id) FROM outreach WHERE lead_id = l.id) 
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

def acquire_lease(url, worker_id, ttl_seconds=900, max_attempts=3, now=None, token=None):
    """Lease exclusivo de um lead (um único UPDATE atômico no SQLite). Devolve o TOKEN de ownership, ou None.

    O token é único por aquisição: só quem o detém renova, libera ou registra o desfecho do lead.
    Lease expirado (worker morto ou lento) pode ser retomado por outro worker, e o token antigo perde
    a autoridade. Cada aquisição conta uma tentativa (attempts + 1); sem tentativas restantes é recusada.
    """
    now = time.time() if now is None else now
    token = token or uuid.uuid4().hex
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        cur = conn.execute("""
            UPDATE leads
            SET claimed_by = ?, claim_token = ?, claim_expires_at = ?, attempts = COALESCE(attempts, 0) + 1
            WHERE url = ? AND COALESCE(attempts, 0) < ?
              AND (COALESCE(claimed_by, '') = '' OR COALESCE(claim_expires_at, 0) <= ?)
        """, (worker_id, token, now + ttl_seconds, url, max_attempts, now))
        conn.commit()
        return token if cur.rowcount == 1 else None

def claim_lead(url, worker_id, ttl_seconds=900, max_attempts=3, now=None):
    """Versão booleana de acquire_lease (o token é o próprio worker_id)."""
    return acquire_lease(url, worker_id, ttl_seconds, max_attempts, now, token=worker_id) is not None

def renew_lease(url, token, ttl_seconds=900, now=None):
    """Heartbeat: estende o lease. Só funciona para quem ainda detém o token; depois que outro worker
    assumiu (ou o lease foi liberado) devolve False e nada é alterado."""
    if not token:
        return False
    now = time.time() if now is None else now
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        cur = conn.execute(
            "UPDATE leads SET claim_expires_at = ? WHERE url = ? AND claim_token = ? AND COALESCE(claimed_by, '') != ''",
            (now + ttl_seconds, url, token))
        conn.commit()
        return cur.rowcount == 1

def owns_lease(url, token):
    """True se o token ainda é o dono atual do lead (nenhum outro worker assumiu)."""
    if not token:
        return False
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        row = conn.execute(
            "SELECT 1 FROM leads WHERE url = ? AND claim_token = ? AND COALESCE(claimed_by, '') != ''", (url, token)).fetchone()
        return row is not None

def release_lead(url, token):
    """Libera o lease, mas só se o token ainda for o do dono (token antigo não solta o lease de outro worker)."""
    if not token:
        return False
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        cur = conn.execute(
            "UPDATE leads SET claimed_by = '', claim_token = '', claim_expires_at = 0 WHERE url = ? AND claim_token = ?",
            (url, token))
        conn.commit()
        return cur.rowcount == 1

def _so_do_dono(token):
    """Cláusula SQL extra: com token, a escrita só vale se o token ainda for o dono do lead."""
    return (" AND claim_token = ?", (token,)) if token is not None else ("", ())

def mark_lead_failure(url, error, backoff_seconds=300, now=None, token=None):
    """Registra a falha e agenda a próxima tentativa: retry_after = agora + backoff * tentativas.
    Com token, só grava se o token ainda for o dono (devolve False caso contrário)."""
    now = time.time() if now is None else now
    extra_sql, extra = _so_do_dono(token)
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        cur = conn.execute(
            "UPDATE leads SET last_error = ?, retry_after = ? + ? * COALESCE(attempts, 0) WHERE url = ?" + extra_sql,
            (str(error)[:500], now, backoff_seconds, url, *extra))
        conn.commit()
        return cur.rowcount == 1

def mark_lead_success(url, token=None):
    """Zera tentativas, erro e backoff do lead. Com token, só vale se o token ainda for o dono."""
    extra_sql, extra = _so_do_dono(token)
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        cur = conn.execute(
            "UPDATE leads SET attempts = 0, last_error = '', retry_after = 0 WHERE url = ?" + extra_sql, (url, *extra))
        conn.commit()
        return cur.rowcount == 1

def exhaust_lead(url, reason, max_attempts=3, token=None):
    """Encerra as tentativas (resultado final, ex.: lead não qualificado): o worker não o pega mais.
    Com token, só vale se o token ainda for o dono."""
    extra_sql, extra = _so_do_dono(token)
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        cur = conn.execute(
            "UPDATE leads SET attempts = ?, last_error = ?, retry_after = 0 WHERE url = ?" + extra_sql,
            (max_attempts, reason, url, *extra))
        conn.commit()
        return cur.rowcount == 1

def get_next_lead(statuses, max_attempts=3, now=None):
    """Próximo lead elegível para um worker: status processável (ou DEPLOYED com rascunho pendente),
    tentativas restantes, fora do backoff e sem claim ativo. Os com menos tentativas vêm primeiro."""
    now = time.time() if now is None else now
    marcas = ", ".join("?" for _ in statuses)
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"""
            SELECT * FROM leads
            WHERE (status IN ({marcas}) OR (status = 'DEPLOYED' AND COALESCE(last_error, '') != ''))
              AND COALESCE(attempts, 0) < ?
              AND COALESCE(retry_after, 0) <= ?
              AND (COALESCE(claimed_by, '') = '' OR COALESCE(claim_expires_at, 0) <= ?)
            ORDER BY COALESCE(attempts, 0) ASC, id ASC
            LIMIT 1
        """, (*statuses, max_attempts, now, now)).fetchone()
        return dict(row) if row else None

def save_design_brief(url, design_brief):
    """Grava só o design_brief do projeto do lead (cria o projeto se não existir). Não toca em outreach."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM leads WHERE url = ?", (url,))
        row = c.fetchone()
        if row:
            lead_id = row[0]
            c.execute("SELECT id FROM projects WHERE lead_id = ?", (lead_id,))
            if c.fetchone():
                c.execute("UPDATE projects SET design_brief = ? WHERE lead_id = ?", (str(design_brief), lead_id))
            else:
                c.execute("INSERT INTO projects (lead_id, design_brief) VALUES (?, ?)", (lead_id, str(design_brief)))
        conn.commit()

def save_outreach_draft(lead_id, canal, mensagem):
    """Grava/atualiza o RASCUNHO de um canal do lead. DRAFT = mensagem preparada, NUNCA enviada.

    Uma linha por (lead, canal): rodar o pipeline de novo atualiza o rascunho em vez de duplicá-lo.
    """
    canal = canal.upper()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM outreach WHERE lead_id = ? AND canal = ?", (lead_id, canal))
        row = c.fetchone()
        if row:
            c.execute("UPDATE outreach SET mensagem = ?, status = 'DRAFT' WHERE id = ?", (mensagem, row[0]))
        else:
            c.execute("INSERT INTO outreach (lead_id, canal, mensagem, status) VALUES (?, ?, ?, 'DRAFT')", (lead_id, canal, mensagem))
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