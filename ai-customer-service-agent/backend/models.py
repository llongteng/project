import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class TicketStatus(str, enum.Enum):
    PENDING = "pending"
    AI_PROCESSING = "ai_processing"
    WAITING_USER = "waiting_user"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(str, enum.Enum):
    ORDER = "order"
    REFUND = "refund"
    ACCOUNT = "account"
    PRODUCT = "product"
    COMPLAINT = "complaint"
    OTHER = "other"


class MessageRole(str, enum.Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class Sentiment(str, enum.Enum):
    NORMAL = "normal"
    ANXIOUS = "anxious"
    ANGRY = "angry"
    COMPLAINT = "complaint"


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_email = Column(String(200), nullable=False)
    category = Column(Enum(TicketCategory), default=TicketCategory.OTHER)
    priority = Column(Enum(TicketPriority), default=TicketPriority.MEDIUM)
    status = Column(Enum(TicketStatus), default=TicketStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sentiment = Column(Enum(Sentiment), nullable=True)
    ai_category = Column(Enum(TicketCategory), nullable=True)
    ai_priority = Column(Enum(TicketPriority), nullable=True)
    need_human = Column(Integer, default=0)
    analysis_reason = Column(Text, nullable=True)
    analysis_status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    analyzed_at = Column(DateTime, nullable=True)

    messages = relationship("Message", back_populates="ticket", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    source_kb_ids = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="messages")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    category = Column(Enum(TicketCategory), default=TicketCategory.OTHER)
    content = Column(Text, nullable=False)
    keywords = Column(String(500), default="")
    enabled = Column(Integer, default=1)
    embedding = Column(Text, nullable=True, default=None)  # JSON-serialized float list
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TicketSummary(Base):
    __tablename__ = "ticket_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), unique=True, nullable=False)
    problem = Column(Text, default="")
    category = Column(String(50), default="")
    sentiment = Column(String(50), default="")
    resolution = Column(Text, default="")
    final_status = Column(String(50), default="")
    need_human = Column(Integer, default=0)
    escalation_reason = Column(Text, default="")
    knowledge_used = Column(Integer, default=0)
    summary_text = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
