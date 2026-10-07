from datetime import datetime, timezone
from sqlalchemy import JSON, Float, ForeignKey, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def now():
    return datetime.now(timezone.utc)

class UserSettings(Base):
    __tablename__ = 'user_settings'
    id: Mapped[str] = mapped_column(String, primary_key=True, default='personal')
    data: Mapped[dict] = mapped_column(JSON)

class FoodPreset(Base):
    __tablename__ = 'food_presets'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, default='personal', index=True)
    data: Mapped[dict] = mapped_column(JSON)

class DailyLog(Base):
    __tablename__ = 'daily_logs'
    __table_args__ = (UniqueConstraint('user_id', 'date'),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, default='personal')
    date: Mapped[str] = mapped_column(String, index=True)
    weight_kg: Mapped[float] = mapped_column(Float)
    profile: Mapped[str] = mapped_column(String, default='sedentary')
    tdee: Mapped[float] = mapped_column(Float, default=2500)
    expenditure_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class FoodEntry(Base):
    __tablename__ = 'food_entries'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    log_id: Mapped[str] = mapped_column(ForeignKey('daily_logs.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)

class ActivityEntry(Base):
    __tablename__ = 'activity_entries'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    log_id: Mapped[str] = mapped_column(ForeignKey('daily_logs.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)

class DailyAnalysis(Base):
    __tablename__ = 'daily_analyses'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    log_id: Mapped[str] = mapped_column(ForeignKey('daily_logs.id'), index=True)
    snapshot_hash: Mapped[str] = mapped_column(String, unique=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default='pending')
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String, default='1')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    profile: Mapped[dict] = mapped_column(JSON)

class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    csrf: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
