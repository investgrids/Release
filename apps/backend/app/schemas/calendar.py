from pydantic import BaseModel

class CalendarEvent(BaseModel):
    id: str
    category: str
    title: str
    date: str
    description: str
