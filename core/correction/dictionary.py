import csv
import json
import re
from pathlib import Path


class CorrectionDictionary:
    """
    Manages a correction dictionary for transcript post-processing.
    Dictionary entries: wrong_term -> correct_term (exact string replacement).

    Handles the common case of STT errors for proper nouns, technical terms,
    company names, and people names that LLM may not reliably fix.
    """

    def __init__(self) -> None:
        self._entries: dict[str, str] = {}

    def add(self, wrong: str, correct: str) -> None:
        """Add a single correction entry."""
        self._entries[wrong] = correct

    def remove(self, wrong: str) -> None:
        """Remove a correction entry."""
        self._entries.pop(wrong, None)

    def apply(self, text: str) -> str:
        """Apply all dictionary corrections to text (single-pass, longest match first)."""
        if not self._entries:
            return text
        sorted_keys = sorted(self._entries, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(k) for k in sorted_keys))
        return pattern.sub(lambda m: self._entries[m.group(0)], text)

    def load_csv(self, path: str | Path) -> None:
        """
        Load from CSV with columns: wrong,correct
        Supports BOM and various encodings common in Windows environments.
        """
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                wrong = row.get("wrong", "").strip()
                correct = row.get("correct", "").strip()
                if wrong and correct:
                    self._entries[wrong] = correct

    def load_json(self, path: str | Path) -> None:
        """
        Load from JSON: {"wrong_term": "correct_term", ...}
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for wrong, correct in data.items():
            if isinstance(correct, str):
                self._entries[wrong] = correct

    def to_prompt_hint(self) -> str:
        """Format dictionary as a hint string for LLM correction prompts."""
        if not self._entries:
            return ""
        lines = [f"- {wrong} → {correct}" for wrong, correct in self._entries.items()]
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, item: str) -> bool:
        return item in self._entries
