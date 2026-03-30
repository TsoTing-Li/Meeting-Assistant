import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.exceptions import DocumentError

SUPPORTED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
SUPPORTED_DOC_TYPES = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv"}


class AssetType(str, enum.Enum):
    IMAGE = "image"
    DOCUMENT = "document"
    OTHER = "other"


@dataclass
class Asset:
    """An attachment to be embedded in or linked from the generated document."""
    name: str                        # Display name
    path: str                        # Storage key or local path
    asset_type: AssetType = AssetType.OTHER
    description: str = ""            # Optional caption/description
    url: str = ""                    # Presigned URL (filled at render time)

    @classmethod
    def from_path(cls, path: str, description: str = "") -> "Asset":
        suffix = Path(path).suffix.lower()
        if suffix in SUPPORTED_IMAGE_TYPES:
            asset_type = AssetType.IMAGE
        elif suffix in SUPPORTED_DOC_TYPES:
            asset_type = AssetType.DOCUMENT
        else:
            asset_type = AssetType.OTHER
        return cls(
            name=Path(path).name,
            path=path,
            asset_type=asset_type,
            description=description,
        )


class DocumentGenerator:
    """
    Generates Markdown documents from summaries and attached assets.

    Images are embedded inline; documents are listed as links.
    """

    def generate(
        self,
        title: str,
        content: str,
        assets: list[Asset] | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Generate a Markdown document string.

        Args:
            title: Document title (H1 heading)
            content: Main content (meeting summary or aggregation report)
            assets: List of attachments to embed/link
            metadata: Optional key-value pairs for the front matter section
        """
        parts: list[str] = []

        # Frontmatter metadata
        if metadata:
            parts.append("---")
            for key, value in metadata.items():
                parts.append(f"{key}: {value}")
            parts.append("---")
            parts.append("")

        # Title
        parts.append(f"# {title}")
        parts.append("")

        # Generation timestamp
        parts.append(f"*生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        parts.append("")

        # Main content
        parts.append(content)

        # Assets section
        if assets:
            images = [a for a in assets if a.asset_type == AssetType.IMAGE]
            docs = [a for a in assets if a.asset_type != AssetType.IMAGE]

            if images:
                parts.append("")
                parts.append("---")
                parts.append("")
                parts.append("## 附圖")
                for asset in images:
                    url = asset.url or asset.path
                    caption = asset.description or asset.name
                    parts.append(f"![{caption}]({url})")
                    if asset.description:
                        parts.append(f"*{asset.description}*")
                    parts.append("")

            if docs:
                parts.append("")
                parts.append("## 附件")
                for asset in docs:
                    url = asset.url or asset.path
                    label = f"{asset.name}"
                    if asset.description:
                        label += f" - {asset.description}"
                    parts.append(f"- [{label}]({url})")

        return "\n".join(parts)

    def save(self, content: str, output_path: str | Path) -> None:
        """Save generated Markdown to a file."""
        path = Path(output_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as e:
            raise DocumentError(f"Failed to save document to '{output_path}': {e}") from e
