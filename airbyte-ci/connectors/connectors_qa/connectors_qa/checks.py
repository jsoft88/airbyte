# Copyright (c) 2023 Airbyte, Inc., all rights reserved.

import os
import textwrap
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple

import semver
import toml
from click.testing import CliRunner
from connector_ops.utils import ConnectorLanguage
from connectors_qa import consts
from connectors_qa.models import Check, CheckCategory, CheckResult
from metadata_service.commands import validate as validate_metadata
from pydash.objects import get


class CheckMigrationGuide(Check):

    name = "Breaking changes must be accompanied by a migration guide"
    description = "When a breaking change is introduced we check that a migration guide is available. It should be stored under  `./docs/integrations/<connector-type>s/<connector-name>-migrations.md`.\nThis document should contain a section for each breaking change, in order of the version descending. It must explain users which action to take to migrate to the new version."
    category = CheckCategory.DOCUMENTATION

    def _run(self) -> CheckResult:
        breaking_changes = get(self.connector.metadata, "releases.breakingChanges")
        if not breaking_changes:
            return self.create_check_result(passed=True, message="No breaking changes found. A migration guide is not required")
        migration_guide_file_path = self.connector.migration_guide_file_path
        migration_guide_exists = migration_guide_file_path is not None and migration_guide_file_path.exists()
        if not migration_guide_exists:
            return self.create_check_result(
                passed=False,
                message=f"Migration guide file is missing for {self.connector.name}. Please create a migration guide at {self.connector.migration_guide_file_path}",
            )

        expected_title = f"# {self.connector.name_from_metadata} Migration Guide"
        expected_version_header_start = "## Upgrading to "
        migration_guide_content = migration_guide_file_path.read_text()
        first_line = migration_guide_content.splitlines()[0]
        if not first_line == expected_title:
            return self.create_check_result(
                passed=False,
                message=f"Migration guide file for {self.connector.technical_name} does not start with the correct header. Expected '{expected_title}', got '{first_line}'",
            )

        # Check that the migration guide contains a section for each breaking change key ## Upgrading to {version}
        # Note that breaking change is a dict where the version is the key
        # Note that the migration guide must have the sections in order of the version descending
        # 3.0.0, 2.0.0, 1.0.0, etc
        # This means we have to record the headings in the migration guide and then check that they are in order
        # We also have to check that the headings are in the breaking changes dict
        ordered_breaking_changes = sorted(breaking_changes.keys(), reverse=True)
        ordered_expected_headings = [f"{expected_version_header_start}{version}" for version in ordered_breaking_changes]

        ordered_heading_versions = []
        for line in migration_guide_content.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith(expected_version_header_start):
                version = stripped_line.replace(expected_version_header_start, "")
                ordered_heading_versions.append(version)

        if ordered_breaking_changes != ordered_heading_versions:
            return self.create_check_result(
                passed=False,
                message=textwrap.dedent(
                    f"""
                Migration guide file for {self.connector.name} has incorrect version headings.
                Check for missing, extra, or misordered headings, or headers with typos.
                Expected headings: {ordered_expected_headings}
                """
                ),
            )
        return self.create_check_result(passed=True, message="The migration guide is correctly templated")


class CheckDocumentationExists(Check):

    name = "Connectors must have user facing documentation"
    description = (
        "The user facing connector documentation should be stored under `./docs/integrations/<connector-type>s/<connector-name>.md`."
    )
    category = CheckCategory.DOCUMENTATION

    def _run(self) -> CheckResult:
        if not self.connector.documentation_file_path or not self.connector.documentation_file_path.exists():
            return self.create_check_result(
                passed=False,
                message=f"User facing documentation file {self.connector.documentation_file_path} is missing. Please create it",
            )
        return self.create_check_result(
            passed=True, message=f"User facing documentation file {self.connector.documentation_file_path} exists"
        )


class CheckDocumentationStructure(Check):

    name = "Connectors documentation follows our guidelines"
    description = f"The user facing connector documentation should follow the guidelines defined in the [documentation standards]({consts.DOCUMENTATION_STANDARDS_URL})."
    category = CheckCategory.DOCUMENTATION

    def _run(self) -> CheckResult:
        errors = []
        with open(self.connector.documentation_file_path) as f:
            doc_lines = [line.lower() for line in f.read().splitlines()]
        if not doc_lines[0].startswith("# "):
            errors.append("The connector name is not used as the main header in the documentation")
        # We usually don't have a metadata if the connector is not published.
        if self.connector.metadata:
            if doc_lines[0].strip() != f"# {self.connector.metadata['name'].lower()}":
                errors.append("The connector name is not used as the main header in the documentation")
        elif not doc_lines[0].startswith("# "):
            errors.append("The connector name is not used as the main header in the documentation")

        expected_sections = ["## Prerequisites", "## Setup guide", "## Supported sync modes", "## Supported streams", "## Changelog"]
        for expected_section in expected_sections:
            if expected_section.lower() not in doc_lines:
                errors.append(f"Connector documentation is missing a '{expected_section.replace('#', '').strip()}' section")

        if errors:
            return self.create_check_result(
                passed=False, message=f"Connector documentation does not follow the guidelines. {'. '.join(errors)}"
            )
        return self.create_check_result(passed=True, message="Documentation guidelines are followed")


class CheckChangelogEntry(Check):

    name = "Connectors must have a changelog entry for each version"
    description = "Each new version of a connector must have a changelog entry defined in the user facing documentation in `./docs/integrations/<connector-type>s/<connector-name>.md."
    category = CheckCategory.DOCUMENTATION

    def _run(self) -> CheckResult:
        if self.connector.documentation_file_path is None or not self.connector.documentation_file_path.exists():
            return self.create_check_result(
                passed=False,
                message=f"User facing documentation file {self.connector.documentation_file_path} is missing. Please create it.",
            )

        doc_lines = self.connector.documentation_file_path.read_text().splitlines()
        after_changelog = False
        entry_found = False
        for line in doc_lines:
            if "# changelog" in line.lower():
                after_changelog = True
            if after_changelog and self.connector.version in line:
                entry_found = True

        if not entry_found:
            return self.create_check_result(
                passed=False, message=f"Changelog entry for version {self.connector.version} is missing in the documentation"
            )

        return self.create_check_result(passed=True, message="Changelog entry found")


class CheckConnectorIconIsAvailable(Check):

    name = "Connectors must have an icon"
    description = "Each connector must have an icon available in at the root of the connector code directory. It must be an SVG file named `icon.svg`."
    category = CheckCategory.ASSETS

    def _run(self) -> CheckResult:
        if not self.connector.icon_path or not self.connector.icon_path.exists():
            return self.create_check_result(passed=False, message=f"Icon file {self.connector.icon_path} is missing")
        return self.create_check_result(passed=True, message="Icon file exists")


class CheckConnectorUsesHTTPSOnly(Check):
    name = "Connectors must use HTTPS only"
    description = "Connectors must use HTTPS only when making requests to external services."
    category = CheckCategory.SECURITY
    ignore_comment = "# ignore-https-check"  # Define the ignore comment pattern

    ignored_directories_for_https_checks = {
        ".venv",
        "tests",
        "unit_tests",
        "integration_tests",
        "build",
        "source-file",
        ".pytest_cache",
        "acceptance_tests_logs",
        ".hypothesis",
        ".ruff_cache",
    }

    ignored_file_name_pattern_for_https_checks = {
        "*Test.java",
        "*.jar",
        "*.pyc",
        "*.gz",
        "*.svg",
        "expected_records.jsonl",
        "expected_records.json",
    }

    ignored_url_prefixes = {
        "http://json-schema.org",
        "http://localhost",
    }

    @staticmethod
    def _read_all_files_in_directory(
        directory: Path, ignored_directories: Optional[Set[str]] = None, ignored_filename_patterns: Optional[Set[str]] = None
    ) -> Iterable[Tuple[str, str]]:
        ignored_directories = ignored_directories if ignored_directories is not None else {}
        ignored_filename_patterns = ignored_filename_patterns if ignored_filename_patterns is not None else {}

        for path in directory.rglob("*"):
            ignore_directory = any([ignored_directory in path.parts for ignored_directory in ignored_directories])
            ignore_filename = any([path.match(ignored_filename_pattern) for ignored_filename_pattern in ignored_filename_patterns])
            ignore = ignore_directory or ignore_filename
            if path.is_file() and not ignore:
                try:
                    for line in open(path, "r"):
                        yield path, line
                except UnicodeDecodeError:
                    continue

    @staticmethod
    def _line_is_comment(line: str, file_path: Path):
        language_comments = {
            ".py": "#",
            ".yml": "#",
            ".yaml": "#",
            ".java": "//",
            ".md": "<!--",
        }

        denote_comment = language_comments.get(file_path.suffix)
        if not denote_comment:
            return False

        trimmed_line = line.lstrip()
        return trimmed_line.startswith(denote_comment)

    def _run(self) -> CheckResult:
        files_with_http_url = set()

        for filename, line in self._read_all_files_in_directory(
            self.connector.code_directory, self.ignored_directories_for_https_checks, self.ignored_file_name_pattern_for_https_checks
        ):
            line = line.lower()
            if self._line_is_comment(line, filename):
                continue
            if self.ignore_comment in line:
                continue
            for prefix in self.ignored_url_prefixes:
                line = line.replace(prefix, "")
            if "http://" in line:
                files_with_http_url.add(str(filename))

        if files_with_http_url:
            files_with_http_url = "\n\t- ".join(files_with_http_url)
            return self.create_check_result(passed=False, message=f"The following files have http:// URLs:\n\t- {files_with_http_url}")
        return self.create_check_result(passed=True, message="No file with http:// URLs found")


class CheckConnectorUsesPoetry(Check):
    name = "Connectors must use Poetry for dependency management"
    description = "Connectors must use [Poetry](https://python-poetry.org/) for dependency management. This is to ensure that all connectors use a dependency management tool which locks dependencies and ensures reproducible installs."
    category = CheckCategory.CODE_QUALITY
    applies_to_connector_languages = {ConnectorLanguage.PYTHON, ConnectorLanguage.LOW_CODE}

    def _run(self) -> CheckResult:
        if not (self.connector.code_directory / consts.PYPROJECT_FILE_NAME).exists():
            return self.create_check_result(passed=False, message="pyproject.toml file is missing")
        if not (self.connector.code_directory / consts.POETRY_LOCK_FILE_NAME).exists():
            return self.create_check_result(passed=False, message="poetry.lock file is missing")
        if (self.connector.code_directory / consts.SETUP_PY_FILE_NAME).exists():
            return self.create_check_result(passed=False, message="setup.py file exists. Please remove it and use pyproject.toml instead")
        return self.create_check_result(passed=True, message="Poetry is used for dependency management")


class CheckConnectorUsesPythonBaseImage(Check):
    name = (
        f"Python connectors must not use a {consts.DOCKERFILE_NAME} and must declare their base image in {consts.METADATA_FILE_NAME} file"
    )
    description = f"Connectors must use our Python connector base image (`{consts.AIRBYTE_PYTHON_CONNECTOR_BASE_IMAGE_NAME}`), declared through the `connectorBuildOptions.baseImage` in their `{consts.METADATA_FILE_NAME}`.\nThis is to ensure that all connectors use a base image which is maintained and has security updates."
    category = CheckCategory.SECURITY
    applies_to_connector_languages = {ConnectorLanguage.PYTHON, ConnectorLanguage.LOW_CODE}

    def _run(self) -> CheckResult:
        dockerfile_path = self.connector.code_directory / consts.DOCKERFILE_NAME
        if dockerfile_path.exists():
            return self.create_check_result(
                passed=False,
                message=f"{consts.DOCKERFILE_NAME} file exists. Please remove it and declare the base image in {consts.METADATA_FILE_NAME} file with the `connectorBuildOptions.baseImage` key",
            )
        if not self.connector.metadata:
            return self.create_check_result(passed=False, message=f"{consts.METADATA_FILE_NAME} file is missing")
        if not get(self.connector.metadata, "connectorBuildOptions.baseImage"):
            return self.create_check_result(
                passed=False, message=f"connectorBuildOptions.baseImage key is missing in {consts.METADATA_FILE_NAME} file"
            )
        return self.create_check_result(passed=True, message="Connector uses the Python connector base image")


class ValidateMetadata(Check):
    name = "Connectors must have valid metadata"
    description = f"Connectors must have a `{consts.METADATA_FILE_NAME}` file at the root of their directory. This file is used to build our connector registry. Its structure must follow our metadata schema. Field values are also validated. This is to ensure that all connectors have the required metadata fields and that the metadata is valid. More details in this [documentation]({consts.METADATA_DOCUMENTATION_URL})."
    category = CheckCategory.ASSETS
    # Metadata lib required the following env var to be set
    # to check if the base image is on DockerHub
    required_env_vars = {"DOCKERHUB_USERNAME", "DOCKERHUB_PASSWORD"}

    def _run(self) -> CheckResult:
        for env_var in self.required_env_vars:
            if env_var not in os.environ:
                raise ValueError(f"Environment variable {env_var} is required for this check")

        metadata_file_path = self.connector.code_directory / consts.METADATA_FILE_NAME
        if not metadata_file_path.exists():
            return self.create_check_result(passed=False, message=f"{consts.METADATA_FILE_NAME} file is missing")
        if not self.connector.documentation_file_path or not self.connector.documentation_file_path.exists():
            return self.create_check_result(
                passed=False,
                message=f"User facing documentation file {self.connector.documentation_file_path} is missing. Please create it",
            )
        result = CliRunner().invoke(
            validate_metadata, [str(metadata_file_path), str(self.connector.documentation_file_path)], catch_exceptions=False
        )
        if result.exit_code == 0:
            return self.create_check_result(passed=True, message="Metadata file is valid")
        else:
            return self.create_check_result(passed=False, message=f"Metadata file is invalid: {result.output}")


class CheckPublishToPyPiIsEnabled(Check):
    name = "Python connectors must have PyPi publishing enabled"
    description = f"Python connectors must have [PyPi](https://pypi.org/) publishing enabled in their `{consts.METADATA_FILE_NAME}` file. This is declared by setting `remoteRegistries.pypi.enabled` to `true` in {consts.METADATA_FILE_NAME}. This is to ensure that all connectors can be published to PyPi and can be used in `airbyte-lib`."
    category = CheckCategory.CODE_QUALITY
    applies_to_connector_languages = {ConnectorLanguage.PYTHON, ConnectorLanguage.LOW_CODE}

    def _run(self) -> CheckResult:
        if not self.connector.metadata:
            return self.create_check_result(passed=False, message=f"{consts.METADATA_FILE_NAME} file is missing")

        publish_to_pypi_is_enabled = get(self.connector.metadata, "remoteRegistries.pypi.enabled", False)
        if not publish_to_pypi_is_enabled:
            return self.create_check_result(passed=False, message="PyPi publishing is not enabled. Please enable it in the metadata file")
        return self.create_check_result(passed=True, message="PyPi publishing is enabled")


class CheckConnectorLicense(Check):
    name = "Connectors must be licensed under MIT or Elv2"
    description = f"Connectors must be licensed under the MIT or Elv2 license. This is to ensure that all connectors are licensed under a permissive license. More details in our [License FAQ]({consts.LICENSE_FAQ_URL})."
    category = CheckCategory.CODE_QUALITY

    def _run(self) -> CheckResult:
        if not self.connector.metadata:
            return self.create_check_result(passed=False, message=f"{consts.METADATA_FILE_NAME} file is missing")
        metadata_license = get(self.connector.metadata, "license")
        if metadata_license.upper() not in ["MIT", "ELV2"]:
            return self.create_check_result(
                passed=False, message=f"Connector is licensed under {metadata_license}. Please use MIT or Elv2 license"
            )

        if (
            self.connector.language in [ConnectorLanguage.LOW_CODE, ConnectorLanguage.PYTHON]
            and (self.connector.code_directory / consts.PYPROJECT_FILE_NAME).exists()
        ):
            pyproject = toml.load((self.connector.code_directory / consts.PYPROJECT_FILE_NAME))
            if poetry_license := get(pyproject, "tool.poetry.license"):
                if poetry_license != metadata_license:
                    return self.create_check_result(
                        passed=False,
                        message=f"Connector is licensed under {poetry_license} in {consts.PYPROJECT_FILE_NAME}, but licensed under {metadata_license} in {consts.METADATA_FILE_NAME}. These two files have to be consistent",
                    )
            else:
                return self.create_check_result(
                    passed=False, message=f"Connector is missing license in {consts.PYPROJECT_FILE_NAME}. Please add it"
                )
        return self.create_check_result(passed=True, message="Connector is licensed under MIT or ELv2 license")


class CheckVersionFollowsSemver(Check):
    name = "Connector version must follow Semantic Versioning"
    description = f"Connector version must follow the Semantic Versioning scheme. This is to ensure that all connectors follow a consistent versioning scheme. Refer to our [Semantic Versioning for Connectors]({consts.SEMVER_FOR_CONNECTORS_DOC_URL}) for more details."
    category = CheckCategory.CODE_QUALITY

    def _run(self) -> CheckResult:
        if self.connector.metadata is None:
            return self.create_check_result(passed=False, message=f"Connector version is missing in {consts.METADATA_FILE_NAME}")
        if "dockerImageTag" not in self.connector.metadata:
            return self.create_check_result(passed=False, message=f"dockerImageTag is missing in {consts.METADATA_FILE_NAME}")
        try:
            metadata_version = semver.Version.parse(str(self.connector.metadata["dockerImageTag"]))
            if (
                self.connector.language in [ConnectorLanguage.LOW_CODE, ConnectorLanguage.PYTHON]
                and (self.connector.code_directory / consts.PYPROJECT_FILE_NAME).exists()
            ):
                pyproject = toml.load((self.connector.code_directory / consts.PYPROJECT_FILE_NAME))
                poetry_version = semver.Version.parse(str(pyproject["tool"]["poetry"]["version"]))
                if metadata_version != poetry_version:
                    return self.create_check_result(
                        passed=False,
                        message=f"Connector version in {consts.METADATA_FILE_NAME} is {metadata_version}, but version in {consts.PYPROJECT_FILE_NAME} is {poetry_version}. These two files have to be consistent",
                    )
        except ValueError:
            return self.create_check_result(
                passed=False, message=f"Connector version {self.connector.metadata['dockerImageTag']} does not follow Semantic Versioning"
            )
