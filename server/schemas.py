from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Criterion(BaseModel):
    id: str = Field(max_length=30)
    text: str = Field(min_length=3, max_length=240)

class Plan(BaseModel):
    question: str = Field(min_length=5, max_length=1500)
    queries: list[str] = Field(min_length=1, max_length=3)
    criteria: list[Criterion] = Field(default_factory=list, max_length=5)
    year_from: int | None = Field(default=None, ge=1800, le=2100)
    year_to: int | None = Field(default=None, ge=1800, le=2100)
    open_access: bool = False
    mode: Literal['fast', 'diligent'] = 'diligent'
    planner: str = 'rules'

    @model_validator(mode='after')
    def validate_plan(self):
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError('Start year must be before end year')
        if any(not q.strip() or len(q) > 300 for q in self.queries):
            raise ValueError('Search queries must be between 1 and 300 characters')
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError('Criteria need unique IDs')
        return self

class PlanRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1500)

class SearchRequest(BaseModel):
    plan: Plan
    rerank: bool = True
    repair: bool = True

class Feedback(BaseModel):
    paper_id: str = Field(max_length=100)
    relevance: Literal[0, 1, 2]
    note: str = Field(default='', max_length=1000)
