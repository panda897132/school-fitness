"""从 git log 自动生成中文 Release Notes"""
import subprocess, sys
from datetime import datetime, timezone


def get_tag_sha(tag: str) -> str | None:
    r = subprocess.run(["git", "rev-list", "-n", "1", tag],
                       capture_output=True, text=True, timeout=10)
    return r.stdout.strip() if r.returncode == 0 else None


def get_previous_tag(current_tag: str) -> str | None:
    """Find the tag that comes before the given tag in version-sorted order."""
    r = subprocess.run(
        ["git", "tag", "-l", "--sort=-version:refname"],
        capture_output=True, text=True, timeout=10
    )
    tags = [t.strip() for t in r.stdout.strip().split("\n") if t.strip()]
    try:
        idx = tags.index(current_tag)
        return tags[idx + 1] if idx + 1 < len(tags) else None
    except ValueError:
        return None


def get_commits(since: str | None, until_sha: str) -> list[dict]:
    fmt = "--format=%H|%ai|%s"
    if since:
        r = subprocess.run(["git", "log", fmt, f"{since}..{until_sha}"],
                           capture_output=True, text=True, timeout=10)
    else:
        r = subprocess.run(["git", "log", fmt, until_sha],
                           capture_output=True, text=True, timeout=10)
    commits = []
    for line in r.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) >= 3:
            commits.append({"hash": parts[0][:7], "date": parts[1], "msg": parts[2]})
    return commits


def categorize(msg: str) -> str:
    if msg.startswith("feat:") or msg.startswith("feat(") or msg.startswith("新增"):
        return "新增"
    if msg.startswith("fix:") or msg.startswith("fix(") or msg.startswith("修复"):
        return "修复"
    if msg.startswith("refactor:") or msg.startswith("refactor(") or msg.startswith("重构"):
        return "重构"
    if msg.startswith("perf:") or msg.startswith("优化"):
        return "优化"
    if msg.startswith("ci:") or msg.startswith("ci("):
        return "CI"
    if msg.startswith("refine:") or msg.startswith("refine("):
        return "优化"
    if msg.startswith("export"):
        return "导出优化"
    if msg.startswith("build"):
        return "构建"
    return "其他"


def strip_prefix(msg: str) -> str:
    for prefix in ["feat: ", "feat(", "fix: ", "fix(", "refactor: ", "refactor(",
                   "perf: ", "ci: ", "ci(", "refine: ", "refine(",
                   "bump ", "chore: ", "export: ", "build: "]:
        if msg.startswith(prefix):
            return msg[len(prefix):]
    for prefix in ["优化", "新增", "修复", "重构"]:
        if msg.startswith(prefix):
            return msg[len(prefix):].lstrip(": ")
    return msg


def main():
    current_tag = sys.argv[1] if len(sys.argv) > 1 else None
    current_sha = get_tag_sha(current_tag) if current_tag else None
    if not current_sha:
        print(f"Error: tag '{current_tag}' not found", file=sys.stderr)
        sys.exit(1)
    prev_tag = get_previous_tag(current_tag) if current_tag else None
    commits = get_commits(prev_tag, current_sha)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [f"## {current_tag} ({now})", ""]
    # Skip merge/chore commits that are not user-facing
    skip_patterns = ("Merge ", "bump to v", "Bump to v")
    cats: dict[str, list[str]] = {}
    for c in commits:
        if any(c["msg"].startswith(p) for p in skip_patterns):
            continue
        cat = categorize(c["msg"])
        msg = strip_prefix(c["msg"])
        cats.setdefault(cat, []).append(f"- {msg}")

    # Filter out "其他" (chore/bump/merge) — not useful for end users
    for cat in ["新增", "修复", "重构", "优化", "导出优化", "CI", "构建"]:
        if cat in cats:
            lines.append(f"### {cat}")
            lines.extend(cats[cat])
            lines.append("")

    # If no meaningful changes, show a simple message
    if len(lines) <= 2:
        lines.append("本次无显著功能变更，主要为依赖更新或内部优化。")

    body = "\n".join(lines).strip()
    print(body)


if __name__ == "__main__":
    main()
