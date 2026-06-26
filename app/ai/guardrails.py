import re
import logging
from typing import List, Set, Optional

logger = logging.getLogger(__name__)

def validate_asset_references(
    text: str,
    known_ids: Set[str],
    known_values: Set[str]
) -> dict:
    """
    Scans LLM output for asset ID/value references and flags any
    that don't exist in the database.
    """
    # Extract anything that looks like an asset ID (e.g., "a1", "a23")
    mentioned_ids = set(re.findall(r'\b(a\d+)\b', text))
    # Extract backtick-quoted values (common LLM pattern)
    mentioned_values = set(re.findall(r'`([^`]+)`', text))
    
    hallucinated_ids = mentioned_ids - known_ids
    hallucinated_values = mentioned_values - known_values - known_ids
    
    return {
        "is_grounded": len(hallucinated_ids) == 0 and len(hallucinated_values) == 0,
        "hallucinated_ids": list(hallucinated_ids),
        "hallucinated_values": list(hallucinated_values),
    }

def sanitize_report(
    report_text: str,
    known_ids: Set[str],
    known_values: Set[str]
) -> str:
    """
    Post-processes a generated report. Appends a disclaimer if
    hallucinated references are detected.
    """
    validation = validate_asset_references(report_text, known_ids, known_values)
    
    if not validation["is_grounded"]:
        logger.warning(f"Hallucination detected: {validation}")
        disclaimer = (
            "\n\n---\n"
            "> ⚠️ **Grounding Warning**: This report may reference assets "
            "not present in the database. The following references could not "
            f"be verified: {validation['hallucinated_ids'] + validation['hallucinated_values']}"
        )
        report_text += disclaimer
    
    return report_text
