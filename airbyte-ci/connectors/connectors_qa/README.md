# Connectors QA

This package has two main purposes:
* Running QA checks on connectors.
* Documenting the QA checks that are run on connectors.

## Installation

```bash
poetry install
```

## Usage

### Running QA checks on one or more connectors:

```bash
poetry run connectors-qa run --name <connector-name> --connector <connector-name>
```

### Generating documentation for QA checks:

```bash
poetry run connectors-qa generate-doumentation <output-file>
```

## Adding a new QA check

To add a new QA check, you need to create a new class in the `checks` module that inherits from `models.Check` and implement the `_run` method. Then, you need to add an instance of this class to the `ENABLED_CHECKS` list in `__init__.py`.
**Please run the `generate-doumentation` command to update the documentation with the new check.**