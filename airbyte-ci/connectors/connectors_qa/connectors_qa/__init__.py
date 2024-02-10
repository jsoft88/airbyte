# Copyright (c) 2023 Airbyte, Inc., all rights reserved.

from connectors_qa import checks

ENABLED_CHECKS = [
    checks.ValidateMetadata(),
    checks.CheckDocumentationExists(),
    checks.CheckDocumentationStructure(),
    checks.CheckChangelogEntry(),
    checks.CheckMigrationGuide(),
    checks.CheckConnectorIconIsAvailable(),
    checks.CheckConnectorUsesHTTPSOnly(),
    checks.CheckConnectorUsesPoetry(),
    checks.CheckConnectorUsesPythonBaseImage(),
    checks.CheckPublishToPyPiIsEnabled(),
    checks.CheckConnectorLicense(),
    checks.CheckVersionFollowsSemver()
]
