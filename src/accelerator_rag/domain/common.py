"""Shared validation primitives, independent of any capability Provider."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr

Nonempty = Annotated[StrictStr, Field(min_length=1, pattern=r"\S")]


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
