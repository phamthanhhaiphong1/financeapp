import enum
import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "database", "data.sqlite")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


class TransactionType(str, enum.Enum):
    EXPENSE = "expense"
    INCOME = "income"


class TransactionCategory(str, enum.Enum):
    AN_UONG = "Ăn uống"
    DI_CHUYEN = "Di chuyển"
    HOA_DON = "Hóa đơn"
    MUA_SAM = "Mua sắm"
    SUC_KHOE = "Sức khỏe"
    GIA_DINH = "Gia đình"
    GIAO_TIEP = "Giao tiếp"
    KHAC = "Khác"


class GamificationActionType(str, enum.Enum):
    UNDER_BUDGET = "under_budget"
    NO_SPEND_DAY = "no_spend_day"
    STREAK_7_DAYS = "streak_7_days"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    monthly_budget = Column(Integer, nullable=False, default=0)
    fire_target = Column(Integer, nullable=False, default=0)
    current_streak = Column(Integer, nullable=False, default=0)
    highest_streak = Column(Integer, nullable=False, default=0)

    transactions = relationship("Transaction", back_populates="user")
    gamification_logs = relationship("GamificationLog", back_populates="user")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(SqlEnum(TransactionType), nullable=False)
    amount = Column(Integer, nullable=False)
    category = Column(SqlEnum(TransactionCategory), nullable=False)
    description = Column(Text)
    is_ai_parsed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class GamificationLog(Base):
    __tablename__ = "gamification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(SqlEnum(GamificationActionType), nullable=False)
    achieved_date = Column(Date, nullable=False)

    user = relationship("User", back_populates="gamification_logs")
