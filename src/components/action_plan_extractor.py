import json
from typing import Any

from haystack import component


@component
class ActionPlanExtractor:
    """
    A component extracting a dictionary from the JSON-formatted reply.
    """

    @component.output_types(parsed_action_plan=dict[str, Any])
    def run(self, replies: list[str]) -> dict[str, Any]:
        return {"parsed_action_plan": json.loads(replies[0])}
