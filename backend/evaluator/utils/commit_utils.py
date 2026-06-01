"""Commit data utility functions."""

from typing import Dict, Any, Optional


def _identity_values(identity: Any) -> list[str]:
    if isinstance(identity, str):
        return [identity]
    if not isinstance(identity, dict):
        return []

    values = []
    for key in ("login", "name", "email"):
        value = identity.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)
    return values


def _identity_emails(identity: Any) -> list[str]:
    if isinstance(identity, str):
        return [identity] if "@" in identity else []
    if not isinstance(identity, dict):
        return []

    email = identity.get("email")
    if isinstance(email, str) and email.strip():
        return [email]
    return []


def get_emails_from_commit(commit_data: Dict[str, Any]) -> list[str]:
    """Extract all author/committer emails from supported commit shapes."""
    emails = []
    seen = set()

    for identity in (commit_data.get("author"), commit_data.get("committer")):
        for email in _identity_emails(identity):
            key = email.lower().strip()
            if key and key not in seen:
                seen.add(key)
                emails.append(email.strip())

    nested = commit_data.get("commit", {})
    if isinstance(nested, dict):
        for identity in (nested.get("author"), nested.get("committer")):
            for email in _identity_emails(identity):
                key = email.lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    emails.append(email.strip())

    return emails


def is_email_identity(value: str) -> bool:
    return "@" in value.strip()


def get_author_from_commit(commit_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract author name from commit data, supporting both formats:
    1. GitHub API format: commit_data["commit"]["author"]["name"]
    2. Custom extraction format: commit_data["author"]
    """
    # Try custom extraction format first (more common in local data)
    if "author" in commit_data and isinstance(commit_data["author"], str):
        return commit_data["author"]

    # Try GitHub/Gitee API format
    if "commit" in commit_data:
        author = commit_data.get("commit", {}).get("author", {}).get("name")
        if author:
            return author

        # Some APIs may populate committer name but not author name
        committer = commit_data.get("commit", {}).get("committer", {}).get("name")
        if committer:
            return committer

    # Some providers use nested dicts for author/committer
    if "author" in commit_data and isinstance(commit_data["author"], dict):
        name = commit_data["author"].get("name")
        if name:
            return name

    if "committer" in commit_data and isinstance(commit_data["committer"], dict):
        name = commit_data["committer"].get("name")
        if name:
            return name

    return None


def is_commit_by_author_email(commit: Dict[str, Any], email: str) -> bool:
    normalized_email = email.lower().strip()
    if not normalized_email:
        return False
    return any(candidate.lower().strip() == normalized_email for candidate in get_emails_from_commit(commit))


def is_commit_by_author(commit: Dict[str, Any], username: str) -> bool:
    """Check if commit is by the specified author identity.

    Email identities are matched against commit email fields only. Name/login
    identities keep the legacy exact name/login matching for direct API callers.
    """
    normalized_username = username.lower().strip()
    if not normalized_username:
        return False

    if is_email_identity(normalized_username):
        return is_commit_by_author_email(commit, normalized_username)

    candidates = []

    # Custom extraction format and provider user objects.
    candidates.extend(_identity_values(commit.get("author")))
    candidates.extend(_identity_values(commit.get("committer")))

    # GitHub/Gitee commit metadata.
    commit_data = commit.get("commit", {})
    if isinstance(commit_data, dict):
        candidates.extend(_identity_values(commit_data.get("author")))
        candidates.extend(_identity_values(commit_data.get("committer")))

    for candidate in candidates:
        if candidate.lower().strip() == normalized_username:
            return True

    return False
