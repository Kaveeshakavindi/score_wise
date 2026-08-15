"""One-off loader for a manually-extracted past paper (see app/seed_data/).

Not part of the admin ingestion pipeline (no vision-LLM extraction here) --
this just loads a paper + its questions from a pre-built JSON file straight
into Postgres, for cases where the JSON was already produced by hand or by a
one-off extraction pass. Idempotent: re-running upserts the Paper row (by
subject+year) and each Question row (by paper_id+question_number) rather than
duplicating them.

Usage (inside the api container, where DATABASE_URL is set):
    python -m app.scripts.seed_paper app/seed_data/2020_ict_paper1_questions.json
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import _to_async_url
from app.db.models import Paper, Question


async def seed(json_path: Path) -> None:
    data = json.loads(json_path.read_text())
    subject = data["subject"]
    year = data["year"]
    questions = data["questions"]

    settings = get_settings()
    engine = create_async_engine(_to_async_url(settings.database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        paper = (
            await session.execute(select(Paper).where(Paper.subject == subject, Paper.year == year))
        ).scalar_one_or_none()
        if paper is None:
            paper = Paper(subject=subject, year=year)
            session.add(paper)
            await session.flush()  # assigns paper.id before it's referenced below
            print(f"Created paper: {subject} {year} (id={paper.id})")
        else:
            print(f"Reusing existing paper: {subject} {year} (id={paper.id})")

        existing_by_number = {
            q.question_number: q
            for q in (
                await session.execute(select(Question).where(Question.paper_id == paper.id))
            ).scalars()
        }

        created, updated = 0, 0
        for q in questions:
            number = q["question_number"]
            row = existing_by_number.get(number)
            if row is None:
                row = Question(paper_id=paper.id, subject=subject, year=year, question_number=number)
                session.add(row)
                created += 1
            else:
                updated += 1
            row.question_text = q["question_text"]
            row.options = q["options"]
            row.correct_answer = q["correct_answer"]
            row.accept_all = q.get("accept_all", False)

        await session.commit()
        print(f"Questions: {created} created, {updated} updated (total {len(questions)}).")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.scripts.seed_paper <path-to-json>")
        sys.exit(1)
    asyncio.run(seed(Path(sys.argv[1])))
