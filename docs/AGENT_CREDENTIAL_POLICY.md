# Agent Credential Policy - Carby Studio

**Effective:** 2026-03-19  
**Enforcement:** MANDATORY for all agents

---

## Policy

All credentials for Carby Studio projects **MUST** be stored in Bitwarden Organization. GPG-encrypted local storage is **DEPRECATED** and will be removed.

---

## For Agents (You)

### When Handling Credentials

1. **ALWAYS use Bitwarden DAO**
   ```python
   from skills.carby-studio.lib.bitwarden_dao import BitwardenDAO
   
   dao = BitwardenDAO()
   success, credential = dao.get(project, type, name)
   ```

2. **NEVER read GPG files directly**
   - Do not use `gpg --decrypt` on credential files
   - Do not read `~/.openclaw/secrets/projects/*/secrets.db.gpg`
   - Do not fall back to GPG storage

3. **Session Management**
   - Use `SessionManager` to handle BW_SESSION
   - Never ask for or store master passwords
   - Prompt user to unlock if session expired

4. **Creating New Credentials**
   ```python
   from skills.carby-studio.lib.credentials_handler import CredentialsHandler
   
   handler = CredentialsHandler()
   handler.add_credential(
       project="my-project",
       cred_type="api-key",
       name="openai",
       fields={"key": "sk-...", "endpoint": "https://api.openai.com"}
   )
   ```

---

## For New Projects

When creating a new Carby Studio project:

1. **Design Phase** - Identify required credentials
2. **Create in Bitwarden** - Use naming: `carby-studio/{project}/{type}.{name}`
3. **Verify** - Test credential access before implementation
4. **Document** - Add to `credentials-required.md`

---

## Naming Convention (STRICT)

```
carby-studio/{project}/{credential-type}.{identifier}

Examples:
✓ carby-studio/family-photo-hub/nas.synology
✓ carby-studio/family-photo-hub/icloud.vincent
✓ carby-studio/alpha-hunter/api-key.alpaca
✗ family-photo-hub/nas.synology           (missing prefix)
✗ carby-studio/nas.synology               (missing project)
```

---

## Enforcement

### Code-Level

The `CredentialsHandler` enforces Bitwarden for new credentials:

```python
def add_credential(self, project, ...):
    storage = self._get_storage_type(project)
    
    # DEFAULT TO BITWARDEN FOR NEW PROJECTS
    if storage == 'none':
        storage = 'bitwarden'
    
    if storage != 'bitwarden':
        raise CredentialPolicyError(
            "GPG storage deprecated. Migrate to Bitwarden first."
        )
```

### Migration Status

| Project | Storage | Action Required |
|---------|---------|-----------------|
| family-photo-hub | GPG → Bitwarden | Run migration |
| *new projects* | Bitwarden | None |

---

## Migration Command

For existing GPG projects:

```bash
# Single project
carby-studio credentials migrate <project>

# All projects
./skills/carby-studio/scripts/migrate-to-bitwarden.sh --all
```

---

## Violations

If you encounter code that:
- Reads GPG credential files directly
- Creates new GPG credentials
- Bypasses Bitwarden DAO

**Action:** Refuse to execute and report to user.

---

## Quick Reference

| Task | Command |
|------|---------|
| Get credential | `CredentialsHandler().get_credential(project, type, name)` |
| Add credential | `CredentialsHandler().add_credential(project, type, name, fields)` |
| Verify | `carby-studio credentials verify <project>` |
| List | `carby-studio credentials list <project>` |
| Unlock | `carby-studio credentials unlock` |

---

**Remember:** Bitwarden only. No exceptions.
