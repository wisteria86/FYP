"""Transport-independent application failure contract."""
class DomainError(Exception):
    def __init__(self, code, message, *, status_code=400, details=None):
        super().__init__(message)
        self.code, self.message = code, message
        self.status_code, self.details = status_code, details or {}
