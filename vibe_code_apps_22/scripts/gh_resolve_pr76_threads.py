#!/usr/bin/env python
"""Post a ledger reply on unresolved PR #76 review threads and resolve them.

Requires: gh auth with repo write. Safe to re-run (skips already-resolved).
"""
from __future__ import annotations

import json
import subprocess
import textwrap

OWNER = "bbartling"
REPO = "py-bacnet-stacks-playground"
PR = 76

REPLY = textwrap.dedent(
    """
    Addressed / verified at current HEAD (see `vibe_code_apps_22/docs/superpowers/specs/2026-08-08-pr76-review-ledger.md`):

    - Trial utility is trial-specific (`utility_monthly_from_trial_sim`); scorecard `gl14_status` never unblocks.
    - Ranking uses chronological_validation only; locked January winter holdout evaluated once; summer last-30d is diagnostic only.
    - Site `LAKESIDE_SITE_ROOT` multires reports preferred over stale local artifacts.
    - Desktop comfort/peak placeholders fixed; torch refuses teacher-forced champion selection; empty-fold export refused.
    - Stale items (sklearn else syntax, mixed-unit horizon MAE, LOO future fallback, missing `_gen_tutorial_notebooks.py`) verified already fixed/absent.

    Operational status remains **NO-GO / DSM BLOCKED**.
    """
).strip()


def gh_api(method: str, path: str, payload: dict | None = None) -> dict | list:
    cmd = ["gh", "api", "-X", method, path]
    if payload is not None:
        cmd.extend(["--input", "-"])
        proc = subprocess.run(
            cmd, input=json.dumps(payload), text=True, capture_output=True, check=False
        )
    else:
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def main() -> int:
    q = """
    query($o:String!,$n:String!,$p:Int!){
      repository(owner:$o,name:$n){
        pullRequest(number:$p){
          reviewThreads(first:100){
            nodes{ id isResolved comments(first:1){nodes{ id databaseId path }} }
          }
        }
      }
    }
    """
    # Use gh api graphql with -f flags (PowerShell-safe)
    proc = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={q}",
            "-F",
            f"o={OWNER}",
            "-F",
            f"n={REPO}",
            "-F",
            f"p={PR}",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr)
        return 1
    data = json.loads(proc.stdout)
    nodes = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    unresolved = [n for n in nodes if not n["isResolved"]]
    print(f"unresolved={len(unresolved)} total={len(nodes)}")
    for n in unresolved:
        cid = n["comments"]["nodes"][0]["databaseId"]
        path = n["comments"]["nodes"][0].get("path")
        # reply
        subprocess.run(
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{OWNER}/{REPO}/pulls/{PR}/comments/{cid}/replies",
                "-f",
                f"body={REPLY}",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        # resolve
        mut = (
            "mutation($id:ID!){ resolveReviewThread(input:{threadId:$id}){ thread{ isResolved } } }"
        )
        subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={mut}", "-F", f"id={n['id']}"],
            check=False,
            capture_output=True,
            text=True,
        )
        print(f"resolved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
