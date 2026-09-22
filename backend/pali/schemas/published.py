"""Public translation fields; provider responses and logs never enter the API."""

from pydantic import BaseModel, ConfigDict, Field


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pali: str
    ko: str
    gloss: str
    note: str


class PublishedTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    natural_ko: str = Field(min_length=1)
    literal_ko: str = Field(min_length=1)
    terms: list[Term]
    grammar_notes: list[str]
    doctrinal_notes: list[str]
    uncertainties: list[str]
    quality_flags: list[str]
