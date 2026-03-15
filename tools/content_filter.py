#!/usr/bin/env python3
"""
Groundswell Content Filter — Check text against brand safety rules.

Fully implemented content safety checker. Validates text against:
  - Blocked topics from config.yaml
  - Cannabis "never say" phrases
  - Platform-specific length limits
  - Link detection (flags links in main text for X/LinkedIn)
  - Basic profanity check

Usage:
    python3 tools/content_filter.py check --text "..."
    python3 tools/content_filter.py check --text "..." --platform x
"""

import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    print(
        json.dumps({"error": "PyYAML is required: pip install pyyaml"}),
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config.yaml")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}
    except yaml.YAMLError:
        return {}


# ---------------------------------------------------------------------------
# Platform length limits (characters)
# ---------------------------------------------------------------------------

PLATFORM_CHAR_LIMITS = {
    "x": 280,
    "threads": 500,
    "linkedin": 3000,
}

# LinkedIn also has a minimum word count from config (min_word_count)
# which we check separately.

# ---------------------------------------------------------------------------
# Profanity list — short, hardcoded, covers obvious cases
# Words that should never appear in Brad's professional content.
# ---------------------------------------------------------------------------

PROFANITY_LIST = [
    "fuck",
    "shit",
    "damn",
    "ass",
    "bitch",
    "bastard",
    "crap",
    "dick",
    "piss",
    "hell",
    "cunt",
    "retard",
    "retarded",
    "nigger",
    "faggot",
    "fag",
]

# ---------------------------------------------------------------------------
# URL detection pattern
# ---------------------------------------------------------------------------

URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+|'  # http/https URLs
    r'www\.[^\s<>"{}|\\^`\[\]]+|'       # www. URLs
    r'[a-zA-Z0-9-]+\.(com|org|net|io|co|ai|dev|app|xyz|us|me|info)\b(/[^\s]*)?',  # bare domains
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Check functions — each returns a list of issue strings
# ---------------------------------------------------------------------------


def check_blocked_topics(text_lower, config):
    """Check text against blocked topics from config.yaml."""
    issues = []
    content_filter = config.get("policy", {}).get("content_filter", {})
    blocked_topics = content_filter.get("blocked_topics", [])

    # Map topic keys to detection patterns
    topic_patterns = {
        "partisan_politics": [
            "republican", "democrat", "maga", "liberal", "conservative",
            "left wing", "right wing", "gop", "dnc", "trump", "biden",
            "political party", "vote for", "voting for",
        ],
        "religion": [
            "pray", "prayer", "jesus", "god bless", "allah", "bible says",
            "church", "mosque", "scripture", "sermon",
        ],
        "personal_attacks": [
            "idiot", "moron", "stupid person", "incompetent",
            "loser", "clown", "fraud",
        ],
        "competitor_bashing": [
            "competitor sucks", "worse than us", "inferior product",
            "they can't", "their product fails",
        ],
        "financial_advice": [
            "buy this stock", "invest in", "financial advice",
            "guaranteed return", "get rich", "not financial advice",
        ],
        "medical_claims": [
            "cures", "treats disease", "medical advice", "heals",
            "prevents cancer", "medical claim",
        ],
    }

    for topic in blocked_topics:
        # Direct topic name match (e.g., "partisan politics" in text)
        topic_words = topic.replace("_", " ")
        if topic_words in text_lower:
            issues.append(f"contains blocked topic: '{topic_words}'")
            continue

        # Pattern-based detection
        patterns = topic_patterns.get(topic, [])
        for pattern in patterns:
            if pattern in text_lower:
                issues.append(f"contains blocked topic indicator: '{pattern}' (topic: {topic})")
                break  # One match per topic is enough

    return issues


def check_cannabis_phrases(text_lower, config):
    """Check text against cannabis 'never say' phrases."""
    issues = []
    content_filter = config.get("policy", {}).get("content_filter", {})
    cannabis_rules = content_filter.get("cannabis_rules", {})
    never_say = cannabis_rules.get("never_say", [])
    alternatives = cannabis_rules.get("always_say_instead", [])

    for i, phrase in enumerate(never_say):
        if phrase.lower() in text_lower:
            suggestion = alternatives[i] if i < len(alternatives) else "see config.yaml for alternatives"
            issues.append(f"contains blocked phrase: '{phrase}' — say instead: '{suggestion}'")

    return issues


def check_length_limits(text, platform):
    """Check text against platform character limits."""
    issues = []

    if not platform:
        return issues

    char_limit = PLATFORM_CHAR_LIMITS.get(platform)
    if char_limit and len(text) > char_limit:
        issues.append(
            f"exceeds {platform} character limit: {len(text)}/{char_limit} characters"
        )

    return issues


def check_links(text, platform):
    """Flag links in main text for platforms where links hurt reach."""
    issues = []

    if not platform:
        return issues

    urls = URL_PATTERN.findall(text)
    if not urls:
        return issues

    # X: links in main tweet hurt reach; should go in reply
    if platform == "x":
        issues.append(
            "contains link in main text — X algorithm penalizes links in tweets. "
            "Put links in a reply instead."
        )

    # LinkedIn: links in post body hurt reach; should go in first comment
    if platform == "linkedin":
        issues.append(
            "contains link in main text — LinkedIn algorithm penalizes links in posts. "
            "Put links in the first comment instead."
        )

    return issues


def check_profanity(text_lower):
    """Check for profanity using word-boundary matching."""
    issues = []

    for word in PROFANITY_LIST:
        # Use word boundary matching to avoid false positives
        # (e.g., "class" should not match "ass")
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text_lower):
            issues.append(f"contains profanity: '{word}'")

    return issues


def check_linkedin_min_words(text, platform, config):
    """Check LinkedIn posts meet minimum word count for dwell time."""
    issues = []

    if platform != "linkedin":
        return issues

    platforms_cfg = config.get("platforms", {}).get("linkedin", {})
    min_words = platforms_cfg.get("min_word_count", 200)
    word_count = len(text.split())

    if word_count < min_words:
        issues.append(
            f"LinkedIn post too short: {word_count} words (minimum: {min_words}). "
            f"Longer posts get more dwell time and reach."
        )

    return issues


# ---------------------------------------------------------------------------
# Main check orchestration
# ---------------------------------------------------------------------------


def run_check(text, platform, config):
    """Run all content filter checks and return the result."""
    issues = []
    text_lower = text.lower()

    # 1. Blocked topics
    issues.extend(check_blocked_topics(text_lower, config))

    # 2. Cannabis never-say phrases
    issues.extend(check_cannabis_phrases(text_lower, config))

    # 3. Platform length limits
    issues.extend(check_length_limits(text, platform))

    # 4. Link detection
    issues.extend(check_links(text, platform))

    # 5. Profanity
    issues.extend(check_profanity(text_lower))

    # 6. LinkedIn minimum word count
    issues.extend(check_linkedin_min_words(text, platform, config))

    safe = len(issues) == 0

    result = {
        "safe": safe,
        "issues": issues,
        "text_length": len(text),
        "word_count": len(text.split()),
    }

    if platform:
        result["platform"] = platform
        char_limit = PLATFORM_CHAR_LIMITS.get(platform)
        if char_limit:
            result["char_limit"] = char_limit
            result["chars_remaining"] = char_limit - len(text)

    return result


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Content Filter — Check text against brand safety rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 tools/content_filter.py check --text "AI agents are transforming cannabis ops"
    python3 tools/content_filter.py check --text "Short post" --platform linkedin
    python3 tools/content_filter.py check --text "Check https://example.com" --platform x
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # check
    p = sub.add_parser("check", help="Check text against content safety rules")
    p.add_argument("--text", required=True, help="Text to check for safety issues")
    p.add_argument(
        "--platform",
        default=None,
        choices=["x", "linkedin", "threads"],
        help="Platform for platform-specific checks (length limits, link rules)",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.command == "check":
        config = load_config()
        result = run_check(args.text, args.platform, config)
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        emit({"ok": False, "error": "unknown_command", "message": f"Unknown command: {args.command}"})


if __name__ == "__main__":
    main()
