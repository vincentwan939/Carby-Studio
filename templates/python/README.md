# {{PROJECT_NAME}}

{{PROJECT_DESCRIPTION}}

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run development server
uvicorn src.main:app --reload

# Build Docker image
docker build -t {{PROJECT_NAME}} .

# Run container
docker run -p 8000:8000 {{PROJECT_NAME}}
```

## API Endpoints

- `GET /health` - Health check
- `GET /` - API info

## Project Structure

See [STRUCTURE.md](STRUCTURE.md) for detailed conventions and patterns.

## Development

```bash
# Run with auto-reload
uvicorn src.main:app --reload

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Type checking
mypy src/

# Linting
ruff check src/

# Formatting
ruff format src/
```

## Configuration

Set via environment variables or `.env` file:

- `APP_NAME` - Application name
- `DEBUG` - Enable debug mode (true/false)
- `DATABASE_URL` - Database connection string
- `SECRET_KEY` - Secret key for JWT tokens
- `CORS_ORIGINS` - Allowed CORS origins (comma-separated)

## License

MIT
