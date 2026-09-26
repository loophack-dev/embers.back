"""System prompt of an agent for a task, in the four blocks of the phase 2 document."""

from __future__ import annotations

from typing import Any

WORK_RULES = """Working rules:
- Answer in the language of the instruction.
- If information that is essential to do the task well is missing, use the ask_user tool once, \
with a concrete question and, when it helps, options. Do not ask about anything you can decide \
with a reasonable assumption.
- If the task asks for a document, a presentation or a file, use the matching tool.
- Finish with a brief summary of what you did."""

EXPECTED_OUTPUT_NAMES = {
    "docx": "a Word document (create_document)",
    "pptx": "a PowerPoint presentation (create_presentation)",
    "md": "a Markdown file (create_markdown)",
}


def build_system_prompt(snapshot: dict[str, Any], expected_output: str | None) -> str:
    identity: dict[str, Any] = snapshot.get("identity") or {}
    identity_lines = [
        f"{label}: {value}"
        for label, value in (
            ("Name", snapshot.get("name")),
            ("Role", identity.get("role")),
            ("Personality", identity.get("persona")),
            ("Tone", identity.get("tone")),
        )
        if value
    ]
    blocks = ["You are an agent in the Embers office.\n" + "\n".join(identity_lines)]

    instructions = snapshot.get("instructions")
    if instructions:
        blocks.append(str(instructions))

    blocks.append(WORK_RULES)

    if expected_output:
        name = EXPECTED_OUTPUT_NAMES.get(expected_output, expected_output)
        blocks.append(f"Expected output: you must deliver {name}.")

    return "\n\n".join(blocks)
