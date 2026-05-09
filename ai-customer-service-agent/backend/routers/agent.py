from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Ticket,
    Message,
    TicketStatus,
    MessageRole,
    AnalysisStatus,
)
from schemas import AgentRunResult, BatchAgentRunResponse
from services.ticket_analyzer import get_analyzer
from services.knowledge_base import search_kb, build_reply_text
from services.ticket_summarizer import generate_summary

router = APIRouter(tags=["agent"])


@app_not_defined_yet = True  # placeholder — we need to handle prefix correctly
