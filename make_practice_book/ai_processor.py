"""
AI helpers for generating ExBook-compatible LaTeX snippets.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional

import requests


RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
AUTH_STATUS_CODES = {401, 403}
TOP_LEVEL_QUESTION_RE = re.compile(r"(?m)^\s*\d+[\.．、]")
TOP_LEVEL_SECTION_RE = re.compile(r"(?m)^\s*[一二三四五六七八九十]+、")


def _split_keys(raw_value: Optional[str]) -> list[str]:
    if not raw_value:
        return []
    items = [item.strip() for item in raw_value.split(";")]
    return [item for item in items if item]


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_base: str
    default_model: str
    env_keys: tuple[str, ...]
    env_key_pools: tuple[str, ...] = ()
    trust_env: bool = True


PROVIDERS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        api_base="https://api.astrdark.cyou",
        default_model="longcat-flash-lite",
        env_keys=("OPENAI_API_KEY", "API_KEY"),
        env_key_pools=("OPENAI_API_KEYS",),
        trust_env=False,
    ),
    "groq": ProviderConfig(
        name="groq",
        api_base="https://api.groq.com/openai/v1",
        default_model="llama-3.1-70b-versatile",
        env_keys=("GROQ_API_KEY",),
        env_key_pools=("GROQ_API_KEYS", "GROQ_API_kEYS"),
    ),
    "zhipu": ProviderConfig(
        name="zhipu",
        api_base="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
        env_keys=("ZHIPUAI_API_KEY", "ZHIPU_API_KEY"),
    ),
}


class AIProcessor:
    """OpenAI-compatible chat client with basic key rotation."""

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        api_keys: Optional[list[str]] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 180,
        max_output_tokens: int = 4000,
    ):
        provider_name = (provider or "groq").strip().lower()
        if provider_name not in PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider_name}")

        self.provider = PROVIDERS[provider_name]
        self.api_base = api_base or self.provider.api_base
        self.model = model or self.provider.default_model
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.session = requests.Session()
        self.session.trust_env = self.provider.trust_env
        self._key_cursor = 0
        self.api_keys = self._load_api_keys(api_key=api_key, api_keys=api_keys)
        if not self.api_keys:
            raise ValueError(
                f"Missing API key for provider '{provider_name}'. "
                f"Set one of: {', '.join(self.provider.env_keys + self.provider.env_key_pools)}"
            )

    def _load_api_keys(
        self,
        api_key: Optional[str] = None,
        api_keys: Optional[list[str]] = None,
    ) -> list[str]:
        keys: list[str] = []

        if api_key:
            keys.append(api_key.strip())
        if api_keys:
            keys.extend(item.strip() for item in api_keys if item and item.strip())

        for env_name in self.provider.env_keys:
            env_value = os.getenv(env_name)
            if env_value:
                keys.append(env_value.strip())

        for env_name in self.provider.env_key_pools:
            keys.extend(_split_keys(os.getenv(env_name)))

        return _unique([item for item in keys if item])

    def _iter_keys(self) -> Iterable[tuple[int, str]]:
        count = len(self.api_keys)
        start = self._key_cursor % count
        for offset in range(count):
            index = (start + offset) % count
            yield index, self.api_keys[index]

    def _post_chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        errors: list[str] = []

        for index, api_key in self._iter_keys():
            last_response = None
            for endpoint in self._chat_completion_endpoints():
                try:
                    response = self.session.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                        timeout=self.timeout,
                    )
                except requests.RequestException as exc:
                    errors.append(f"key#{index + 1}: network error: {exc}")
                    last_response = None
                    break

                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except json.JSONDecodeError:
                        errors.append(
                            f"key#{index + 1}: 200 non-json response from {endpoint}: "
                            f"{response.text[:300]!r}"
                        )
                        last_response = response
                        continue

                    try:
                        content = payload["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError):
                        errors.append(
                            f"key#{index + 1}: 200 unexpected payload from {endpoint}: "
                            f"{str(payload)[:300]}"
                        )
                        last_response = response
                        continue

                    self._key_cursor = (index + 1) % len(self.api_keys)
                    return content

                last_response = response
                if response.status_code != 404:
                    break

            if last_response is None:
                continue

            detail = f"key#{index + 1}: {last_response.status_code} {last_response.text[:300]}"
            errors.append(detail)

            if last_response.status_code in AUTH_STATUS_CODES:
                continue
            if last_response.status_code in RETRYABLE_STATUS_CODES:
                continue

            raise RuntimeError(f"{self.provider.name} request failed: {detail}")

        raise RuntimeError(
            f"All {self.provider.name} API keys failed. " + " | ".join(errors)
        )

    def _chat_completion_endpoints(self) -> list[str]:
        base = self.api_base.rstrip("/")
        if self.provider.name == "openai":
            if base.endswith("/v1"):
                return [f"{base}/chat/completions"]
            return [
                f"{base}/v1/chat/completions",
                f"{base}/chat/completions",
            ]
        return [f"{base}/chat/completions"]

    def process_to_exbook_latex(
        self,
        markdown_content: str,
        custom_prompt: Optional[str] = None,
        *,
        section_title: Optional[str] = None,
        expected_question_count: Optional[int] = None,
    ) -> str:
        prompt = (
            custom_prompt.replace("{content}", markdown_content)
            if custom_prompt
            else self._get_exbook_prompt(
                markdown_content,
                section_title=section_title,
                expected_question_count=expected_question_count,
            )
        )

        raw = self._post_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional educational content formatter. "
                        "Output strictly LaTeX snippets compatible with the ExBook class. "
                        "Do not include the preamble or document environment."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=self.max_output_tokens,
        )
        sanitized = sanitize_latex_output(raw)
        if not self._validate_exbook_output(sanitized):
            sanitized = self._attempt_exbook_repair(sanitized)
        return sanitized

    def process_with_segments(
        self,
        markdown_content: str,
        segment_size: int = 2400,
        *,
        section_title: Optional[str] = None,
        expected_question_count: Optional[int] = None,
    ) -> str:
        segments = self._split_content(markdown_content, segment_size)
        processed: list[str] = []
        for index, segment in enumerate(segments, start=1):
            segment_title = (
                f"{section_title}（分段 {index}/{len(segments)}）"
                if section_title and len(segments) > 1
                else section_title
            )
            segment_question_count = _estimate_question_target(
                segment,
                fallback=expected_question_count,
                total_segments=len(segments),
            )
            processed.append(
                self.process_to_exbook_latex(
                    segment,
                    section_title=segment_title,
                    expected_question_count=segment_question_count,
                )
            )
        return "\n\n".join(processed)

    def _split_content(self, content: str, max_chars: int = 2400) -> list[str]:
        lines = content.splitlines()
        segments: list[str] = []
        current: list[str] = []
        current_length = 0

        for line in lines:
            size = len(line) + 1
            if current and current_length + size > max_chars:
                segments.append("\n".join(current))
                current = [line]
                current_length = size
            else:
                current.append(line)
                current_length += size

        if current:
            segments.append("\n".join(current))

        return segments

    def _get_exbook_prompt(
        self,
        markdown_content: str,
        *,
        section_title: Optional[str] = None,
        expected_question_count: Optional[int] = None,
    ) -> str:
        prompt = r"""
你是一个专业的教育内容格式化专家，专门处理考研试题的 LaTeX 格式化。

你的任务是把输入的纯文本或 Markdown 内容改写成 ExBook 兼容的 LaTeX 片段。

硬性要求：
1. 只输出片段，不要输出 \documentclass、\begin{document}、\end{document}。
2. 每个题目必须独立成框，使用单独的 bbox 环境；每个 bbox 内恰好一个 \qitem。
3. 章节标题必须放在 qitems 环境之外，可以使用 \section*{...}。
4. 不要臆造题目内容；无法识别时保留原始文本。
5. 如果存在子题，例如“（1）（2）”，保留在同一个 \qitem 中。
6. 如果输入中包含年份或试卷标题，这些标题必须写成 \section*{...} 或普通标题，不能写成 \qitem。
7. 不要遗漏题目；每一道顶层题号都应对应一个 \qitem。

推荐输出结构：
\section*{章节标题}
\begin{qitems}
  \begin{bbox}
    \qitem 题目内容
  \end{bbox}
\end{qitems}

上下文信息：
- 当前输入只是整份文档的一个局部分块，不是全文。
- 当前分块标题：{section_title}
- 预估本分块顶层题目数量：{expected_question_count}

执行要求：
- 优先保持完整覆盖，不要为了简洁省略后半部分题目。
- 如果遇到“一、二、三”这种大题分组，分组标题写在 qitems 外，分组下的具体小题再写成 \qitem。
- 如果预估题量大于 0，输出的 \qitem 数量应尽量与之接近。

现在请把以下内容转换为 ExBook 兼容 LaTeX 片段：

{markdown_content}
"""
        return (
            prompt.replace("{section_title}", section_title or "未命名分块")
            .replace(
                "{expected_question_count}",
                str(expected_question_count if expected_question_count is not None else "未知"),
            )
            .replace("{markdown_content}", markdown_content)
        )

    def _validate_exbook_output(self, latex_content: str) -> bool:
        if not latex_content:
            return False
        if not re.search(r"\\begin\{qitems\}", latex_content):
            return False
        qitem_count = len(re.findall(r"\\qitem", latex_content))
        bbox_count = len(re.findall(r"\\begin\{bbox\}", latex_content))
        return qitem_count > 0 and qitem_count == bbox_count

    def _attempt_exbook_repair(self, latex_content: str) -> str:
        return sanitize_latex_output(latex_content)


def sanitize_latex_output(text: str) -> str:
    """Clean common model artifacts and enforce a minimal ExBook shape."""
    if not text:
        return ""

    content = text.replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"(?m)^\s*```.*$", "", content)
    content = re.sub(r"(?m)^\s*:::+\s*$", "", content)
    content = re.sub(r"(?m)^\s*---+\s*$", "", content)
    content = re.sub(r"(?mi)^\s*\\documentclass[^\n]*\n?", "", content)
    content = re.sub(r"(?mi)^\s*\\usepackage[^\n]*\n?", "", content)
    content = content.replace(r"\begin{document}", "").replace(r"\end{document}", "")
    content = content.replace(":::", "")
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    if re.search(r"\\begin\{qitems\}", content):
        return _expand_multi_question_bboxes(content)

    questions = _split_questions_from_content(content)
    if not questions:
        questions = [content or "% empty"]

    lines = ["\\begin{qitems}"]
    for question in questions:
        lines.append("  \\begin{bbox}")
        lines.append(f"    \\qitem {question.strip()}")
        lines.append("  \\end{bbox}")
    lines.append("\\end{qitems}")
    return _expand_multi_question_bboxes("\n".join(lines))


def _expand_multi_question_bboxes(content: str) -> str:
    pattern = re.compile(
        r"\\begin\{bbox\}\s*\\qitem\s*(?P<body>.*?)\s*\\end\{bbox\}",
        re.DOTALL,
    )

    def _replace(match: re.Match[str]) -> str:
        body = match.group("body").strip()
        questions = _split_grouped_qitem(body)
        if len(questions) <= 1:
            return match.group(0)

        blocks: list[str] = []
        for question in questions:
            blocks.append("\\begin{bbox}")
            blocks.append(f"  \\qitem {question.strip()}")
            blocks.append("\\end{bbox}")
        return "\n".join(blocks)

    return pattern.sub(_replace, content)


def _split_grouped_qitem(body: str) -> list[str]:
    latex_items = _split_latex_enumerated_qitem(body)
    if len(latex_items) > 1:
        return latex_items

    matches = list(TOP_LEVEL_QUESTION_RE.finditer(body))
    if len(matches) < 2:
        return [body]

    heading = body[: matches[0].start()].strip()
    questions: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        question = body[match.start() : end].strip()
        if heading:
            question = f"{heading}\n\n{question}"
        questions.append(question)
    return questions


def _split_latex_enumerated_qitem(body: str) -> list[str]:
    lines = body.splitlines()
    heading_lines: list[str] = []
    current_item: list[str] | None = None
    items: list[str] = []
    enumerate_depth = 0
    inside_top_enumerate = False

    for line in lines:
        stripped = line.strip()

        if not inside_top_enumerate:
            if stripped.startswith(r"\begin{enumerate}"):
                inside_top_enumerate = True
                enumerate_depth = 1
                continue
            heading_lines.append(line)
            continue

        if stripped.startswith(r"\begin{enumerate}"):
            enumerate_depth += 1
            if current_item is not None:
                current_item.append(line)
            continue

        if stripped.startswith(r"\end{enumerate}"):
            enumerate_depth -= 1
            if enumerate_depth == 0:
                continue
            if current_item is not None:
                current_item.append(line)
            continue

        if enumerate_depth == 1 and stripped.startswith(r"\item "):
            if current_item:
                items.append("\n".join(current_item).strip())
            current_item = [stripped[len(r"\item ") :]]
            continue

        if current_item is not None:
            current_item.append(line)

    if current_item:
        items.append("\n".join(current_item).strip())

    if len(items) < 2:
        return [body]

    heading = "\n".join(line.rstrip() for line in heading_lines).strip()
    result: list[str] = []
    for item in items:
        question = item
        if heading:
            question = f"{heading}\n\n{item}"
        result.append(question.strip())
    return result


def _split_questions_from_content(content: str) -> list[str]:
    if not content.strip():
        return []

    patterns = [
        r"(?:^|\n)\s*(\d+[\.、])\s*",
        r"(?:^|\n)\s*\((\d+)\)\s*",
        r"(?:^|\n)\s*([一二三四五六七八九十]+[\.、])\s*",
    ]

    questions = [content]
    for pattern in patterns:
        updated: list[str] = []
        for chunk in questions:
            parts = re.split(pattern, chunk)
            if len(parts) == 1:
                updated.append(chunk)
                continue

            current = ""
            for index, part in enumerate(parts):
                if index % 2 == 1:
                    if current.strip():
                        updated.append(current.strip())
                    current = part + " "
                else:
                    current += part
            if current.strip():
                updated.append(current.strip())

        if len(updated) > len(questions):
            questions = updated
            break

    return [item for item in questions if item.strip()]


def _estimate_question_target(
    content: str,
    *,
    fallback: Optional[int],
    total_segments: int,
) -> Optional[int]:
    numeric_matches = len(TOP_LEVEL_QUESTION_RE.findall(content))
    if numeric_matches > 0:
        return numeric_matches

    section_matches = len(TOP_LEVEL_SECTION_RE.findall(content))
    if section_matches > 0:
        return section_matches

    if fallback is None or fallback <= 0:
        return fallback

    return max(1, fallback // max(total_segments, 1))


def process_with_ai_exbook(
    markdown_content: str,
    provider: str = "openai",
    api_key: Optional[str] = None,
    api_keys: Optional[list[str]] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
    use_segments: bool = False,
    max_output_tokens: int = 4000,
    segment_size: int = 2400,
    section_title: Optional[str] = None,
    expected_question_count: Optional[int] = None,
    custom_prompt: Optional[str] = None,
) -> str:
    processor = AIProcessor(
        provider=provider,
        api_key=api_key,
        api_keys=api_keys,
        api_base=api_base,
        model=model,
        max_output_tokens=max_output_tokens,
    )
    if use_segments:
        return processor.process_with_segments(
            markdown_content,
            segment_size=segment_size,
            section_title=section_title,
            expected_question_count=expected_question_count,
        )
    return processor.process_to_exbook_latex(
        markdown_content,
        custom_prompt=custom_prompt,
        section_title=section_title,
        expected_question_count=expected_question_count,
    )
