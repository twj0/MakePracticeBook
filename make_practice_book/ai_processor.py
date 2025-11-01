"""
AI Processor Module - Convert Markdown content to exercise book format using AI
"""

import os
from typing import Optional
import requests
import re


class AIProcessor:
    """AI processor class for calling various AI APIs"""
    
    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize AI processor
        
        Args:
            api_key: API key
            api_base: API base URL
            model: Model to use
        """
        self.api_key = api_key or os.getenv("API_KEY")
        self.api_base = api_base or os.getenv("API_BASE", "https://api.openai.com/v1")
        self.model = model
        
        if not self.api_key:
            raise ValueError("Missing API key. Please set API_KEY environment variable or pass it as parameter")
    
    def process_exercise_book(self, markdown_content: str, custom_prompt: Optional[str] = None) -> str:
        """
        Convert Markdown content to exercise book format
        
        Args:
            markdown_content: Markdown formatted content
            custom_prompt: Custom prompt for AI processing (optional)
            
        Returns:
            str: Processed exercise book content
        """
        if custom_prompt:
            # Avoid str.format which breaks on LaTeX braces; only replace the supported placeholder
            prompt = custom_prompt.replace("{content}", markdown_content)
        else:
            prompt = self._get_default_prompt(markdown_content)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a professional educational content organizer, skilled at organizing textbook content into a format suitable for handwritten exercise books."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                raise Exception(f"AI processing failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network request error: {str(e)}")
        except Exception as e:
            raise Exception(f"AI processing error: {str(e)}")

    def process_to_exbook_latex(self, markdown_content: str, custom_prompt: Optional[str] = None) -> str:
        """
        Convert Markdown content to ExBook-compatible LaTeX fragments only.
        The returned content should be LaTeX snippets (sections, qitems, etc.),
        not a full document.
        """
        if custom_prompt:
            # Avoid str.format which breaks on LaTeX braces; only replace the supported placeholder
            prompt = custom_prompt.replace("{content}", markdown_content)
        else:
            prompt = self._get_exbook_prompt(markdown_content)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional educational content formatter. "
                        "Output strictly LaTeX snippets compatible with the ExBook class. "
                        "Do NOT include preamble or document environment. "
                        "Each problem MUST be in its own bbox with a single \\qitem. "
                        "Section titles MUST be outside qitems."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 4000
        }

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=data,
                timeout=120
            )
            if response.status_code == 200:
                result = response.json()
                raw = result['choices'][0]['message']['content']
                sanitized = sanitize_latex_output(raw)
                # Validate structure; attempt repair if needed
                try:
                    if not self._validate_exbook_output(sanitized):
                        sanitized = self._attempt_exbook_repair(sanitized)
                except Exception:
                    # In case of any unexpected error, still return sanitized
                    pass
                return sanitized
            else:
                raise Exception(f"AI processing failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network request error: {str(e)}")
        except Exception as e:
            raise Exception(f"AI processing error: {str(e)}")
    
    def _get_default_prompt(self, markdown_content: str) -> str:
        """
        Get default prompt for exercise book conversion
        
        Args:
            markdown_content: Markdown content to process
            
        Returns:
            str: Formatted prompt
        """
        prompt = f"""
You are a professional educational content organizer. Please convert the following content into a format suitable for creating an exercise book:

Requirements:
1. Carefully identify each question, and each question should be separated independently
2. Add numbering to each question
3. Keep the integrity of the questions without omitting any content
4. Leave enough blank space after each question for handwritten answers
5. Preserve descriptions of original formulas, charts, and other important information
6. Output in standard Markdown format

Content:
{markdown_content}

Please strictly follow this format for output:

# Exercise Book

## Question 1

[Specific content of the question, maintaining original format]

---

[The dividing line above is for the question area, and below is for the answer area]

[Answer area, with enough space for handwriting]


## Question 2

[Specific content of the question, maintaining original format]

---

[The dividing line above is for the question area, and below is for the answer area]

[Answer area, with enough space for handwriting]
"""
        return prompt

    def _get_exbook_prompt(self, markdown_content: str) -> str:
        r"""
        Optimized prompt for generating ExBook-compatible LaTeX snippets with strict
        per-question bbox structure and section placement rules.
        """
        prompt = r"""
你是一个专业的教育内容格式化专家，专门处理考研试题的LaTeX格式化。

重要规则：
1. 每个题目必须独立成框，使用单独的 bbox 环境；每个 bbox 内恰好一个 \qitem。
2. 章节标题（如“2006年硕士学位研究生入学考试试题”）必须放在 qitems 环境之外。
3. 题目编号（如“1.”、“2.”、“3.” 或 “（1）” 等）用于题目分割。

输出格式要求：

对于章节标题：
\section*{2006年硕士学位研究生入学考试试题}

对于每个题目：
\begin{qitems}
  \begin{bbox}
    \qitem 1．简要回答下列问题（每小题5分，共30分）
    （1）要使湿衣服干得快，可采取哪些措施？说明理由。
    （2）供暖使室内温度升高，室内空气的总内能是否增加？为什么？
  \end{bbox}
  \begin{bbox}
    \qitem 2．（15分）某燃气轮机装置中……
  \end{bbox}
  ...
\end{qitems}

特别注意：
- 每个题目编号开始新的 bbox。
- 不要将多个题目放在同一个 bbox 中。
- 章节标题不要放在 \qitem 内，应独立为 \section 或 \section*。
- 保持原始题目的完整性（包括公式、图表描述等）；不要臆造内容。
- 子题（（1）、（2）…）应保留在同一个题目的 bbox 中。

现在，请将以下 Markdown 内容转换为符合上述要求的 ExBook LaTeX 格式：

{markdown_content}
"""
        # Avoid str.format which breaks on LaTeX braces; only replace the supported placeholder
        return prompt.replace("{markdown_content}", markdown_content)
    
    def process_with_segments(self, markdown_content: str, segment_size: int = 2000) -> str:
        """
        Process long content by segments to avoid token limits
        
        Args:
            markdown_content: Markdown content to process
            segment_size: Maximum characters per segment
            
        Returns:
            str: Processed exercise book content
        """
        # Split content into segments
        segments = self._split_content(markdown_content, segment_size)
        
        processed_segments = []
        for i, segment in enumerate(segments):
            print(f"Processing segment {i+1}/{len(segments)}...")
            try:
                result = self.process_exercise_book(segment)
                processed_segments.append(result)
            except Exception as e:
                print(f"Warning: Failed to process segment {i+1}: {str(e)}")
                # Keep original content if processing fails
                processed_segments.append(segment)
        
        return "\n\n".join(processed_segments)
    
    def _split_content(self, content: str, max_chars: int = 2000) -> list:
        """
        Split content into smaller segments
        
        Args:
            content: Content to split
            max_chars: Maximum characters per segment
            
        Returns:
            list: List of content segments
        """
        lines = content.split('\n')
        segments = []
        current_segment = []
        current_length = 0
        
        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            
            if current_length + line_length > max_chars and current_segment:
                # Save current segment and start new one
                segments.append('\n'.join(current_segment))
                current_segment = [line]
                current_length = line_length
            else:
                current_segment.append(line)
                current_length += line_length
        
        # Add last segment
        if current_segment:
            segments.append('\n'.join(current_segment))
        
        return segments

    def _validate_exbook_output(self, latex_content: str) -> bool:
        """Validate that LaTeX content follows ExBook structure.
        - Must contain qitems environment
        - Each question should be one bbox containing one \qitem
        """
        if not latex_content:
            return False
        if not re.search(r"\\begin\{qitems\}", latex_content):
            return False
        m = re.search(r"\\begin\{qitems\}(.*?)\\end\{qitems\}", latex_content, re.DOTALL)
        if not m:
            return False
        body = m.group(1)
        qitem_count = len(re.findall(r"\\qitem", body))
        bbox_count = len(re.findall(r"\\begin\{bbox\}", body))
        if qitem_count == 0 or bbox_count == 0:
            return False
        # Basic expectation: same count (not strict, but good heuristic)
        return qitem_count == bbox_count

    def _attempt_exbook_repair(self, latex_content: str) -> str:
        """Attempt to repair ExBook LaTeX content by re-sanitizing and splitting.
        Currently delegates to sanitize_latex_output().
        """
        try:
            return sanitize_latex_output(latex_content)
        except Exception:
            return latex_content


def sanitize_latex_output(text: str) -> str:
    r"""
    Sanitize AI-generated LaTeX snippets for ExBook.
    - Strip Markdown artifacts: code fences ```..., ::: blocks, --- hr lines
    - Remove malformed or empty section commands like \section*{:::}
    - Remove preamble/document wrappers (\documentclass, \usepackage, \begin{document}, \end{document})
    - Attempt to split a single, long bbox into multiple questions using numbering patterns
    - Ensure at least a minimal ExBook structure exists (wrap into qitems/bbox/\qitem when needed)
    """
    if not text:
        return ""

    # Normalize line endings
    s = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove fenced code block markers (```...)
    s = re.sub(r"(?m)^\s*```.*$", "", s)

    # Remove ::: divider lines
    s = re.sub(r"(?m)^\s*:::+\s*$", "", s)

    # Remove horizontal rule lines consisting of --- or longer
    s = re.sub(r"(?m)^\s*---+\s*$", "", s)

    # Remove obvious malformed section artifacts
    s = s.replace(r"\section*{:::}", "")
    s = s.replace(r"\section*:::}", "")
    s = re.sub(r"\\section\*\s*\{\s*\}", "", s)  # empty starred section
    s = re.sub(r"\\section\*\s*\{\s*[:\-–—]+\s*\}", "", s)  # section with only punctuation

    # Remove preamble/document wrappers if any leaked in
    s = re.sub(r"(?mi)^\s*\\documentclass[^\n]*\n?", "", s)
    s = re.sub(r"(?mi)^\s*\\usepackage[^\n]*\n?", "", s)
    s = re.sub(r"\\begin\{document\}|\\end\{document\}", "", s)

    # Remove stray ::: tokens left inline
    s = s.replace(":::", "")

    # Trim excessive blank lines
    s = re.sub(r"\n{3,}", "\n\n", s).strip()

    # If qitems exists but only one bbox, try to split into multiple questions
    qitems_block = re.search(r"\\begin\{qitems\}(.*?)\\end\{qitems\}", s, re.DOTALL)
    if qitems_block:
        inner = qitems_block.group(1)
        bbox_count = len(re.findall(r"\\begin\{bbox\}", inner))
        if bbox_count == 1:
            bbox_match = re.search(r"\\begin\{bbox\}(.*?)\\end\{bbox\}", inner, re.DOTALL)
            if bbox_match:
                only_bbox = bbox_match.group(1)
                # Extract and temporarily remove section titles inside qitems if any leaked in
                sections = re.findall(r"\\(section\*?)\{([^}]+)\}", only_bbox)
                content_wo_sections = re.sub(r"\\(section\*?)\{[^}]+\}", "", only_bbox).strip()
                # Split into questions
                qs = _split_questions_from_content(content_wo_sections)
                rebuilt = []
                # Re-add sections before qitems
                for sec_type, title in sections:
                    rebuilt.append(f"\\{sec_type}{{{title}}}")
                rebuilt.append("\\begin{qitems}")
                for q in qs:
                    if q.strip():
                        rebuilt.append("  \\begin{bbox}")
                        rebuilt.append("    \\qitem " + q.strip())
                        rebuilt.append("  \\end{bbox}")
                rebuilt.append("\\end{qitems}")
                s = s.replace(qitems_block.group(0), "\n".join(rebuilt))

    # Ensure minimal ExBook structure if none present
    if not re.search(r"\\begin\{qitems\}", s):
        inner = s.strip() or r"% (empty)"
        s = (
            "\\begin{qitems}\n"
            "  \\begin{bbox}\n"
            "    \\qitem " + inner + "\n"
            "  \\end{bbox}\n"
            "\\end{qitems}"
        )

    return s


def _split_questions_from_content(content: str) -> list:
    """Split questions by common numbering patterns in Chinese exam text.
    Prioritized patterns: 1. / 2. / 3. ...; then (1) / (2) ...; then Chinese numerals like 一. 二.
    """
    if not content:
        return []

    text = content
    # Normalize bullet variants
    # Try numeric with dot or Chinese list punctuation
    patterns = [
        r"(?:^|\n)\s*(\d+[\.、])\s*",
        r"(?:^|\n)\s*\((\d+)\)\s*",
        r"(?:^|\n)\s*([一二三四五六七八九十]+[\.、])\s*",
    ]

    # Default: single question
    questions = [text]
    for pat in patterns:
        new_questions = []
        for chunk in questions:
            parts = re.split(pat, chunk)
            if len(parts) > 1:
                current = ""
                for i, part in enumerate(parts):
                    if i % 2 == 1:  # numbering token
                        if current.strip():
                            new_questions.append(current.strip())
                        current = part + " "
                    else:
                        current += part
                if current.strip():
                    new_questions.append(current.strip())
            else:
                new_questions.append(chunk)
        if len(new_questions) > len(questions):
            questions = new_questions
            break

    return questions

class GroqProcessor(AIProcessor):
    """Groq AI processor with default settings"""
    
    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv("GROQ_API_KEY")
        super().__init__(
            api_key=api_key,
            api_base="https://api.groq.com/openai/v1",
            model="llama3-70b-8192"
        )


class ZhipuAIProcessor(AIProcessor):
    """Zhipu AI processor with default settings"""
    
    def __init__(self, api_key: Optional[str] = None):
        # Support common alias ZHIPU_API_KEY as fallback to avoid confusion
        api_key = api_key or os.getenv("ZHIPUAI_API_KEY") or os.getenv("ZHIPU_API_KEY")
        super().__init__(
            api_key=api_key,
            api_base="https://open.bigmodel.cn/api/paas/v4",
            model="glm-4"
        )


# Utility function for quick AI processing
def process_content(
    markdown_content: str, 
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: str = "gpt-3.5-turbo",
    use_segments: bool = False
) -> str:
    """
    Quick AI processing utility function
    
    Args:
        markdown_content: Markdown content to process
        api_key: API key
        api_base: API base URL
        model: Model to use
        use_segments: Whether to process in segments for long content
        
    Returns:
        str: Processed exercise book content
    """
    processor = AIProcessor(api_key=api_key, api_base=api_base, model=model)
    
    if use_segments:
        return processor.process_with_segments(markdown_content)
    else:
        return processor.process_exercise_book(markdown_content)


def process_with_ai(
    markdown_content: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: str = "glm-4",
    use_segments: bool = False,
) -> str:
    """
    GUI-friendly wrapper to process Markdown with AI.
    Selects provider (groq/zhipu) and delegates to the right processor.

    Args:
        markdown_content: Markdown content to process
        provider: 'groq' or 'zhipu' (default 'zhipu')
        api_key: API key (falls back to env vars when None)
        api_base: Ignored (kept for backward compatibility)
        model: Model name
        use_segments: Whether to process by segments for long content

    Returns:
        str: Processed exercise book content
    """
    prov = (provider or "zhipu").strip().lower()

    if prov == "groq":
        processor = GroqProcessor(api_key=api_key)
        # allow model override via AIProcessor.model
        processor.model = model or processor.model
    else:
        # default to Zhipu (GLM)
        processor = ZhipuAIProcessor(api_key=api_key)
        processor.model = model or processor.model

    if use_segments:
        return processor.process_with_segments(markdown_content)
    return processor.process_exercise_book(markdown_content)


def process_with_ai_exbook(
    markdown_content: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: str = "glm-4",
) -> str:
    """
    GUI-friendly wrapper to produce ExBook-compatible LaTeX snippets from Markdown.
    """
    prov = (provider or "zhipu").strip().lower()
    if prov == "groq":
        processor = GroqProcessor(api_key=api_key)
        processor.model = model or processor.model
    else:
        processor = ZhipuAIProcessor(api_key=api_key)
        processor.model = model or processor.model
    return processor.process_to_exbook_latex(markdown_content)
