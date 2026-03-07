# Node.js Express + TypeScript Project Structure

## Directory Layout

```
{{PROJECT_NAME}}/
├── package.json              # Dependencies and scripts
├── tsconfig.json             # TypeScript configuration
├── README.md                 # Project documentation
├── Dockerfile                # Production container image
├── src/
│   ├── index.ts              # Application entry point
│   ├── app.ts                # Express app configuration
│   ├── config.ts             # Environment configuration
│   ├── routes/               # API route handlers
│   │   └── index.ts
│   ├── controllers/          # Request handlers
│   │   └── health.ts
│   ├── middleware/           # Express middleware
│   │   └── error.ts
│   └── types/                # TypeScript type definitions
│       └── index.ts
└── tests/
    └── app.test.ts           # Application tests
```

## Conventions

### Code Organization
- **src/**: All application code
- **routes/**: Express route definitions
- **controllers/**: Request handling logic
- **middleware/**: Express middleware (auth, error handling, etc.)
- **types/**: Shared TypeScript interfaces
- **tests/**: Test files (mirror src/ structure)

### Key Patterns

1. **Configuration via Environment**
   ```typescript
   import { config } from './config';
   const port = config.port;
   ```

2. **Express Router Pattern**
   ```typescript
   // routes/users.ts
   import { Router } from 'express';
   export const userRouter = Router();
   userRouter.get('/', getUsers);
   ```

3. **Async Error Handling**
   ```typescript
   import { Request, Response, NextFunction } from 'express';
   
   export const asyncHandler = (fn: Function) => {
     return (req: Request, res: Response, next: NextFunction) => {
       Promise.resolve(fn(req, res, next)).catch(next);
     };
   };
   ```

4. **Type Safety**
   - Use Zod for runtime validation
   - Define interfaces for all API contracts
   - Avoid `any` type

## Customization Points

### 1. Add Routes
**File:** `src/routes/`  
**Action:** Create route modules
```typescript
// src/routes/users.ts
import { Router } from 'express';
import { getUsers, createUser } from '../controllers/users';

export const userRouter = Router();

userRouter.get('/', getUsers);
userRouter.post('/', createUser);
```

**Then register in app.ts:**
```typescript
import { userRouter } from './routes/users';
app.use('/users', userRouter);
```

### 2. Add Controllers
**File:** `src/controllers/`  
**Action:** Implement request handlers
```typescript
// src/controllers/users.ts
import { Request, Response } from 'express';

export const getUsers = async (req: Request, res: Response) => {
  const users = await userService.findAll();
  res.json({ users });
};
```

### 3. Add Middleware
**File:** `src/middleware/`  
**Action:** Implement middleware
```typescript
// src/middleware/auth.ts
import { Request, Response, NextFunction } from 'express';

export const authMiddleware = (
  req: Request,
  res: Response,
  next: NextFunction
) => {
  // Auth logic here
  next();
};
```

### 4. Add Dependencies
**File:** `package.json`  
**Action:** Add to dependencies
```json
{
  "dependencies": {
    "express": "^4.18.2",
    "your-dep": "^1.0.0"
  }
}
```

Then run:
```bash
npm install
```

## Preserved Patterns (Don't Remove)

These are critical for production:

1. **Health Check Endpoint** (`GET /health`)
   - Required for load balancers
   - Used by Docker HEALTHCHECK

2. **Error Handling Middleware**
   - Centralized error handling
   - Consistent error responses

3. **Non-root User in Dockerfile**
   - Security best practice
   - Prevents container escape attacks

4. **TypeScript Strict Mode**
   - Type safety enforced
   - Catches errors at compile time

## Escape Hatches

You can deviate when needed:

- **Switch to Fastify** instead of Express (update app.ts)
- **Use Prisma ORM** (add to dependencies)
- **Add GraphQL** (install Apollo Server)
- **Use pnpm instead of npm** (update Dockerfile)
- **Add Makefile** for complex build steps

## Testing

```bash
# Run tests
npm test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch
```

## Running Locally

```bash
# Install dependencies
npm install

# Run development server (with hot reload)
npm run dev

# Run production build
npm run build
npm start
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

Create `.env` file:

```
NODE_ENV=development
PORT=3000
DATABASE_URL=postgresql://user:pass@localhost:5432/db
JWT_SECRET=your-secret-key
```
