# Rust Axum Project Structure

## Directory Layout

```
{{PROJECT_NAME}}/
├── Cargo.toml                # Rust package manifest
├── Cargo.lock                # Dependency lock file
├── README.md                 # Project documentation
├── Dockerfile                # Production container image
├── src/
│   ├── main.rs               # Application entry point
│   ├── lib.rs                # Library exports
│   ├── config.rs             # Configuration
│   ├── routes/               # Route handlers
│   │   ├── mod.rs
│   │   └── health.rs
│   ├── handlers/             # Request handlers
│   │   └── health.rs
│   ├── middleware/           # Axum middleware
│   │   └── error.rs
│   └── models/               # Data models
│       └── user.rs
└── tests/
    └── health_test.rs        # Integration tests
```

## Conventions

### Code Organization
- **src/main.rs**: Application entry point
- **src/lib.rs**: Library exports (for testing)
- **src/config.rs**: Environment configuration
- **src/routes/**: Route definitions and composition
- **src/handlers/**: HTTP request handlers
- **src/middleware/**: Axum middleware
- **src/models/**: Database models (SQLx)
- **tests/**: Integration tests

### Key Patterns

1. **Configuration via Environment**
   ```rust
   use crate::config::Config;
   let config = Config::from_env();
   ```

2. **Axum Handler Pattern**
   ```rust
   use axum::{extract::State, Json};
   
   async fn get_users(
       State(pool): State<PgPool>
   ) -> Result<Json<Vec<User>>, AppError> {
       let users = sqlx::query_as!(User, "SELECT * FROM users")
           .fetch_all(&pool)
           .await?;
       Ok(Json(users))
   }
   ```

3. **Error Handling**
   ```rust
   use thiserror::Error;
   
   #[derive(Error, Debug)]
   pub enum AppError {
       #[error("database error")]
       Database(#[from] sqlx::Error),
   }
   ```

4. **State Management**
   ```rust
   #[derive(Clone)]
   pub struct AppState {
       pub db: PgPool,
       pub config: Config,
   }
   ```

## Customization Points

### 1. Add Handlers
**File:** `src/handlers/`  
**Action:** Create handler functions
```rust
// src/handlers/users.rs
use axum::{extract::State, Json};

pub async fn list_users(
    State(state): State<AppState>
) -> Result<Json<Vec<User>>, AppError> {
    // Handler logic
}
```

**Then add to routes:**
```rust
// src/routes/mod.rs
use crate::handlers::users;

pub fn routes() -> Router {
    Router::new()
        .route("/users", get(users::list_users))
}
```

### 2. Add Models
**File:** `src/models/`  
**Action:** Create structs
```rust
// src/models/user.rs
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct User {
    pub id: i64,
    pub email: String,
}
```

### 3. Add Middleware
**File:** `src/middleware/`  
**Action:** Implement tower middleware
```rust
// src/middleware/auth.rs
use axum::middleware::Next;

pub async fn auth_middleware<B>(
    req: Request<B>,
    next: Next<B>,
) -> Response {
    // Middleware logic
    next.run(req).await
}
```

### 4. Add Dependencies
**File:** `Cargo.toml`  
```toml
[dependencies]
serde = { version = "1.0", features = ["derive"] }
```

## Preserved Patterns (Don't Remove)

These are critical for production:

1. **Health Check Endpoint** (`GET /health`)
   - Required for load balancers
   - Used by Kubernetes probes

2. **Graceful Shutdown**
   - Handles Ctrl+C (SIGINT)
   - Uses tokio::signal

3. **Structured Logging**
   - Uses tracing for structured logs
   - JSON format in production

4. **Error Handling**
   - thiserror for error definitions
   - anyhow for error propagation
   - Custom IntoResponse for errors

## Escape Hatches

You can deviate when needed:

- **Switch to Actix-web** (replace axum in Cargo.toml)
- **Use Diesel instead of SQLx** (update models/)
- **Add GraphQL** (install async-graphql)
- **Use NATS/Redis** (add to dependencies)

## Testing

```bash
# Run tests
cargo test

# Run with output
cargo test -- --nocapture

# Run specific test
cargo test health_check
```

## Running Locally

```bash
# Build
cargo build

# Run development
cargo run

# Run release build
cargo run --release

# Check (fast feedback)
cargo check

# Format code
cargo fmt

# Run linter
cargo clippy
```

## Building Docker Image

```bash
# Build
docker build -t {{PROJECT_NAME}} .

# Run
docker run -p 3000:3000 {{PROJECT_NAME}}

# Check health
curl http://localhost:3000/health
```

## Environment Variables

- `PORT` - Server port (default: 3000)
- `RUST_LOG` - Log level (default: info)
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret for JWT tokens

## Rust Best Practices

1. **Use Result everywhere**: Don't unwrap in production code
2. **Structured logging**: Use tracing, not println!
3. **Clone strategically**: Use Arc<State> for shared state
4. **Async all the way**: Don't block the async runtime
5. **Type safety**: Leverage Rust's type system
