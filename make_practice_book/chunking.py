"""
Chunk long extracted source text into exam-aware units before LLM formatting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path


YEAR_HEADER_RE = re.compile(
    r"(?m)^(?:#\s*)?(?P<year>20\d{2}|19\d{2})年硕士学位研究生入学考试试题.*$"
)
ANSWER_TITLE_RE = re.compile(r"答案")
TOP_LEVEL_ARABIC_RE = re.compile(r"(?m)^\s*\d+[\.．、]")
TOP_LEVEL_SECTION_RE = re.compile(r"(?m)^\s*[一二三四五六七八九十]+、")


@dataclass
class SourceChunk:
    chunk_id: str
    title: str
    year: str | None
    question_estimate: int
    char_count: int
    content: str


@dataclass
class ChunkReport:
    section_count: int
    chunk_count: int
    estimated_questions: int
    chunks: list[SourceChunk]


def chunk_source_text(
    source_text: str,
    max_chars: int = 6000,
    include_answers: bool = False,
) -> ChunkReport:
    sections = _split_year_sections(source_text, include_answers=include_answers)
    chunks: list[SourceChunk] = []
    total_questions = 0

    for section_index, (section_title, section_year, section_body) in enumerate(sections, start=1):
        section_chunks = _split_section_into_chunks(
            section_title=section_title,
            section_year=section_year,
            section_body=section_body,
            max_chars=max_chars,
            section_index=section_index,
        )
        chunks.extend(section_chunks)
        total_questions += sum(chunk.question_estimate for chunk in section_chunks)

    return ChunkReport(
        section_count=len(sections),
        chunk_count=len(chunks),
        estimated_questions=total_questions,
        chunks=chunks,
    )


def write_chunk_report(report: ChunkReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "section_count": report.section_count,
        "chunk_count": report.chunk_count,
        "estimated_questions": report.estimated_questions,
        "chunks": [asdict(chunk) for chunk in report.chunks],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _split_year_sections(
    source_text: str,
    *,
    include_answers: bool = False,
) -> list[tuple[str, str | None, str]]:
    matches = list(YEAR_HEADER_RE.finditer(source_text))
    if not matches:
        return [("全文", None, source_text.strip())]

    sections: list[tuple[str, str | None, str]] = []
    prefix = source_text[: matches[0].start()].strip()
    if prefix:
        sections.append(("前置内容", None, prefix))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source_text)
        title = match.group(0).strip().lstrip("#").strip()
        if not include_answers and ANSWER_TITLE_RE.search(title):
            continue

        block = source_text[match.end() : end].strip()
        year = match.group("year")
        sections.append((title, year, block))

    return sections


def _split_section_into_chunks(
    *,
    section_title: str,
    section_year: str | None,
    section_body: str,
    max_chars: int,
    section_index: int,
) -> list[SourceChunk]:
    items = _split_by_question_markers(section_body)
    if not items:
        items = [section_body.strip()]

    chunks: list[SourceChunk] = []
    current_parts: list[str] = []
    current_len = 0
    chunk_number = 1

    for item in items:
        item = item.strip()
        if not item:
            continue
        item_len = len(item) + 2
        if current_parts and current_len + item_len > max_chars:
            chunks.append(
                _make_chunk(
                    section_index=section_index,
                    chunk_number=chunk_number,
                    section_title=section_title,
                    section_year=section_year,
                    content="\n\n".join(current_parts),
                )
            )
            chunk_number += 1
            current_parts = [item]
            current_len = item_len
        else:
            current_parts.append(item)
            current_len += item_len

    if current_parts:
        chunks.append(
            _make_chunk(
                section_index=section_index,
                chunk_number=chunk_number,
                section_title=section_title,
                section_year=section_year,
                content="\n\n".join(current_parts),
            )
        )

    return chunks


def _split_by_question_markers(section_body: str) -> list[str]:
    question_pattern = _question_pattern_for_text(section_body)
    lines = section_body.splitlines()
    items: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                current.append("")
            continue

        if question_pattern and question_pattern.match(stripped) and current:
            items.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        items.append("\n".join(current).strip())

    return items


def _make_chunk(
    *,
    section_index: int,
    chunk_number: int,
    section_title: str,
    section_year: str | None,
    content: str,
) -> SourceChunk:
    question_estimate = _estimate_question_count(content)
    return SourceChunk(
        chunk_id=f"s{section_index:02d}-c{chunk_number:02d}",
        title=section_title,
        year=section_year,
        question_estimate=question_estimate,
        char_count=len(content),
        content=content.strip(),
    )


def _question_pattern_for_text(text: str) -> re.Pattern[str] | None:
    if TOP_LEVEL_ARABIC_RE.search(text):
        return TOP_LEVEL_ARABIC_RE
    if TOP_LEVEL_SECTION_RE.search(text):
        return TOP_LEVEL_SECTION_RE
    return None


def _estimate_question_count(text: str) -> int:
    arabic_matches = list(TOP_LEVEL_ARABIC_RE.finditer(text))
    section_matches = list(TOP_LEVEL_SECTION_RE.finditer(text))

    if not arabic_matches and not section_matches:
        return 0
    if arabic_matches and not section_matches:
        return len(arabic_matches)
    if section_matches and not arabic_matches:
        return len(section_matches)

    total = 0
    bounds = [match.start() for match in section_matches] + [len(text)]
    for index, section_match in enumerate(section_matches):
        start = section_match.end()
        end = bounds[index + 1]
        count = len(TOP_LEVEL_ARABIC_RE.findall(text[start:end]))
        total += count if count > 0 else 1

    first_section_start = section_matches[0].start()
    prefix_count = len(TOP_LEVEL_ARABIC_RE.findall(text[:first_section_start]))
    return total + prefix_count
