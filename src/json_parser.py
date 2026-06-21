"""JSON parsing helper — handles LLMs that don't output clean JSON."""
from __future__ import annotations

import json
import re


def parse_json(text: str) -> dict | list:
    """Parse JSON from LLM output, handling common issues.

    Tries:
      1. Direct json.loads
      2. Extract from ```json ... ``` fences
      3. Extract from ``` ... ``` fences
      4. Find first { or [ and matching close
      5. Return empty dict
    """
    text = text.strip()

    # 1. Direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. ```json ... ```
    m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. ``` ... ```
    m = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 4. Find first { or [ and match
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        break

    return {}
