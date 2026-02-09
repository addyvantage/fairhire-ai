from datetime import datetime

from pydantic import BaseModel


class ResumeOut(BaseModel):
    id: int
    original_filename: str
    parsed_text: str
    created_at: datetime

    model_config = {"from_attributes": True}
