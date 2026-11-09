"""Coordinate requests sharing a credential; never retry blindly after a 429."""
import hashlib
import math
import re
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from types import SimpleNamespace


def seconds(value, default=0):
    try:
        return max(0, float(value))
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        parts = re.fullmatch(r'(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?', value)
        if parts and any(parts.groups()):
            return sum(float(n or 0)*unit for n, unit in zip(parts.groups(), (3600, 60, 1, .001)))
        try:
            return max(0, (parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    return default


class QuotaDeferred(RuntimeError):
    status_code = 429

    def __init__(self, delay):
        self.retry_after = max(1, math.ceil(delay))
        self.response = SimpleNamespace(headers={'retry-after': str(self.retry_after)})
        super().__init__('Provider quota is cooling down; the request was not sent.')


class ProviderQuota:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.blocked_until = 0
        self.tokens = None
        self.token_reset = 0
        self.last_foreground = -float('inf')
        self.requests = 0
        self.deferred = 0
        self.last_headers = {}
        self.limit_reason = None

    def reserve(self, estimated_tokens, background=False):
        now = self.clock()
        delay = self.blocked_until-now
        if background:
            delay = max(delay, self.last_foreground+12-now)
        if self.token_reset <= now:
            self.tokens = None
        if self.tokens is not None and self.tokens < estimated_tokens:
            delay = max(delay, self.token_reset-now)
        if delay > 0:
            self.deferred += 1
            error=QuotaDeferred(delay)
            error.limit_reason=self.limit_reason if self.blocked_until>now else None
            raise error
        if self.tokens is not None:
            self.tokens -= estimated_tokens
        if not background:
            self.last_foreground = now
        self.requests += 1

    def observe(self, headers, limited=False):
        now = self.clock()
        headers = {str(k).lower(): v for k, v in headers.items()}
        self.last_headers={k:v for k,v in headers.items() if k.startswith('x-ratelimit-') or k=='retry-after'}
        if limited:
            self.blocked_until = max(self.blocked_until, now+seconds(headers.get('retry-after'), 15))
        try:
            remaining = int(headers['x-ratelimit-remaining-tokens'])
            reset = seconds(headers.get('x-ratelimit-reset-tokens'))
            if reset > 0:
                self.tokens, self.token_reset = remaining, now+reset
        except (KeyError, TypeError, ValueError):
            pass
        # Do not assume a provider's "requests" header means RPM; Groq uses RPD.
        if str(headers.get('x-ratelimit-remaining-requests')) == '0':
            self.blocked_until = max(self.blocked_until, now+seconds(headers.get('x-ratelimit-reset-requests'), 60))

    def observe_error(self, message):
        # Keep only quota terminology and numbers, never organization IDs or prompts.
        self.limit_reason=None
        match=re.search(r'(tokens per (?:day|minute)|requests per (?:day|minute))[^:]*:\s*Limit\s+(\d[\d,]*(?:\.\d+)?),\s*Used\s+(\d[\d,]*(?:\.\d+)?),\s*Requested\s+(\d[\d,]*(?:\.\d+)?)',str(message),re.I)
        if match:self.limit_reason={'kind':match[1].lower(),'limit':match[2],'used':match[3],'requested':match[4]}


_quotas = {}
_lock = threading.Lock()


def shared_quota(base_url, api_key, model):
    key = (base_url.rstrip('/'), hashlib.sha256(api_key.encode()).digest(), model)
    with _lock:
        return _quotas.setdefault(key, ProviderQuota())
