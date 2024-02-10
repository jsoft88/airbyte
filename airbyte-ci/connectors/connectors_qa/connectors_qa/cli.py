# Copyright (c) 2023 Airbyte, Inc., all rights reserved.

from itertools import product
from pathlib import Path
from typing import Set

import click
from connector_ops.utils import Connector
from connectors_qa import ENABLED_CHECKS
from connectors_qa.consts import CONNECTORS_QA_DOC_TEMPLATE_NAME
from connectors_qa.models import CheckStatus
from connectors_qa.utils import remove_strict_encrypt_suffix
from jinja2 import Environment, PackageLoader, select_autoescape


@click.group
def connectors_qa():
    pass


@connectors_qa.command("run", help="Run the QA checks on the given connectors.")
@click.option(
    "-n", "--name", "connectors", required=True, multiple=True, help="The technical name of the connector. e.g. 'source-google-sheets'."
)
def run(connectors: Set[Connector]):
    connectors = {Connector(remove_strict_encrypt_suffix(connector)) for connector in connectors}
    check_results = []
    for connector, check in product(connectors, ENABLED_CHECKS):
        check_result = check.run(connector)
        check_results.append(check_result)
        click.echo(check_result)
    failed_checks = [check_result for check_result in check_results if check_result.status is CheckStatus.FAILED]
    if failed_checks:
        raise click.ClickException(f"{len(failed_checks)} checks failed")


@connectors_qa.command("generate-documentation", help="Generate the documentation for the QA checks.")
@click.argument("output_file", type=click.Path(writable=True, dir_okay=False, path_type=Path))
def generate_documentation(output_file: Path):
    checks_by_category = {}
    for check in ENABLED_CHECKS:
        checks_by_category.setdefault(check.category, []).append(check)

    jinja_env = Environment(
        loader=PackageLoader(__package__, "templates"),
        autoescape=select_autoescape(),
        trim_blocks=False,
        lstrip_blocks=True,
    )
    template = jinja_env.get_template(CONNECTORS_QA_DOC_TEMPLATE_NAME)
    documentation = template.render(checks_by_category=checks_by_category)
    output_file.write_text(documentation)
