import hashlib
import json
import math
import re
import secrets
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import BoundedSemaphore, Lock

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import Account, AuthSession, SearchPreference, UserProfile
from ..services import REGISTRY

COOKIE_NAME = "jobhunter_session"
_SCRYPT_PREFIX = "scrypt$16384$8$1"
_SCRYPT_SLOTS = BoundedSemaphore(4)
_DUMMY_HASH = f"{_SCRYPT_PREFIX}${'00' * 16}${'00' * 64}"
_THROTTLE_LOCK = Lock()
_THROTTLE_BUCKETS: dict[tuple[str, str], deque[float]] = {}
_THROTTLE_WINDOW_SECONDS = 300
_THROTTLE_MAX_BUCKETS = 2048
_LOGIN_LIMIT = 10
_REGISTER_LIMIT = 5
_MAX_BODY_BYTES = 8192


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        raise HTTPException(status_code=403, detail="X-Requested-With: XMLHttpRequest is required")
    origin = request.headers.get("origin")
    if origin is not None and origin not in {value.strip() for value in config.CORS_ORIGINS}:
        raise HTTPException(status_code=403, detail="Request origin is not allowed")


router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(require_csrf)])


def normalize_phone(phone: str) -> str:
    phone = phone.strip()
    if re.fullmatch(r"01[0-9]{9}", phone):
        return "+20" + phone[1:]
    if re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
        return phone
    raise ValueError("Use an Egyptian mobile number (01xxxxxxxxx) or an international +country-code number")


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    phone: str = Field(min_length=1, max_length=32)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def canonical_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("password")
    @classmethod
    def valid_password_text(cls, value: SecretStr) -> SecretStr:
        try:
            value.get_secret_value().encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Password must contain valid Unicode text") from None
        return value


class RegisterIn(LoginIn):
    name: str = Field(min_length=1, max_length=200, validation_alias=AliasChoices("name", "full_name"))

    @field_validator("name")
    @classmethod
    def registered_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Name must contain valid Unicode text") from None
        return value


class AuthOut(BaseModel):
    id: int
    profile_id: int
    phone: str
    full_name: str


async def _read_credentials(request: Request, schema: type[LoginIn]) -> LoginIn:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Authentication request is too large")
        body.extend(chunk)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise HTTPException(status_code=422, detail="Expected a JSON object") from None
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        # Never echo credentials or arbitrary input in validation errors.
        detail = [{"loc": ["body", *error["loc"]], "msg": error["msg"], "type": error["type"]}
                  for error in exc.errors(include_input=False, include_context=False, include_url=False)]
        raise HTTPException(status_code=422, detail=detail) from None


async def _login_data(request: Request) -> LoginIn:
    return await _read_credentials(request, LoginIn)


async def _register_data(request: Request) -> RegisterIn:
    return await _read_credentials(request, RegisterIn)


def _throttle(request: Request, action: str, limit: int) -> None:
    now = time.monotonic()
    cutoff = now - _THROTTLE_WINDOW_SECONDS
    key = (action, request.client.host if request.client else "unknown")
    with _THROTTLE_LOCK:
        for existing_key, attempts in list(_THROTTLE_BUCKETS.items()):
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if not attempts:
                del _THROTTLE_BUCKETS[existing_key]
        attempts = _THROTTLE_BUCKETS.get(key)
        if attempts is None:
            if len(_THROTTLE_BUCKETS) >= _THROTTLE_MAX_BUCKETS:
                raise HTTPException(status_code=429, detail="Too many authentication attempts. Try again later.",
                                    headers={"Retry-After": str(_THROTTLE_WINDOW_SECONDS)})
            attempts = _THROTTLE_BUCKETS[key] = deque()
        if len(attempts) >= limit:
            retry_after = max(1, math.ceil(attempts[0] + _THROTTLE_WINDOW_SECONDS - now))
            raise HTTPException(status_code=429, detail="Too many authentication attempts. Try again later.",
                                headers={"Retry-After": str(retry_after)})
        attempts.append(now)


def _limit_login(request: Request) -> None:
    _throttle(request, "login", _LOGIN_LIMIT)


def _limit_register(request: Request) -> None:
    _throttle(request, "register", _REGISTER_LIMIT)


def _password_digest(password: str, salt: bytes) -> bytes:
    with _SCRYPT_SLOTS:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1,
                              dklen=64, maxmem=32 * 1024 * 1024)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"{_SCRYPT_PREFIX}${salt.hex()}${_password_digest(password, salt).hex()}"


def _verify_password(password: str, stored: str) -> bool:
    valid_format = isinstance(stored, str) and re.fullmatch(
        r"scrypt\$16384\$8\$1\$[0-9a-f]{32}\$[0-9a-f]{128}", stored
    ) is not None
    # Reject stored work-factor changes without allowing unbounded scrypt memory.
    _, salt, expected = (stored if valid_format else _DUMMY_HASH).rsplit("$", 2)
    digest = _password_digest(password, bytes.fromhex(salt))
    return secrets.compare_digest(digest, bytes.fromhex(expected)) and valid_format


def _cookie_token(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    return token if token and re.fullmatch(r"[A-Za-z0-9_-]{43}", token) else None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Authentication required")


def _current_session(request: Request, db: Session) -> AuthSession:
    token = _cookie_token(request)
    if token is None:
        raise _unauthorized()
    session = db.get(AuthSession, _token_hash(token))
    if session is None:
        raise _unauthorized()
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise _unauthorized()
    return session


def get_current_profile(request: Request, db: Session = Depends(get_db)) -> UserProfile:
    require_csrf(request)
    session = _current_session(request, db)
    account = db.get(Account, session.account_id)
    profile = db.get(UserProfile, account.profile_id) if account else None
    if profile is None:
        raise _unauthorized()
    return profile


def _new_session(request: Request, db: Session, account: Account) -> str:
    old_token = _cookie_token(request)
    if old_token:
        old_session = db.get(AuthSession, _token_hash(old_token))
        if old_session:
            db.delete(old_session)
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=_token_hash(token), account_id=account.id,
                       expires_at=datetime.now(timezone.utc) + timedelta(seconds=config.SESSION_MAX_AGE_SECONDS)))
    return token


def _set_cookie(response: Response, token: str) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(COOKIE_NAME, token, max_age=config.SESSION_MAX_AGE_SECONDS,
                        httponly=True, samesite="lax", path="/", secure=config.SESSION_COOKIE_SECURE)


def _auth_out(account: Account, profile: UserProfile) -> AuthOut:
    return AuthOut(id=account.id, profile_id=profile.id, phone=account.phone, full_name=profile.full_name)


@router.post("/register", status_code=201, response_model=AuthOut, dependencies=[Depends(_limit_register)])
def register(request: Request, response: Response, data: RegisterIn = Depends(_register_data),
             db: Session = Depends(get_db)):
    password_hash = _hash_password(data.password.get_secret_value())
    try:
        profile = UserProfile(full_name=data.name, phone=data.phone, country="", salary_currency="")
        db.add(profile)
        db.flush()
        account = Account(phone=data.phone, password_hash=password_hash, profile_id=profile.id)
        db.add(account)
        db.flush()
        db.add(SearchPreference(id=profile.id, enabled=False, sources=list(REGISTRY)))
        token = _new_session(request, db, account)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This phone number is already registered") from None
    _set_cookie(response, token)
    return _auth_out(account, profile)


@router.post("/login", response_model=AuthOut, dependencies=[Depends(_limit_login)])
def login(request: Request, response: Response, data: LoginIn = Depends(_login_data),
          db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.phone == data.phone).first()
    valid_password = _verify_password(data.password.get_secret_value(),
                                      account.password_hash if account else _DUMMY_HASH)
    if account is None or not valid_password:
        raise HTTPException(status_code=401, detail="Invalid phone or password")
    profile = db.get(UserProfile, account.profile_id)
    if profile is None:
        raise HTTPException(status_code=401, detail="Invalid phone or password")
    token = _new_session(request, db, account)
    db.commit()
    _set_cookie(response, token)
    return _auth_out(account, profile)


@router.post("/logout", response_model=dict[str, bool])
def logout(request: Request, response: Response, profile: UserProfile = Depends(get_current_profile),
           db: Session = Depends(get_db)):
    db.delete(_current_session(request, db))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie(COOKIE_NAME, path="/", secure=config.SESSION_COOKIE_SECURE,
                           httponly=True, samesite="lax")
    return {"ok": True}


@router.get("/me", response_model=AuthOut)
def me(response: Response, profile: UserProfile = Depends(get_current_profile), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.profile_id == profile.id).first()
    if account is None:
        raise _unauthorized()
    response.headers["Cache-Control"] = "no-store"
    return _auth_out(account, profile)
