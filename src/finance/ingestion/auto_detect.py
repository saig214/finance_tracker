"""Deterministic auto-detection system based on parser-owned rules."""

from __future__ import annotations

import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from finance.ingestion.base import BaseParser, ParserProbeResult
from finance.ingestion.registry import ParserRegistry


PARSER_ORDER = [
    "hdfc_bank_csv",
    "hdfc_bank_pdf",
    "icici_credit_card",
    "hdfc_credit_card_legacy",
    "hdfc_credit_card",
]

PARSER_PASSWORD_ENV = {
    "hdfc_credit_card": "HDFC_PDF_PASSWORD",
    "hdfc_credit_card_legacy": "HDFC_PDF_PASSWORD",
    "hdfc_bank_pdf": "HDFC_PDF_PASSWORD",
    "icici_credit_card": "ICICI_PDF_PASSWORD",
}


def _resolve_password(explicit_password: str | None, parser_name: str) -> str | None:
    """Resolve parser password from explicit value or parser-specific env var."""
    if explicit_password:
        return explicit_password

    password_env_var = PARSER_PASSWORD_ENV.get(parser_name)
    if password_env_var:
        return os.getenv(password_env_var)

    return None


def _instantiate_parser(
    parser_cls: type[BaseParser],
    password: str | None,
) -> BaseParser:
    """Instantiate parser class using required args contract."""
    required_args = getattr(parser_cls, "required_args", [])

    if "password" in required_args:
        if not password:
            raise ValueError("Password required by parser")
        return parser_cls(password=password)

    if "profile" in required_args:
        # Skip parsers requiring external profile selection in auto-detect.
        raise ValueError("Profile-based parser is not auto-detectable")

    return parser_cls()


def _validate_pdf_access(file_path: Path, password: str | None) -> tuple[bool, str | None]:
    """Return whether PDF can be opened with provided password."""
    if file_path.suffix.lower() != ".pdf":
        return True, None
    try:
        import pikepdf

        try:
            with pikepdf.open(file_path):
                return True, None
        except pikepdf.PasswordError:
            if not password:
                return False, "Encrypted PDF requires password"
            try:
                with pikepdf.open(file_path, password=password):
                    return True, None
            except Exception:
                return False, "Unable to decrypt PDF with provided password"
    except Exception:
        # If pikepdf is unavailable/unexpectedly fails, defer to parser.can_parse.
        return True, None


def _iter_parsers_in_order() -> list[tuple[str, type[BaseParser]]]:
    rows: list[tuple[str, type[BaseParser]]] = []
    for name in PARSER_ORDER:
        try:
            rows.append((name, ParserRegistry.get(name)))
        except KeyError:
            continue
    return rows


def _build_detection_metadata(parser_name: str, parser: BaseParser) -> dict:
    return {
        "profile_id": parser_name,
        "parser_class": parser_name,
        "metadata": {
            "bank": getattr(parser, "entity", None),
            "product": getattr(parser, "entity_type", None),
        },
    }


def _reconciliation_to_dict(parse_result) -> dict | None:
    recon = getattr(parse_result, "reconciliation", None)
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


def _reconciliation_error(parse_result) -> str | None:
    """Return hard-stop reconciliation error string when reconciliation fails."""
    recon = getattr(parse_result, "reconciliation", None)
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


def _probe_parser(
    *,
    parser_name: str,
    parser_cls: type[BaseParser],
    file_path: Path,
    explicit_password: str | None,
) -> tuple[str, BaseParser | None, ParserProbeResult]:
    """Instantiate and probe a parser using the uniform probe interface."""
    parser_password = _resolve_password(explicit_password, parser_name)
    try:
        parser = _instantiate_parser(parser_cls, parser_password)
    except Exception as exc:  # noqa: BLE001
        return parser_name, None, ParserProbeResult(matched=False, reason=f"init_error:{exc}")

    result = parser.probe(file_path)
    return parser_name, parser, result


def auto_detect_parser(
    file_path: Path,
    password: Optional[str] = None,
    min_confidence: float | None = None,
) -> tuple[Optional[BaseParser], float, dict | None]:
    """Detect parser by ordered first-match over parser-owned can_parse rules.

    min_confidence is ignored and kept only for backward compatibility.
    """
    del min_confidence

    # PDF gate: wrong/missing explicit password rejects before parser probing.
    can_open_pdf, pdf_error = _validate_pdf_access(file_path, password)
    if not can_open_pdf:
        return None, 0.0, {"error": pdf_error or "pdf_access_error"}

    parser_rows = _iter_parsers_in_order()
    if not parser_rows:
        return None, 0.0, None

    matched: list[tuple[str, BaseParser]] = []
    with ThreadPoolExecutor(max_workers=len(parser_rows)) as pool:
        futures = [
            pool.submit(
                _probe_parser,
                parser_name=parser_name,
                parser_cls=parser_cls,
                file_path=file_path,
                explicit_password=password,
            )
            for parser_name, parser_cls in parser_rows
        ]
        for fut in as_completed(futures):
            parser_name, parser, probe = fut.result()
            if probe.matched and parser is not None:
                matched.append((parser_name, parser))

    ordered_names = [name for name, _ in parser_rows]
    matched.sort(key=lambda row: ordered_names.index(row[0]))

    if len(matched) > 1:
        return None, 0.0, {"error": "ambiguous_match", "matches": [m[0] for m in matched]}
    if len(matched) == 1:
        parser_name, parser = matched[0]
        return parser, 1.0, _build_detection_metadata(parser_name, parser)
    return None, 0.0, None


def get_parser_suggestions(
    file_path: Path,
    top_n: int = 3,
    password: str | None = None,
) -> list[tuple[str, float, dict]]:
    """Get parser suggestions from deterministic parser rule checks."""
    suggestions: list[tuple[str, float, dict]] = []

    parser_rows = _iter_parsers_in_order()
    with ThreadPoolExecutor(max_workers=max(len(parser_rows), 1)) as pool:
        futures = [
            pool.submit(
                _probe_parser,
                parser_name=parser_name,
                parser_cls=parser_cls,
                file_path=file_path,
                explicit_password=password,
            )
            for parser_name, parser_cls in parser_rows
        ]
        matched_rows: list[str] = []
        for fut in as_completed(futures):
            parser_name, _, probe = fut.result()
            if probe.matched:
                matched_rows.append(parser_name)

    ordered_names = [name for name, _ in parser_rows]
    matched_rows.sort(key=lambda name: ordered_names.index(name))

    for parser_name in matched_rows[:top_n]:
        parser_cls = ParserRegistry.get(parser_name)
        suggestions.append(
            (
                parser_name,
                1.0,
                {
                    "profile_id": parser_name,
                    "bank": getattr(parser_cls, "entity", None),
                    "product": getattr(parser_cls, "entity_type", None),
                    "format": getattr(parser_cls, "format", "unknown"),
                    "description": parser_cls.description,
                },
            )
        )

    return suggestions


def auto_import(
    file_path: Path,
    password: Optional[str] = None,
    password_env: Optional[str] = None,
    min_confidence: float | None = None,
) -> dict:
    """Automated import flow with deterministic parser selection."""
    from finance.core.database import SessionLocal
    from finance.core.models import Transaction
    from finance.processing.pipeline import process_transactions
    from finance.services.import_service import import_raw_transactions

    # Optional override env var passed by CLI.
    if password_env and not password:
        password = os.getenv(password_env)

    parser, confidence, matched_profile = auto_detect_parser(
        file_path,
        password=password,
        min_confidence=min_confidence,
    )

    if not parser:
        if matched_profile and matched_profile.get("error") == "ambiguous_match":
            matches = ", ".join(matched_profile.get("matches", []))
            return {
                "success": False,
                "parser_used": None,
                "confidence": confidence,
                "transactions_imported": 0,
                "errors": [f"Ambiguous parser match: {matches}"],
                "matched_profile": matched_profile,
            }
        if matched_profile and matched_profile.get("error"):
            return {
                "success": False,
                "parser_used": None,
                "confidence": confidence,
                "transactions_imported": 0,
                "errors": [str(matched_profile.get("error"))],
                "matched_profile": matched_profile,
            }
        return {
            "success": False,
            "parser_used": None,
            "confidence": confidence,
            "transactions_imported": 0,
            "errors": ["No matching parser — create a parser first"],
            "matched_profile": matched_profile,
        }

    try:
        parse_result = parser.parse(file_path)
    except Exception as e:
        return {
            "success": False,
            "parser_used": parser.__class__.__name__,
            "confidence": confidence,
            "transactions_imported": 0,
            "errors": [f"Parse failed: {str(e)}"],
            "matched_profile": matched_profile,
        }

    if not parse_result.success:
        return {
            "success": False,
            "parser_used": parser.__class__.__name__,
            "confidence": confidence,
            "transactions_imported": 0,
            "errors": parse_result.errors,
            "matched_profile": matched_profile,
        }

    recon_error = _reconciliation_error(parse_result)
    if recon_error:
        return {
            "success": False,
            "parser_used": parser.__class__.__name__,
            "confidence": confidence,
            "transactions_imported": 0,
            "errors": [recon_error],
            "matched_profile": matched_profile,
            "reconciliation": _reconciliation_to_dict(parse_result),
        }

    source_metadata = dict(parse_result.metadata or {})
    reconciliation = _reconciliation_to_dict(parse_result)
    if reconciliation is not None:
        source_metadata["reconciliation"] = reconciliation
    profile_metadata = dict((matched_profile or {}).get("metadata", {}))
    if matched_profile:
        profile_metadata["profile_id"] = matched_profile.get("profile_id")
        profile_metadata["match_score"] = confidence
        profile_metadata["parser_class"] = matched_profile.get("parser_class")
    source_metadata.update(profile_metadata)

    db = SessionLocal()
    try:
        created = import_raw_transactions(
            db,
            raw_transactions=parse_result.transactions,
            file_path=file_path,
            source_type=parse_result.source_type,
            file_hash=parse_result.file_hash,
            file_size=parse_result.file_size,
            metadata=source_metadata,
        )

        if created > 0:
            new_txns = (
                db.query(Transaction)
                .order_by(Transaction.id.desc())
                .limit(created)
                .all()
            )
            process_transactions(db, new_txns)

        return {
            "success": True,
            "parser_used": parser.__class__.__name__,
            "confidence": confidence,
            "transactions_imported": created,
            "errors": [],
            "warnings": list(parse_result.warnings),
            "reconciliation": reconciliation,
            "matched_profile": matched_profile,
            "parser_metadata": {
                "entity": getattr(parser, "entity", "generic"),
                "entity_type": getattr(parser, "entity_type", "statement"),
                "format": getattr(parser, "format", "unknown"),
            },
        }

    except Exception as e:
        return {
            "success": False,
            "parser_used": parser.__class__.__name__,
            "confidence": confidence,
            "transactions_imported": 0,
            "errors": [f"Import failed: {str(e)}"],
            "matched_profile": matched_profile,
        }
    finally:
        db.close()
