from google.genai import types
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    name: str = Field(
        description="The name of the user"
    )
    grade: str = Field(
        description="The grade of the user"
    )
    at_risk: bool = Field(
        description="Whether the user has an outstanding risk alert"
    )
    
class RiskProfile(BaseModel):
    status: str = Field(
        description="The status of the risk profile: NO_RISK, AT_RISK, IN_RISK"
    )
    active_category: str = Field(
        description="The active category of the risk profile: Suicidality, Mania, Psychosis, Substance use, Abuse and neglect"
    )
    triggering_statement: str = Field(
        description="The specific user message that initiated the most recent risk assessment pathway."
    )
    assessment_history: list[str] = Field(
        description="A log of the interaction steps taken during an assessment loop to provide context for the final decision."
    )