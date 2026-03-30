import json
import pytest
from datetime import datetime

from core.models.meeting import Meeting, MeetingType
from core.models.task import Task, TaskType, TaskStatus
from core.models.transcript import Transcript
from core.models.summary import Summary
from core.models.prompt import SystemPrompt, PromptScene
from core.correction.dictionary import CorrectionDictionary


def test_meeting_participants_property():
    m = Meeting()
    m.participants = ["Alice", "Bob"]
    assert m.participants == ["Alice", "Bob"]


def test_meeting_topics_property():
    m = Meeting()
    m.topics = ["Topic A", "Topic B"]
    assert m.topics == ["Topic A", "Topic B"]


def test_meeting_empty_participants():
    m = Meeting()
    assert m.participants == []


def test_meeting_type_enum():
    assert MeetingType.WEEKLY_STANDUP == "weekly_standup"
    assert MeetingType.GENERAL == "general"


def test_task_type_enum():
    assert TaskType.STT == "stt"
    assert TaskType.CORRECTION == "correction"
    assert TaskType.SUMMARY == "summary"


def test_task_status_enum():
    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.DONE == "done"
    assert TaskStatus.FAILED == "failed"
    assert TaskStatus.CANCELLED == "cancelled"


def test_summary_asset_refs_property():
    s = Summary()
    s.asset_refs = ["path/to/image.png", "path/to/doc.pdf"]
    assert s.asset_refs == ["path/to/image.png", "path/to/doc.pdf"]


def test_summary_empty_asset_refs():
    s = Summary()
    assert s.asset_refs == []


def test_summary_source_meeting_ids():
    s = Summary()
    ids = ["a1b2c3d4-0000-0000-0000-000000000001", "a1b2c3d4-0000-0000-0000-000000000002"]
    s.source_meeting_ids = ids
    assert s.source_meeting_ids == ids


def test_system_prompt_required_fields():
    p = SystemPrompt()
    assert "meeting_type" in p.required_fields
    assert "date" in p.required_fields
    assert "participants" in p.required_fields
    assert "topics" in p.required_fields


def test_system_prompt_custom_required_fields():
    p = SystemPrompt()
    p.required_fields = ["meeting_type", "date"]
    assert p.required_fields == ["meeting_type", "date"]


def test_prompt_scene_enum():
    assert PromptScene.WEEKLY_STANDUP == "weekly_standup"
    assert PromptScene.CUSTOM == "custom"
