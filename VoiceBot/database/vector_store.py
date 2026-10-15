"""Separate vector-retrieval storage with explicit organization isolation."""
import json
import math
from database.connection import connect_database


class SqliteVectorStore:
    def __init__(self, path):
        self.path = path
        with connect_database(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS vectors(document_id TEXT,organization_id TEXT,position INTEGER,text TEXT,embedding TEXT,PRIMARY KEY(document_id,position))')
            db.execute('CREATE INDEX IF NOT EXISTS vectors_org ON vectors(organization_id)')

    def store(self, document_id, organization_id, chunks, embeddings):
        if len(chunks) != len(embeddings):
            raise ValueError('Each document chunk requires its own embedding')
        with connect_database(self.path) as db:
            db.execute('DELETE FROM vectors WHERE document_id=?', (document_id,))
            db.executemany('INSERT INTO vectors VALUES (?,?,?,?,?)',
                [(document_id,organization_id,i,text,json.dumps(vector)) for i,(text,vector) in enumerate(zip(chunks,embeddings))])

    def delete(self, document_id):
        with connect_database(self.path) as db:
            db.execute('DELETE FROM vectors WHERE document_id=?', (document_id,))

    def search(self, query_embedding, organization_id, limit=3,document_ids=None):
        with connect_database(self.path) as db:
            rows = db.execute('SELECT * FROM vectors WHERE organization_id=?', (organization_id,)).fetchall()
        results = []
        qnorm = math.sqrt(sum(x*x for x in query_embedding)) or 1
        for row in rows:
            if document_ids is not None and row['document_id'] not in document_ids:continue
            vector = json.loads(row['embedding'])
            if len(vector) != len(query_embedding):
                continue
            similarity = sum(a*b for a,b in zip(query_embedding,vector))/(qnorm*(math.sqrt(sum(x*x for x in vector)) or 1))
            if similarity > .2:
                results.append({'document_id':row['document_id'],'text':row['text'],'score':similarity})
        return sorted(results,key=lambda item:item['score'],reverse=True)[:limit]
