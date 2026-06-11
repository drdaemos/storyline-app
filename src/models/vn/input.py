"""The generation input object: structured + free-form data, per the system design."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VNInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VNCharacter(VNInputModel):
    name: str = Field(..., min_length=1)
    background: str = ""
    appearance: str = ""
    protagonist: bool = False


class VNSetting(VNInputModel):
    world_description: str = ""
    # Structured anchor shape is undefined in the spec; minimal placeholder: named places.
    anchors: list[str] = Field(default_factory=list)


class PremiseScope(VNInputModel):
    """Structured size knobs — hard-gateable at generation time. [D8]"""

    target_scenes: int = Field(..., ge=1)
    target_endings: int = Field(..., ge=1)


class Premise(VNInputModel):
    synopsis: str = Field(..., min_length=1)
    protagonist_goal: str = Field(..., min_length=1)
    scope: PremiseScope


class VNInput(VNInputModel):
    characters: list[VNCharacter] = Field(..., min_length=1)
    setting: VNSetting = Field(default_factory=VNSetting)
    rules: str = ""
    premise: Premise

    @model_validator(mode="after")
    def exactly_one_protagonist(self) -> "VNInput":
        count = sum(1 for c in self.characters if c.protagonist)
        if count != 1:
            raise ValueError(f"exactly one character must carry the protagonist flag, got {count}")
        return self
