import re


def sanitize_posix_username(raw_username: str) -> str:
    """
    Sanitizes raw username (such as email/UPN or display name) to adhere to POSIX regex `^[a-z_][a-z0-9_-]{1,31}$`.
    """
    if not raw_username or not isinstance(raw_username, str):
        raise ValueError("Username must be a non-empty string.")

    # Lowercase and split email or domain suffix if present
    name = raw_username.lower().split("@")[0].split("\\")[-1]

    # Replace invalid chars with underscores
    sanitized = re.sub(r"[^a-z0-9_-]", "_", name)

    # Ensure leading char matches ^[a-z_]
    if not sanitized or not re.match(r"^[a-z_]", sanitized):
        sanitized = f"u_{sanitized}"

    # Truncate to maximum 32 characters
    sanitized = sanitized[:32]

    # Enforce minimum length (at least 2 chars matching pattern)
    if len(sanitized) < 2:
        sanitized = f"{sanitized}_u"

    if not re.match(r"^[a-z_][a-z0-9_-]{1,31}$", sanitized):
        raise ValueError(f"Failed to produce valid POSIX username from '{raw_username}'")

    return sanitized
