"""Backward-compatible training facade over explicitly composed services.

The HTTP contract remains unchanged; responsibility-specific services own
catalog, scenarios, sessions, assessment, adaptation, progress, and knowledge.
"""
from pathlib import Path
from types import SimpleNamespace
from database.training_repository import SqliteTrainingRepository
from services.catalog_service import CatalogService
from services.scenario_service import ScenarioService
from services.session_service import SessionService
from services.assessment_service import AssessmentService
from services.progress_service import ProgressService
from services.adaptive_service import AdaptiveTrainingService
from services.knowledge_service import KnowledgeService
from services.administration_service import AdministrationService
from services.training_support import SKILLS, SCENARIOS


class TrainingService:
    _owners = {'_initialize': 'catalog', '_seed_platform_catalog': 'catalog', '_seed_english_curriculum': 'catalog', 'skills': 'catalog', '_activity': 'catalog', 'activities': 'catalog', 'resources': 'catalog', 'scenario_preview': 'scenario', 'prompt': 'scenario', 'fallback_reply': 'scenario', 'create_session': 'session', 'session': 'session', 'add_turn': 'session', 'response_speakers': 'session', 'evaluate_progress': 'session', 'caption_preferences': 'session', 'set_opening_caption': 'session', 'add_posture': 'session', 'assessment_prompt': 'assessment', 'assess': 'assessment', '_assessment_dict': 'assessment', 'dashboard': 'progress', 'history': 'progress', 'plan': 'adaptive', 'add_document': 'knowledge', 'documents': 'knowledge', 'delete_document': 'knowledge', 'search': 'knowledge'}
    plan = staticmethod(AdaptiveTrainingService.plan)
    _owners['cancel_session'] = 'session'
    _owners['completion_review_prompt'] = 'session'
    _owners['save_completion_review'] = 'session'

    def __init__(self, database_path):
        self.path = Path(database_path)
        self.repository = SqliteTrainingRepository(self.path)
        self.context = SimpleNamespace(repository=self.repository)
        self.context.catalog = CatalogService(self.context)
        self.context.scenario = ScenarioService(self.context)
        self.context.session = SessionService(self.context)
        self.context.assessment = AssessmentService(self.context)
        self.context.progress = ProgressService(self.context)
        self.context.adaptive = AdaptiveTrainingService(self.context)
        self.context.knowledge = KnowledgeService(self.context)
        self.context.administration = AdministrationService(self.context)
        self.context.catalog._initialize()

    def connect(self):
        return self.repository.connect()

    def __getattr__(self, name):
        owner = self._owners.get(name)
        if owner is None:
            raise AttributeError(name)
        return getattr(getattr(self.context, owner), name)
