from pydantic import BaseModel

class StoryCard(BaseModel):
    id: str
    title: str
    description: str
    theme: str
    image: str
