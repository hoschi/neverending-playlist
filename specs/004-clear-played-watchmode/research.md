# Research: Clear Played Watchmode

## 1. Background Task Scheduling

### Decision
We will use **`apscheduler`** for managing the recurring 10-minute background task.

### Rationale
- **Simplicity and Integration**: `apscheduler` is a lightweight library that integrates cleanly with FastAPI's startup and shutdown events (`lifespan`). This avoids the complexity of setting up and managing a separate worker process and message broker like Celery or ARQ would require.
- **Sufficient for the Use Case**: The requirement is for a simple, recurring task that runs within the application context. `apscheduler`'s `AsyncIOScheduler` is perfectly suited for this `asyncio`-based application.
- **Stateful Scheduling**: While the job *state* (our application logic's state) will be managed separately, `apscheduler` itself can be configured with a persistent job store if needed in the future, though for now, an in-memory store is sufficient.

### Alternatives Considered
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
