"""Provider/model catalog (loaded from YAML) and the demo tool catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from embers.contracts.common import ArtifactType, Provider


@dataclass(frozen=True)
class ModelEntry:
    id: str
    label: str


@dataclass(frozen=True)
class ProviderEntry:
    provider: Provider
    models: tuple[ModelEntry, ...]


class ProviderCatalog:
    """Providers and their models, in file order."""

    def __init__(self, entries: list[ProviderEntry]) -> None:
        self._entries = entries
        self._model_ids = {e.provider: {m.id for m in e.models} for e in entries}

    @classmethod
    def from_yaml(cls, path: Path) -> ProviderCatalog:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries = [
            ProviderEntry(
                provider=Provider(item["provider"]),
                models=tuple(ModelEntry(id=m["id"], label=m["label"]) for m in item["models"]),
            )
            for item in raw["providers"]
        ]
        return cls(entries)

    @property
    def entries(self) -> list[ProviderEntry]:
        return list(self._entries)

    def has_model(self, provider: Provider, model_id: str) -> bool:
        return model_id in self._model_ids.get(provider, set())


@dataclass(frozen=True)
class Tool:
    id: str
    description: str
    artifact_type: ArtifactType | None


# Registered only; execution arrives in phase 3. Descriptions are verbatim from the contract.
TOOL_CATALOG: tuple[Tool, ...] = (
    Tool("create_document", "Genera un informe en Word", ArtifactType.DOCX),
    Tool("create_presentation", "Genera una presentación", ArtifactType.PPTX),
    Tool("create_markdown", "Genera un documento de texto", ArtifactType.MD),
)

TOOL_IDS: frozenset[str] = frozenset(tool.id for tool in TOOL_CATALOG)

DEFAULT_TOOL_IDS: tuple[str, ...] = tuple(tool.id for tool in TOOL_CATALOG)
