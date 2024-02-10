# Copyright (c) 2023 Airbyte, Inc., all rights reserved.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Set

from connector_ops.utils import Connector, ConnectorLanguage

ALL_LANGUAGES = {ConnectorLanguage.JAVA, ConnectorLanguage.LOW_CODE, ConnectorLanguage.PYTHON}


class CheckCategory(Enum):
    """The category of a QA check"""

    CODE_QUALITY = "📝 Code Quality"
    DOCUMENTATION = "📄 Documentation"
    ASSETS = "💼 Assets"
    SECURITY = "🔒 Security"


class CheckStatus(Enum):
    """The status of a QA check"""

    PASSED = "Passed"
    FAILED = "Failed"
    SKIPPED = "Skipped"


@dataclass
class CheckResult:
    """The result of a QA check

    Attributes:
        check (Check): The QA check that was run
        status (CheckStatus): The status of the check
        message (str): A message explaining the result of the check
    """

    check: Check
    status: CheckStatus
    message: str

    def __repr__(self) -> str:
        if self.status == CheckStatus.PASSED:
            emoji = "✅"
        elif self.status == CheckStatus.FAILED:
            emoji = "❌"
        else:
            emoji = "🔶"

        return f"{self.check.connector} - {emoji} - {self.status.value} - {self.check.name}: {self.message}."


class Check(ABC):

    connector: Connector | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the QA check

        Raises:
            NotImplementedError: Subclasses must implement name property/attribute

        Returns:
            str: The name of the QA check
        """
        raise NotImplementedError("Subclasses must implement name property/attribute")

    @property
    def required(self) -> bool:
        """Whether the QA check is required

        Returns:
            bool: Whether the QA check is required
        """
        return True

    @property
    @abstractmethod
    def description(self) -> str:
        """A full description of the QA check. Used for documentation purposes.
        It can use markdown syntax.

        Raises:
            NotImplementedError: Subclasses must implement description property/attribute

        Returns:
            str: The description of the QA check
        """
        raise NotImplementedError("Subclasses must implement description property/attribute")

    @property
    def applies_to_connector_languages(self) -> Set[ConnectorLanguage]:
        """The connector languages that the QA check applies to

        Raises:
            NotImplementedError: Subclasses must implement applies_to_connector_languages property/attribute

        Returns:
            Set[ConnectorLanguage]: The connector languages that the QA check applies to
        """
        return ALL_LANGUAGES

    @property
    @abstractmethod
    def category(self) -> CheckCategory:
        """The category of the QA check

        Raises:
            NotImplementedError: Subclasses must implement category property/attribute

        Returns:
            CheckCategory: The category of the QA check
        """
        raise NotImplementedError("Subclasses must implement category property/attribute")

    def run(self, connector: Connector) -> CheckResult:
        self.connector = connector
        if self.connector.language not in self.applies_to_connector_languages:
            return self.skip(f"Check does not apply to {self.connector.language.value} connectors")
        return self._run()

    def _run(self) -> CheckResult:
        raise NotImplementedError("Subclasses must implement run method")

    def skip(self, reason: str) -> CheckResult:
        return CheckResult(check=self, status=CheckStatus.SKIPPED, message=reason)

    def create_check_result(self, passed: bool, message: str) -> CheckResult:
        status = CheckStatus.PASSED if passed else CheckStatus.FAILED
        return CheckResult(check=self, status=status, message=message)
