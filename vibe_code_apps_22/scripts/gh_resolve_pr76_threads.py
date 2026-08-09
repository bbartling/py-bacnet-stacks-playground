#!/usr/bin/env python
"""Post a ledger reply on unresolved PR #76 review threads and resolve them.

Requires: gh auth with repo write. Safe to re-run (skips already-resolved).
Resolves a thread only after a successful reply API call.
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

    - Rescore never overwrites original `summary.json`; writes versioned `summary_rescored_<ts>.json`.
    - Rescore preserves failed/rejected statuses; shared post_run_metrics schema with execute_trial.
    - q15 promotion fail-closed; monthly completeness + safe `complete_month` parse.
    - Forward chrono policy (train→Dec15, val Dec15–31, locked Jan); holdout champion-only.
    - Proxy family renamed `EPLUS_PROXY_CORRECTOR_DIAGNOSTIC` / `DIAGNOSTIC_ONLY`.
    - Day-level peak metrics; residual narrative from computed signs; no personal site fallbacks.

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
    n_ok = 0
    n_skip = 0
    for n in unresolved:
        cid = n["comments"]["nodes"][0]["databaseId"]
        path = n["comments"]["nodes"][0].get("path")
        reply = subprocess.run(
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
        if reply.returncode != 0:
            print(f"SKIP resolve {path}: reply failed: {reply.stderr or reply.stdout}")
            n_skip += 1
            continue
        mut = (
            "mutation($id:ID!){ resolveReviewThread(input:{threadId:$id}){ thread{ isResolved } } }"
        )
        resol = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={mut}", "-F", f"id={n['id']}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if resol.returncode != 0:
            print(f"reply ok but resolve failed {path}: {resol.stderr or resol.stdout}")
            n_skip += 1
            continue
        print(f"resolved {path}")
        n_ok += 1
    print(f"done resolved={n_ok} skipped={n_skip}")
    return 0 if n_skip == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
