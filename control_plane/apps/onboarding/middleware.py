from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from control_plane.apps.onboarding.models import UserSSHPublicKey


class EnforceSSHKeyMiddleware:
    """
    Middleware ensuring that any authenticated user lacking an active registered SSH key
    is redirected to the SSH public key onboarding page.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            onboarding_url = reverse("register_ssh_key") if _has_url("register_ssh_key") else "/onboarding/ssh-key/"
            exempt_paths = [
                onboarding_url,
                "/admin/",
                "/accounts/logout/",
                "/logout/",
            ]
            if not any(request.path.startswith(path) for path in exempt_paths):
                has_active_key = UserSSHPublicKey.objects.filter(
                    user=request.user, is_active=True
                ).exists()
                if not has_active_key:
                    return redirect(f"{onboarding_url}?next={request.path}")

        return self.get_response(request)


def _has_url(name: str) -> bool:
    from django.urls import NoReverseMatch
    try:
        reverse(name)
        return True
    except NoReverseMatch:
        return False
