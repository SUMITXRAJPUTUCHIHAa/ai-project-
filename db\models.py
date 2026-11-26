"""SQLAlchemy models (portable across PostgreSQL and SQLite)."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ConversationLog(Base):
    __tablename__ = "conversation_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=False)
    user_query = Column(Text, nullable=False)
    detected_intent = Column(String(64), index=True)
    slots = Column(Text, default="{}")
    rule_id = Column(String(64), index=True)
    is_answered = Column(Boolean, default=True, index=True)
    confidence = Column(Float, default=0.0)
    version = Column(String(16), index=True, default="2.4")
    is_seed = Column(Boolean, default=False, index=True)
    timestamp = Column(DateTime, default=utcnow, index=True)


class CustomRule(Base):
    __tablename__ = "custom_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(64), unique=True, nullable=False)
    label = Column(String(80))
    pattern = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class SessionState(Base):
    __tablename__ = "session_state"
    session_id = Column(String(64), primary_key=True)
    state_json = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True)
    user_query = Column(Text)
    contact = Column(String(160))
    created_at = Column(DateTime, default=utcnow)
