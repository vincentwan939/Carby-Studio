# Go Gin Project Structure

## Directory Layout

```
{{PROJECT_NAME}}/
├── go.mod                    # Go module definition
├── go.sum                    # Dependency checksums
├── README.md                 # Project documentation
├── Dockerfile                # Production container image
├── cmd/
│   └── api/
│       └── main.go           # Application entry point
├── internal/
│   ├── config/               # Configuration
│   │   └── config.go
│   ├── handlers/             # HTTP handlers
│   │   └── health.go
│   ├── middleware/           # Gin middleware
│   │   └── error.go
│   ├── models/               # Data models
│   │   └── user.go
│   └── routes/               # Route definitions
│       └── routes.go
├── pkg/
│   └── utils/                # Shared utilities
│       └── response.go
└── tests/
    └── health_test.go        # Handler tests
```

## Conventions

### Code Organization (Standard Go Project Layout)
- **cmd/**: Main applications for this project
- **internal/**: Private application code
  - **config/**: Environment configuration
  - **handlers/**: HTTP request handlers
  - **middleware/**: Gin middleware
  - **models/**: Database models (GORM)
  - **routes/**: Route setup
- **pkg/**: Public libraries (can be imported by other projects)
- **tests/**: Test files

### Key Patterns

1. **Configuration via Environment**
   ```go
   import "{{PROJECT_NAME}}/internal/config"
   cfg := config.Load()
   port := cfg.Port
   ```

2. **Gin Handler Pattern**
   ```go
   func GetUsers(c *gin.Context) {
       users := []User{{ID: 1, Name: "John"}}
       c.JSON(200, gin.H{"users": users})
   }
   ```

3. **Dependency Injection**
   ```go
   type Handler struct {
       db *gorm.DB
   }
   
   func (h *Handler) GetUser(c *gin.Context) {
       // Use h.db
   }
   ```

4. **Error Handling**
   - Return errors up the call stack
   - Use middleware for centralized error handling
   - Log errors with context

## Customization Points

### 1. Add Handlers
**File:** `internal/handlers/`  
**Action:** Create handler functions
```go
// internal/handlers/user.go
package handlers

import "github.com/gin-gonic/gin"

func GetUsers(c *gin.Context) {
    c.JSON(200, gin.H{"users": []})
}
```

**Then register in routes:**
```go
// internal/routes/routes.go
router.GET("/users", handlers.GetUsers)
```

### 2. Add Models
**File:** `internal/models/`  
**Action:** Create GORM models
```go
// internal/models/user.go
package models

import "gorm.io/gorm"

type User struct {
    gorm.Model
    Email string `gorm:"uniqueIndex"`
    Name  string
}
```

### 3. Add Middleware
**File:** `internal/middleware/`  
**Action:** Implement middleware
```go
// internal/middleware/auth.go
package middleware

import "github.com/gin-gonic/gin"

func Auth() gin.HandlerFunc {
    return func(c *gin.Context) {
        // Auth logic
        c.Next()
    }
}
```

### 4. Add Dependencies
```bash
go get github.com/some/package
```

## Preserved Patterns (Don't Remove)

These are critical for production:

1. **Health Check Endpoint** (`GET /health`)
   - Required for load balancers
   - Used by Kubernetes/Docker health checks

2. **Graceful Shutdown**
   - Handles SIGTERM/SIGINT
   - Allows in-flight requests to complete

3. **Non-root User in Dockerfile**
   - Security best practice

4. **Structured Logging**
   - Use standard log package or structured logger
   - Consistent log format

## Escape Hatches

You can deviate when needed:

- **Switch to Echo/Fiber** (replace gin in go.mod)
- **Use sqlx instead of GORM** (update models/)
- **Add gRPC** (add cmd/grpc/)
- **Use PostgreSQL/MySQL** (update config)
- **Add Redis** (add internal/cache/)

## Testing

```bash
# Run tests
go test ./...

# Run with coverage
go test -cover ./...

# Run specific test
go test ./internal/handlers -v
```

## Running Locally

```bash
# Download dependencies
go mod download

# Run development server
go run cmd/api/main.go

# Build binary
go build -o bin/api cmd/api/main.go

# Run binary
./bin/api
```

## Building Docker Image

```bash
# Build
docker build -t {{PROJECT_NAME}} .

# Run
docker run -p 8080:8080 {{PROJECT_NAME}}

# Check health
curl http://localhost:8080/health
```

## Environment Variables

- `PORT` - Server port (default: 8080)
- `ENV` - Environment: development|production (default: development)
- `DATABASE_URL` - Database connection string
- `JWT_SECRET` - Secret for JWT tokens

## Go Best Practices

1. **Keep cmd/ small**: Business logic goes in internal/
2. **Interface boundaries**: Define interfaces at package boundaries
3. **Context propagation**: Pass context.Context through call chain
4. **Error wrapping**: Use fmt.Errorf with %w verb
5. **No global state**: Pass dependencies explicitly
