from urllib.parse import quote
from typing import Sequence


def generate_teams_chat_url(requester_upn: str, request_id: int, host_list: Sequence[str]) -> str:
    """
    Generates a 1-click Microsoft Teams Chat Deep Link URL.
    Spec: https://teams.microsoft.com/l/chat/0/0?users=<upn>&topicName=Access%20Request%20%23<id>&message=Regarding%20your%20access%20request%20for%20<hosts>
    """
    if not requester_upn:
        raise ValueError("Requester UPN cannot be empty.")

    hosts_str = ", ".join(host_list) if host_list else "no hosts specified"
    topic_name = f"Access Request #{request_id}"
    message = f"Regarding your access request for {hosts_str}"

    encoded_upn = quote(requester_upn)
    encoded_topic = quote(topic_name)
    encoded_msg = quote(message)

    return f"https://teams.microsoft.com/l/chat/0/0?users={encoded_upn}&topicName={encoded_topic}&message={encoded_msg}"
