"""CLI entry point for the DTIC Research Landscape Analyzer."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from src.config import DEFAULT_OUTPUT_DIR
from src.models import MilitaryBranch, UserProposal, Verdict
from src.pipeline import run_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DTIC Research Landscape Analyzer — explore research coverage and gaps"
    )
    parser.add_argument("--title", required=True, help="Research topic title")
    parser.add_argument("--topic", default="", help="General description of the research area (non-sensitive)")
    parser.add_argument("--abstract", default="", help="(Deprecated) Use --topic instead")
    parser.add_argument(
        "--keywords",
        default="",
        help="Comma-separated keywords",
    )
    parser.add_argument(
        "--branch",
        default="navy",
        choices=[b.value for b in MilitaryBranch],
        help="Branch of interest (default: navy)",
    )
    parser.add_argument(
        "--context",
        default="",
        help="Additional research focus context",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for reports (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--summary-file",
        default="",
        help="Path to write GitHub Actions step summary (e.g. $GITHUB_STEP_SUMMARY)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    topic_description = args.topic or args.abstract

    proposal = UserProposal(
        title=args.title,
        abstract=args.abstract,
        topic_description=topic_description,
        keywords=keywords,
        military_branch=MilitaryBranch(args.branch),
        additional_context=args.context,
    )

    report, markdown, summary = await run_pipeline(proposal, output_dir=args.output)

    # Write step summary if requested (GitHub Actions)
    if args.summary_file:
        with open(args.summary_file, "a", encoding="utf-8") as f:
            f.write(summary)

    # Print result to stdout
    print(f"\n{'='*60}")
    print(f"LANDSCAPE ASSESSMENT: {report.verdict.value}")
    print(f"CONFIDENCE: {report.confidence:.0%}")
    print(f"{'='*60}")
    print(f"\nFull report saved to: {args.output}/")

    # Exit code: 0 for UNIQUE/NAVY_UNIQUE, 1 for AT_RISK/NEEDS_REVIEW
    if report.verdict in (Verdict.UNIQUE, Verdict.NAVY_UNIQUE):
        return 0
    return 1


def cli_entry():
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    cli_entry()
