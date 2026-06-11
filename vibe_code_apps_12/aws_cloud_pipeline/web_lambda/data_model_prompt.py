"""LLM prompts for BRICK data model redesign (vibe12 / DynamoDB series)."""

from __future__ import annotations

import json
from typing import Any

DATA_MODEL_REDESIGN_CORE = """You are an HVAC ontology engineer for Vibe12 (AWS IoT + DynamoDB telemetry).

Task:
1) Wait until I upload BOTH:
   - data_model_export.json from GET /api/data-model/{site}/{building}/export
   - Open-FDD Arrow FDD rule definitions (JSON list with id, code, config, optional brick_scope)

2) Do not produce final output until both are present.

When files are available:
- Analyze the model JSON and FDD rules together.
- Redefine/enrich the model to align with BRICK semantics for HVAC.
- Add/normalize:
  - BRICK classes for sites, equipment, and points (equipment_type, brick_type)
  - equipment/point typing consistency
  - relationship edges in "relationships" array:
    - feeds / isFedBy / hasPart / isPartOf (predicate names)
  - required supporting relationships for AHU/VAV/plant flows
- Preserve existing IDs when possible.
- Do not invent sensors unless clearly justified from registry/telemetry context.
- CRITICAL: preserve metadata.external_ref (DynamoDB series_id) for every point with telemetry.
- external_id = operator tag (SAT, ZAT); metadata.external_ref = full series_id like site#building#system#point.

Import requirements (import_ready_json):
- Non-empty "sites" array; every point.site_id must exist in sites[].id
- Every points[].equipment_id must exist in equipment[].id (or set equipment_id null)
- Set fdd_input to Bake-a-Py rule input key when it differs from brick_type
- "import_ready_json" must contain ONLY keys: sites, equipment, points, relationships (optional)

Rule handling:
- Check whether Bake-a-Py rules with brick_scope match available equipment/point classes.
- Report missing mappings in rule_compatibility_notes.
- Suggest brick_scope blocks: equipment_classes + point_classes for class-scoped rules."""

DATA_MODEL_REDESIGN_OUTPUT_API = """

OUTPUT MODE — machine consumer (POST /api/data-model/.../assistant/openclaw):
- Return ONLY one JSON object. No markdown fences, no prose outside JSON.
- Required keys: validation_notes, relationship_summary, rule_compatibility_notes, import_ready_json
- import_ready_json: { sites, equipment, points, relationships? }
- Optional: proposed_rule_json (array of Bake-a-Py rule objects)"""

DATA_MODEL_REDESIGN_OUTPUT_HUMAN = """

OUTPUT MODE — human (Data Model tab "Copy LLM Prompt"):
- Preferred: === FILE: vibe12_data_model_import_ready.json === with valid JSON only
- Also provide validation_notes, relationship_summary, rule_compatibility_notes
- JSON must validate against import shape with preserved external_ref series_ids"""

SYSTEM_PROMPT = DATA_MODEL_REDESIGN_CORE + DATA_MODEL_REDESIGN_OUTPUT_API


def get_data_model_redesign_prompt(human_mode: bool = True) -> str:
    return DATA_MODEL_REDESIGN_CORE + (
        DATA_MODEL_REDESIGN_OUTPUT_HUMAN if human_mode else DATA_MODEL_REDESIGN_OUTPUT_API
    )


def build_openclaw_user_message(model: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    parts = [
        "Current GET /api/data-model/export JSON:",
        json.dumps(model, indent=2),
        "",
        "Bake-a-Py FDD rules (enabled and draft):",
        json.dumps(rules, indent=2),
        "",
        "Both artifacts present. Respond with ONE JSON object per system instructions.",
    ]
    return "\n".join(parts)
