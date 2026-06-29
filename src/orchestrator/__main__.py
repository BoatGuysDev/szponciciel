import sys

from logging_config import get_logger
from orchestrator.graph import build_orchestrator

log = get_logger(__name__)

_USAGE = """usage: python -m orchestrator "<prompt>"

  "post videos about the USA-Iran conflict"   # targeted topic
  "research and post a few videos"            # generic (category sweep)"""


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(_USAGE, file=sys.stderr)
        return 2

    prompt = " ".join(args)
    try:
        result = build_orchestrator().invoke({"prompt": prompt})
    except Exception as exc:
        log.exception("orchestrator.run_failed", prompt=prompt)
        print(f"Run crashed: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1

    if result.get("is_fatal_error"):
        print(f"Run failed: {result.get('error_message')}", file=sys.stderr)
        return 1

    outcomes = result.get("outcomes") or []
    completed = sum(1 for o in outcomes if o.get("status") == "completed")
    print(f"Run {result.get('run_id')}: {completed}/{len(outcomes)} videos posted")
    for o in outcomes:
        if o.get("status") == "completed":
            print(f"  ✓ {o['persona_id']} -> {o.get('zernio_post_id')}")
        else:
            print(f"  ✗ {o['persona_id']}: {o.get('error_message')}")

    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
