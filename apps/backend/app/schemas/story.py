from pydantic import BaseModel
from typing import Optional


class StoryCard(BaseModel):
    id: str
    title: str
    description: str
    theme: str
    image: str


class StoryDetail(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    theme: str
    image: str
