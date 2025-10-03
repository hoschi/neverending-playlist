<!--
Sync Impact Report:

- **Version Change**: None → 1.0.0
- **Added Sections**:
  - Core Principles (10 principles defined)
  - Development Workflow
  - Governance
- **Removed Sections**:
  - All placeholder sections
- **Templates Requiring Updates**:
  - ✅ `.specify/templates/plan-template.md` (No changes needed, already aligned)
  - ✅ `.specify/templates/spec-template.md` (No changes needed, already aligned)
  - ✅ `.specify/templates/tasks-template.md` (No changes needed, already aligned)
- **Follow-up TODOs**:
  - None
-->
# Supabase to Spotify Constitution

## Core Principles

### I. Functional Core, Imperative Shell (FCIS)
The project is strictly divided into a `src/core` containing pure, stateless business logic and a `src/shell` for all side effects (e.g., I/O, database access, API calls). The shell depends on the core, but the core must never depend on the shell.

### II. Strict Typing
All code MUST pass `mypy --strict` validation. Type hints are non-negotiable for all functions, variables, and data structures. The use of `Any` is forbidden unless explicitly justified for interoperability with untyped libraries.

### III. Functional & Immutable by Default
Code must be written in a functional style, separating data from behavior. Data structures must be **treated as if they were immutable**.
- **Data Structures:**
  - Data classes (like Pydantic Models or dataclasses) must NOT contain methods, except for `__post_init__` for validation.
- **Behavior:**
  - Logic MUST be implemented as **free functions** outside of data classes.
  - State changes are achieved by creating new instances, not by mutating existing ones.
- **Truly Immutable Structures:**
  - The `pyrsistent` library should only be used for performance-critical reasons where its structural sharing provides a significant benefit. Its use must be explicitly specified in a task.
- **Prohibited:**
  - Classes with methods (except for allowed magic methods).
  - Inheritance of classes for code reuse.
  - Stateful classes with `self` mutation.
  - Service classes with `__init__` and instance variables.
- **Allowed Exceptions:**
  - `Pydantic` validators and `Config` in models (for data boundaries).
  - Magic methods for Python protocols (`__str__`, `__repr__`, `__eq__`, `__hash__`).
  - Properties for computed read-only fields (to be used sparingly).

### IV. Railway Oriented Programming for Error Handling
Expected errors (e.g., validation failures, network errors) MUST be handled using the `returns.Result` monad. Functions that can fail must return a `Result[SuccessType, FailureType]`, making error paths explicit in the type system. Exceptions should only be used for unrecoverable system errors.

### V. Data Validation at Boundaries
All external data—from API responses, user input, or database queries—MUST be validated by Pydantic models at the application's entry points (the "imperative shell"). This ensures that the functional core operates only on trusted, type-safe data.

### VI. Dependency Inversion via Protocols
The functional core MUST NOT depend on concrete implementations. Instead, it should depend on abstract interfaces defined with `typing.Protocol`. This allows for interchangeable implementations (e.g., a real database vs. an in-memory mock) and ensures the core remains decoupled and highly testable.

### VII. Comprehensive and Automated Testing
Every piece of business logic MUST be fully tested to achieve 100% line and branch coverage. The testing strategy includes:
- **Unit Tests:** For individual functions.
- **Property-Based Tests:** Using `hypothesis` to test functions against a wide range of generated data.
- **Protocol-Based Mocking:** Using test doubles that adhere to the same `Protocol` as the real implementation.
- **Test Data Generation:** Using `polyfactory` to create valid test data for Pydantic models.

### VIII. Don't Repeat Yourself (DRY)
Code duplication is to be strictly avoided. Reusable logic should be encapsulated in well-defined service functions. Common behavioral patterns should be abstracted using `typing.Protocol`.

### IX. Structured and Asynchronous Logging
Logging MUST be implemented using `Loguru` for its structured, configurable, and process-safe capabilities. Logs should provide context and be filterable by module and severity.

## Development Workflow

The standard development workflow is as follows:
1.  Define data structures and protocols in `src/core`.
2.  Implement pure business logic as functions in `src/core/services/`. Group related functions in modules (e.g., `user_operations.py`). Use namespaces through modules instead of classes.
3.  Write comprehensive tests in `tests/core` that cover all logic.
4.  Implement the imperative shell in `src/shell` (e.g., API endpoints, CLI commands) that calls the core services.
5.  Write integration tests for the shell in `tests/shell`.
6.  Run `poe check-all` to ensure all quality gates (formatting, linting, type checking, testing) pass before committing.

## Governance

This Constitution is the single source of truth for the project's architecture and coding standards. All code reviews MUST enforce these principles. Any proposed deviation requires a formal amendment to this document.

**Version**: 1.0.1 | **Ratified**: 2025-10-03 | **Last Amended**: 2025-10-03