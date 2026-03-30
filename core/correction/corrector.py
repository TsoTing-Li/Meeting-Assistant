from core.correction.dictionary import CorrectionDictionary
from core.llm.base import BaseLLM
from core.exceptions import CorrectionError

CORRECTION_SYSTEM_PROMPT = """你是一個專業的會議逐字稿校正助手，專門處理中英文混合的會議紀錄。

請根據以下規則校正逐字稿：
1. 修正因語音辨識造成的錯字、同音字錯誤
2. 修正中英文混合時常見的辨識錯誤
3. 若有提供自訂詞彙表，請優先使用詞彙表中的正確詞彙
4. 保持原文語意，不要增加或刪減內容
5. 修正標點符號，讓文章更易閱讀
6. 只回傳校正後的逐字稿，不要加上任何說明

{dictionary_section}"""

CORRECTION_USER_PROMPT = """請校正以下會議逐字稿：

{transcript}"""


class TranscriptCorrector:
    """
    Two-stage transcript correction:
    1. Apply dictionary substitutions (high-confidence proper nouns)
    2. LLM-based contextual correction for remaining errors
    """

    def __init__(self, llm: BaseLLM, dictionary: CorrectionDictionary | None = None) -> None:
        self.llm = llm
        self.dictionary = dictionary or CorrectionDictionary()

    def correct(self, transcript: str) -> str:
        """Correct a transcript using dictionary + LLM."""
        if not transcript.strip():
            return transcript

        # Stage 1: Apply dictionary corrections
        after_dict = self.dictionary.apply(transcript)

        # Stage 2: LLM contextual correction
        dictionary_section = ""
        if len(self.dictionary) > 0:
            dictionary_section = f"自訂詞彙表（請確保使用以下正確詞彙）：\n{self.dictionary.to_prompt_hint()}"

        system_prompt = CORRECTION_SYSTEM_PROMPT.format(
            dictionary_section=dictionary_section
        ).strip()

        try:
            corrected = self.llm.chat(
                system_prompt=system_prompt,
                user_message=CORRECTION_USER_PROMPT.format(transcript=after_dict),
            )
            return corrected.strip()
        except Exception as e:
            raise CorrectionError(f"LLM correction failed: {e}") from e
