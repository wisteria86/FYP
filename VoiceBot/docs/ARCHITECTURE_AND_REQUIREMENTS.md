# Hikari architecture and requirements alignment

Source: F26-042.pdf, Figures 5.1 and 5.2 (PDF pages 64 and 68), FR-01–FR-24 (42–43), NFR-01–NFR-12 (45–46).

## Architecture

```text
React presentation (frontend/src)
    → FastAPI API contracts, authentication, authorization (api)
    → application services and TrainingOrchestrator (services)
    → domain entities and provider interfaces (domain)
    → replaceable intelligence adapters (integrations, intelligence, modules)
    → relational SQLite storage (database) + separate organization-scoped vector store
```

Provider calls are injected into the conversation orchestrator; it does not import FastAPI or model implementations. HTTP serialization and ownership checks stay at the API boundary. The existing `core/training_service.py` is a compatibility facade, not the business-logic monolith. Existing routes and learner UI are preserved.

The service-to-storage boundary currently provides transactional connections through `SqliteTrainingRepository`. Responsibility-specific services still contain SQL unit-of-work queries. This is deliberately documented as a migration boundary, not falsely presented as a complete ORM/repository-per-aggregate implementation. Moving remaining model startup and speech routes out of `api/server.py` is a further structural cleanup, not required to use the split training services.

## Class diagram mapping

All fourteen entity types from Figure 5.2 are represented in `domain/entities.py`: Organization, User, Skill, Subskill, Scenario, TrainingSession, Assessment, AssessmentMetric, Proficiency, ProficiencyUpdate, TrainingPlan, Recommendation, Document and DocumentChunk. They are framework-independent contracts; existing relational DTOs remain compatibility representations. TrainingSession enforces legal lifecycle transitions, and Assessment excludes unavailable modalities instead of awarding invented scores.

| Diagram service | Implementation |
| --- | --- |
| UserService | `services/auth_service.py` (AuthService; existing name retained) |
| TrainingService | compatibility facade + `services/session_service.py` and `training_orchestrator.py` |
| ScenarioService | `services/scenario_service.py` |
| AssessmentService | `services/assessment_service.py` |
| AdaptiveTrainingService | `services/adaptive_service.py` |
| KnowledgeService | `services/knowledge_service.py` |
| ProgressService | `services/progress_service.py` |
| AdministrationService | `services/administration_service.py` |

`domain/ports.py` defines SpeechService, SpeechAnalysisService, ConversationalAIService, VisionService, EmbeddingService and RetrievalService contracts. Implementations include local speech, transcript-based speech analysis, conversational LLM, body-landmark vision, MiniLM embeddings and SQLite cosine retrieval. Not every legacy speech route has migrated to the new speech adapter yet.

## Functional requirement traceability

“Implemented” below means a code path exists; it is not an assertion of validated educational efficacy or production certification.

| FR | Implementation and evidence / remaining qualification |
| --- | --- |
| 01 Authentication | AuthService, cookie sessions, password hashing, revocation; `test_auth.py` |
| 02 Profiles/preferences/progress | account settings, CatalogService, ProgressService; private per-user queries |
| 03 Skill/recommended activity selection | DB-backed catalogs, activity APIs and preserved Training UI |
| 04 Real-time spoken interaction | existing voice stream, mic, STT/LLM/TTS pipeline; physical-device timing remains to validate |
| 05 Adaptive contextual scenarios | ScenarioService uses selected activity, proficiency and objectives; quality needs human rubric validation |
| 06 AI role counterparts | activity participant metadata and TrainingOrchestrator preserve role-specific turn order |
| 07 Speech-to-text | existing Whisper medium GPU pipeline preserved; actual recording accuracy needs mic tests |
| 08 Activity-specific assessment | language evaluation plus communication heuristics and transcript evidence; not a validated objective skill test |
| 09 Optional camera | existing camera control plus local body-pose worker; training continues when camera unavailable |
| 10 Posture indicators | 33 body landmarks, head/shoulder/hip visibility checks; non-clinical presentation proxies, not medical posture diagnosis |
| 11 Multimodal fusion | domain Assessment combines available metrics; missing voice/visual is reported and excluded |
| 12 Explainable feedback | existing corrections/evidence/strengths/improvements persist in assessment |
| 13 Proficiency update | assessment + proficiency + audit history commit in one transaction; concurrent-completion test |
| 14 Skill/subskill tracking | normalized catalogs, history and updates for directly matching assessed metrics; unmeasured subskills retain their previous value rather than receiving unrelated proxy scores |
| 15 Recommendations | weakest-skill/activity selection persisted with source assessment; recommendation quality needs evaluation |
| 16 Personalized plans | persistent plans and activities, with completed history retained; dashboard reads persisted upcoming items |
| 17 Dashboard | existing Home/Progress UI and ProgressService |
| 18 Authorized organization uploads | KnowledgeService requires owner/admin membership; demo compatibility exception is development-only |
| 19 Processing/embeddings/RAG | text extraction, chunks, cached CPU MiniLM and separate SQLite vector store; failed document status retained |
| 20 Grounded organization practice | organization-scoped retrieval injected into contextual roleplay; lexical fallback if embeddings fail |
| 21 AI literacy | existing catalog/scenarios/resources retained, including responsible AI and social-engineering awareness |
| 22 Session history | private persisted sessions, turns and assessments; existing history routes/UI |
| 23 Administration | explicit administrator email allowlist; settings panel/API manage skills, subskills, new activity/scenario creation, existing scenario edits and bounded document configuration; deactivation preserves history |
| 24 Linked assessment/adaptation | assessment IDs → recommendation sources → persisted plan activities; returned through dashboard |

## Nonfunctional requirements and evidence

| NFR | Status/evidence |
| --- | --- |
| 01 Typical common operations under 2 seconds | updated isolated authenticated HTTP benchmark: 300 reads, p95 154.4 ms, maximum 222.1 ms; all measured requests under two seconds, not a production-network guarantee |
| 02 Twenty authenticated common-operation users | 20 concurrent clients exercised dashboard/history/skills; not proof of 20 simultaneous GPU voice sessions |
| 03 Minimize unnecessary pauses | threaded model/retrieval work and preserved voice pipeline; no new hardware latency guarantee |
| 04 AI-failure consistency | transactional/idempotent assessment, immutable completed outcome, failed-document isolation; tests cover these invariants |
| 05 Independent modules | separate scenario/session/assessment/adaptation/knowledge/intelligence modules; legacy API speech composition remains to clean up |
| 06 Extendable catalog | DB catalogs support new skills/subskills/activities without account/progress code changes; versioned administrator scenario edits survive seeding |
| 07 Reusable infrastructure | shared auth, connection policy, migrations, ownership checks, service context and domain errors |
| 08 Security/isolation | auth cookies, hashed credentials, user/session ownership, organization-scoped retrieval and explicit admin authorization; production penetration testing outstanding |
| 09 Privacy | local vision/embeddings; uploaded documents remain scoped to organization. Configured external LLM can receive transcript and retrieved chunks, so deployment policy/consent must disclose it |
| 10 Usability | learner workflow preserved; completion/exit and failure guidance improved; administrator editor uses form fields rather than handwritten JSON |
| 11 Desktop browsers | production frontend builds; actual Chrome/Edge/Firefox mic/camera interoperability not certified in this refactor |
| 12 Clear failures | structured errors and mic/model/document/camera failure handling; real device/network disruption testing outstanding |

## Verification and operations

Run `.venv\Scripts\python.exe -m unittest discover -s tests`, `npm run build` in frontend, and `.venv\Scripts\python.exe scripts\benchmark_common_operations.py`. Benchmark storage is temporary and never changes the real database. The expanded suite contains 58 regression/architecture/learning acceptance tests. The production build succeeds. A real cached MiniLM test returned 384-dimensional vectors, retrieved the vacation policy for a time-off query, and returned no hits for a different organization. See [prototype acceptance evidence](PROTOTYPE_ACCEPTANCE.md) for the latest UI walkthrough and live speech measurements.

Set `ADMIN_EMAILS` in `.env` to the email of an existing trusted account, restart the backend, then sign in again to expose the administrator settings panel. Organization ownership does not automatically grant platform administration. No account was elevated by this refactor.

Whisper medium/CUDA settings and existing selectable TTS engines are retained. Vision assets are served locally under `/vision`; the pose worker runs off the browser main thread and should fail independently from voice. Model caching requires disk space, but embeddings run on CPU to avoid competing with voice models for GPU memory.

Before claiming full FR/NFR acceptance: extend calibrated rubric-specific measurements to currently unmeasured subskills, validate privacy/consent against deployment policy, exercise real mic/camera/audio sessions, and run cross-browser and production/network load tests. This document distinguishes implementation from those remaining acceptance tasks.
