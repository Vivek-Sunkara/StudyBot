import sqlite3
from pathlib import Path

class Database:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def init(self):
        with self.conn() as c:
            c.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS documents(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chunks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                page INTEGER NOT NULL DEFAULT 0,
                section TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
            ''')

    def create_document(self, filename, file_type):
        with self.conn() as c:
            return c.execute(
                "INSERT INTO documents(filename,file_type) VALUES(?,?)",
                (filename, file_type)
            ).lastrowid

    def insert_chunks(self, document_id, chunks):
        with self.conn() as c:
            c.executemany(
                "INSERT INTO chunks(document_id,page,section,content) VALUES(?,?,?,?)",
                [(document_id, x.get("page", 0), x.get("section", ""), x["content"])
                 for x in chunks]
            )

    def all_chunks(self):
        with self.conn() as c:
            rows = c.execute('''
                SELECT c.id chunk_id,c.page,c.section,c.content,d.filename document
                FROM chunks c JOIN documents d ON d.id=c.document_id
                ORDER BY c.id
            ''').fetchall()
            return [dict(x) for x in rows]

    def list_documents(self):
        with self.conn() as c:
            rows = c.execute('''
                SELECT d.id,d.filename,d.file_type,d.created_at,COUNT(c.id) chunks
                FROM documents d LEFT JOIN chunks c ON c.document_id=d.id
                GROUP BY d.id ORDER BY d.id DESC
            ''').fetchall()
            return [dict(x) for x in rows]

    def document_count(self):
        with self.conn() as c:
            return c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def chunk_count(self):
        with self.conn() as c:
            return c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def add_message(self, conversation_id, role, content):
        with self.conn() as c:
            c.execute(
                "INSERT INTO messages(conversation_id,role,content) VALUES(?,?,?)",
                (conversation_id, role, content)
            )
