# Python FastAPI Project Structure

## Directory Layout

```
{{PROJECT_NAME}}/
├── pyproject.toml          # Dependencies and tool configuration
├── README.md               # Project documentation
├── Dockerfile              # Production container image
├── src/
│   ├── __init__.py         # Package marker (version info)
│   ├── main.py             # FastAPI application entry point
│   ├── config.py           # Pydantic settings (env vars)
│   ├── models/             # SQLAlchemy database models
│   │   └── __init__.py
│   ├── routers/            # FastAPI route modules
│   │   └── __init__.py
│   └── services/           # Business logic layer
│       └── __init__.py
└── tests/
    ├── __init__.py
    ├── conftest.py         # pytest fixtures
    └── test_main.py        # Main application tests
```

## Conventions

### Code Organization
- **src/**: All application code
- **models/**: Database models (SQLAlchemy 2.0 style with type hints)
- **routers/**: API route handlers (FastAPI routers)
- **services/**: Business logic (pure functions when possible)
- **tests/**: Mirror src/ structure

### Key Patterns

1. **Configuration via Environment**
   ```python
   from config import settings
   database_url = settings.database_url
   ```

2. **Dependency Injection**
   ```python
   from fastapi import Depends
   from services.db import get_db

   @app.get("/users")
   def list_users(db: Session = Depends(get_db)):
       ...
   ```

3. **Pydantic Models**
   - Use for request/response validation
   - Separate from SQLAlchemy models

4. **Error Handling**
   - Use FastAPI HTTPException for HTTP errors
   - Use custom exceptions for business logic
   - Centralize error handlers in main.py

## Customization Points

### 1. Add Database Models
**File:** `src/models/`  
**Action:** Create SQLAlchemy models
```python
# src/models/user.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
```

### 2. Add API Routes
**File:** `src/routers/`  
**Action:** Create FastAPI routers
```python
# src/routers/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
def list_users():
    return {"users": []}
```

**Then register in main.py:**
```python
from routers import users
app.include_router(users.router)
```

### 3. Add Business Logic
**File:** `src/services/`  
**Action:** Implement services
```python
# src/services/user_service.py
def create_user(email: str) -> dict:
    # Business logic here
    return {"id": 1, "email": email}
```

### 4. Add Dependencies
**File:** `pyproject.toml`  
**Action:** Add under `[project.dependencies]`
```toml
[project.dependencies]
fastapi = ">=0.104.0"
# Add your deps here
redis = ">=5.0.0"
```

## Preserved Patterns (Don't Remove)

These are critical for production:

1. **Health Check Endpoint** (`/health`)
   - Required for load balancers
   - Used by Docker HEALTHCHECK

2. **Non-root User in Dockerfile**
   - Security best practice
   - Prevents container escape attacks

3. **Multi-stage Docker Build**
   - Smaller production images
   - No build tools in final image

4. **Pydantic Settings (config.py)**
   - Environment-based configuration
   - Type-safe settings access

## Escape Hatches

You can deviate when needed:

- **Replace entire src/** if you prefer different architecture
- **Change Dockerfile base image** (e.g., Alpine instead of slim)
- **Switch to async SQLAlchemy** if you need async
- **Add Makefile** for complex build steps
- **Use poetry instead of pip** (update pyproject.toml)

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test
pytest tests/test_main.py::test_health_check -v
```

## Running Locally

```bash
# Install dependencies
pip install -e ".[dev]"

# Run development server
uvicorn src.main:app --reload

# Run production server
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Building Docker Image

```bash
# Build
docker build -t {{PROJECT_NAME}} .

# Run
docker run -p 8000:8000 {{PROJECT_NAME}}

# Check health
curl http://localhost:8000/health
```
