from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import extract, func

from backend.core.gemini_service import parse_expense
from backend.models.database import (
    SessionLocal,
    Transaction,
    TransactionCategory,
    TransactionType,
    User,
)

router = APIRouter(prefix="/api", tags=["transactions"])


class ParseRequest(BaseModel):
    text: Optional[str] = None
    image_base64: Optional[str] = None


class ParsedTransaction(BaseModel):
    type: TransactionType = TransactionType.EXPENSE
    amount: int
    currency: str = "VND"
    category: str
    description: str


class ParseResponse(BaseModel):
    transactions: List[ParsedTransaction]


class ConfirmedTransaction(BaseModel):
    type: TransactionType = TransactionType.EXPENSE
    amount: int
    category: TransactionCategory
    description: Optional[str] = None
    is_ai_parsed: bool = True

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value):
        if value <= 0:
            raise ValueError("amount must be a positive integer")
        return value


class SaveTransactionsRequest(BaseModel):
    user_id: int
    transactions: List[ConfirmedTransaction]


class SaveTransactionsResponse(BaseModel):
    saved: int
    transaction_ids: List[int]
    current_streak: int


class MonthlySummaryResponse(BaseModel):
    total_income: int
    total_expense: int
    balance: int


class TransactionItem(BaseModel):
    id: int
    type: TransactionType
    amount: int
    category: str
    description: Optional[str] = None


class TransactionListResponse(BaseModel):
    transactions: List[TransactionItem]


class MonthOption(BaseModel):
    year: int
    month: int


class AvailableMonthsResponse(BaseModel):
    months: List[MonthOption]


@router.post("/parse", response_model=ParseResponse)
def parse_transactions(payload: ParseRequest):
    if payload.image_base64:
        parse_args = (payload.image_base64,)
        parse_kwargs = {"is_image": True}
    elif payload.text:
        parse_args = (payload.text,)
        parse_kwargs = {"is_image": False}
    else:
        raise HTTPException(status_code=400, detail="Provide either 'text' or 'image_base64'")

    try:
        raw = parse_expense(*parse_args, **parse_kwargs)
        parsed = [ParsedTransaction(**item) for item in raw]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to parse AI response: {exc}")

    return ParseResponse(transactions=parsed)


@router.post("/transactions", response_model=SaveTransactionsResponse)
def create_transactions(payload: SaveTransactionsRequest):
    db = SessionLocal()
    try:
        user = db.get(User, payload.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        today = date.today()
        yesterday = today - timedelta(days=1)

        txns_today = (
            db.query(Transaction)
            .filter(Transaction.user_id == user.id, func.date(Transaction.created_at) == today)
            .count()
        )
        is_first_of_day = txns_today == 0

        created = []
        for item in payload.transactions:
            txn = Transaction(
                user_id=user.id,
                type=item.type,
                amount=item.amount,
                category=item.category,
                description=item.description,
                is_ai_parsed=item.is_ai_parsed,
            )
            db.add(txn)
            created.append(txn)

        if is_first_of_day:
            txns_yesterday = (
                db.query(Transaction)
                .filter(Transaction.user_id == user.id, func.date(Transaction.created_at) == yesterday)
                .count()
            )
            user.current_streak = user.current_streak + 1 if txns_yesterday > 0 else 1
            if user.current_streak > user.highest_streak:
                user.highest_streak = user.current_streak

        db.commit()
        for txn in created:
            db.refresh(txn)

        return SaveTransactionsResponse(
            saved=len(created),
            transaction_ids=[txn.id for txn in created],
            current_streak=user.current_streak,
        )
    finally:
        db.close()


@router.get("/summary/monthly", response_model=MonthlySummaryResponse)
def get_monthly_summary(user_id: int, year: Optional[int] = None, month: Optional[int] = None):
    db = SessionLocal()
    try:
        today = date.today()
        target_year = year or today.year
        target_month = month or today.month

        def sum_for(txn_type: TransactionType) -> int:
            return (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.user_id == user_id,
                    Transaction.type == txn_type,
                    extract("year", Transaction.created_at) == target_year,
                    extract("month", Transaction.created_at) == target_month,
                )
                .scalar()
            )

        total_income = sum_for(TransactionType.INCOME)
        total_expense = sum_for(TransactionType.EXPENSE)

        return MonthlySummaryResponse(
            total_income=total_income,
            total_expense=total_expense,
            balance=total_income - total_expense,
        )
    finally:
        db.close()


@router.get("/transactions/monthly", response_model=TransactionListResponse)
def get_monthly_transactions(user_id: int, year: Optional[int] = None, month: Optional[int] = None):
    db = SessionLocal()
    try:
        today = date.today()
        target_year = year or today.year
        target_month = month or today.month

        rows = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user_id,
                extract("year", Transaction.created_at) == target_year,
                extract("month", Transaction.created_at) == target_month,
            )
            .order_by(Transaction.created_at.desc())
            .all()
        )
        return TransactionListResponse(
            transactions=[
                TransactionItem(
                    id=t.id,
                    type=t.type,
                    amount=t.amount,
                    category=t.category,
                    description=t.description,
                )
                for t in rows
            ]
        )
    finally:
        db.close()


@router.get("/transactions/months", response_model=AvailableMonthsResponse)
def get_available_months(user_id: int):
    db = SessionLocal()
    try:
        rows = (
            db.query(
                extract("year", Transaction.created_at),
                extract("month", Transaction.created_at),
            )
            .filter(Transaction.user_id == user_id)
            .distinct()
            .all()
        )
        months = sorted(
            (MonthOption(year=int(y), month=int(m)) for y, m in rows),
            key=lambda opt: (opt.year, opt.month),
            reverse=True,
        )
        return AvailableMonthsResponse(months=months)
    finally:
        db.close()
