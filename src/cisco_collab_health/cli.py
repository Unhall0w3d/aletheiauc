"""Command-line interface for alpha assessment runs."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from cisco_collab_health.artifacts import (
    ArtifactStore,
    write_assessment_artifacts,
    write_preflight_artifacts,
)
from cisco_collab_health.collectors.base import CollectionContext
from cisco_collab_health.collectors.sample import SampleCollector
from cisco_collab_health.config import ensure_runtime_profile, select_or_create_runtime_profile
from cisco_collab_health.engine import AssessmentEngine
from cisco_collab_health.interfaces import PreflightResult, run_publisher_preflight
from cisco_collab_health.models.assessment import AssessmentReport
from cisco_collab_health.reports.html import HtmlReportBuilder
from cisco_collab_health.reports.json import JsonReportBuilder
from cisco_collab_health.reports.summary import ExecutiveSummaryBuilder
from cisco_collab_health.rules.basic import ClusterIdentityRule, NodeReachabilityRule
from cisco_collab_health.status import StatusPrinter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ccha",
        description="Cisco Collaboration Health Assessment Tool alpha runner.",
    )
    parser.add_argument(
        "--format",
        choices=("summary", "json"),
        default="summary",
        help="Terminal output format.",
    )
    parser.add_argument(
        "--html-report",
        default=None,
        help="Path for the styled HTML report. Defaults to reports/assessment-<timestamp>.html.",
    )
    parser.add_argument(
        "--no-html-report",
        action="store_true",
        help="Do not write the styled HTML report.",
    )
    parser.add_argument(
        "--artifact-dir",
        default="assessment_runs",
        help="Directory for local per-run artifacts. Defaults to assessment_runs/.",
    )
    parser.add_argument(
        "--no-artifacts",
        action="store_true",
        help="Do not write local parser/debug artifacts.",
    )
    parser.add_argument(
        "--profile",
        help="Local connection profile name. If omitted, choose from saved profiles or create one.",
    )
    parser.add_argument(
        "--reset-profile",
        action="store_true",
        help="Replace the saved local profile and stored credentials.",
    )
    parser.add_argument(
        "--no-save-credentials",
        action="store_true",
        help="Prompt for passwords but do not store them in the OS credential store.",
    )
    parser.add_argument(
        "--skip-profile",
        action="store_true",
        help="Run the current offline sample assessment without prompting for connection details.",
    )
    parser.add_argument(
        "--probe-interfaces",
        action="store_true",
        help="Deprecated alias; Publisher preflight runs automatically after profile load.",
    )
    parser.add_argument(
        "--axl-port",
        type=int,
        default=8443,
        help="AXL HTTPS port.",
    )
    parser.add_argument(
        "--risport-port",
        type=int,
        default=8443,
        help="RISPort70 HTTPS port.",
    )
    parser.add_argument(
        "--control-center-port",
        type=int,
        default=8443,
        help="Control Center Services HTTPS port.",
    )
    parser.add_argument(
        "--perfmon-port",
        type=int,
        default=8443,
        help="PerfMon HTTPS port.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status_stream = sys.stderr if args.format == "json" else sys.stdout
    status = StatusPrinter(stream=status_stream)

    try:
        return _run(args, status)
    except KeyboardInterrupt:
        status.warn("Interrupted by user")
        return 130
    except (OSError, ValueError) as exc:
        status.fail(str(exc))
        return 1


def _run(args: argparse.Namespace, status: StatusPrinter) -> int:
    context = CollectionContext()
    run_started = datetime.now()
    artifact_store: ArtifactStore | None = None
    profile_name = "sample"

    if not args.skip_profile:
        status.stage("Loading connection profile")
        if args.profile:
            runtime_profile = ensure_runtime_profile(
                args.profile,
                reset=args.reset_profile,
                save_credentials=not args.no_save_credentials,
            )
        else:
            runtime_profile = select_or_create_runtime_profile(
                reset=args.reset_profile,
                save_credentials=not args.no_save_credentials,
            )
        for warning in runtime_profile.warnings:
            status.warn(warning)
        context = CollectionContext(
            target=runtime_profile.stored.publisher_ip,
            username=runtime_profile.stored.gui_username,
            publisher_ip=runtime_profile.stored.publisher_ip,
            gui_username=runtime_profile.stored.gui_username,
            gui_password=runtime_profile.gui_password,
            os_username=runtime_profile.stored.os_username,
            os_password=runtime_profile.os_password,
        )
        profile_name = runtime_profile.stored.name
        artifact_store = _create_artifact_store(args, status, profile_name, run_started)
        _write_manifest(
            artifact_store,
            profile_name=profile_name,
            publisher_ip=runtime_profile.stored.publisher_ip,
            skipped_profile=False,
        )
        status.ok(f"Profile loaded: {runtime_profile.stored.name}")
        status.stage(f"Running Publisher preflight: {runtime_profile.stored.publisher_ip}")
        preflight = run_publisher_preflight(
            context,
            axl_port=args.axl_port,
            risport_port=args.risport_port,
            control_center_port=args.control_center_port,
            perfmon_port=args.perfmon_port,
        )
        _print_preflight_status(preflight, status)
        if artifact_store:
            write_preflight_artifacts(artifact_store, runtime_profile.stored.publisher_ip, preflight)
            status.ok(f"Preflight artifacts written: {artifact_store.root}")
    else:
        status.warn("Skipping profile and Publisher preflight")
        artifact_store = _create_artifact_store(args, status, profile_name, run_started)
        _write_manifest(
            artifact_store,
            profile_name=profile_name,
            publisher_ip=None,
            skipped_profile=True,
        )

    status.stage("Running collectors")
    engine = AssessmentEngine(
        collectors=[SampleCollector()],
        rules=[ClusterIdentityRule(), NodeReachabilityRule()],
    )
    report = engine.run(context)
    status.ok("Collectors completed")
    if artifact_store:
        write_assessment_artifacts(artifact_store, report)
        status.ok(f"Assessment artifacts written: {artifact_store.root}")

    html_report_path = None
    if not args.no_html_report:
        status.stage("Writing HTML report")
        try:
            html_report_path = _write_html_report(report, args.html_report)
            status.ok(f"HTML report written: {html_report_path}")
        except OSError as exc:
            status.fail(f"Unable to write HTML report: {exc}")

    status.stage("Rendering terminal output")
    if args.format == "json":
        print(JsonReportBuilder().build(report))
    else:
        print(ExecutiveSummaryBuilder().build(report, str(html_report_path) if html_report_path else None))

    return 0


def _write_html_report(report: AssessmentReport, requested_path: str | None) -> Path:
    if requested_path:
        path = Path(requested_path).expanduser()
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path("reports") / f"assessment-{timestamp}.html"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HtmlReportBuilder().build(report), encoding="utf-8")
    return path


def _create_artifact_store(
    args: argparse.Namespace,
    status: StatusPrinter,
    profile_name: str,
    run_started: datetime,
) -> ArtifactStore | None:
    if args.no_artifacts:
        status.warn("Skipping local artifact storage")
        return None

    status.stage("Preparing local artifact storage")
    store = ArtifactStore.create(args.artifact_dir, profile_name, run_started)
    status.ok(f"Artifact directory: {store.root}")
    return store


def _write_manifest(
    store: ArtifactStore | None,
    *,
    profile_name: str,
    publisher_ip: str | None,
    skipped_profile: bool,
) -> None:
    if not store:
        return

    store.write_manifest(
        {
            "tool": "helios",
            "profile_name": profile_name,
            "publisher_ip": publisher_ip,
            "skipped_profile": skipped_profile,
        }
    )


def _print_preflight_status(preflight: PreflightResult, status: StatusPrinter) -> None:
    for check in preflight.connectivity:
        message = f"{check.name}: {check.target}"
        if check.available:
            status.ok(message)
        else:
            detail = f" - {check.reason}" if check.reason else ""
            status.warn(f"{message}{detail}")

    for interface in preflight.interfaces:
        message = f"{interface.name}: {interface.endpoint}"
        if interface.available:
            status.ok(message)
        else:
            detail = f" - {interface.reason}" if interface.reason else ""
            status.warn(f"{message}{detail}")

    if preflight.available_interfaces:
        status.info("Enabled interfaces: " + ", ".join(preflight.available_interfaces))
    else:
        status.warn("No Publisher API interfaces passed preflight")


if __name__ == "__main__":
    raise SystemExit(main())
