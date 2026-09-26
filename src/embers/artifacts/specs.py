"""Structured input of the file tools, with the limits of the phase 2 document."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Title = Annotated[str, Field(min_length=1, max_length=200)]
Text = Annotated[str, Field(min_length=1, max_length=4000)]

MAX_SECTIONS = 30
MAX_SLIDES = 20
MAX_BULLETS_PER_SLIDE = 6
MAX_MARKDOWN_CHARS = 100_000


class Table(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headers: Annotated[list[str], Field(min_length=1, max_length=12)]
    rows: Annotated[list[list[str]], Field(max_length=100)]


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: Title
    paragraphs: list[Text] = Field(default_factory=list)
    bullets: list[Text] = Field(default_factory=list)
    table: Table | None = None


class DocumentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    summary: Text | None = None
    sections: Annotated[list[Section], Field(min_length=1, max_length=MAX_SECTIONS)]


class Slide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    bullets: Annotated[list[Text], Field(max_length=MAX_BULLETS_PER_SLIDE)] = Field(
        default_factory=list
    )
    notes: Text | None = None


class PresentationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    subtitle: Title | None = None
    slides: Annotated[list[Slide], Field(min_length=1, max_length=MAX_SLIDES)]


class MarkdownSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    content: Annotated[str, Field(min_length=1, max_length=MAX_MARKDOWN_CHARS)]


ArtifactSpec = DocumentSpec | PresentationSpec | MarkdownSpec
