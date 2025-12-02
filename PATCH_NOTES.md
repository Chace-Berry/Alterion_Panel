# Patch Notes – December 2, 2025

## Backend
- Refactored `create_admin_user.py` to save PGAdmin credentials.
- Secret manager fixes: resolved issues with database access and credential storage.
- Added multi-database structure for env variables with 3 layers of encryption

## Docker Compose
- Updated `docker-compose.yml`:
  - Changed `env_file` for `backend` and `celery` services to reference `../backend/.env` (the correct backend directory).
  - Ensured all services use consistent environment and volume paths.
  - Confirmed removal of outdated certbot logic and unnecessary webroot references.
  - Added `certs` named volume for certificate management.
  - Verified static and media file volumes are mapped correctly for backend and nginx services.

## Installer
- Fixed installer logic to correctly detect and set up backend.
- Improved installer reliability for environment setup and file placement.
- Enhanced installer background tasks to support new multi-database structure and secret manager features.

## File System & Directory Structure
- Confirmed `.env` and certs are now reliably placed and referenced in the backend directory.
- Validated backend and node_agent directories are at the same level for consistent environment setup.

## General
- Verified no errors in updated Python and Compose files.
- Confirmed all environment, credential, and certificate logic is robust and easy to maintain.
- Improved reliability and clarity of environment setup for local and Docker deployments.
