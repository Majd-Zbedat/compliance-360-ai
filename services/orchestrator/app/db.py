"""SQLAlchemy persistence layer (SQLite by default, Postgres-ready)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


class AuditRow(Base):
    __tablename__ = "audits"

    id = Column(String(64), primary_key=True)
    filename = Column(String(256), nullable=False)
    status = Column(String(32), nullable=False)
    overall_risk = Column(String(16), nullable=False, default="Unknown")
    parties = Column(JSON, nullable=False, default=list)
    jurisdiction = Column(String(128), nullable=True)
    contract_type = Column(String(128), nullable=True)
    requester = Column(String(128), nullable=True)
    clauses = Column(JSON, nullable=False, default=list)
    findings = Column(JSON, nullable=False, default=list)
    report_markdown = Column(Text, nullable=True)
    safe_report_markdown = Column(Text, nullable=True)
    input_guardrail_passed = Column(Boolean, nullable=False, default=True)
    output_guardrail_passed = Column(Boolean, nullable=False, default=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


_engine = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def _init_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        return
    if settings.database_url.startswith("sqlite"):
        settings.sqlite_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            future=True,
        )
    else:
        _engine = create_engine(settings.database_url, future=True)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    _init_engine()


@contextmanager
def session_scope() -> Iterator[Session]:
    _init_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def row_to_dict(row: AuditRow) -> dict:
    return {
        "id": row.id,
        "filename": row.filename,
        "status": row.status,
        "overall_risk": row.overall_risk,
        "parties": list(row.parties or []),
        "jurisdiction": row.jurisdiction,
        "contract_type": row.contract_type,
        "requester": row.requester,
        "clauses": list(row.clauses or []),
        "findings": list(row.findings or []),
        "report_markdown": row.report_markdown,
        "safe_report_markdown": row.safe_report_markdown,
        "input_guardrail_passed": bool(row.input_guardrail_passed),
        "output_guardrail_passed": bool(row.output_guardrail_passed),
        "rejection_reason": row.rejection_reason,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def dump_json(payload) -> str:
    return json.dumps(payload, default=str)
