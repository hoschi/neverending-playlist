# Research: Clear Played Watchmode

## 1. Background Task Scheduling

### Decision
We will use **`dramatiq`** for managing the recurring 10-minute background task.

### Rationale
- **Type-Safety and Better Annotations**: `dramatiq` provides excellent Type-Safety with proper type annotations, which aligns with the project's strict typing requirements. Unlike `apscheduler`, `dramatiq` has comprehensive type stubs and supports async operations natively.
- **Simplicity and Integration**: `dramatiq` is designed for modern Python applications and integrates cleanly with FastAPI's async ecosystem. It provides a simple, async-first approach without complex configuration.
- **Production-Ready**: `dramatiq` is built for production use with robust error handling, retry mechanisms, and excellent logging capabilities, making it suitable for background task processing.
- **Async-Native**: As an asyncio-native library, `dramatiq` is perfectly suited for this async-based application, avoiding any blocking operations.
- **Type Safety**: The main driver for this change is superior Type-Safety compared to `apscheduler`, which lacks proper type annotations.

### Alternatives Considered
- **`apscheduler`**: Originally considered but rejected due to poor Type-Safety and lack of proper type annotations, which doesn't align with the project's strict typing requirements.
- **`celery`**: Overkill for this feature. It requires a separate message broker (like RabbitMQ or Redis) and a worker process, which adds significant operational complexity for a single, simple recurring task.
- **`arq` (Asyncio-RQ)**: A good `asyncio`-native option, but like Celery, it requires a Redis instance and a separate worker setup. For this self-contained feature, keeping the scheduler within the main application process is simpler.
- **FastAPI's `BackgroundTasks`**: Not suitable because it's designed for short-lived, "fire-and-forget" tasks triggered by a request. It does not support recurring or scheduled tasks.

## 2. State Management

### Decision
We will use a simple **in-memory singleton object** to manage the state of the checker.

### Rationale
- **Simplicity**: This is the simplest possible solution. It involves creating a single, shared object (e.g., a Pydantic model instance) that the API endpoint and the `apscheduler` job can both access. This avoids introducing external dependencies like a database or Redis.
- **Alignment with Request**: The user described a transient "watchmode" initiated by a simple GET request. A state that resets on application restart is acceptable for this use case. If the server restarts, the user can simply hit the endpoint again to re-activate the checker.
- **Avoids I/O Overhead**: An in-memory solution is extremely fast and avoids the latency of database or network calls for state updates.

### Alternatives Considered
- **Database (Supabase)**: Using a new table in Supabase would provide persistence across restarts and support for multiple server workers. However, it adds database I/O overhead for state checks and requires schema management, which is more complexity than is currently warranted.
- **Redis**: Redis would be a high-performance solution for state management, but it introduces a new external dependency to the project, which is not justified for this single feature.
