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


@router.post("/parse", response_model=ParseResponse)
def parse_transactions(payload: ParseRequest):
    if payload.image_base64:
        raw = parse_expense(payload.image_base64, is_image=True)
    elif payload.text:
        raw = parse_expense(payload.text, is_image=False)
    else:
        raise HTTPException(status_code=400, detail="Provide either 'text' or 'image_base64'")

    try:
        parsed = [ParsedTransaction(**item) for item in raw]
    except (TypeError, ValueError) as exc:
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
def get_monthly_summary(user_id: int):
    db = SessionLocal()
    try:
        today = date.today()

        def sum_for(txn_type: TransactionType) -> int:
            return (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.user_id == user_id,
                    Transaction.type == txn_type,
                    extract("year", Transaction.created_at) == today.year,
                    extract("month", Transaction.created_at) == today.month,
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
