from datetime import datetime

from pydantic import BaseModel, Field


class JobDescriptionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    company: str = Field(min_length=2, max_length=255)
    description_text: str = Field(min_length=20)


class JobDescriptionOut(BaseModel):
    id: int
    title: str
    company: str
    description_text: str
    created_at: datetime

    model_config = {"from_attributes": True}
