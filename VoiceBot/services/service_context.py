"""Explicitly wired application-service dependencies, not provider globals."""
class ApplicationService:
    def __init__(self, context):
        self.context = context
        self.repository = context.repository

    @property
    def path(self):
        return self.repository.path

    def connect(self):
        return self.repository.connect()
