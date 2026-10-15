from typing import Optional, Any
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from control_plane.apps.authentication.utils import sanitize_posix_username

User = get_user_model()


class EntraIDOIDCBackend(ModelBackend):
    """
    Custom authentication backend processing Microsoft Entra ID (Azure AD) OIDC claims.
    """

    def authenticate_oidc_claims(self, claims: dict[str, Any]) -> Optional[User]:
        entra_oid = claims.get("oid")
        upn = claims.get("upn") or claims.get("preferred_username") or claims.get("email")

        if not entra_oid or not upn:
            return None

        roles = claims.get("roles", [])
        is_admin = "Access.Admin" in roles

        posix_base = sanitize_posix_username(upn)

        # Retrieve existing user or create new
        user, created = User.objects.get_or_create(
            entra_oid=entra_oid,
            defaults={
                "username": upn,
                "upn": upn,
                "email": upn,
                "posix_username": posix_base,
            },
        )

        # Update claims and role permissions
        changed = False
        if user.upn != upn:
            user.upn = upn
            user.email = upn
            changed = True

        if is_admin:
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                changed = True
        else:
            if user.is_staff or user.is_superuser:
                user.is_staff = False
                user.is_superuser = False
                changed = True

        if not user.posix_username:
            user.posix_username = posix_base
            changed = True

        if changed or created:
            user.save()

        return user
