from pydantic import BaseModel


class ActionPlan(BaseModel):
    user_action: str
    user_intent: str
    previous_action_outcome: str
    character_action: str
    reasoning: str
    state_update: dict[str, str]
    followup_action: str
