# Security fixes — A1 & A2

**Date:** 2026-10-14
**Status:** Documented, pending implementation

---

## A1 — `/api/auth/seed` unprotected endpoint

### File & location

**File:** `crm/routes/auth.py`, lines 123–165

```python
@auth_bp.post('/seed')
def seed_production():          # ← NO @jwt_required() decorator
    """Seed initial users and workspaces."""
    User.query.delete()         # ← wipes ALL users
    Workspace.query.delete()    # ← wipes ALL workspaces
    db.session.commit()
    # ... reseeds with known credentials ...
```

### Problem

- **No authentication required.** Anyone can `POST /api/auth/seed` and destroy the database.
- The endpoint **deletes all users and workspaces** before reseeding.
- It reseeds with **known hardcoded passwords** (see A2).

### Fix

```python
@auth_bp.post('/seed')
@jwt_required()  # ← ADD THIS
def seed_production():
    # Verify superadmin
    from ..models.user import User
    uid = int(get_jwt_identity())
    user = User.query.filter_by(id=uid, is_deleted=False).first()
    if not user or user.role != 'superadmin':
        return jsonify({'error': 'Superadmin only'}), 403
    
    # ... rest of seeding logic ...
```

**Better:** Remove the endpoint entirely from production. Use a CLI command or migration for seeding instead of an HTTP endpoint.

### Test

`tests/test_security.py::test_seed_endpoint_requires_auth` — verifies 401 without token.

---

## A2 — Hardcoded credentials in source code

### Files & locations

#### `crm/__init__.py`

**Function: `_seed_default_users()`** (lines 38–65)
```python
user = User(email="olesya00007@yahoo.com", role="superadmin", workspace_id=ws.id)
user.set_password("Test12345!")  # ← HARDCODED
```

**Function: `_ensure_test_users()`** (lines 67–80)
```python
gmail_user = User(email="olesya00007@gmail.com", role="superadmin", ...)
gmail_user.set_password("Test1")  # ← HARDCODED
```

**Function: `_ensure_workspace_users()`** (lines 83–121)
```python
roster = [
    ("superadmin@lexflow.it", "lexflow0826", "superadmin", "lexflow", ["Test12345!"]),
    ("olesya00007@yahoo.com", "crm0826", "superadmin", "lexflow", ["Test12345!"]),
    ("alegra_007@proton.me", "avibe0826", "admin", "avibeagency", []),
    ("ms.okuneva@internet.ru", "pagliano0826", "admin", "pagliano", []),
    ("olesya00007@google.com", "Romanelli0826", "admin", "romanelli-studio", []),
    ("preview@romanelli.test", "Romanelli0826", "admin", "romanelli-studio", []),
    ("ferro@lexflow.it", "ferro0826", "admin", "tommasoferro", []),
]
```

**Romanelli sub-workspace users** (lines 127–128)
```python
subs = [
    ("romanelli-cl1", "Romanelli Client 1", "cl1@romanelli.test", "cl10826"),
    ("romanelli-cl2", "Romanelli Client 2", "cl2@romanelli.test", "cl20826"),
]
```

#### `crm/routes/auth.py` — `seed_production()` (lines 151–158)
```python
users_data = [
    ('olesya00007@yahoo.com', 'Test12345!', 'superadmin', workspaces[0].id),
    ('avibe@lexflow.test', 'Avibe@12345', 'admin', workspaces[0].id),
    ('pagliano@lexflow.test', 'Pag@12345', 'admin', workspaces[2].id),
    ('romanelli@lexflow.test', 'Rom@12345', 'admin', workspaces[3].id),
    ('audit@lexflow.test', 'Audit@12345', 'admin', workspaces[4].id),
    ('ferro@lexflow.test', 'Ferro@12345', 'admin', workspaces[5].id),
]
```

#### `crm/config.py` (lines 29–30)
```python
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
```
These fall back to a **committed dev key** if env vars are missing.

### Problem

- **13+ hardcoded passwords** in source code.
- Passwords are reset on every boot (until user changes them).
- Dev secret keys fall back to committed values.
- Anyone with repo access knows all production credentials.

### Fix approach

1. **Remove all hardcoded passwords.** Use environment variables:
   ```python
   # .env (gitignored)
   SEED_SUPERADMIN_PASSWORD=<generated>
   SEED_ADMIN_PASSWORD=<generated>
   ```

2. **Force password change on first login.** Add `must_change_password` flag to User model.

3. **Remove the seed endpoint from production.** Use Flask CLI:
   ```bash
   flask seed --superadmin-password="$(openssl rand -hex 16)"
   ```

4. **Fail fast on missing secrets:**
   ```python
   SECRET_KEY = os.environ["SECRET_KEY"]  # KeyError if missing — no fallback
   ```

5. **Add pre-commit hook** to detect hardcoded credentials:
   ```bash
   # .git/hooks/pre-commit
   git diff --cached | grep -i 'set_password\|password.*=.*["\']' && exit 1
   ```

### Test

`tests/test_security.py::test_no_hardcoded_passwords_in_source` — scans source for `set_password("...")` patterns.

---

## Implementation priority

| Order | Fix | Effort | Risk |
|---|---|---|---|
| 1 | A1: Add `@jwt_required()` + superadmin check to `/api/auth/seed` | 5 min | Low |
| 2 | A2: Remove dev key fallback in `config.py` | 5 min | Low |
| 3 | A2: Replace hardcoded passwords with env vars | 30 min | Medium |
| 4 | A2: Force password change on first login | 1h | Medium |
| 5 | A1: Remove seed endpoint entirely, use CLI | 30 min | Low |

**Total: ~2.5h for all fixes.**

---

## How to run tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v

# Expected: A1 test PASSES after fix, A2 test FAILS until passwords removed
```
