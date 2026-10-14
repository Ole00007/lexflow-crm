"""Security regression tests — A1 (unprotected seed) and A2 (hardcoded creds)."""


def test_seed_endpoint_requires_auth(client):
    """A1: /api/auth/seed must NOT be callable without a JWT."""
    resp = client.post("/api/auth/seed")
    assert resp.status_code == 401, (
        "CRITICAL: /api/auth/seed is unprotected — anyone can wipe the database"
    )


def test_seed_endpoint_requires_superadmin(client, superadmin_headers):
    """A1: Even with a token, seed should be restricted (not a normal user action)."""
    resp = client.post("/api/auth/seed", headers=superadmin_headers)
    # Should either be 403 (forbidden) or 404 (removed) — NOT 200/201
    assert resp.status_code in (403, 404), (
        f"CRITICAL: /api/auth/seed returned {resp.status_code} — should be restricted"
    )


def test_no_hardcoded_passwords_in_source():
    """A2: Verify no plaintext passwords in source code."""
    import re
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    # Files that should NOT contain hardcoded passwords
    check_files = [
        "crm/__init__.py",
        "crm/routes/auth.py",
    ]
    # Patterns that indicate hardcoded credentials
    patterns = [
        r'set_password\(["\'][^"\']+["\']\)',
        r'password\s*=\s*["\'][^"\']+["\']',
    ]
    violations = []
    for filepath in check_files:
        full_path = project_root / filepath
        if not full_path.exists():
            continue
        content = full_path.read_text()
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                violations.append(f"{filepath}: {len(matches)} hardcoded password(s)")

    # This test documents the current state — it will FAIL until A2 is fixed
    if violations:
        pytest.fail(
            "A2 VIOLATION — hardcoded passwords found:\n" + "\n".join(violations)
        )
