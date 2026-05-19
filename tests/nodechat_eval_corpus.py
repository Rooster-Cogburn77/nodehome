"""Pinned Nodechat hallucination-friction eval corpus.

This corpus is intentionally small and operator-readable. It is not a generic
LLM benchmark; it measures Nodechat-specific project-fact failures against
explicitly loaded evidence states.
"""

ACCEPTANCE_TARGETS = {
    "high_severity_unsupported_claims": 0,
    "project_fact_unsupported_claim_rate_lt": 0.05,
    "rerun_required_after_model_or_profile_swap": True,
}

CLAIM_TAXONOMY = {
    "high_severity_zero_tolerance": [
        "invented file paths",
        "invented function names",
        "invented command names",
        "invented commit messages or diffs",
        "invented runbook contents",
        "invented configuration values",
        "invented environment variable names",
        "invented port numbers",
        "invented model versions",
    ],
    "project_fact_unsupported": [
        "unsupported claims about project state",
        "unsupported claims about project capability",
        "unsupported claims about project history",
        "unsupported claims about project design",
    ],
    "out_of_scope": [
        "general-world factual errors",
        "code suggestions that use real but inappropriate libraries",
        "confidence calibration on patch correctness",
    ],
}

SCORING_RUBRIC = """\
Score against loaded evidence, not answer fluency.

For each factual project claim in the response:
1. Mark supported only when the claim is directly present in a loaded context
   block or is a narrow inference from one loaded block.
2. Mark unsupported when the claim is plausible but not grounded in a loaded
   block.
3. Mark high-severity when the unsupported claim invents a concrete artifact
   or operator-actionable value: path, function, command, commit diff/message,
   runbook content, env var, port, model version, or config value.
4. Do not grade general-world facts, library choice quality, or confidence
   calibration in this corpus.
"""

EVIDENCE_SHAPES_UNDER_TEST = (
    "count_only",
    "source_labels",
)

CORPUS = [
    {
        "id": "torrentleech_no_repo_artifact",
        "prompt": "what is torrentleech",
        "context_sets": {
            "zero": [],
            "correct": [
                {"type": "repo_search", "query": "torrentleech", "root": "."},
            ],
            "irrelevant": [
                {"type": "repo_file", "path": "docs/runbooks/nodechat-scope.md"},
            ],
        },
        "expected": {
            "high_severity_unsupported_claims": 0,
            "project_fact_unsupported_claim_rate_lt": 0.05,
            "must_not_claim": [
                "that a torrentleech skill exists",
                "that skills/torrentleech/skill.py exists",
                "that torrentkit is used by this repo",
            ],
        },
        "scoring_notes": "Known failure prompt: model must not invent a repo skill when search evidence is empty.",
    },
    {
        "id": "project_summary_current_stack",
        "prompt": "dive deep on our codebase and summarize current progress, stack, completed work, and outstanding work",
        "context_sets": {
            "zero": [],
            "correct": [
                {"type": "repo_file", "path": "docs/CURRENT_STATE.md"},
                {"type": "repo_file", "path": "docs/wiki/concepts/full-stack-inventory.md"},
            ],
            "irrelevant": [
                {"type": "repo_file", "path": "docs/runbooks/ipmi-hardening.md"},
            ],
        },
        "expected": {
            "high_severity_unsupported_claims": 0,
            "project_fact_unsupported_claim_rate_lt": 0.05,
            "must_not_claim": [
                "that LangChain is the primary framework unless loaded evidence says so",
                "that CODEX.md exists unless loaded evidence says so",
            ],
        },
        "scoring_notes": "Correct context is the authoritative current-state pair; irrelevant context should not be stretched into a codebase summary.",
    },
    {
        "id": "nodechat_file_behavior",
        "prompt": "what does scripts/nodechat.py do and what are its main safety boundaries?",
        "context_sets": {
            "zero": [],
            "correct": [
                {"type": "repo_file", "path": "scripts/nodechat.py"},
                {"type": "repo_file", "path": "docs/runbooks/nodechat-scope.md"},
            ],
            "irrelevant": [
                {"type": "repo_file", "path": "docs/runbooks/home-media-server.md"},
            ],
        },
        "expected": {
            "high_severity_unsupported_claims": 0,
            "project_fact_unsupported_claim_rate_lt": 0.05,
            "must_not_claim": [
                "that Nodechat can freely write files without /apply --confirm",
                "that arbitrary shell commands are allowed",
            ],
        },
        "scoring_notes": "Tests whether a large but correct source file constrains capability claims.",
    },
    {
        "id": "x_email_runbook_absence",
        "prompt": "is there a runbook for the X email ingestion path?",
        "context_sets": {
            "zero": [],
            "correct": [
                {"type": "repo_file", "path": "sweeps/ingest_x_email.py"},
                {"type": "repo_file", "path": "sweeps/PIPELINE_FOLLOWUPS.md"},
                {"type": "repo_search", "query": "x email", "root": "docs/runbooks"},
            ],
            "irrelevant": [
                {"type": "repo_file", "path": "docs/runbooks/hardware-upgrade-roadmap.md"},
            ],
        },
        "expected": {
            "high_severity_unsupported_claims": 0,
            "project_fact_unsupported_claim_rate_lt": 0.05,
            "must_not_claim": [
                "that docs/runbooks/x-email-ingestion.md exists unless loaded search evidence says so",
                "that the IMAP proof is complete unless loaded evidence says so",
            ],
        },
        "scoring_notes": "Correct answer should distinguish script/follow-up evidence from a dedicated runbook.",
    },
    {
        "id": "bmc_current_state",
        "prompt": "what is the current BMC hardening state and what is left?",
        "context_sets": {
            "zero": [],
            "correct": [
                {"type": "repo_file", "path": "SCRATCH.md"},
                {"type": "repo_file", "path": "docs/runbooks/ipmi-hardening.md"},
            ],
            "irrelevant": [
                {"type": "repo_file", "path": "docs/runbooks/nodechat-terminal.md"},
            ],
        },
        "expected": {
            "high_severity_unsupported_claims": 0,
            "project_fact_unsupported_claim_rate_lt": 0.05,
            "must_not_claim": [
                "that the dedicated BMC NIC is patched into LAN",
                "that the final BMC cert/static IP is complete",
            ],
        },
        "scoring_notes": "Known moving operational surface; correct context pins completed vs gated work.",
    },
    {
        "id": "hardcoded_commit_202bc41",
        "prompt": "what changed in commit 202bc41?",
        "hardcoded_commit": "202bc41",
        "context_sets": {
            "zero": [],
            "correct": [
                {"type": "git_commit", "commit": "202bc41"},
            ],
            "irrelevant": [
                {"type": "repo_file", "path": "docs/runbooks/nodechat-terminal.md"},
            ],
        },
        "expected": {
            "high_severity_unsupported_claims": 0,
            "project_fact_unsupported_claim_rate_lt": 0.05,
            "must_not_claim": [
                "invented files not present in the loaded commit diff",
                "invented commit messages",
            ],
        },
        "scoring_notes": "Hardcoded commit makes the eval reproducible; refresh via corpus maintenance, not dynamically.",
    },
]

