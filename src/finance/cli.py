"""Command-line interface for the finance project.

The main initial command is importing a Splitwise JSON backup into the database.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import click

from finance.core.database import SessionLocal, init_db
from finance.core.models import Transaction
from finance.ingestion import (
    SplitwiseParser,
    BankCsvParser,
    HDFCCreditCardParser,
    ICICICreditCardParser,
)
from finance.ingestion.parsers.hdfc import create_hdfc_parser
from finance.ingestion.parsers.icici import create_icici_parser
from finance.processing.pipeline import process_transactions
from finance.processing.reconciler import reconcile_splitwise_against_bank
from finance.services.import_service import import_raw_transactions, import_splitwise_transactions, summarize_parse_errors_warnings
from finance.ingestion.registry import ParserRegistry
# Import parsers to ensure registration
import finance.ingestion.parsers  # noqa: F401

@click.group()
def main() -> None:
    """Personal finance data tools."""


def _reconciliation_to_dict(result) -> dict | None:
    recon = getattr(result, "reconciliation", None)
    if recon is None:
        return None
    return {
        "expected_total": str(recon.expected_total) if recon.expected_total is not None else None,
        "actual_total": str(recon.actual_total),
        "difference": str(recon.difference) if recon.difference is not None else None,
        "matches": bool(recon.matches),
        "expected_count": recon.expected_count,
        "actual_count": recon.actual_count,
    }


def _metadata_with_reconciliation(result) -> dict:
    payload = dict(result.metadata or {})
    recon = _reconciliation_to_dict(result)
    if recon is not None:
        payload["reconciliation"] = recon
    return payload


def _echo_reconciliation(result) -> None:
    recon = _reconciliation_to_dict(result)
    if recon is None:
        return

    status = "MATCH" if recon["matches"] else "MISMATCH"
    click.echo(
        "Reconciliation: "
        f"{status} expected={recon['expected_total']} "
        f"actual={recon['actual_total']} diff={recon['difference']}"
    )


def _reconciliation_error(result) -> str | None:
    recon = getattr(result, "reconciliation", None)
    if recon is None:
        return None
    if recon.expected_total is None:
        return None
    if recon.matches:
        return None
    return (
        "Reconciliation mismatch: "
        f"expected={recon.expected_total} "
        f"actual={recon.actual_total} "
        f"diff={recon.difference}"
    )


def _seed_profiles_dir(target_dir: Path) -> tuple[int, int]:
    """Copy bundled seed profiles into target directory if missing."""
    target_dir.mkdir(parents=True, exist_ok=True)
    # Profiles are now embedded in parser modules, so just create the directory
    return 0, 0


@main.command("init")
def init_command() -> None:
    """Initialize the project for first-time setup.
    
    Creates necessary directories, database, and sample .env file.
    """
    from finance.core.config import settings
    
    click.echo("🚀 Initializing Personal Finance Tracker...")
    click.echo("")
    
    # 1. Create data directories
    dirs_to_create = [
        settings.DATA_DIR,
        settings.DB_DIR,
        settings.RAW_DIR,
        settings.IMPORTS_DIR,
        settings.PROFILES_DIR,
    ]
    
    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        click.echo(f"  ✓ Created {dir_path}")
    
    # 2. Initialize database
    click.echo("")
    click.echo("📦 Initializing database...")
    init_db()
    click.echo(f"  ✓ Database ready at {settings.DB_DIR / 'finance.db'}")
    
    # 3. Create .env.example if not exists
    env_example = Path(".env.example")
    if not env_example.exists():
        env_example.write_text("""# Database (default: data/db/finance.db)
# DATABASE_URL=sqlite:///data/db/finance.db

# PDF Passwords for credit card statements
HDFC_CC_PASSWORD=your_password_here
ICICI_CC_PASSWORD=your_password_here

# Application
DEBUG=false
""")
        click.echo(f"  ✓ Created {env_example}")
    
    # 4. Seed categories if needed
    from finance.core.database import SessionLocal
    from finance.core.models import Category
    
    db = SessionLocal()
    try:
        category_count = db.query(Category).count()
        if category_count == 0:
            click.echo("")
            click.echo("📂 Seeding default categories...")
            # Import and run the seed script
            try:
                from scripts.seed_categories import seed_categories
                seed_categories(db)
                click.echo("  ✓ Default categories created")
            except ImportError:
                click.echo("  ⚠ Category seeder not found. Run manually if needed.")
        else:
            click.echo(f"  ✓ {category_count} categories already exist")
    finally:
        db.close()

    # 5. Seed profile JSON files
    click.echo("")
    click.echo("🧩 Seeding parser profiles...")
    created, skipped = _seed_profiles_dir(settings.PROFILES_DIR)
    click.echo(f"  ✓ Profiles created: {created}")
    click.echo(f"  ✓ Profiles already present: {skipped}")
    
    click.echo("")
    click.echo("✅ Initialization complete!")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Copy .env.example to .env and fill in your passwords")
    click.echo("  2. Place your bank statements in data/raw/")
    click.echo("  3. Run: finance import")
    click.echo("")

@main.command("auto-import")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--password", "-p", help="Password for encrypted files")
@click.option("--password-env", help="Environment variable name for password (e.g., HDFC_CC_PASSWORD)")
@click.option("--min-confidence", type=float, default=None, help="Minimum confidence threshold (0-1)")
@click.option("--dry-run", is_flag=True, help="Show detection results without importing")
def auto_import_command(
    file_path: Path,
    password: Optional[str],
    password_env: Optional[str],
    min_confidence: Optional[float],
    dry_run: bool
) -> None:
    """Automatically detect parser and import file.

    This is the easiest way to import - just point to your file and the system
    figures out which parser to use based on content analysis.

    Examples:
        finance auto-import statement.pdf
        finance auto-import statement.pdf --password-env HDFC_CC_PASSWORD
        finance auto-import statement.pdf --dry-run  # See detection without importing
    """
    from finance.ingestion.auto_detect import get_parser_suggestions, auto_import

    click.echo(f"🔍 Analyzing {file_path.name}...")
    click.echo()

    # Show suggestions
    suggestions = get_parser_suggestions(file_path, top_n=3, password=password)
    if suggestions:
        click.echo("Top parser matches:")
        for name, conf, meta in suggestions:
            bank = (meta.get("bank") or "unknown").upper()
            product = (meta.get("product") or "statement").replace("_", " ")
            click.echo(f"  {conf:>5.0%}  {bank:10}  {product:15}  ({name})")
        click.echo()

    if dry_run:
        click.echo("Dry-run mode - not importing.")
        return

    # Perform auto-import
    result = auto_import(file_path, password, password_env, min_confidence)

    if result['success']:
        parser_meta = result.get('parser_metadata', {})
        click.echo(f"✓ Detected: {parser_meta.get('entity', 'unknown')} {parser_meta.get('entity_type', 'unknown')}")
        click.echo(f"✓ Confidence: {result['confidence']:.0%}")
        click.echo(f"✓ Parser: {result['parser_used']}")
        recon = result.get("reconciliation")
        if recon is not None:
            status = "MATCH" if recon.get("matches") else "MISMATCH"
            click.echo(
                "✓ Reconciliation: "
                f"{status} expected={recon.get('expected_total')} "
                f"actual={recon.get('actual_total')} diff={recon.get('difference')}"
            )
        warnings = result.get("warnings") or []
        if warnings:
            click.echo(f"✓ Parse warnings: {len(warnings)}")
        click.echo()
        click.echo(f"✓ Imported {result['transactions_imported']} transactions")
        click.echo()
        click.echo("View dashboard: finance web")
    else:
        click.echo("❌ Import failed:", err=True)
        for error in result['errors']:
            click.echo(f"  - {error}", err=True)
        click.echo()
        click.echo("Try manual import with: finance import", err=True)


@main.command("import")
@click.option("--file", "file_path", type=click.Path(exists=True, path_type=Path), help="File to import")
def import_wizard_command(file_path: Optional[Path]) -> None:
    """Interactive import wizard."""
    if not file_path:
        file_path = click.prompt("Enter file path", type=click.Path(exists=True, path_type=Path))

    parsers = ParserRegistry.list_parsers()
    
    # 1. Ask for parser/bank
    click.echo("\nAvailable Parsers:")
    for idx, p in enumerate(parsers, 1):
        click.echo(f"{idx}. {p['name']} ({p['description']})")
    
    choice = click.prompt("Select parser", type=click.IntRange(1, len(parsers)))
    selected_parser_meta = parsers[choice - 1]
    parser_name = selected_parser_meta["name"]
    parser_cls = ParserRegistry.get(parser_name)
    
    # 2. Collect arguments
    kwargs = {}
    if "password" in selected_parser_meta["required_args"]:
        # Try to guess env var name based on parser name
        env_var = f"{parser_name.upper()}_PDF_PASSWORD"
        kwargs["password"] = click.prompt("PDF Password", hide_input=True, default=os.getenv(env_var, ""))
    
    if "profile" in selected_parser_meta["required_args"]:
        # TODO: List profiles if possible, for now just text
        kwargs["profile"] = click.prompt("Bank Profile (e.g., generic_drcr, hdfc_bank)", default="generic_drcr")

    # 3. Instantiate and Parse
    try:
        parser = parser_cls(**kwargs)
    except Exception as e:
        click.echo(f"Error checking requirements: {e}", err=True)
        return

    if not parser.can_parse(file_path):
        click.echo(f"Parser '{parser_name}' cannot parse this file. Check format/password.", err=True)
        return

    click.echo(f"Parsing {file_path} with {parser_name}...")
    result = parser.parse(file_path)

    if result.errors:
        click.echo("Errors during parsing:", err=True)
        for err in result.errors:
            click.echo(f"- {err}", err=True)
        return
    recon_error = _reconciliation_error(result)
    if recon_error:
        click.echo(recon_error, err=True)
        return

    # 4. Save
    db = SessionLocal()
    try:
        created = import_raw_transactions(
            db,
            raw_transactions=result.transactions,
            file_path=file_path,
            source_type=result.source_type,
            file_hash=result.file_hash,
            file_size=result.file_size,
            metadata=_metadata_with_reconciliation(result),
        )

        if created:
            new_txns = (
                db.query(Transaction)
                .order_by(Transaction.id.desc())
                .limit(created)
                .all()
            )
            process_transactions(db, new_txns)
            
        summary = summarize_parse_errors_warnings(result)
        click.echo(
            f"\nImport complete.\n"
            f"Parsed: {summary['record_count']}\n"
            f"Inserted: {created}\n"
            f"Errors: {len(summary['errors'])}\n"
            f"Warnings: {len(summary['warnings'])}"
        )
        _echo_reconciliation(result)
    finally:
        db.close()


@main.command("list-parsers")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON for agents")
def list_parsers_command(json_output: bool) -> None:
    """List available parsers."""
    parsers = ParserRegistry.list_parsers()
    if json_output:
        click.echo(json.dumps(parsers, indent=2))
    else:
        for p in parsers:
            click.echo(f"- {p['name']}: {p['description']}")
            click.echo(f"  Formats: {', '.join(p['supported_formats'])}")
            click.echo(f"  Args: {', '.join(p['required_args'])}")
            click.echo("")

@main.command("parser-info")
@click.argument("parser_name")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON for agents")
@click.option("--extended", "-e", is_flag=True, help="Show extended metadata")
def parser_info_command(parser_name: str, json_output: bool, extended: bool) -> None:
    """Get details about a specific parser.

    Use --extended to see example inputs, field mappings, and other metadata.
    """
    try:
        info = ParserRegistry.get_parser_metadata(parser_name)
    except KeyError:
        click.echo(f"Parser '{parser_name}' not found.", err=True)
        sys.exit(1)

    if json_output:
        click.echo(json.dumps(info, indent=2))
    else:
        click.echo(f"Name: {info['name']}")
        click.echo(f"Description: {info['description']}")
        click.echo(f"Formats: {', '.join(info.get('supported_formats', []))}")
        click.echo(f"Required Args: {', '.join(info.get('required_args', []))}")

        if extended:
            click.echo()
            click.echo("Extended Metadata:")
            if info.get('example_input'):
                click.echo(f"  Example Input: {info['example_input']}")
            if info.get('field_mappings'):
                click.echo(f"  Field Mappings: {info['field_mappings']}")
            if info.get('parser_version'):
                click.echo(f"  Version: {info['parser_version']}")
            if info.get('author'):
                click.echo(f"  Author: {info['author']}")
            if info.get('documentation_url'):
                click.echo(f"  Docs: {info['documentation_url']}")


@main.command("init-db")
def init_db_command() -> None:
    """Create all database tables using the current models."""
    init_db()
    click.echo("Database initialized.")


@main.command("import-splitwise")
@click.argument("backup_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--current-user-id",
    type=int,
    default=None,
    help="Optional Splitwise user id of the current user. "
    "If omitted, it will be taken from the backup file.",
)
def import_splitwise_command(backup_path: Path, current_user_id: Optional[int]) -> None:
    """Import a Splitwise JSON backup file into the database.

    Uses split-aware import: computes your actual share of each expense,
    creates person merchants, and populates transaction splits.
    """
    parser = SplitwiseParser(current_user_id=current_user_id)

    if not parser.can_parse(backup_path):
        click.echo("File does not look like a valid Splitwise backup JSON.", err=True)
        sys.exit(1)

    result = parser.parse(backup_path)

    if result.errors:
        click.echo("Errors while parsing Splitwise backup:", err=True)
        for err in result.errors:
            click.echo(f"- {err}", err=True)
        sys.exit(1)

    db = SessionLocal()
    try:
        import_result = import_splitwise_transactions(
            db,
            raw_transactions=result.transactions,
            file_path=backup_path,
            source_type=result.source_type,
            file_hash=result.file_hash,
            file_size=result.file_size,
            persons=parser.get_persons(),
            groups=parser.get_groups(),
            current_user_id=parser.current_user_id,
            metadata=_metadata_with_reconciliation(result),
        )

        created = import_result["created"]
        if created:
            new_txns = (
                db.query(Transaction)
                .order_by(Transaction.id.desc())
                .limit(created)
                .all()
            )
            process_transactions(db, new_txns)
    finally:
        db.close()

    summary = summarize_parse_errors_warnings(result)
    click.echo(
        f"Splitwise import complete.\n"
        f"  Parsed:          {summary['record_count']}\n"
        f"  Created:         {import_result['created']}\n"
        f"  Updated:         {import_result['updated']}\n"
        f"  Auto-created:    {import_result['auto_created']} (friend-paid expenses)\n"
        f"  Persons:         {import_result['persons_imported']}\n"
        f"  Errors:          {len(summary['errors'])}\n"
        f"  Warnings:        {len(summary['warnings'])}"
    )


@main.command("import-bank-csv")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--profile",
    type=str,
    default="generic_drcr",
    help="Bank CSV profile to use (e.g. generic_drcr)",
)
def import_bank_csv_command(csv_path: Path, profile: str) -> None:
    """Import a bank CSV file using a configured profile and process it."""
    parser = BankCsvParser(profile=profile)
    if not parser.can_parse(csv_path):
        click.echo("File does not look like a CSV bank statement.", err=True)
        sys.exit(1)

    result = parser.parse(csv_path)
    if result.errors:
        click.echo("Errors while parsing bank CSV:", err=True)
        for err in result.errors:
            click.echo(f"- {err}", err=True)
        sys.exit(1)

    db = SessionLocal()
    try:
        created = import_raw_transactions(
            db,
            raw_transactions=result.transactions,
            file_path=csv_path,
            source_type=result.source_type,
            file_hash=result.file_hash,
            file_size=result.file_size,
            metadata=_metadata_with_reconciliation(result),
        )

        new_txns = (
            db.query(Transaction)
            .order_by(Transaction.id.desc())
            .limit(created)
            .all()
        )
        process_transactions(db, new_txns)
    finally:
        db.close()

    summary = summarize_parse_errors_warnings(result)
    click.echo(
        f"Bank CSV import complete. Parsed={summary['record_count']} "
        f"Inserted={created} Errors={len(summary['errors'])} "
        f"Warnings={len(summary['warnings'])}"
    )


@main.command("reconcile")
@click.option("--dry-run", is_flag=True, help="Preview reconciliation without applying changes")
def reconcile_command(dry_run: bool) -> None:
    """Run reconciliation between Splitwise and bank transactions.

    Matches Splitwise expenses and settlements against bank transactions,
    then sets effective_amount on bank records and marks Splitwise duplicates
    as excluded to prevent double-counting in reports.
    """
    db = SessionLocal()
    try:
        result = reconcile_splitwise_against_bank(db, dry_run=dry_run)
    finally:
        db.close()

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(
        f"{prefix}Reconciliation complete.\n"
        f"  Total pairs:     {result['total_pairs']}\n"
        f"  Expense matches: {result['expense_pairs']}\n"
        f"  Settlements:     {result['settlement_pairs']}"
    )

    if result["changes"] and dry_run:
        click.echo("\nPreview of changes:")
        for c in result["changes"][:20]:
            if c["type"] == "settlement":
                click.echo(f"  SETTLEMENT: {c['sw_desc'][:40]} <-> {c['bank_desc'][:40]} ({c['amount']})")
            else:
                click.echo(f"  EXPENSE: {c['sw_desc'][:40]} <-> {c['bank_desc'][:40]} (full={c['full_amount']}, share={c['effective_amount']})")
        if len(result["changes"]) > 20:
            click.echo(f"  ... and {len(result['changes']) - 20} more")


@main.command("import-hdfc-cc")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option("--password", envvar="HDFC_PDF_PASSWORD", help="PDF password (or set HDFC_PDF_PASSWORD env var)")
def import_hdfc_cc_command(pdf_path: Path, password: Optional[str]) -> None:
    """Import a single HDFC credit card PDF statement."""

    if not password:
        click.echo("Error: Password required. Use --password or set HDFC_PDF_PASSWORD env var", err=True)
        sys.exit(1)

    parser = create_hdfc_parser(password)

    if not parser.can_parse(pdf_path):
        click.echo(f"Cannot parse {pdf_path} - invalid PDF or wrong password", err=True)
        sys.exit(1)

    result = parser.parse(pdf_path)

    if result.errors:
        click.echo("Errors while parsing:", err=True)
        for err in result.errors:
            click.echo(f"- {err}", err=True)
        sys.exit(1)
    recon_error = _reconciliation_error(result)
    if recon_error:
        click.echo(recon_error, err=True)
        sys.exit(1)

    db = SessionLocal()
    try:
        created = import_raw_transactions(
            db,
            raw_transactions=result.transactions,
            file_path=pdf_path,
            source_type=result.source_type,
            file_hash=result.file_hash,
            file_size=result.file_size,
            metadata=_metadata_with_reconciliation(result),
        )

        if created:
            new_txns = (
                db.query(Transaction)
                .order_by(Transaction.id.desc())
                .limit(created)
                .all()
            )
            process_transactions(db, new_txns)
    finally:
        db.close()

    summary = summarize_parse_errors_warnings(result)
    click.echo(
        f"HDFC import complete. Parsed={summary['record_count']} "
        f"Inserted={created} Errors={len(summary['errors'])} "
        f"Warnings={len(summary['warnings'])}"
    )
    _echo_reconciliation(result)


@main.command("import-hdfc-batch")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--password", envvar="HDFC_PDF_PASSWORD", help="PDF password (or set HDFC_PDF_PASSWORD env var)")
def import_hdfc_batch_command(directory: Path, password: Optional[str]) -> None:
    """Import all HDFC credit card PDFs from a directory."""

    if not password:
        click.echo("Error: Password required. Use --password or set HDFC_PDF_PASSWORD env var", err=True)
        sys.exit(1)

    pdf_files = sorted(directory.glob("*.pdf"))

    if not pdf_files:
        click.echo(f"No PDF files found in {directory}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(pdf_files)} PDF files")
    parser = create_hdfc_parser(password)

    total_created = 0
    total_parsed = 0
    failed = []

    for pdf_file in pdf_files:
        click.echo(f"Processing {pdf_file.name}...", nl=False)

        try:
            if not parser.can_parse(pdf_file):
                click.echo(" SKIP (cannot parse)")
                failed.append(pdf_file.name)
                continue

            result = parser.parse(pdf_file)

            if result.errors:
                click.echo(f" ERROR: {result.errors[0]}")
                failed.append(pdf_file.name)
                continue
            recon_error = _reconciliation_error(result)
            if recon_error:
                click.echo(f" ERROR: {recon_error}")
                failed.append(pdf_file.name)
                continue

            db = SessionLocal()
            try:
                created = import_raw_transactions(
                    db,
                    raw_transactions=result.transactions,
                    file_path=pdf_file,
                    source_type=result.source_type,
                    file_hash=result.file_hash,
                    file_size=result.file_size,
                    metadata=_metadata_with_reconciliation(result),
                )

                if created:
                    new_txns = (
                        db.query(Transaction)
                        .order_by(Transaction.id.desc())
                        .limit(created)
                        .all()
                    )
                    process_transactions(db, new_txns)

                total_created += created
                total_parsed += len(result.transactions)
                click.echo(f" OK (parsed={len(result.transactions)}, inserted={created})")
                _echo_reconciliation(result)

            finally:
                db.close()

        except Exception as e:
            click.echo(f" ERROR: {str(e)}")
            failed.append(pdf_file.name)

    click.echo(f"\n✅ Batch import complete:")
    click.echo(f"   Files processed: {len(pdf_files)}")
    click.echo(f"   Total parsed: {total_parsed}")
    click.echo(f"   Total inserted: {total_created}")
    if failed:
        click.echo(f"   Failed: {len(failed)}")
        for name in failed[:10]:
            click.echo(f"      - {name}")


@main.command("import-hdfc-bank")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option("--password", envvar="HDFC_PDF_PASSWORD", help="PDF password (or set HDFC_PDF_PASSWORD env var)")
def import_hdfc_bank_command(pdf_path: Path, password: Optional[str]) -> None:
    """Import a single HDFC Bank Account PDF statement."""

    if not password:
        click.echo("Error: Password required. Use --password or set HDFC_PDF_PASSWORD env var", err=True)
        sys.exit(1)

    from finance.ingestion.bank_account_pdf import create_hdfc_bank_parser
    parser = create_hdfc_bank_parser(password)

    if not parser.can_parse(pdf_path):
        click.echo(f"Cannot parse {pdf_path} - invalid PDF, wrong password, or not an HDFC Bank statement", err=True)
        sys.exit(1)

    result = parser.parse(pdf_path)

    if result.errors:
        click.echo("Errors while parsing:", err=True)
        for err in result.errors:
            click.echo(f"- {err}", err=True)
        sys.exit(1)
    recon_error = _reconciliation_error(result)
    if recon_error:
        click.echo(recon_error, err=True)
        sys.exit(1)

    db = SessionLocal()
    try:
        created = import_raw_transactions(
            db,
            raw_transactions=result.transactions,
            file_path=pdf_path,
            source_type=result.source_type,
            file_hash=result.file_hash,
            file_size=result.file_size,
            metadata=_metadata_with_reconciliation(result),
        )

        if created:
            new_txns = (
                db.query(Transaction)
                .order_by(Transaction.id.desc())
                .limit(created)
                .all()
            )
            process_transactions(db, new_txns)
    finally:
        db.close()

    summary = summarize_parse_errors_warnings(result)
    click.echo(
        f"HDFC Bank import complete. Parsed={summary['record_count']} "
        f"Inserted={created} Errors={len(summary['errors'])} "
        f"Warnings={len(summary['warnings'])}"
    )
    _echo_reconciliation(result)


@main.command("import-icici-cc")
@click.argument("pdf_path", type=click.Path(exists=True, path_type=Path))
@click.option("--password", envvar="ICICI_PDF_PASSWORD", help="PDF password (or set ICICI_PDF_PASSWORD env var)")
def import_icici_cc_command(pdf_path: Path, password: Optional[str]) -> None:
    """Import a single ICICI credit card PDF statement."""

    if not password:
        click.echo("Error: Password required. Use --password or set ICICI_PDF_PASSWORD env var", err=True)
        sys.exit(1)

    parser = create_icici_parser(password)

    if not parser.can_parse(pdf_path):
        click.echo(f"Cannot parse {pdf_path} - invalid PDF or wrong password", err=True)
        sys.exit(1)

    result = parser.parse(pdf_path)

    if result.errors:
        click.echo("Errors while parsing:", err=True)
        for err in result.errors:
            click.echo(f"- {err}", err=True)
        sys.exit(1)
    recon_error = _reconciliation_error(result)
    if recon_error:
        click.echo(recon_error, err=True)
        sys.exit(1)

    db = SessionLocal()
    try:
        created = import_raw_transactions(
            db,
            raw_transactions=result.transactions,
            file_path=pdf_path,
            source_type=result.source_type,
            file_hash=result.file_hash,
            file_size=result.file_size,
            metadata=_metadata_with_reconciliation(result),
        )

        if created:
            new_txns = (
                db.query(Transaction)
                .order_by(Transaction.id.desc())
                .limit(created)
                .all()
            )
            process_transactions(db, new_txns)
    finally:
        db.close()

    summary = summarize_parse_errors_warnings(result)
    click.echo(
        f"ICICI import complete. Parsed={summary['record_count']} "
        f"Inserted={created} Errors={len(summary['errors'])} "
        f"Warnings={len(summary['warnings'])}"
    )
    _echo_reconciliation(result)


@main.command("import-icici-batch")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--password", envvar="ICICI_PDF_PASSWORD", help="PDF password (or set ICICI_PDF_PASSWORD env var)")
def import_icici_batch_command(directory: Path, password: Optional[str]) -> None:
    """Import all ICICI credit card PDFs from a directory."""

    if not password:
        click.echo("Error: Password required. Use --password or set ICICI_PDF_PASSWORD env var", err=True)
        sys.exit(1)

    pdf_files = sorted(directory.glob("*.pdf"))

    if not pdf_files:
        click.echo(f"No PDF files found in {directory}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(pdf_files)} PDF files")
    parser = create_icici_parser(password)

    total_created = 0
    total_parsed = 0
    failed = []

    for pdf_file in pdf_files:
        click.echo(f"Processing {pdf_file.name}...", nl=False)

        try:
            if not parser.can_parse(pdf_file):
                click.echo(" SKIP (cannot parse)")
                failed.append(pdf_file.name)
                continue

            result = parser.parse(pdf_file)

            if result.errors:
                click.echo(f" ERROR: {result.errors[0]}")
                failed.append(pdf_file.name)
                continue
            recon_error = _reconciliation_error(result)
            if recon_error:
                click.echo(f" ERROR: {recon_error}")
                failed.append(pdf_file.name)
                continue

            db = SessionLocal()
            try:
                created = import_raw_transactions(
                    db,
                    raw_transactions=result.transactions,
                    file_path=pdf_file,
                    source_type=result.source_type,
                    file_hash=result.file_hash,
                    file_size=result.file_size,
                    metadata=_metadata_with_reconciliation(result),
                )

                if created:
                    new_txns = (
                        db.query(Transaction)
                        .order_by(Transaction.id.desc())
                        .limit(created)
                        .all()
                    )
                    process_transactions(db, new_txns)

                total_created += created
                total_parsed += len(result.transactions)
                click.echo(f" OK (parsed={len(result.transactions)}, inserted={created})")
                _echo_reconciliation(result)

            finally:
                db.close()

        except Exception as e:
            click.echo(f" ERROR: {str(e)}")
            failed.append(pdf_file.name)

    click.echo(f"\n✅ Batch import complete:")
    click.echo(f"   Files processed: {len(pdf_files)}")
    click.echo(f"   Total parsed: {total_parsed}")
    click.echo(f"   Total inserted: {total_created}")
    if failed:
        click.echo(f"   Failed: {len(failed)}")
        for name in failed[:10]:
            click.echo(f"      - {name}")


@main.command("recategorize")
@click.option("--merchant-id", type=int, help="Only recategorize transactions from this merchant")
@click.option("--dry-run", is_flag=True, default=True, help="Preview changes without applying")
@click.option("--apply", "apply_changes", is_flag=True, help="Apply changes (opposite of dry-run)")
def recategorize_command(merchant_id: Optional[int], dry_run: bool, apply_changes: bool) -> None:
    """Re-run categorization on existing transactions."""

    # If --apply is specified, turn off dry-run
    if apply_changes:
        dry_run = False

    db = SessionLocal()
    try:
        result = bulk_recategorize(
            db,
            merchant_id=merchant_id,
            dry_run=dry_run
        )

        click.echo(f"Checked: {result['total_checked']} transactions")
        click.echo(f"Changed: {result['changed']} transactions")

        if result['changed'] > 0 and result['changes']:
            click.echo("\nSample changes:")
            for change in result['changes'][:10]:
                click.echo(
                    f"  • {change['description'][:50]} "
                    f"→ Category {change['after_category']} "
                    f"(was {change['before_category']})"
                )

        if dry_run:
            click.echo("\n⚠️  DRY RUN - No changes applied. Use --apply to commit changes.")
        else:
            click.echo(f"\n✅ Applied {result['changed']} categorization changes")

    finally:
        db.close()


@main.command("update-rule-metadata")
@click.option("--dry-run", is_flag=True, default=True, help="Preview changes without applying")
@click.option("--apply", "apply_changes", is_flag=True, help="Apply changes (opposite of dry-run)")
def update_rule_metadata_command(dry_run: bool, apply_changes: bool) -> None:
    """Update applied_rule_id for all existing transactions.
    
    This re-runs categorization logic to populate the applied_rule_id field
    for historical transactions, enabling rule tracking and analytics.
    """
    from finance.processing.categorizer import apply_categorization
    
    # If --apply is specified, turn off dry-run
    if apply_changes:
        dry_run = False

    db = SessionLocal()
    try:
        # Get all transactions
        transactions = db.query(Transaction).all()
        total = len(transactions)
        
        click.echo(f"Processing {total} transactions...")
        
        updated = 0
        with click.progressbar(transactions, label='Updating rule metadata') as bar:
            for tx in bar:
                # Store original value
                original_rule_id = tx.applied_rule_id
                
                # Re-run categorization to set applied_rule_id
                apply_categorization(db, tx)
                
                # Check if it changed
                if tx.applied_rule_id != original_rule_id:
                    updated += 1
        
        if not dry_run:
            db.commit()
            click.echo(f"\n✅ Updated {updated} transactions with rule metadata")
        else:
            db.rollback()
            click.echo(f"\n⚠️  DRY RUN - Would update {updated} transactions. Use --apply to commit changes.")
            
    finally:
        db.close()



@main.command("clean-and-reimport")
@click.option("--skip-splitwise", is_flag=True, help="Skip splitwise import")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def clean_and_reimport_command(skip_splitwise: bool, yes: bool) -> None:
    """Delete all transactions and reimport from data/raw directory.

    This will:
    1. Delete all transactions and source files
    2. Auto-import all files from data/raw/
    """
    from finance.core.config import settings
    from finance.core.models import SourceFile

    db = SessionLocal()
    try:
        # Count existing data
        tx_count = db.query(Transaction).count()
        source_count = db.query(SourceFile).count()

        click.echo(f"⚠️  WARNING: This will delete:")
        click.echo(f"   - {tx_count} transactions")
        click.echo(f"   - {source_count} source files")
        click.echo()

        if not yes:
            if not click.confirm("Are you sure you want to proceed?"):
                click.echo("Aborted.")
                return

        # Delete all data
        click.echo("🗑️  Deleting existing data...")
        db.query(Transaction).delete()
        db.query(SourceFile).delete()
        db.commit()
        click.echo("   ✓ Deleted all transactions and source files")
        click.echo()

    finally:
        db.close()

    # Now reimport everything
    raw_dir = settings.RAW_DIR
    click.echo(f"📂 Scanning {raw_dir} for files...")
    click.echo()

    total_imported = 0

    # 1. Import Splitwise if exists
    if not skip_splitwise:
        splitwise_file = raw_dir / "splitwise_backup.json"
        if splitwise_file.exists():
            click.echo("📊 Importing Splitwise...")
            try:
                parser = SplitwiseParser()
                if parser.can_parse(splitwise_file):
                    result = parser.parse(splitwise_file)
                    if not result.errors:
                        db = SessionLocal()
                        try:
                            import_result = import_splitwise_transactions(
                                db,
                                raw_transactions=result.transactions,
                                file_path=splitwise_file,
                                source_type=result.source_type,
                                file_hash=result.file_hash,
                                file_size=result.file_size,
                                persons=parser.get_persons(),
                                groups=parser.get_groups(),
                                current_user_id=parser.current_user_id,
                                metadata=_metadata_with_reconciliation(result),
                            )
                            created = import_result["created"]
                            if created:
                                new_txns = db.query(Transaction).order_by(Transaction.id.desc()).limit(created).all()
                                process_transactions(db, new_txns)
                            click.echo(f"   ✓ Imported {created} Splitwise transactions ({import_result['auto_created']} friend-paid)")
                            total_imported += created
                        finally:
                            db.close()
            except Exception as e:
                click.echo(f"   ✗ Error: {e}", err=True)
            click.echo()

    # 2. Import HDFC CC batch
    hdfc_cc_dir = raw_dir / "hdfc_cc"
    if hdfc_cc_dir.exists():
        # Match both .pdf and .PDF extensions
        pdf_files = sorted(list(hdfc_cc_dir.glob("*.pdf")) + list(hdfc_cc_dir.glob("*.PDF")))
        if pdf_files:
            click.echo(f"💳 Importing {len(pdf_files)} HDFC Credit Card statements...")
            password = settings.HDFC_CC_PASSWORD or settings.HDFC_PDF_PASSWORD
            if password:
                parser = create_hdfc_parser(password)
                for pdf_file in pdf_files:
                    try:
                        if parser.can_parse(pdf_file):
                            result = parser.parse(pdf_file)
                            if result.errors:
                                click.echo(f"   ✗ {pdf_file.name}: {result.errors[0]}", err=True)
                                continue

                            db = SessionLocal()
                            try:
                                created = import_raw_transactions(
                                    db,
                                    raw_transactions=result.transactions,
                                    file_path=pdf_file,
                                    source_type=result.source_type,
                                    file_hash=result.file_hash,
                                    file_size=result.file_size,
                                    metadata=_metadata_with_reconciliation(result),
                                )
                                if created:
                                    new_txns = db.query(Transaction).order_by(Transaction.id.desc()).limit(created).all()
                                    process_transactions(db, new_txns)

                                recon_err = _reconciliation_error(result)
                                status = "⚠" if recon_err else "✓"
                                click.echo(f"   {status} {pdf_file.name}: {created} txns")
                                total_imported += created
                            finally:
                                db.close()
                    except Exception as e:
                        click.echo(f"   ✗ {pdf_file.name}: {e}", err=True)
            else:
                click.echo("   ✗ HDFC_CC_PASSWORD not set", err=True)
            click.echo()

    # 3. Import ICICI batch
    icici_dir = raw_dir / "icici"
    if icici_dir.exists():
        # Match both .pdf and .PDF extensions
        pdf_files = sorted(list(icici_dir.glob("*.pdf")) + list(icici_dir.glob("*.PDF")))
        if pdf_files:
            click.echo(f"💳 Importing {len(pdf_files)} ICICI Credit Card statements...")
            password = settings.ICICI_CC_PASSWORD or settings.ICICI_PDF_PASSWORD
            if password:
                parser = create_icici_parser(password)
                for pdf_file in pdf_files:
                    try:
                        if parser.can_parse(pdf_file):
                            result = parser.parse(pdf_file)
                            if result.errors:
                                click.echo(f"   ✗ {pdf_file.name}: {result.errors[0]}", err=True)
                                continue

                            db = SessionLocal()
                            try:
                                created = import_raw_transactions(
                                    db,
                                    raw_transactions=result.transactions,
                                    file_path=pdf_file,
                                    source_type=result.source_type,
                                    file_hash=result.file_hash,
                                    file_size=result.file_size,
                                    metadata=_metadata_with_reconciliation(result),
                                )
                                if created:
                                    new_txns = db.query(Transaction).order_by(Transaction.id.desc()).limit(created).all()
                                    process_transactions(db, new_txns)

                                recon_err = _reconciliation_error(result)
                                status = "⚠" if recon_err else "✓"
                                click.echo(f"   {status} {pdf_file.name}: {created} txns")
                                total_imported += created
                            finally:
                                db.close()
                    except Exception as e:
                        click.echo(f"   ✗ {pdf_file.name}: {e}", err=True)
            else:
                click.echo("   ✗ ICICI_CC_PASSWORD not set", err=True)
            click.echo()

    # 4. Import Bank Account PDFs
    bank_pdfs = list(raw_dir.glob("5010*.pdf")) + list(raw_dir.glob("5010*.PDF"))
    if bank_pdfs:
        click.echo(f"🏦 Importing {len(bank_pdfs)} HDFC Bank Account statements...")
        # Check for HDFC_BANK_PASSWORD first, fall back to HDFC_PDF_PASSWORD
        password = settings.HDFC_BANK_PASSWORD or settings.HDFC_PDF_PASSWORD
        if password:
            from finance.ingestion.bank_account_pdf import create_hdfc_bank_parser
            parser = create_hdfc_bank_parser(password)
            for pdf_file in bank_pdfs:
                try:
                    if parser.can_parse(pdf_file):
                        result = parser.parse(pdf_file)
                        if result.errors:
                            click.echo(f"   ✗ {pdf_file.name}: {result.errors[0]}", err=True)
                            continue

                        db = SessionLocal()
                        try:
                            created = import_raw_transactions(
                                db,
                                raw_transactions=result.transactions,
                                file_path=pdf_file,
                                source_type=result.source_type,
                                file_hash=result.file_hash,
                                file_size=result.file_size,
                                metadata=_metadata_with_reconciliation(result),
                            )
                            if created:
                                new_txns = db.query(Transaction).order_by(Transaction.id.desc()).limit(created).all()
                                process_transactions(db, new_txns)

                            recon_err = _reconciliation_error(result)
                            status = "⚠" if recon_err else "✓"
                            click.echo(f"   {status} {pdf_file.name}: {created} txns")
                            total_imported += created
                        finally:
                            db.close()
                except Exception as e:
                    click.echo(f"   ✗ {pdf_file.name}: {e}", err=True)
        else:
            click.echo("   ✗ HDFC_BANK_PASSWORD not set", err=True)
        click.echo()

    # 5. Import CSV files
    csv_files = list(raw_dir.glob("*.txt")) + list(raw_dir.glob("*.csv"))
    csv_files = [f for f in csv_files if f.name != ".env"]
    if csv_files:
        click.echo(f"📄 Importing {len(csv_files)} CSV/TXT files...")
        for csv_file in csv_files:
            try:
                # Use hdfc_bank profile for HDFC format CSVs
                parser = BankCsvParser(profile="hdfc_bank")
                if parser.can_parse(csv_file):
                    result = parser.parse(csv_file)
                    if not result.errors:
                        db = SessionLocal()
                        try:
                            created = import_raw_transactions(
                                db,
                                raw_transactions=result.transactions,
                                file_path=csv_file,
                                source_type=result.source_type,
                                file_hash=result.file_hash,
                                file_size=result.file_size,
                                metadata=_metadata_with_reconciliation(result),
                            )
                            if created:
                                new_txns = db.query(Transaction).order_by(Transaction.id.desc()).limit(created).all()
                                process_transactions(db, new_txns)
                            click.echo(f"   ✓ {csv_file.name}: {created} txns")
                            total_imported += created
                        finally:
                            db.close()
            except Exception as e:
                click.echo(f"   ✗ {csv_file.name}: {e}", err=True)
        click.echo()

    click.echo("=" * 50)
    click.echo(f"✅ Import complete! Total transactions imported: {total_imported}")
    click.echo()
    click.echo("View dashboard: finance web")


@main.command("web")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, default=True, help="Enable auto-reload")
def web_command(host: str, port: int, reload: bool) -> None:
    """Start the web interface."""
    import uvicorn
    uvicorn.run("finance.web.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
