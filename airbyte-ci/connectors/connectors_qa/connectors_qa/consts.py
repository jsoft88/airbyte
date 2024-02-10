# Copyright (c) 2023 Airbyte, Inc., all rights reserved.

from base_images.python.bases import AirbytePythonConnectorBaseImage

CONNECTORS_QA_DOC_TEMPLATE_NAME = "connectors_qa.md.j2"
DOCKER_INDEX = "docker.io"
DOCKERFILE_NAME = "Dockerfile"
DOCUMENTATION_STANDARDS_URL = "https://hackmd.io/Bz75cgATSbm7DjrAqgl4rw"
LICENSE_FAQ_URL = "https://docs.airbyte.com/developer-guides/licenses/license-faq"
METADATA_DOCUMENTATION_URL = "https://docs.airbyte.com/connector-development/connector-metadata-file"
METADATA_FILE_NAME = "metadata.yaml"
POETRY_LOCK_FILE_NAME = "poetry.lock"
PYPROJECT_FILE_NAME = "pyproject.toml"
SEMVER_FOR_CONNECTORS_DOC_URL = "https://docs.airbyte.com/contributing-to-airbyte/#semantic-versioning-for-connectors"
SETUP_PY_FILE_NAME = "setup.py"

# Derived from other constants
AIRBYTE_PYTHON_CONNECTOR_BASE_IMAGE_NAME = f"{DOCKER_INDEX}/{AirbytePythonConnectorBaseImage.repository}"
