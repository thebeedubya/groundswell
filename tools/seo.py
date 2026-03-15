#!/usr/bin/env python3
"""
Groundswell SEO monitoring tool.

CLI tool for search visibility monitoring, page audits, and SEO health checks.

Usage:
    python3 tools/seo.py audit --url https://dbradwood.com
    python3 tools/seo.py audit --url https://dbradwood.com/writing/some-post
    python3 tools/seo.py sitemap-check
    python3 tools/seo.py index-status
    python3 tools/seo.py rankings --keywords "Brad Wood,AI Operator"
    python3 tools/seo.py search-console --days 28
    python3 tools/seo.py internal-links --slug "post-slug"
    python3 tools/seo.py keyword-gaps
    python3 tools/seo.py competitors
    python3 tools/seo.py status
"""

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from _common import REPO_ROOT, emit, fail, now_iso


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SITE_URL = "https://dbradwood.com"
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"
CONTENT_DIR = os.path.join(REPO_ROOT, "content", "writing")
USER_AGENT = "Groundswell-SEO/1.0 (+https://dbradwood.com)"

# Ideal ranges
TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 120, 160


# ---------------------------------------------------------------------------
# HTML parser for SEO audit
# ---------------------------------------------------------------------------

class SEOHTMLParser(HTMLParser):
    """Extract SEO-relevant elements from an HTML document."""

    def __init__(self):
        super().__init__()
        self._tag_stack = []
        self._capture = None

        # Collected data
        self.title = None
        self.meta_description = None
        self.canonical = None
        self.robots_meta = None
        self.viewport = None
        self.og_tags = {}
        self.h1s = []
        self.h2s = []
        self.images = []          # list of {"src": ..., "alt": ...}
        self.links_internal = []
        self.links_external = []
        self.structured_data = [] # raw JSON-LD strings
        self._base_url = SITE_URL

    def set_base_url(self, url):
        self._base_url = url

    # -- parser callbacks ---------------------------------------------------

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self._tag_stack.append(tag)

        if tag == "title":
            self._capture = "title"
            self._capture_buf = []

        elif tag == "meta":
            name = (attrs_dict.get("name") or "").lower()
            prop = (attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content", "")

            if name == "description":
                self.meta_description = content
            elif name == "robots":
                self.robots_meta = content
            elif name == "viewport":
                self.viewport = content
            elif prop.startswith("og:"):
                self.og_tags[prop] = content

        elif tag == "link":
            rel = (attrs_dict.get("rel") or "").lower()
            href = attrs_dict.get("href", "")
            if rel == "canonical":
                self.canonical = href

        elif tag == "h1":
            self._capture = "h1"
            self._capture_buf = []

        elif tag == "h2":
            self._capture = "h2"
            self._capture_buf = []

        elif tag == "img":
            self.images.append({
                "src": attrs_dict.get("src", ""),
                "alt": attrs_dict.get("alt", ""),
            })

        elif tag == "a":
            href = attrs_dict.get("href", "")
            if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                parsed = urlparse(href)
                if parsed.netloc and parsed.netloc not in ("dbradwood.com", "www.dbradwood.com"):
                    self.links_external.append(href)
                else:
                    self.links_internal.append(href)

        elif tag == "script":
            stype = (attrs_dict.get("type") or "").lower()
            if stype == "application/ld+json":
                self._capture = "jsonld"
                self._capture_buf = []

    def handle_endtag(self, tag):
        if self._capture == "title" and tag == "title":
            self.title = "".join(self._capture_buf).strip()
            self._capture = None
        elif self._capture == "h1" and tag == "h1":
            self.h1s.append("".join(self._capture_buf).strip())
            self._capture = None
        elif self._capture == "h2" and tag == "h2":
            self.h2s.append("".join(self._capture_buf).strip())
            self._capture = None
        elif self._capture == "jsonld" and tag == "script":
            self.structured_data.append("".join(self._capture_buf).strip())
            self._capture = None

        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data):
        if self._capture is not None:
            self._capture_buf.append(data)


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def fetch(url, timeout=15):
    """Fetch a URL and return (status_code, body_text).  Raises on network error."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except HTTPError as exc:
        return exc.code, ""
    except URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Subcommands — fully implemented
# ---------------------------------------------------------------------------

def cmd_audit(args):
    """Full SEO audit for a single URL."""
    url = args.url
    try:
        status, html = fetch(url)
    except RuntimeError as exc:
        fail(str(exc))

    if status != 200:
        fail(f"HTTP {status} for {url}")

    parser = SEOHTMLParser()
    parser.set_base_url(url)
    try:
        parser.feed(html)
    except Exception as exc:
        fail(f"HTML parse error: {exc}")

    issues = []
    score = 100

    # --- Title tag ---
    if not parser.title:
        issues.append({"field": "title", "severity": "error", "message": "Missing <title> tag"})
        score -= 15
    else:
        tlen = len(parser.title)
        if tlen < TITLE_MIN:
            issues.append({"field": "title", "severity": "warning",
                           "message": f"Title too short ({tlen} chars, ideal {TITLE_MIN}-{TITLE_MAX})",
                           "value": parser.title})
            score -= 5
        elif tlen > TITLE_MAX:
            issues.append({"field": "title", "severity": "warning",
                           "message": f"Title too long ({tlen} chars, ideal {TITLE_MIN}-{TITLE_MAX})",
                           "value": parser.title})
            score -= 5

    # --- Meta description ---
    if not parser.meta_description:
        issues.append({"field": "meta_description", "severity": "error",
                       "message": "Missing meta description"})
        score -= 15
    else:
        dlen = len(parser.meta_description)
        if dlen < DESC_MIN:
            issues.append({"field": "meta_description", "severity": "warning",
                           "message": f"Meta description short ({dlen} chars, ideal {DESC_MIN}-{DESC_MAX})",
                           "value": parser.meta_description})
            score -= 5
        elif dlen > DESC_MAX:
            issues.append({"field": "meta_description", "severity": "warning",
                           "message": f"Meta description long ({dlen} chars, may be truncated)",
                           "value": parser.meta_description})
            score -= 3

    # --- H1 ---
    if len(parser.h1s) == 0:
        issues.append({"field": "h1", "severity": "error", "message": "No H1 tag found"})
        score -= 10
    elif len(parser.h1s) > 1:
        issues.append({"field": "h1", "severity": "warning",
                       "message": f"Multiple H1 tags ({len(parser.h1s)})", "values": parser.h1s})
        score -= 5

    # --- Canonical ---
    if not parser.canonical:
        issues.append({"field": "canonical", "severity": "warning",
                       "message": "No canonical URL set"})
        score -= 5

    # --- Robots meta ---
    if parser.robots_meta:
        robots_lower = parser.robots_meta.lower()
        if "noindex" in robots_lower:
            issues.append({"field": "robots", "severity": "error",
                           "message": "Page is set to noindex", "value": parser.robots_meta})
            score -= 20
        if "nofollow" in robots_lower:
            issues.append({"field": "robots", "severity": "warning",
                           "message": "Page is set to nofollow", "value": parser.robots_meta})
            score -= 5

    # --- Viewport ---
    if not parser.viewport:
        issues.append({"field": "viewport", "severity": "warning",
                       "message": "No viewport meta tag (mobile-unfriendly)"})
        score -= 5

    # --- OG tags ---
    expected_og = ["og:title", "og:description", "og:image", "og:url"]
    missing_og = [t for t in expected_og if t not in parser.og_tags]
    if missing_og:
        issues.append({"field": "og_tags", "severity": "warning",
                       "message": f"Missing OG tags: {', '.join(missing_og)}"})
        score -= 2 * len(missing_og)

    # --- Image alt text ---
    images_missing_alt = [img for img in parser.images if not img.get("alt")]
    if images_missing_alt:
        issues.append({"field": "images", "severity": "warning",
                       "message": f"{len(images_missing_alt)} image(s) missing alt text",
                       "images": [img["src"] for img in images_missing_alt[:5]]})
        score -= min(10, len(images_missing_alt) * 2)

    # --- Structured data ---
    has_structured = len(parser.structured_data) > 0
    if not has_structured:
        issues.append({"field": "structured_data", "severity": "info",
                       "message": "No JSON-LD structured data found"})
        score -= 3

    score = max(0, score)

    emit({
        "command": "audit",
        "url": url,
        "timestamp": now_iso(),
        "score": score,
        "title": parser.title,
        "meta_description": parser.meta_description,
        "canonical": parser.canonical,
        "h1_count": len(parser.h1s),
        "h1s": parser.h1s,
        "h2_count": len(parser.h2s),
        "image_count": len(parser.images),
        "images_missing_alt": len(images_missing_alt),
        "internal_links": len(parser.links_internal),
        "external_links": len(parser.links_external),
        "has_structured_data": has_structured,
        "has_viewport": parser.viewport is not None,
        "og_tags": parser.og_tags,
        "issues": issues,
    })


def cmd_sitemap_check(args):
    """Verify sitemap is accessible and parse its URLs."""
    try:
        status, body = fetch(SITEMAP_URL, timeout=20)
    except RuntimeError as exc:
        fail(str(exc))

    if status != 200:
        fail(f"Sitemap returned HTTP {status}")

    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        fail(f"Sitemap XML parse error: {exc}")

    # Handle namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    urls = []
    for url_elem in root.findall(f".//{ns}url"):
        loc = url_elem.find(f"{ns}loc")
        lastmod = url_elem.find(f"{ns}lastmod")
        if loc is not None and loc.text:
            urls.append({
                "loc": loc.text.strip(),
                "lastmod": lastmod.text.strip() if lastmod is not None and lastmod.text else None,
            })

    # Spot-check a few URLs (up to 5)
    broken = []
    for entry in urls[:5]:
        try:
            st, _ = fetch(entry["loc"], timeout=10)
            if st != 200:
                broken.append({"url": entry["loc"], "status": st})
        except RuntimeError:
            broken.append({"url": entry["loc"], "status": "error"})

    emit({
        "command": "sitemap-check",
        "timestamp": now_iso(),
        "sitemap_url": SITEMAP_URL,
        "url_count": len(urls),
        "sample_urls": [u["loc"] for u in urls[:10]],
        "broken_sample": broken,
        "status": "ok" if not broken else "issues_found",
    })


def cmd_internal_links(args):
    """Suggest internal links for a blog post based on local content."""
    slug = args.slug
    if not os.path.isdir(CONTENT_DIR):
        fail(f"Content directory not found: {CONTENT_DIR}")

    # Find the target post
    target_file = None
    for fname in os.listdir(CONTENT_DIR):
        if fname.replace(".mdx", "").replace(".md", "") == slug:
            target_file = os.path.join(CONTENT_DIR, fname)
            break

    if not target_file or not os.path.isfile(target_file):
        fail(f"Post not found: {slug} (looked in {CONTENT_DIR})")

    with open(target_file, "r", encoding="utf-8") as f:
        target_content = f.read().lower()

    # Build index of other posts: slug -> title + key phrases
    other_posts = []
    for fname in os.listdir(CONTENT_DIR):
        fslug = fname.replace(".mdx", "").replace(".md", "")
        if fslug == slug:
            continue
        fpath = os.path.join(CONTENT_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract title from frontmatter
        title = fslug
        title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1)

        other_posts.append({
            "slug": fslug,
            "title": title,
            "path": f"/writing/{fslug}",
        })

    # Find mentions: check if any other post's key terms appear in the target
    suggestions = []
    # Key topic phrases to look for
    topic_keywords = {
        "ai agent": "AI agents",
        "multi-agent": "multi-agent systems",
        "cannabis": "cannabis",
        "compliance": "compliance",
        "operator": "operator",
        "revenue": "revenue operations",
        "claude": "Claude",
        "automation": "automation",
        "exit-and-reinvoke": "exit-and-reinvoke pattern",
        "groundswell": "Groundswell",
        "brand": "brand building",
        "linkedin": "LinkedIn",
        "social media": "social media",
    }

    for post in other_posts:
        post_title_lower = post["title"].lower()
        matched_topics = []
        for keyword, label in topic_keywords.items():
            if keyword in target_content and keyword in post_title_lower:
                matched_topics.append(label)

        # Also check if the other post's slug words appear in the target
        slug_words = [w for w in post["slug"].split("-") if len(w) > 4]
        slug_matches = sum(1 for w in slug_words if w in target_content)

        if matched_topics or slug_matches >= 2:
            suggestions.append({
                "link_to": post["path"],
                "link_title": post["title"],
                "reason": f"Shared topics: {', '.join(matched_topics)}" if matched_topics
                          else f"Content overlap ({slug_matches} keyword matches)",
            })

    # Sort by number of reasons / relevance
    suggestions.sort(key=lambda s: len(s.get("reason", "")), reverse=True)

    emit({
        "command": "internal-links",
        "timestamp": now_iso(),
        "target_slug": slug,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions[:10],
        "total_posts_scanned": len(other_posts),
    })


def cmd_status(args):
    """Overall SEO health summary combining multiple checks."""
    results = {}

    # 1. Sitemap check
    try:
        status, body = fetch(SITEMAP_URL, timeout=15)
        if status == 200:
            try:
                root = ElementTree.fromstring(body)
                ns = ""
                if root.tag.startswith("{"):
                    ns = root.tag.split("}")[0] + "}"
                url_count = len(root.findall(f".//{ns}url"))
                results["sitemap"] = {"status": "ok", "url_count": url_count}
            except ElementTree.ParseError:
                results["sitemap"] = {"status": "error", "detail": "XML parse error"}
        else:
            results["sitemap"] = {"status": "error", "detail": f"HTTP {status}"}
    except RuntimeError as exc:
        results["sitemap"] = {"status": "error", "detail": str(exc)}

    # 2. Homepage audit (lightweight)
    try:
        status, html = fetch(SITE_URL, timeout=15)
        if status == 200:
            parser = SEOHTMLParser()
            parser.feed(html)
            homepage_issues = []
            if not parser.title:
                homepage_issues.append("missing title")
            if not parser.meta_description:
                homepage_issues.append("missing meta description")
            if len(parser.h1s) == 0:
                homepage_issues.append("missing H1")
            if not parser.canonical:
                homepage_issues.append("missing canonical")
            if not parser.viewport:
                homepage_issues.append("missing viewport")
            if not parser.structured_data:
                homepage_issues.append("no structured data")

            results["homepage"] = {
                "status": "ok" if not homepage_issues else "issues",
                "title": parser.title,
                "issues": homepage_issues,
            }
        else:
            results["homepage"] = {"status": "error", "detail": f"HTTP {status}"}
    except RuntimeError as exc:
        results["homepage"] = {"status": "error", "detail": str(exc)}

    # 3. GA4 measurement ID presence
    if "html" in dir() or True:
        try:
            _, homepage_html = fetch(SITE_URL, timeout=10)
            has_ga4 = "G-D1KM6BWGG4" in homepage_html or "gtag" in homepage_html
            results["analytics"] = {
                "status": "ok" if has_ga4 else "not_detected",
                "ga4_detected": has_ga4,
            }
        except RuntimeError:
            results["analytics"] = {"status": "unknown", "detail": "Could not fetch homepage"}

    # Overall health
    statuses = [v.get("status") for v in results.values()]
    if all(s == "ok" for s in statuses):
        overall = "healthy"
    elif any(s == "error" for s in statuses):
        overall = "degraded"
    else:
        overall = "needs_attention"

    emit({
        "command": "status",
        "timestamp": now_iso(),
        "overall": overall,
        "checks": results,
    })


# ---------------------------------------------------------------------------
# Subcommands — stubs (need API credentials)
# ---------------------------------------------------------------------------

def _stub(command, needs):
    """Return a standard 'not configured' stub response."""
    emit({
        "command": command,
        "timestamp": now_iso(),
        "status": "not_configured",
        "message": f"This command requires {needs}. Set up credentials to enable.",
        "setup_steps": [
            f"Obtain {needs} credentials",
            "Add credentials to config.yaml under seo.{} section".format(command.replace("-", "_")),
            "Re-run this command",
        ],
    })


def cmd_index_status(args):
    """Check Google indexing status. Requires Search Console API."""
    _stub("index-status", "Google Search Console API")


def cmd_rankings(args):
    """Check keyword rankings. Requires SERP API or Search Console."""
    keywords = [k.strip() for k in args.keywords.split(",")]
    emit({
        "command": "rankings",
        "timestamp": now_iso(),
        "status": "not_configured",
        "keywords_requested": keywords,
        "message": "Keyword ranking tracking requires a SERP API (e.g., SerpAPI, DataForSEO) "
                   "or Google Search Console API. Set up credentials to enable.",
        "setup_steps": [
            "Choose a SERP API provider or set up Search Console API",
            "Add API key to config.yaml under seo.rankings section",
            "Re-run this command",
        ],
    })


def cmd_search_console(args):
    """Get Search Console performance data. Requires API credentials."""
    days = args.days
    emit({
        "command": "search-console",
        "timestamp": now_iso(),
        "status": "not_configured",
        "days_requested": days,
        "message": "Search Console data requires Google Search Console API credentials.",
        "setup_steps": [
            "Create a Google Cloud project and enable Search Console API",
            "Create a service account and download credentials JSON",
            "Add credentials path to config.yaml under seo.search_console section",
            "Verify dbradwood.com ownership in Search Console",
            "Re-run this command",
        ],
    })


def cmd_keyword_gaps(args):
    """Identify content opportunities from keyword gaps. Requires ranking data."""
    _stub("keyword-gaps", "keyword ranking data (SERP API or Search Console)")


def cmd_competitors(args):
    """Track competitor rankings. Requires SERP data."""
    _stub("competitors", "SERP API for competitor tracking")


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="seo",
        description="Groundswell SEO monitoring tool",
    )
    sub = p.add_subparsers(dest="command")
    sub.required = True

    # audit
    sp = sub.add_parser("audit", help="Full page SEO audit")
    sp.add_argument("--url", required=True, help="URL to audit")
    sp.set_defaults(func=cmd_audit)

    # sitemap-check
    sp = sub.add_parser("sitemap-check", help="Verify sitemap accessibility")
    sp.set_defaults(func=cmd_sitemap_check)

    # index-status
    sp = sub.add_parser("index-status", help="Check Google indexing (stub)")
    sp.set_defaults(func=cmd_index_status)

    # rankings
    sp = sub.add_parser("rankings", help="Check keyword rankings (stub)")
    sp.add_argument("--keywords", required=True, help="Comma-separated keywords")
    sp.set_defaults(func=cmd_rankings)

    # search-console
    sp = sub.add_parser("search-console", help="Search Console data (stub)")
    sp.add_argument("--days", type=int, default=28, help="Days of data (default: 28)")
    sp.set_defaults(func=cmd_search_console)

    # internal-links
    sp = sub.add_parser("internal-links", help="Suggest internal links for a post")
    sp.add_argument("--slug", required=True, help="Post slug to analyze")
    sp.set_defaults(func=cmd_internal_links)

    # keyword-gaps
    sp = sub.add_parser("keyword-gaps", help="Content opportunities (stub)")
    sp.set_defaults(func=cmd_keyword_gaps)

    # competitors
    sp = sub.add_parser("competitors", help="Competitor rankings (stub)")
    sp.set_defaults(func=cmd_competitors)

    # status
    sp = sub.add_parser("status", help="Overall SEO health summary")
    sp.set_defaults(func=cmd_status)

    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
