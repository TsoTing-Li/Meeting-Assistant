import pytest
from pathlib import Path
from core.document.generator import DocumentGenerator, Asset, AssetType
from core.exceptions import DocumentError


@pytest.fixture
def generator():
    return DocumentGenerator()


@pytest.fixture
def sample_assets():
    return [
        Asset(name="architecture.png", path="images/architecture.png", asset_type=AssetType.IMAGE,
              description="系統架構圖", url="http://storage/images/architecture.png"),
        Asset(name="report.pdf", path="docs/report.pdf", asset_type=AssetType.DOCUMENT,
              description="詳細報告"),
    ]


def test_generate_returns_string(generator):
    result = generator.generate("Test Title", "Test content")
    assert isinstance(result, str)
    assert "# Test Title" in result


def test_generate_includes_title(generator):
    result = generator.generate("會議標題", "內容")
    assert "# 會議標題" in result


def test_generate_includes_content(generator):
    result = generator.generate("Title", "## 決議事項\n- 採用方案A")
    assert "## 決議事項" in result
    assert "採用方案A" in result


def test_generate_with_images(generator, sample_assets):
    result = generator.generate("Title", "content", assets=sample_assets)
    assert "## 附圖" in result
    assert "architecture.png" in result or "系統架構圖" in result
    assert "http://storage/images/architecture.png" in result


def test_generate_with_documents(generator, sample_assets):
    result = generator.generate("Title", "content", assets=sample_assets)
    assert "## 附件" in result
    assert "report.pdf" in result


def test_generate_without_assets(generator):
    result = generator.generate("Title", "content", assets=None)
    assert "## 附圖" not in result
    assert "## 附件" not in result


def test_generate_with_empty_assets(generator):
    result = generator.generate("Title", "content", assets=[])
    assert "## 附圖" not in result


def test_generate_with_metadata(generator):
    metadata = {"date": "2026-03-20", "author": "Alice"}
    result = generator.generate("Title", "content", metadata=metadata)
    assert "---" in result
    assert "date: 2026-03-20" in result
    assert "author: Alice" in result


def test_generate_includes_timestamp(generator):
    result = generator.generate("Title", "content")
    assert "生成時間" in result


def test_asset_from_path_image():
    asset = Asset.from_path("images/photo.png", description="照片")
    assert asset.asset_type == AssetType.IMAGE
    assert asset.name == "photo.png"
    assert asset.description == "照片"


def test_asset_from_path_document():
    asset = Asset.from_path("docs/report.pdf")
    assert asset.asset_type == AssetType.DOCUMENT


def test_asset_from_path_other():
    asset = Asset.from_path("data/output.bin")
    assert asset.asset_type == AssetType.OTHER


def test_save_writes_file(generator, tmp_path):
    content = "# 測試文件\n內容"
    output = tmp_path / "output.md"
    generator.save(content, output)
    assert output.exists()
    assert output.read_text(encoding="utf-8") == content


def test_save_creates_parent_dirs(generator, tmp_path):
    content = "# Test"
    output = tmp_path / "nested" / "deep" / "output.md"
    generator.save(content, output)
    assert output.exists()
