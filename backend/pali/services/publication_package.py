"""Portable publication package validation, with no database or provider calls."""

import hashlib
import json
import re
from pathlib import Path

from ..schemas.published import PublishedTranslation
from .publication_import import Artifact


def validate_package(path: Path) -> Artifact:
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("schema_version") != "published_translation_v1":
        raise ValueError("Expected published_translation_v1 package")
    literature, summary, items = data["literature"], data["summary"], data["items"]
    allowed = {"id", "name", "pali_name", "pitaka", "nikaya", "display_metadata"}
    if set(literature) - allowed or not all(
        literature.get(k) for k in ("id", "name", "pali_name", "pitaka")
    ):
        raise ValueError("Invalid literature metadata")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", literature["id"]):
        raise ValueError("Invalid literature ID")
    if not items or summary["count"] != len(items):
        raise ValueError("Incomplete package")
    if not all(
        isinstance(summary.get(k), str) and summary[k]
        for k in ("source_commit", "model", "prompt_version")
    ):
        raise ValueError("Missing source/translation provenance")
    keys, orders, locations = set(), set(), {}
    for item in items:
        src, result, position = item["source"], item["result"], item["location"]
        key, order = src["stable_segment_key"], src["sort_order"]
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= 160
            or type(order) is not int
            or key in keys
            or order in orders
        ):
            raise ValueError("Invalid or duplicate source identity")
        if (
            src["literature_id"] != literature["id"]
            or src["source_commit"] != summary["source_commit"]
        ):
            raise ValueError("Mixed literature or source edition")
        original = src["original_text"]
        if not original.strip() or src["normalized_text"] != original:
            raise ValueError("Invalid original text")
        digest = hashlib.sha256(original.encode()).hexdigest()
        if (
            digest != src["source_text_hash"]
            or result["stable_segment_key"] != key
            or result["source_text_hash"] != digest
        ):
            raise ValueError("Source/translation hash mismatch")
        if result["status"] != "succeeded" or result["schema_valid"] is not True:
            raise ValueError("Unsuccessful translation")
        PublishedTranslation.model_validate(result["parsed_translation_json"])
        chapter, verse, kind = position["chapter"], position["verse"], position["kind"]
        if chapter is not None and (type(chapter) is not int or chapter < 1):
            raise ValueError("Chapter must be positive or null for appendix")
        if verse is not None and (type(verse) is not int or verse < 1):
            raise ValueError("Verse must be positive or null")
        if kind not in {"verse", "passage", "supplement", "appendix"} or (
            verse is not None and kind != "verse"
        ):
            raise ValueError("Invalid source kind")
        # Required for provenance and common chapter navigation, even if title is null.
        for field in ("source_path", "xml_node_path", "vagga_name"):
            if field not in src:
                raise ValueError(f"Missing source field: {field}")
        keys.add(key)
        orders.add(order)
        locations[key] = (chapter, verse, kind)
    if orders != set(range(1, len(items) + 1)):
        raise ValueError("Source order must cover 1..count without gaps")
    return Artifact(
        hashlib.sha256(raw).hexdigest(),
        summary,
        sorted(items, key=lambda x: x["source"]["sort_order"]),
        literature,
        locations,
    )
