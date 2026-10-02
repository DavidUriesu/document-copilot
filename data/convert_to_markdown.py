from __future__ import annotations

import json
from pathlib import Path

from docling.document_converter import DocumentConverter

DATA_DIR = Path(__file__).resolve().parent
INPUT_DIR = DATA_DIR / "downloads"
OUTPUT_DIR = DATA_DIR / "markdown"
HTML_SUFFIXES = {".htm", ".html"}


def html_files() -> list[Path]:
    return sorted(
        path
        for path in INPUT_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in HTML_SUFFIXES
    )


def markdown_path(source_path: Path) -> Path:
    relative_path = source_path.relative_to(INPUT_DIR)
    return (OUTPUT_DIR / relative_path).with_suffix(".md")


def convert_documents(source_paths: list[Path]) -> None:
    converter = DocumentConverter()

    for index, source_path in enumerate(source_paths, start=1):
        destination = markdown_path(source_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{index}/{len(source_paths)}] {source_path.relative_to(INPUT_DIR)}")
        result = converter.convert(source_path)
        result.document.save_as_markdown(destination)


def write_markdown_manifest() -> None:
    source_manifest = INPUT_DIR / "manifest.json"
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))

    for filing in manifest["filings"]:
        source_path = Path(filing["local_path"].replace("\\", "/"))
        filing["local_path"] = source_path.with_suffix(".md").as_posix()

    destination_manifest = OUTPUT_DIR / "manifest.json"
    destination_manifest.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    source_paths = html_files()
    if not source_paths:
        raise RuntimeError(f"No .htm or .html files found in {INPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_documents(source_paths)
    write_markdown_manifest()
    print(f"Converted {len(source_paths)} document(s) to {OUTPUT_DIR}")
    print(f"Manifest: {OUTPUT_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
