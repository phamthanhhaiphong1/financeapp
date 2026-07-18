import hashlib
import re
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func

from backend.models.database import SessionLocal, User

router = APIRouter(prefix="/api", tags=["users"])

PIN_PATTERN = re.compile(r"^\d{4}$")


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{pin}".encode("utf-8")).hexdigest()


class IdentifyUserRequest(BaseModel):
    name: str
    pin: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tên không được để trống")
        return value

    @field_validator("pin")
    @classmethod
    def pin_is_4_digits(cls, value: str) -> str:
        if not PIN_PATTERN.match(value):
            raise ValueError("PIN phải gồm đúng 4 chữ số")
        return value


class IdentifyUserResponse(BaseModel):
    user_id: int
    name: str
    created: bool


@router.post("/users/identify", response_model=IdentifyUserResponse)
def identify_user(payload: IdentifyUserRequest):
    db = SessionLocal()
    try:
        try:
            existing = db.query(User).filter(func.lower(User.name) == payload.name.lower()).first()

            if existing:
                expected_hash = _hash_pin(payload.pin, existing.pin_salt or "")
                if not existing.pin_hash or expected_hash != existing.pin_hash:
                    raise HTTPException(status_code=401, detail="Sai mã PIN cho tên này")
                return IdentifyUserResponse(user_id=existing.id, name=existing.name, created=False)

            salt = secrets.token_hex(16)
            new_user = User(
                name=payload.name,
                pin_salt=salt,
                pin_hash=_hash_pin(payload.pin, salt),
                email=f"user-{secrets.token_hex(8)}@fire-finance.local",
                monthly_budget=0,
                fire_target=0,
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            return IdentifyUserResponse(user_id=new_user.id, name=new_user.name, created=True)
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi máy chủ khi xác thực: {exc}")
    finally:
        db.close()
