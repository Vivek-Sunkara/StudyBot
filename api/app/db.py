import sqlite3
from pathlib import Path
from datetime import datetime, timezone

try:
    from bson import ObjectId
    from gridfs import GridFSBucket
    from pymongo import MongoClient
except ImportError:
    ObjectId = None
    GridFSBucket = None
    MongoClient = None

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
                kind TEXT NOT NULL DEFAULT 'document',
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
            CREATE TABLE IF NOT EXISTS conversations(
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New study session',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
            ''')
            columns = {row[1] for row in c.execute("PRAGMA table_info(documents)")}
            if "kind" not in columns:
                c.execute("ALTER TABLE documents ADD COLUMN kind TEXT NOT NULL DEFAULT 'document'")

    def create_document(self, filename, file_type, kind="document", data=None):
        with self.conn() as c:
            return c.execute(
                "INSERT INTO documents(filename,file_type,kind) VALUES(?,?,?)",
                (filename, file_type, kind)
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
                SELECT c.id chunk_id,c.page,c.section,c.content,d.filename document,d.kind
                FROM chunks c JOIN documents d ON d.id=c.document_id
                ORDER BY c.id
            ''').fetchall()
            return [dict(x) for x in rows]

    def list_documents(self):
        with self.conn() as c:
            rows = c.execute('''
                SELECT d.id,d.filename,d.file_type,d.kind,d.created_at,COUNT(c.id) chunks
                FROM documents d LEFT JOIN chunks c ON c.document_id=d.id
                GROUP BY d.id ORDER BY d.id DESC
            ''').fetchall()
            return [dict(x) for x in rows]

    def rename_document(self, document_id, filename):
        with self.conn() as c:
            result = c.execute("UPDATE documents SET filename=? WHERE id=?", (filename, document_id))
            return result.rowcount > 0

    def delete_document(self, document_id):
        with self.conn() as c:
            c.execute("DELETE FROM documents WHERE id=?", (document_id,))

    def document_count(self):
        with self.conn() as c:
            return c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def chunk_count(self):
        with self.conn() as c:
            return c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def add_message(self, conversation_id, role, content):
        with self.conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO conversations(id,title) VALUES(?,?)",
                (conversation_id, "New study session"),
            )
            c.execute(
                "INSERT INTO messages(conversation_id,role,content) VALUES(?,?,?)",
                (conversation_id, role, content)
            )
            c.execute(
                "UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (conversation_id,),
            )
            if role == "user":
                c.execute(
                    "UPDATE conversations SET title=? WHERE id=? AND title='New study session'",
                    (content.strip()[:60] or "New study session", conversation_id),
                )

    def get_messages(self, conversation_id, limit=12):
        with self.conn() as c:
            rows = c.execute(
                """SELECT role, content FROM messages
                   WHERE conversation_id=? ORDER BY id DESC LIMIT ?""",
                (conversation_id, limit),
            ).fetchall()
        return list(reversed([dict(row) for row in rows]))

    def list_conversations(self):
        with self.conn() as c:
            rows = c.execute("""
                SELECT c.id,c.title,c.created_at,c.updated_at,
                       COUNT(m.id) message_count
                FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.id
                GROUP BY c.id ORDER BY c.updated_at DESC
            """).fetchall()
            return [dict(row) for row in rows]

    def rename_conversation(self, conversation_id, title):
        with self.conn() as c:
            result = c.execute("UPDATE conversations SET title=? WHERE id=?", (title, conversation_id))
            return result.rowcount > 0


class MongoDatabase:
    def __init__(self, uri, database_name):
        if MongoClient is None:
            raise RuntimeError("pymongo is required when MONGODB_URI is configured")
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.database = self.client[database_name]
        self.documents = self.database.documents
        self.chunks = self.database.chunks
        self.conversations = self.database.conversations
        self.messages = self.database.messages
        self.files = GridFSBucket(self.database)

    def _id(self, value):
        return value if isinstance(value, ObjectId) else ObjectId(str(value))

    def create_document(self, filename, file_type, kind="document", data=None):
        now = datetime.now(timezone.utc)
        file_id = self.files.upload_from_stream(filename, data) if data else None
        result = self.documents.insert_one({
            "filename": filename, "file_type": file_type, "kind": kind,
            "file_id": file_id, "created_at": now,
        })
        return str(result.inserted_id)

    def insert_chunks(self, document_id, chunks):
        if chunks:
            self.chunks.insert_many([
                {"document_id": self._id(document_id), "page": x.get("page", 0),
                 "section": x.get("section", ""), "content": x["content"]}
                for x in chunks
            ])

    def all_chunks(self):
        result = []
        for chunk in self.chunks.find().sort("_id", 1):
            document = self.documents.find_one({"_id": chunk["document_id"]})
            if document:
                result.append({"chunk_id": str(chunk["_id"]), "page": chunk["page"],
                               "section": chunk["section"], "content": chunk["content"],
                               "document": document["filename"], "kind": document.get("kind", "document")})
        return result

    def list_documents(self):
        result = []
        for document in self.documents.find().sort("created_at", -1):
            result.append({"id": str(document["_id"]), "filename": document["filename"],
                           "file_type": document["file_type"],
                           "kind": document.get("kind", "document"),
                           "created_at": document["created_at"].isoformat(),
                           "chunks": self.chunks.count_documents({"document_id": document["_id"]})})
        return result

    def rename_document(self, document_id, filename):
        result = self.documents.update_one({"_id": self._id(document_id)}, {"$set": {"filename": filename}})
        return result.matched_count > 0

    def delete_document(self, document_id):
        oid = self._id(document_id)
        document = self.documents.find_one({"_id": oid})
        if document and document.get("file_id"):
            try:
                self.files.delete(document["file_id"])
            except Exception:
                pass
        self.chunks.delete_many({"document_id": oid})
        self.documents.delete_one({"_id": oid})

    def document_count(self):
        return self.documents.count_documents({})

    def chunk_count(self):
        return self.chunks.count_documents({})

    def add_message(self, conversation_id, role, content):
        now = datetime.now(timezone.utc)
        self.conversations.update_one(
            {"_id": conversation_id},
            {"$setOnInsert": {"title": "New study session", "created_at": now}, "$set": {"updated_at": now}},
            upsert=True,
        )
        self.messages.insert_one({"conversation_id": conversation_id, "role": role,
                                  "content": content, "created_at": now})
        if role == "user":
            self.conversations.update_one(
                {"_id": conversation_id, "title": "New study session"},
                {"$set": {"title": content.strip()[:60] or "New study session"}},
            )

    def get_messages(self, conversation_id, limit=12):
        rows = list(self.messages.find({"conversation_id": conversation_id}).sort("created_at", -1).limit(limit))
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def list_conversations(self):
        return [{"id": row["_id"], "title": row["title"],
                 "created_at": row["created_at"].isoformat(),
                 "updated_at": row["updated_at"].isoformat(),
                 "message_count": self.messages.count_documents({"conversation_id": row["_id"]})}
                for row in self.conversations.find().sort("updated_at", -1)]

    def rename_conversation(self, conversation_id, title):
        result = self.conversations.update_one({"_id": conversation_id}, {"$set": {"title": title}})
        return result.matched_count > 0
