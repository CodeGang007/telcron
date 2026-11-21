"""Request limits for the sign-up and sign-in routes (DEF-044), and the caller's address.

Fixed windows counted in Redis: one counter per route and client address, one per route and email
address. A request over either limit is refused with 429 `rate_limited` and `Retry-After`. Email
addresses are hashed before they become keys. When Redis cannot be reached the limits are skipped
(logged): sign-in must not depend on the cache, and the per-account rules (five tries a code, the
password lockout) still hold.
"""

import hashlib
import ipaddress
import logging

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from .config import get_settings
from .redis import get_redis

log = logging.getLogger("telcron.ratelimit")
PREFIX = "rl:"
HOUR, QUARTER, DAY = 3600, 900, 86400

# route -> (setting for one client address, setting for one email address, window in seconds)
LIMITS: dict[str, tuple[str, str, int]] = {
    "register": ("register_per_ip_per_hour", "register_per_email_per_hour", HOUR),
    "resend": ("resend_per_ip_per_hour", "resend_per_email_per_hour", HOUR),
    "verify": ("verify_per_ip_per_hour", "verify_per_email_per_hour", HOUR),
    "login": ("login_per_ip_per_15_minutes", "login_per_email_per_15_minutes", QUARTER),
}


class RateLimited(HTTPException):
    def __init__(self, retry_after: int, first: bool) -> None:
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited",
                         headers={"Retry-After": str(retry_after)})
        # True for the request that crossed the limit: the one worth recording.
        self.first = first


def _address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _trusted() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    nets = []
    for part in get_settings().trusted_proxies.split(","):
        if part.strip():
            nets.append(ipaddress.ip_network(part.strip(), strict=False))
    return nets


def client_ip(request: Request) -> str | None:
    """The caller's address. X-Forwarded-For is read only when the connection comes from a
    configured proxy, from the right, stopping at the first hop that is not a proxy: anything left
    of that was written by the client and proves nothing. None when there is no usable address."""
    peer = _address(request.client.host) if request.client else None
    if peer is None:
        return None
    trusted = _trusted()
    if not any(peer in net for net in trusted):
        return str(peer)
    for hop in reversed(request.headers.get("x-forwarded-for", "").split(",")):
        addr = _address(hop.strip())
        if addr is None:
            break
        if not any(addr in net for net in trusted):
            return str(addr)
    return str(peer)


def _key(scope: str, kind: str, value: str) -> str:
    return f"{PREFIX}{scope}:{kind}:{hashlib.sha256(value.lower().encode()).hexdigest()[:32]}"


async def _count(key: str, window: int) -> tuple[int, int]:
    redis = await get_redis()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(key, 0, ex=window, nx=True)
        pipe.incr(key)
        pipe.ttl(key)
        _, count, ttl = await pipe.execute()
    return count, ttl


async def enforce(scope: str, *, ip: str | None, email: str | None) -> None:
    """Count this request against the route's limits; raise RateLimited when one is exceeded."""
    s = get_settings()
    if not s.rate_limits_enabled:
        return
    ip_setting, email_setting, window = LIMITS[scope]
    checks = [(kind, value, getattr(s, setting))
              for kind, value, setting in (("ip", ip, ip_setting), ("email", email, email_setting))
              if value]
    for kind, value, limit in checks:
        try:
            count, ttl = await _count(_key(scope, kind, value), window)
        except (RedisError, OSError):
            log.warning("rate limits skipped: redis unavailable (route %s)", scope)
            return
        if count > limit:
            raise RateLimited(max(ttl, 1), first=count == limit + 1)


async def allow_mail(email: str) -> bool:
    """May one more email go to this address today? Over the cap nothing is sent and the caller
    answers as if it had been, so the cap says nothing about whether the address has an account."""
    s = get_settings()
    if not s.rate_limits_enabled:
        return True
    try:
        count, _ = await _count(_key("mail", "email", email), DAY)
    except (RedisError, OSError):
        log.warning("mail cap skipped: redis unavailable")
        return True
    return count <= s.mail_per_address_per_day
