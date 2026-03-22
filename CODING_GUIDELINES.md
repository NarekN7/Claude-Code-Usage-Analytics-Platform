````md
# Coding Guidelines for AI-Generated Code

These rules MUST be followed for all generated Python code. They are mandatory and non-negotiable.

---

## 1. Documentation

- Every function and class MUST include a complete docstring.
- Docstrings MUST follow this structure:

```python
def example(arg1: int) -> str:
    """
    Short description of the function.

    Args:
        arg1 (int): Description of the argument.

    Returns:
        str: Description of the return value.

    Raises:
        ValueError: If invalid input is provided.
    """
````

* Use clear, concise, and professional language.
* Avoid redundant or vague descriptions.

---

## 2. Exception Handling

* NEVER use bare `Exception` or generic exception handling.
* Always catch and handle **specific exception types** first.
* For application-level errors, raise `AppException` from `exceptions.py`.
* Do NOT silently ignore exceptions.
* Always preserve the original error context when re-raising.

---

## 3. Logging

* Every `raise` statement MUST be preceded by a logging call.
* Use appropriate logging levels:

  * `logger.error` → for critical failures
  * `logger.warning` → for recoverable issues
* Logs MUST include enough contextual information for debugging.
* Do NOT log sensitive data.

---

## 4. Code Quality & Best Practices

* Follow Python best practices and clean code principles.
* Prefer small, modular, and testable functions.
* Avoid duplicated logic (DRY principle).
* Use explicit type hints wherever applicable.
* Do NOT introduce unnecessary complexity.
* Use meaningful variable and function names.
* Follow OOP principles where appropriate.

---

## 5. Imports

* All imports MUST be placed at the top of the file.
* Do NOT use inline imports unless absolutely necessary.
* Group imports in the following order:

  1. Standard library
  2. Third-party libraries
  3. Local modules

---

## 6. Code Structure & Separation of Concerns

* Business logic MUST be separated from entry-point scripts.
* Main scripts should act only as orchestrators.
* Core logic MUST be implemented in reusable utility modules or services.
* Avoid placing complex logic inside controllers, routes, or CLI entry files.

---

## 7. General Principles

* Code MUST be production-ready.
* Code MUST be readable and maintainable.
* Prefer clarity over cleverness.
* Every implementation should be easy to test and debug.

```

