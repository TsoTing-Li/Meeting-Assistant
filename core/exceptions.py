class MeetingAssistantError(Exception):
    """Base exception for Meeting Assistant"""


class STTError(MeetingAssistantError):
    """Speech-to-text conversion failed"""


class CorrectionError(MeetingAssistantError):
    """Transcript correction failed"""


class SummaryError(MeetingAssistantError):
    """Summary generation failed"""


class AggregationError(MeetingAssistantError):
    """Multi-meeting aggregation failed"""


class StorageError(MeetingAssistantError):
    """File storage operation failed"""


class LLMError(MeetingAssistantError):
    """LLM call failed"""


class DocumentError(MeetingAssistantError):
    """Document generation failed"""


class PromptValidationError(MeetingAssistantError):
    """System prompt validation failed (missing required fields)"""
