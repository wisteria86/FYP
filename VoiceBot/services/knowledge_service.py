"""KnowledgeService: one application responsibility, shared transactional storage."""
from services.training_support import *
from services.training_support import _now, _json, _words
from services.service_context import ApplicationService
import os
import logging
from database.vector_store import SqliteVectorStore
from integrations.embeddings import embedding_provider
from domain.errors import DomainError


class KnowledgeService(ApplicationService):
    def __init__(self, context):
        super().__init__(context)
        self.embedder = embedding_provider()
        self._vectors = None

    @property
    def vectors(self):
        if self._vectors is None:
            self._vectors = SqliteVectorStore(self.path.with_name(self.path.stem+'-vectors.db'))
        return self._vectors

    def organization(self, user_id, write=False):
        with self.connect() as db:
            membership = db.execute('SELECT organization_id,role FROM organization_memberships WHERE user_id=? ORDER BY created_at LIMIT 1', (user_id,)).fetchone()
        if not membership:
            raise DomainError('organization_required','Organization membership is required',status_code=403)
        if write and membership['role'] not in {'owner','admin'} and user_id != 'demo':
            raise DomainError('document_permission','Only organization owners and administrators may upload documents',status_code=403)
        return membership['organization_id']

    def add_document(self, user_id: str, name: str, content: str) -> dict[str, Any]:
        organization_id = self.organization(user_id, write=True)
        clean = re.sub(r"\s+", " ", content).strip()
        if not clean:
            raise ValueError("No readable text found")
        chunks = [clean[i:i + 900] for i in range(0, len(clean), 750)]
        if len(chunks) > self.context.administration.document_chunk_limit():
            raise ValueError('Document has too much text; split it into smaller documents')
        doc_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,'processing',?)", (doc_id, user_id, name, clean, _json(chunks), _now()))
            db.execute('INSERT INTO document_organizations VALUES (?,?)', (doc_id,organization_id))
        try:
            semantic = os.getenv('HIKARI_SKIP_MODELS','').lower() != 'true'
            if semantic:
                self.vectors.store(doc_id, organization_id, chunks, self.embedder.generate_embedding(chunks))
            with self.connect() as db:
                db.executemany('INSERT INTO document_chunks(id,document_id,position,content,embedding_ref) VALUES (?,?,?,?,?)',
                    [(str(uuid.uuid4()),doc_id,i,text,f'{doc_id}:{i}' if semantic else None) for i,text in enumerate(chunks)])
                db.execute("UPDATE documents SET status='ready' WHERE id=?", (doc_id,))
        except Exception as exc:
            with self.connect() as db:
                db.execute("UPDATE documents SET status='failed' WHERE id=?", (doc_id,))
            raise DomainError('document_processing_failed','Document processing failed; previously uploaded documents are unchanged',status_code=503) from exc
        return {"id": doc_id, "name": name, "status": "ready", "chunks": len(chunks), "created_at": _now()}

    def documents(self, user_id: str = "demo") -> list[dict[str, Any]]:
        organization_id = self.organization(user_id)
        with self.connect() as db:
            rows = db.execute("SELECT d.id,d.name,d.status,d.created_at,json_array_length(d.chunks) chunks FROM documents d JOIN document_organizations o ON o.document_id=d.id WHERE o.organization_id=? ORDER BY d.created_at DESC", (organization_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, document_id: str, user_id: str = "demo") -> bool:
        organization_id = self.organization(user_id, write=True)
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM document_organizations WHERE document_id=? AND organization_id=?', (document_id,organization_id)).fetchone():
                return False
            db.execute('DELETE FROM document_chunks WHERE document_id=?', (document_id,))
            db.execute('DELETE FROM documents WHERE id=?', (document_id,))
        self.vectors.delete(document_id)
        return True

    def search(self, query: str, user_id: str = "demo", limit: int = 3, document_ids: list[str] | None = None) -> list[dict[str, str]]:
        organization_id = self.organization(user_id)
        query_terms = Counter(w for w in _words(query) if w not in STOP_WORDS)
        with self.connect() as db:
            docs = db.execute("SELECT d.id,d.name,d.chunks FROM documents d JOIN document_organizations o ON o.document_id=d.id WHERE o.organization_id=? AND d.status='ready'", (organization_id,)).fetchall()
        if document_ids is not None:docs=[doc for doc in docs if doc['id'] in document_ids]
        if docs and os.getenv('HIKARI_SKIP_MODELS','').lower() != 'true':
            try:
                for doc in docs:
                    with self.connect() as db:
                        indexed = db.execute('SELECT 1 FROM document_chunks WHERE document_id=? AND embedding_ref IS NOT NULL LIMIT 1', (doc['id'],)).fetchone()
                    if not indexed:
                        chunks = json.loads(doc['chunks'])
                        self.vectors.store(doc['id'],organization_id,chunks,self.embedder.generate_embedding(chunks))
                        with self.connect() as db:
                            for i,text in enumerate(chunks):
                                db.execute('INSERT INTO document_chunks(id,document_id,position,content,embedding_ref) VALUES (?,?,?,?,?) ON CONFLICT(document_id,position) DO UPDATE SET embedding_ref=excluded.embedding_ref', (str(uuid.uuid4()),doc['id'],i,text,f"{doc['id']}:{i}"))
                names = {doc['id']:doc['name'] for doc in docs}
                hits = self.vectors.search(self.embedder.generate_embedding([query])[0],organization_id,limit,document_ids=document_ids)
                return [{'document_id':hit['document_id'],'name':names[hit['document_id']],'text':hit['text'],'retrieval_mode':'semantic'} for hit in hits if hit['document_id'] in names]
            except Exception:
                logging.getLogger(__name__).warning('Semantic retrieval unavailable; using organization-scoped lexical fallback',exc_info=True)
        matches = []
        for doc in docs:
            for chunk in json.loads(doc["chunks"]):
                terms = Counter(w for w in _words(chunk) if w not in STOP_WORDS)
                score = sum(min(count, terms.get(term, 0)) * math.log(2 + len(chunk) / 200) for term, count in query_terms.items())
                if score:
                    matches.append((score, {'document_id':doc['id'],"name": doc["name"], "text": chunk}))
        return [item for _, item in sorted(matches, key=lambda x: x[0], reverse=True)[:limit]]

    def policy_observations(self, session, turns):
        """Conservative evidence checks, not semantic policy certification."""
        passages=session.get('knowledge_evidence',[])
        text=' '.join(turns).lower()
        rule_evidence=[]
        for passage in passages:
            terms={term for term in _words(passage['text']) if len(term)>3 and term not in STOP_WORDS}
            matched=[turn for turn in turns if terms and len(terms.intersection(_words(turn)))>=min(4,len(terms))]
            # Negated compliance must not be awarded a positive application check.
            matched=[turn for turn in matched if not re.search(r"\b(?:skip|bypass|ignore|without approval|do not need|don't need)\b",turn,re.I)]
            rule_evidence.extend(matched)
        applied=[turn for turn in turns if re.search(r'\b(?:i will|we will|before|must|required|request|approval|follow)\b',turn,re.I)]
        verify=[turn for turn in turns if re.search(r'\b(?:verify|check|ask|confirm|not covered|not stated|uncertain)\b',turn,re.I)]
        values=[('Explain the relevant policy rule',rule_evidence),('Apply the rule to the request',applied if rule_evidence else []),('Verify anything the document does not cover',verify)]
        return [{'name':name,'met':bool(evidence),'evidence':[item[:240] for item in evidence[:2]]} for name,evidence in values]
