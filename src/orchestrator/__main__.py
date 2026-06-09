import sys

from orchestrator.graph import build_orchestrator

_USAGE = """usage: python -m orchestrator "<prompt>"

  "post videos about the USA-Iran conflict"   # targeted topic
  "research and post a few videos"            # generic (category sweep)"""


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(_USAGE, file=sys.stderr)
        return 2

    prompt = " ".join(args)
    result = build_orchestrator().invoke({"prompt": prompt})

    if result.get("is_fatal_error"):
        print(f"Run failed: {result.get('error_message')}", file=sys.stderr)
        return 1

    outcomes = result.get("outcomes") or []
    completed = sum(1 for o in outcomes if o.get("status") == "completed")
    print(f"Run {result.get('run_id')}: {completed}/{len(outcomes)} videos posted")
    for o in outcomes:
        if o.get("status") == "completed":
            print(f"  ✓ {o['persona_id']} -> {o.get('tiktok_post_id')}")
        else:
            print(f"  ✗ {o['persona_id']}: {o.get('error_message')}")

    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
