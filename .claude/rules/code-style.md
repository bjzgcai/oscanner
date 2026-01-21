# Code Style Guidelines

## Python (Backend)

### Formatting
- **Line length**: 100-120 chars (flexible)
- **Indentation**: 4 spaces
- **Imports**: Standard lib → Third-party → Local
- **Type hints**: Use for function signatures

### Naming
- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_prefix`

### Patterns
- **Error handling**: Return empty/default values with logging (avoid raising)
- **Async**: Use `async/await` for IO operations
- **Path handling**: Use `pathlib.Path` over `os.path`
- **JSON operations**: Use atomic writes (write to `.tmp`, then rename)

### FastAPI Conventions
- Route naming: `/api/{resource}/{action}`
- Response models: Use Pydantic models
- Error responses: `HTTPException` with status codes

## TypeScript/React (Frontend)

### Formatting
- **Line length**: 100 chars
- **Indentation**: 2 spaces
- **Semicolons**: Optional (prefer without)
- **Quotes**: Single quotes for strings

### Components
- Functional components with hooks
- Props interface: `{ComponentName}Props`
- State management: React hooks + Context API
- File structure: One component per file

### Naming
- Components: `PascalCase.tsx`
- Utilities: `camelCase.ts`
- Constants: `UPPER_SNAKE_CASE`
- CSS classes: `kebab-case`

### Patterns
- **API calls**: Centralized in service functions
- **State**: Use `useState` for local, Context for global
- **Effects**: Clean up in `useEffect` returns
- **Styling**: Inline styles or CSS modules (Ant Design theming)

## Documentation
- **Functions**: Docstring for complex logic only
- **APIs**: Document in OpenAPI/Swagger (FastAPI auto-generates)
- **README**: Keep updated with setup instructions
- **Comments**: Explain "why", not "what"
