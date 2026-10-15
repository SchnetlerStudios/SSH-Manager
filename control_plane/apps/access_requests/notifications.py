from typing import Any
from control_plane.apps.access_requests.models import AccessRequest


def build_adaptive_card_payload(request_obj: AccessRequest, hosts: list[str]) -> dict[str, Any]:
    hosts_text = ", ".join(hosts) if hosts else "None"
    upn = request_obj.requester.upn or request_obj.requester.username

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "size": "Medium",
                            "weight": "Bolder",
                            "text": f"JIT Access Request #{request_obj.id}",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Requester:", "value": upn},
                                {"title": "Access Level:", "value": request_obj.access_level},
                                {"title": "Target Hosts:", "value": hosts_text},
                                {"title": "Start Time:", "value": request_obj.start_datetime.isoformat()},
                                {"title": "End Time:", "value": request_obj.end_datetime.isoformat()},
                                {"title": "Motivation:", "value": request_obj.motivation},
                            ],
                        },
                    ],
                },
            }
        ],
    }
