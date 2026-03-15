#!/usr/bin/env python3
"""
Groundswell Learning Engine CLI.

Implements 7 learning loops with EMA smoothing, anti-overfitting,
and conservative early learning.

Usage:
    python3 tools/learning.py get-weights --platform x
    python3 tools/learning.py log-action --type reply --target @handle --platform x --metadata '{...}'
    python3 tools/learning.py log-content --post-id abc --platform x --metadata '{...}'
    python3 tools/learning.py log-edit --draft "..." --final "..."
    python3 tools/learning.py compute-weights
    python3 tools/learning.py audience-update
    python3 tools/learning.py conversion-check
    python3 tools/learning.py decay-check
    python3 tools/learning.py chain-update
    python3 tools/learning.py status
"""

import argparse
import difflib
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

try:
    import yaml
except ImportError:
    yaml = None


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")
CONFIG_PATH = os.path.join(REPO_ROOT, "config.yaml")

AUDIENCE_CLUSTERS = {
    "ai_builder": re.compile(
        r"\b(ai|artificial.intelligence|ml|machine.learning|agent|llm|gpt|"
        r"deep.learning|neural|nlp|automation)\b",
        re.IGNORECASE,
    ),
    "cannabis_ops": re.compile(
        r"\b(cannabis|hemp|dispensary|cultivation|grower|marijuana|weed|"
        r"thc|cbd|mjbiz|canna)\b",
        re.IGNORECASE,
    ),
    "vc": re.compile(
        r"\b(investor|venture|fund|angel|seed|series.[abcde]|capital|"
        r"portfolio|lp|gp)\b",
        re.IGNORECASE,
    ),
    "media": re.compile(
        r"\b(journalist|reporter|podcast|editor|writer|columnist|"
        r"newsletter|media|press)\b",
        re.IGNORECASE,
    ),
    "executive": re.compile(
        r"\b(ceo|cto|coo|cfo|cmo|vp|director|founder|co-founder|"
        r"president|partner|managing)\b",
        re.IGNORECASE,
    ),
}

DEFAULT_LEARNING_CONFIG = {
    "ema_alpha_early": 0.15,
    "ema_alpha_steady": 0.30,
    "early_period_weeks": 4,
    "exploration_ratio_start": 0.40,
    "exploration_ratio_floor": 0.20,
    "exploration_decay_posts": 1000,
    "min_samples_content_dna": 30,
    "min_samples_conversion": 10,
    "min_samples_audience": 5,
    "min_chains_for_model": 50,
    "max_weight_change_daily": 0.05,
    "max_weight_change_weekly": 0.20,
    "outlier_threshold": 10.0,
    "outlier_min_baseline_samples": 50,
    "decay_min_windows": 4,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_connection(db_path=None):
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def rows_to_list(rows):
    return [dict(r) for r in rows]


def load_config():
    """Load learning config from config.yaml, falling back to defaults."""
    if yaml is None:
        return dict(DEFAULT_LEARNING_CONFIG)
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_LEARNING_CONFIG)
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f) or {}
    merged = dict(DEFAULT_LEARNING_CONFIG)
    merged.update(cfg.get("learning", {}))
    return merged


def strategy_get(conn, key):
    """Read a JSON value from strategy_state, or None."""
    row = conn.execute(
        "SELECT value FROM strategy_state WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


def strategy_set(conn, key, value):
    """Upsert a JSON value into strategy_state with version bump."""
    ts = now_iso()
    existing = conn.execute(
        "SELECT version FROM strategy_state WHERE key = ?", (key,)
    ).fetchone()
    new_version = (existing["version"] + 1) if existing else 1
    conn.execute(
        "INSERT INTO strategy_state (key, value, version, updated_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
        "version = ?, updated_at = excluded.updated_at",
        (key, json.dumps(value), new_version, ts, new_version),
    )
    return new_version


def get_ema_alpha(conn, cfg):
    """Determine EMA alpha based on how long the system has been running."""
    row = conn.execute(
        "SELECT MIN(timestamp) as first_ts FROM events"
    ).fetchone()
    if row is None or row["first_ts"] is None:
        return cfg["ema_alpha_early"], 0.0
    first_ts = row["first_ts"].replace("Z", "+00:00")
    try:
        first_dt = datetime.fromisoformat(first_ts)
    except ValueError:
        return cfg["ema_alpha_early"], 0.0
    now = datetime.now(timezone.utc)
    weeks_active = (now - first_dt).total_seconds() / (7 * 24 * 3600)
    if weeks_active < cfg["early_period_weeks"]:
        return cfg["ema_alpha_early"], weeks_active
    return cfg["ema_alpha_steady"], weeks_active


def clamp_weight_change(new_val, old_val, max_change):
    """Bound weight change to +-max_change from previous value."""
    if old_val is None:
        return new_val
    delta = new_val - old_val
    if abs(delta) > max_change:
        return old_val + max_change * (1.0 if delta > 0 else -1.0)
    return new_val


def classify_edit(draft, final):
    """Classify the type of edit Brad made."""
    sm = difflib.SequenceMatcher(None, draft, final)
    ratio = sm.ratio()
    magnitude = 1.0 - ratio

    # Heuristic classification
    if magnitude < 0.05:
        return "minor_tweak", magnitude

    draft_words = set(draft.lower().split())
    final_words = set(final.lower().split())
    added = final_words - draft_words
    removed = draft_words - final_words

    # Mostly additions
    if len(added) > len(removed) * 2 and len(removed) < 5:
        return "content_addition", magnitude
    # Mostly removals
    if len(removed) > len(added) * 2 and len(added) < 5:
        return "content_removal", magnitude

    # Check structural changes (paragraph/sentence reordering)
    draft_lines = [l.strip() for l in draft.strip().split("\n") if l.strip()]
    final_lines = [l.strip() for l in final.strip().split("\n") if l.strip()]
    if len(draft_lines) != len(final_lines) and magnitude > 0.15:
        return "restructure", magnitude

    # Check for sentence reordering
    if set(draft_lines) == set(final_lines) and draft_lines != final_lines:
        return "restructure", magnitude

    # Default: tone/word-choice changes
    return "tone_shift", magnitude


# ---------------------------------------------------------------------------
# Subcommand: get-weights
# ---------------------------------------------------------------------------

def cmd_get_weights(args):
    conn = get_connection(args.db)
    platform = args.platform

    content_weights = strategy_get(conn, f"content_weights:{platform}")
    audience_weights = strategy_get(conn, f"audience_weights:{platform}")
    conversion_weights = strategy_get(conn, f"conversion_weights:{platform}")
    voice_patterns = strategy_get(conn, "voice_patterns")
    chain_model = strategy_get(conn, f"chain_model:{platform}")
    exploration_ratio = strategy_get(conn, "exploration_ratio")
    decay_alerts = strategy_get(conn, "decay_alerts")

    # Determine confidence level
    content_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_genome WHERE platform = ?",
        (platform,),
    ).fetchone()["cnt"]
    conversion_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM engagement_conversions "
        "WHERE platform = ? AND followed_back IS NOT NULL",
        (platform,),
    ).fetchone()["cnt"]
    audience_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM audience_graph WHERE platform = ?",
        (platform,),
    ).fetchone()["cnt"]

    cfg = load_config()
    confidence = 0.0
    if content_count >= cfg["min_samples_content_dna"]:
        confidence += 0.3
    if conversion_count >= cfg["min_samples_conversion"]:
        confidence += 0.3
    if audience_count >= cfg["min_samples_audience"]:
        confidence += 0.2
    if voice_patterns is not None:
        confidence += 0.2

    # Default priors when no weights exist
    default_content = {
        "hook_type": {},
        "format": {},
        "topic_cluster": {},
        "timing_hour": {},
        "emotional_register": {},
    }
    default_audience = {}
    default_conversion = {}

    conn.close()
    emit({
        "platform": platform,
        "content_weights": content_weights or default_content,
        "audience_weights": audience_weights or default_audience,
        "conversion_weights": conversion_weights or default_conversion,
        "voice_patterns": voice_patterns,
        "chain_model": chain_model,
        "exploration_ratio": exploration_ratio if exploration_ratio is not None else cfg["exploration_ratio_start"],
        "decay_alerts": decay_alerts,
        "confidence": round(confidence, 2),
        "sample_sizes": {
            "content": content_count,
            "conversions": conversion_count,
            "audience": audience_count,
        },
    })


# ---------------------------------------------------------------------------
# Subcommand: log-action
# ---------------------------------------------------------------------------

def cmd_log_action(args):
    conn = get_connection(args.db)
    ts = now_iso()

    meta = {}
    if args.metadata:
        try:
            meta = json.loads(args.metadata)
        except json.JSONDecodeError:
            conn.close()
            fail("Invalid JSON in --metadata")

    conn.execute(
        "INSERT INTO engagement_conversions "
        "(action_type, platform, target_handle, target_tier, topic, timing, "
        "touch_number, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            args.type,
            args.platform,
            args.target,
            meta.get("tier"),
            meta.get("topic"),
            meta.get("timing"),
            meta.get("touch_number"),
            ts,
        ),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    emit({"ok": True, "id": row_id, "created_at": ts})


# ---------------------------------------------------------------------------
# Subcommand: log-content
# ---------------------------------------------------------------------------

def cmd_log_content(args):
    conn = get_connection(args.db)
    ts = now_iso()

    meta = {}
    if args.metadata:
        try:
            meta = json.loads(args.metadata)
        except json.JSONDecodeError:
            conn.close()
            fail("Invalid JSON in --metadata")

    conn.execute(
        "INSERT OR IGNORE INTO content_genome "
        "(post_id, platform, posted_at, hook_type, format, length_bucket, "
        "has_image, has_video, has_screenshot, topic_cluster, "
        "emotional_register, identity_bucket, timing_hour, timing_day, "
        "created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            args.post_id,
            args.platform,
            meta.get("posted_at", ts),
            meta.get("hook_type"),
            meta.get("format"),
            meta.get("length_bucket"),
            1 if meta.get("has_image") else 0,
            1 if meta.get("has_video") else 0,
            1 if meta.get("has_screenshot") else 0,
            meta.get("topic_cluster"),
            meta.get("emotional_register"),
            meta.get("identity_bucket"),
            meta.get("timing_hour"),
            meta.get("timing_day"),
            ts,
        ),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    emit({"ok": True, "id": row_id, "post_id": args.post_id, "created_at": ts})


# ---------------------------------------------------------------------------
# Subcommand: log-edit
# ---------------------------------------------------------------------------

def cmd_log_edit(args):
    conn = get_connection(args.db)
    ts = now_iso()

    classification, magnitude = classify_edit(args.draft, args.final)

    # Extract specific patterns from the diff
    sm = difflib.SequenceMatcher(None, args.draft.split(), args.final.split())
    patterns = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            patterns.append({
                "op": tag,
                "from": " ".join(args.draft.split()[i1:i2]) if i1 < i2 else "",
                "to": " ".join(args.final.split()[j1:j2]) if j1 < j2 else "",
            })

    conn.execute(
        "INSERT INTO edit_signals "
        "(draft_text, final_text, edit_classification, edit_magnitude, "
        "specific_patterns, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            args.draft,
            args.final,
            classification,
            round(magnitude, 4),
            json.dumps(patterns[:20]),  # cap pattern list
            ts,
        ),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    emit({
        "ok": True,
        "id": row_id,
        "classification": classification,
        "magnitude": round(magnitude, 4),
        "pattern_count": len(patterns),
        "created_at": ts,
    })


# ---------------------------------------------------------------------------
# Subcommand: compute-weights (the main learning cascade)
# ---------------------------------------------------------------------------

def cmd_compute_weights(args):
    conn = get_connection(args.db)
    cfg = load_config()
    alpha, weeks_active = get_ema_alpha(conn, cfg)
    ts = now_iso()
    updates = []

    # -----------------------------------------------------------------------
    # Step 1: Content DNA weights (Loop 1)
    # -----------------------------------------------------------------------
    platforms = [r["platform"] for r in conn.execute(
        "SELECT DISTINCT platform FROM content_genome"
    ).fetchall()]

    content_features = [
        "hook_type", "format", "topic_cluster",
        "timing_hour", "emotional_register",
    ]

    for platform in platforms:
        rows = rows_to_list(conn.execute(
            "SELECT * FROM content_genome WHERE platform = ? "
            "AND performance_multiple IS NOT NULL",
            (platform,),
        ).fetchall())

        if not rows:
            continue

        # Compute baseline average
        all_perf = [r["performance_multiple"] for r in rows if r["performance_multiple"] is not None]
        if not all_perf:
            continue
        baseline = sum(all_perf) / len(all_perf)

        old_weights = strategy_get(conn, f"content_weights:{platform}") or {}
        new_weights = {}

        for feature in content_features:
            buckets = defaultdict(list)
            for r in rows:
                val = r.get(feature)
                if val is not None:
                    buckets[str(val)].append(r["performance_multiple"])

            feature_weights = {}
            old_feature = old_weights.get(feature, {})

            for bucket_val, perfs in buckets.items():
                if len(perfs) < cfg["min_samples_content_dna"]:
                    # Not enough samples -- keep old weight or skip
                    if bucket_val in old_feature:
                        feature_weights[bucket_val] = {
                            "weight": old_feature[bucket_val].get("weight", 1.0),
                            "samples": len(perfs),
                            "sufficient": False,
                        }
                    continue

                avg_perf = sum(perfs) / len(perfs)

                # Outlier detection
                outlier = False
                if (baseline > 0
                        and avg_perf > cfg["outlier_threshold"] * baseline
                        and len(perfs) < cfg["outlier_min_baseline_samples"]):
                    outlier = True

                # EMA smoothing
                old_weight = None
                if bucket_val in old_feature:
                    old_weight = old_feature[bucket_val].get("weight")

                if old_weight is not None:
                    ema_val = alpha * avg_perf + (1 - alpha) * old_weight
                else:
                    ema_val = avg_perf

                # Bound weight change
                ema_val = clamp_weight_change(
                    ema_val, old_weight, cfg["max_weight_change_weekly"]
                )

                feature_weights[bucket_val] = {
                    "weight": round(ema_val, 4),
                    "samples": len(perfs),
                    "sufficient": True,
                    "outlier_suspected": outlier,
                }

            new_weights[feature] = feature_weights

        strategy_set(conn, f"content_weights:{platform}", new_weights)
        updates.append(f"content_weights:{platform}")

    # -----------------------------------------------------------------------
    # Step 2: Audience cluster weights (Loop 2)
    # -----------------------------------------------------------------------
    for platform in platforms:
        rows = rows_to_list(conn.execute(
            "SELECT account_cluster, "
            "AVG(connector_score) as avg_connector, "
            "AVG(conversion_value) as avg_conversion, "
            "COUNT(*) as cnt "
            "FROM audience_graph WHERE platform = ? "
            "GROUP BY account_cluster",
            (platform,),
        ).fetchall())

        if not rows:
            continue

        old_aud = strategy_get(conn, f"audience_weights:{platform}") or {}
        new_aud = {}

        for r in rows:
            cluster = r["account_cluster"] or "other"
            if r["cnt"] < cfg["min_samples_audience"]:
                if cluster in old_aud:
                    new_aud[cluster] = old_aud[cluster]
                continue

            score = (r["avg_connector"] or 0.0) + (r["avg_conversion"] or 0.0)
            old_score = old_aud.get(cluster, {}).get("weight")

            if old_score is not None:
                ema_val = alpha * score + (1 - alpha) * old_score
            else:
                ema_val = score

            new_aud[cluster] = {
                "weight": round(ema_val, 4),
                "samples": r["cnt"],
                "avg_connector": round(r["avg_connector"] or 0, 4),
                "avg_conversion": round(r["avg_conversion"] or 0, 4),
            }

        strategy_set(conn, f"audience_weights:{platform}", new_aud)
        updates.append(f"audience_weights:{platform}")

    # -----------------------------------------------------------------------
    # Step 3: Conversion model (Loop 3)
    # -----------------------------------------------------------------------
    conv_platforms = [r["platform"] for r in conn.execute(
        "SELECT DISTINCT platform FROM engagement_conversions "
        "WHERE followed_back IS NOT NULL"
    ).fetchall()]

    for platform in conv_platforms:
        rows = rows_to_list(conn.execute(
            "SELECT action_type, target_tier, "
            "COUNT(*) as total, "
            "SUM(CASE WHEN followed_back = 1 THEN 1 ELSE 0 END) as converted "
            "FROM engagement_conversions "
            "WHERE platform = ? AND followed_back IS NOT NULL "
            "GROUP BY action_type, target_tier",
            (platform,),
        ).fetchall())

        if not rows:
            continue

        old_conv = strategy_get(conn, f"conversion_weights:{platform}") or {}
        new_conv = {}

        for r in rows:
            key = f"{r['action_type']}:tier{r['target_tier'] or 'unknown'}"
            if r["total"] < cfg["min_samples_conversion"]:
                if key in old_conv:
                    new_conv[key] = old_conv[key]
                continue

            rate = r["converted"] / r["total"] if r["total"] > 0 else 0.0
            old_rate = old_conv.get(key, {}).get("rate")

            if old_rate is not None:
                ema_rate = alpha * rate + (1 - alpha) * old_rate
            else:
                ema_rate = rate

            new_conv[key] = {
                "rate": round(ema_rate, 4),
                "samples": r["total"],
                "raw_rate": round(rate, 4),
            }

        strategy_set(conn, f"conversion_weights:{platform}", new_conv)
        updates.append(f"conversion_weights:{platform}")

    # -----------------------------------------------------------------------
    # Step 4: Voice patterns (Loop 4)
    # -----------------------------------------------------------------------
    edit_rows = rows_to_list(conn.execute(
        "SELECT edit_classification, edit_magnitude, created_at "
        "FROM edit_signals ORDER BY created_at"
    ).fetchall())

    if edit_rows:
        # Aggregate by classification
        class_counts = defaultdict(int)
        class_magnitudes = defaultdict(list)
        for r in edit_rows:
            cls = r["edit_classification"] or "unknown"
            class_counts[cls] += 1
            if r["edit_magnitude"] is not None:
                class_magnitudes[cls].append(r["edit_magnitude"])

        # Compute edit frequency trend (compare first half to second half)
        mid = len(edit_rows) // 2
        first_half = edit_rows[:mid] if mid > 0 else edit_rows
        second_half = edit_rows[mid:] if mid > 0 else []

        if first_half and second_half:
            try:
                first_start = datetime.fromisoformat(
                    first_half[0]["created_at"].replace("Z", "+00:00")
                )
                first_end = datetime.fromisoformat(
                    first_half[-1]["created_at"].replace("Z", "+00:00")
                )
                second_start = datetime.fromisoformat(
                    second_half[0]["created_at"].replace("Z", "+00:00")
                )
                second_end = datetime.fromisoformat(
                    second_half[-1]["created_at"].replace("Z", "+00:00")
                )
                first_days = max((first_end - first_start).total_seconds() / 86400, 1)
                second_days = max((second_end - second_start).total_seconds() / 86400, 1)
                first_rate = len(first_half) / first_days
                second_rate = len(second_half) / second_days
                trend = "declining" if second_rate < first_rate * 0.8 else (
                    "increasing" if second_rate > first_rate * 1.2 else "stable"
                )
            except (ValueError, TypeError):
                trend = "unknown"
        else:
            trend = "insufficient_data"

        voice = {
            "total_edits": len(edit_rows),
            "edit_frequency_trend": trend,
            "classifications": {
                cls: {
                    "count": class_counts[cls],
                    "avg_magnitude": round(
                        sum(class_magnitudes[cls]) / len(class_magnitudes[cls]), 4
                    ) if class_magnitudes[cls] else 0,
                }
                for cls in class_counts
            },
            "most_common_edit": max(class_counts, key=class_counts.get),
        }

        strategy_set(conn, "voice_patterns", voice)
        updates.append("voice_patterns")

    # -----------------------------------------------------------------------
    # Step 5: Chain model (Loop 6)
    # -----------------------------------------------------------------------
    chain_platforms = [r["platform"] for r in conn.execute(
        "SELECT DISTINCT platform FROM touchpoint_chain"
    ).fetchall()]

    for platform in chain_platforms:
        chain_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM touchpoint_chain WHERE platform = ?",
            (platform,),
        ).fetchone()["cnt"]

        if chain_count < cfg["min_chains_for_model"]:
            continue

        chains = rows_to_list(conn.execute(
            "SELECT touchpoint_sequence, outcome, days_to_follow "
            "FROM touchpoint_chain WHERE platform = ?",
            (platform,),
        ).fetchall())

        # Group by sequence pattern
        seq_stats = defaultdict(lambda: {"outcomes": [], "days": []})
        for c in chains:
            seq = c["touchpoint_sequence"] or "unknown"
            seq_stats[seq]["outcomes"].append(c["outcome"])
            if c["days_to_follow"] is not None:
                seq_stats[seq]["days"].append(c["days_to_follow"])

        model = {}
        for seq, stats in seq_stats.items():
            followed = sum(1 for o in stats["outcomes"] if o == "followed")
            total = len(stats["outcomes"])
            avg_days = (
                round(sum(stats["days"]) / len(stats["days"]), 2)
                if stats["days"] else None
            )
            model[seq] = {
                "conversion_rate": round(followed / total, 4) if total > 0 else 0,
                "avg_days_to_follow": avg_days,
                "sample_size": total,
            }

        # Sort by conversion rate to find best sequences
        best = sorted(
            model.items(), key=lambda x: x[1]["conversion_rate"], reverse=True
        )[:10]

        chain_data = {
            "total_chains": chain_count,
            "sequences": model,
            "best_sequences": [{"sequence": k, **v} for k, v in best],
        }

        strategy_set(conn, f"chain_model:{platform}", chain_data)
        updates.append(f"chain_model:{platform}")

    # -----------------------------------------------------------------------
    # Step 6: Decay detection (Loop 7)
    # -----------------------------------------------------------------------
    decay_alerts = _compute_decay(conn, cfg)
    if decay_alerts is not None:
        strategy_set(conn, "decay_alerts", decay_alerts)
        updates.append("decay_alerts")

    # -----------------------------------------------------------------------
    # Step 7: Exploration ratio
    # -----------------------------------------------------------------------
    total_posts = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_genome"
    ).fetchone()["cnt"]

    start = cfg["exploration_ratio_start"]
    floor = cfg["exploration_ratio_floor"]
    decay_posts = cfg["exploration_decay_posts"]

    if decay_posts > 0 and total_posts > 0:
        ratio = max(floor, start - (start - floor) * (total_posts / decay_posts))
    else:
        ratio = start

    strategy_set(conn, "exploration_ratio", round(ratio, 4))
    updates.append("exploration_ratio")

    # -----------------------------------------------------------------------
    # Step 8: Write model compilation
    # -----------------------------------------------------------------------
    model_keys = [u for u in updates if u != "exploration_ratio" and u != "decay_alerts"]
    for mk in model_keys:
        data = strategy_get(conn, mk)
        sample_size = 0
        confidence = 0.0

        if isinstance(data, dict):
            # Estimate sample size from nested data
            for v in data.values():
                if isinstance(v, dict):
                    if "samples" in v:
                        sample_size += v["samples"]
                    for inner in v.values():
                        if isinstance(inner, dict) and "samples" in inner:
                            sample_size += inner["samples"]

            confidence = min(1.0, sample_size / 100.0)

        existing_model = conn.execute(
            "SELECT model_version FROM learned_models WHERE model_key = ?",
            (mk,),
        ).fetchone()
        new_version = (existing_model["model_version"] + 1) if existing_model else 1

        conn.execute(
            "INSERT INTO learned_models "
            "(model_key, model_version, model_data, confidence, sample_size, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(model_key) DO UPDATE SET "
            "model_version = ?, model_data = excluded.model_data, "
            "confidence = excluded.confidence, sample_size = excluded.sample_size, "
            "updated_at = excluded.updated_at",
            (mk, new_version, json.dumps(data), round(confidence, 4),
             sample_size, ts, new_version),
        )

    conn.commit()
    conn.close()

    emit({
        "ok": True,
        "ema_alpha": alpha,
        "weeks_active": round(weeks_active, 2),
        "total_posts": total_posts,
        "exploration_ratio": round(ratio, 4),
        "updates": updates,
        "timestamp": ts,
    })


# ---------------------------------------------------------------------------
# Shared decay computation
# ---------------------------------------------------------------------------

def _compute_decay(conn, cfg):
    """Compute decay alerts from pattern_effectiveness table."""
    window_count = conn.execute(
        "SELECT COUNT(DISTINCT window_start) as cnt FROM pattern_effectiveness"
    ).fetchone()["cnt"]

    if window_count < cfg["decay_min_windows"]:
        return None

    patterns = rows_to_list(conn.execute(
        "SELECT pattern_key, platform, window_start, avg_performance, sample_count "
        "FROM pattern_effectiveness ORDER BY pattern_key, window_start"
    ).fetchall())

    if not patterns:
        return None

    # Group by pattern_key
    grouped = defaultdict(list)
    for p in patterns:
        grouped[(p["pattern_key"], p["platform"])].append(p)

    alerts = []
    for (pattern_key, platform), windows in grouped.items():
        if len(windows) < cfg["decay_min_windows"]:
            continue

        all_perfs = [w["avg_performance"] for w in windows if w["avg_performance"] is not None]
        if len(all_perfs) < cfg["decay_min_windows"]:
            continue

        historical_avg = sum(all_perfs) / len(all_perfs)
        recent_avg = sum(all_perfs[-2:]) / len(all_perfs[-2:])

        if historical_avg <= 0:
            continue

        change_pct = (recent_avg - historical_avg) / historical_avg

        status = "stable"
        if change_pct < -0.40:
            status = "retired"
        elif change_pct < -0.20:
            status = "declining"

        if status != "stable":
            alerts.append({
                "pattern_key": pattern_key,
                "platform": platform,
                "status": status,
                "historical_avg": round(historical_avg, 4),
                "recent_avg": round(recent_avg, 4),
                "change_pct": round(change_pct, 4),
                "windows_analyzed": len(all_perfs),
            })

    return {"alerts": alerts, "computed_at": now_iso()}


# ---------------------------------------------------------------------------
# Subcommand: decay-check
# ---------------------------------------------------------------------------

def cmd_decay_check(args):
    conn = get_connection(args.db)
    cfg = load_config()

    # First, compute rolling windows and insert into pattern_effectiveness
    # Get content data for windowing
    now = datetime.now(timezone.utc)
    windows_inserted = 0

    for days_back, label in [(7, "7d"), (14, "14d"), (30, "30d")]:
        window_start = (now - timedelta(days=days_back)).isoformat().replace("+00:00", "Z")
        window_end = now.isoformat().replace("+00:00", "Z")

        # Content patterns
        rows = rows_to_list(conn.execute(
            "SELECT hook_type, format, topic_cluster, platform, "
            "AVG(performance_multiple) as avg_perf, COUNT(*) as cnt "
            "FROM content_genome "
            "WHERE posted_at >= ? AND performance_multiple IS NOT NULL "
            "GROUP BY hook_type, format, topic_cluster, platform",
            (window_start,),
        ).fetchall())

        for r in rows:
            pattern_key = f"{r['hook_type'] or 'none'}:{r['format'] or 'none'}:{r['topic_cluster'] or 'none'}"
            platform = r["platform"]

            # Check if this window already exists
            existing = conn.execute(
                "SELECT id FROM pattern_effectiveness "
                "WHERE pattern_key = ? AND platform = ? "
                "AND window_start = ? AND window_end = ?",
                (pattern_key, platform, window_start, window_end),
            ).fetchone()

            if existing:
                continue

            conn.execute(
                "INSERT INTO pattern_effectiveness "
                "(pattern_key, platform, window_start, window_end, "
                "sample_count, avg_performance, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pattern_key, platform, window_start, window_end,
                 r["cnt"], r["avg_perf"], now_iso()),
            )
            windows_inserted += 1

    conn.commit()

    # Now compute decay
    decay_alerts = _compute_decay(conn, cfg)
    if decay_alerts is not None:
        strategy_set(conn, "decay_alerts", decay_alerts)
        conn.commit()

    conn.close()
    emit({
        "ok": True,
        "windows_inserted": windows_inserted,
        "decay_alerts": decay_alerts,
    })


# ---------------------------------------------------------------------------
# Subcommand: audience-update
# ---------------------------------------------------------------------------

def cmd_audience_update(args):
    conn = get_connection(args.db)
    ts = now_iso()

    # Scan recent engagement events
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    events = rows_to_list(conn.execute(
        "SELECT details FROM events "
        "WHERE event_type IN ('engagement', 'reply', 'like', 'repost', 'follow', 'outbound_engagement') "
        "AND timestamp >= ?",
        (cutoff,),
    ).fetchall())

    updated = 0
    created = 0

    for event in events:
        if not event.get("details"):
            continue
        try:
            details = json.loads(event["details"])
        except (json.JSONDecodeError, TypeError):
            continue

        handle = details.get("target_handle") or details.get("handle")
        platform = details.get("platform", "x")
        if not handle:
            continue

        # Check if account exists
        existing = conn.execute(
            "SELECT * FROM audience_graph WHERE handle = ? AND platform = ?",
            (handle, platform),
        ).fetchone()

        bio = details.get("bio", "")
        follower_count = details.get("follower_count")

        # Classify cluster
        cluster = "other"
        if bio:
            for cluster_name, pattern in AUDIENCE_CLUSTERS.items():
                if pattern.search(bio):
                    cluster = cluster_name
                    break

        if existing:
            conn.execute(
                "UPDATE audience_graph SET "
                "total_interactions = total_interactions + 1, "
                "last_interaction = ?, "
                "bio = COALESCE(?, bio), "
                "follower_count = COALESCE(?, follower_count), "
                "account_cluster = ? "
                "WHERE handle = ? AND platform = ?",
                (ts, bio or None, follower_count, cluster, handle, platform),
            )
            updated += 1
        else:
            conn.execute(
                "INSERT INTO audience_graph "
                "(handle, platform, follower_count, bio, account_cluster, "
                "total_interactions, first_interaction, last_interaction) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (handle, platform, follower_count, bio, cluster, ts, ts),
            )
            created += 1

    conn.commit()
    conn.close()
    emit({
        "ok": True,
        "events_scanned": len(events),
        "accounts_updated": updated,
        "accounts_created": created,
    })


# ---------------------------------------------------------------------------
# Subcommand: conversion-check
# ---------------------------------------------------------------------------

def cmd_conversion_check(args):
    conn = get_connection(args.db)

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    pending = rows_to_list(conn.execute(
        "SELECT id, action_type, platform, target_handle, target_tier, "
        "created_at "
        "FROM engagement_conversions "
        "WHERE followed_back IS NULL AND created_at <= ?",
        (cutoff,),
    ).fetchall())

    conn.close()
    emit({
        "ok": True,
        "pending_checks": pending,
        "count": len(pending),
        "note": "Each entry needs follow-back verification via x_api.py. "
                "Update followed_back and follower_delta fields after checking.",
    })


# ---------------------------------------------------------------------------
# Subcommand: chain-update
# ---------------------------------------------------------------------------

def cmd_chain_update(args):
    conn = get_connection(args.db)
    ts = now_iso()

    # Build touchpoint chains from engagement_conversions
    # Group actions by target_handle + platform
    actions = rows_to_list(conn.execute(
        "SELECT target_handle, platform, action_type, followed_back, "
        "created_at "
        "FROM engagement_conversions "
        "WHERE target_handle IS NOT NULL "
        "ORDER BY target_handle, platform, created_at",
    ).fetchall())

    chains_by_target = defaultdict(list)
    for a in actions:
        key = (a["target_handle"], a["platform"])
        chains_by_target[key].append(a)

    inserted = 0
    for (handle, platform), touches in chains_by_target.items():
        if len(touches) < 2:
            continue

        # Build sequence string
        sequence = " -> ".join(t["action_type"] for t in touches)

        # Determine outcome
        followed = any(t.get("followed_back") == 1 for t in touches)
        outcome = "followed" if followed else "not_followed"

        # Calculate days from first to last touch (or follow)
        try:
            first_dt = datetime.fromisoformat(
                touches[0]["created_at"].replace("Z", "+00:00")
            )
            last_dt = datetime.fromisoformat(
                touches[-1]["created_at"].replace("Z", "+00:00")
            )
            days = (last_dt - first_dt).total_seconds() / 86400
        except (ValueError, TypeError):
            days = None

        # Check if this chain already exists for this handle+platform
        existing = conn.execute(
            "SELECT id FROM touchpoint_chain "
            "WHERE target_handle = ? AND platform = ?",
            (handle, platform),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE touchpoint_chain SET "
                "touchpoint_sequence = ?, outcome = ?, "
                "days_to_follow = ? "
                "WHERE id = ?",
                (sequence, outcome, round(days, 2) if days else None,
                 existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO touchpoint_chain "
                "(target_handle, platform, touchpoint_sequence, outcome, "
                "days_to_follow, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (handle, platform, sequence, outcome,
                 round(days, 2) if days else None, ts),
            )
            inserted += 1

    conn.commit()
    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM touchpoint_chain"
    ).fetchone()["cnt"]
    conn.close()

    emit({
        "ok": True,
        "chains_inserted": inserted,
        "targets_analyzed": len(chains_by_target),
        "total_chains": total,
    })


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------

def cmd_status(args):
    conn = get_connection(args.db)
    cfg = load_config()

    content_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_genome"
    ).fetchone()["cnt"]
    audience_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM audience_graph"
    ).fetchone()["cnt"]
    conversion_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM engagement_conversions"
    ).fetchone()["cnt"]
    edit_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM edit_signals"
    ).fetchone()["cnt"]
    chain_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM touchpoint_chain"
    ).fetchone()["cnt"]

    exploration = strategy_get(conn, "exploration_ratio")
    _, weeks_active = get_ema_alpha(conn, cfg)

    # Per-platform sample counts
    platform_counts = rows_to_list(conn.execute(
        "SELECT platform, COUNT(*) as content_posts FROM content_genome "
        "GROUP BY platform"
    ).fetchall())

    platform_conversions = rows_to_list(conn.execute(
        "SELECT platform, COUNT(*) as conversions FROM engagement_conversions "
        "GROUP BY platform"
    ).fetchall())

    platform_audience = rows_to_list(conn.execute(
        "SELECT platform, COUNT(*) as accounts FROM audience_graph "
        "GROUP BY platform"
    ).fetchall())

    # Model confidence levels
    models = rows_to_list(conn.execute(
        "SELECT model_key, model_version, confidence, sample_size, updated_at "
        "FROM learned_models ORDER BY model_key"
    ).fetchall())

    # Learning phase
    phase = "early" if weeks_active < cfg["early_period_weeks"] else "steady"

    conn.close()
    emit({
        "total_content_posts": content_count,
        "total_audience_accounts": audience_count,
        "total_conversions_tracked": conversion_count,
        "total_edit_signals": edit_count,
        "total_touchpoint_chains": chain_count,
        "exploration_ratio": exploration if exploration is not None else cfg["exploration_ratio_start"],
        "weeks_active": round(weeks_active, 2),
        "learning_phase": phase,
        "early_period_weeks": cfg["early_period_weeks"],
        "per_platform": {
            "content": {r["platform"]: r["content_posts"] for r in platform_counts},
            "conversions": {r["platform"]: r["conversions"] for r in platform_conversions},
            "audience": {r["platform"]: r["accounts"] for r in platform_audience},
        },
        "models": models,
    })


def cmd_drift_check(args):
    """Check current system state against immutable baseline anchors.

    Compares actual content mix, identity allocation, voice scores,
    and behavioral metrics against the bounds in baseline_anchors.json.
    If anything is outside bounds for 2+ consecutive weeks, flags it.
    """
    conn = get_connection(args.db)

    anchors_path = os.path.join(REPO_ROOT, "data", "baseline_anchors.json")
    if not os.path.exists(anchors_path):
        emit({"ok": False, "error": "baseline_anchors.json not found"})
        return

    with open(anchors_path) as f:
        anchors = json.load(f)

    alerts = []
    metrics = {}

    # 1. Check content mix ratios (last 2 weeks of posts)
    try:
        rows = conn.execute(
            "SELECT identity_bucket, COUNT(*) as cnt FROM content_genome "
            "WHERE created_at > datetime('now', '-14 days') GROUP BY identity_bucket"
        ).fetchall()
        total = sum(r["cnt"] for r in rows) if rows else 0
        if total > 0:
            mix = {r["identity_bucket"]: r["cnt"] / total for r in rows}
            metrics["content_mix"] = mix

            # Check content_mix_targets
            for key, bounds in anchors.get("content_mix_targets", {}).items():
                actual = mix.get(key, 0)
                if actual < bounds["min"]:
                    alerts.append({
                        "type": "content_mix_low",
                        "metric": key,
                        "actual": round(actual, 3),
                        "min": bounds["min"],
                        "target": bounds["target"],
                    })
                elif actual > bounds["max"]:
                    alerts.append({
                        "type": "content_mix_high",
                        "metric": key,
                        "actual": round(actual, 3),
                        "max": bounds["max"],
                        "target": bounds["target"],
                    })
    except Exception:
        pass

    # 2. Check identity allocation (last 2 weeks)
    try:
        rows = conn.execute(
            "SELECT topic_cluster, COUNT(*) as cnt FROM content_genome "
            "WHERE created_at > datetime('now', '-14 days') GROUP BY topic_cluster"
        ).fetchall()
        total = sum(r["cnt"] for r in rows) if rows else 0
        if total > 0:
            alloc = {r["topic_cluster"]: r["cnt"] / total for r in rows}
            metrics["identity_allocation"] = alloc

            for key, bounds in anchors.get("identity_allocation_targets", {}).items():
                actual = alloc.get(key, 0)
                if actual < bounds["min"]:
                    alerts.append({
                        "type": "identity_drift_low",
                        "metric": key,
                        "actual": round(actual, 3),
                        "min": bounds["min"],
                    })
                elif actual > bounds["max"]:
                    alerts.append({
                        "type": "identity_drift_high",
                        "metric": key,
                        "actual": round(actual, 3),
                        "max": bounds["max"],
                    })
    except Exception:
        pass

    # 3. Check consecutive engagement bait (behavioral guardrail)
    try:
        rows = conn.execute(
            "SELECT identity_bucket FROM content_genome "
            "ORDER BY id DESC LIMIT 10"
        ).fetchall()
        consecutive_bait = 0
        max_consecutive_bait = 0
        for r in rows:
            if r["identity_bucket"] == "engagement_bait":
                consecutive_bait += 1
                max_consecutive_bait = max(max_consecutive_bait, consecutive_bait)
            else:
                consecutive_bait = 0

        max_allowed = anchors.get("behavioral_guardrails", {}).get("max_engagement_bait_consecutive", 2)
        if max_consecutive_bait > max_allowed:
            alerts.append({
                "type": "engagement_bait_streak",
                "consecutive": max_consecutive_bait,
                "max_allowed": max_allowed,
            })
        metrics["max_consecutive_engagement_bait"] = max_consecutive_bait
    except Exception:
        pass

    # 4. Check strategy weight velocity (are weights changing too fast?)
    try:
        rows = conn.execute(
            "SELECT model_key, model_data, updated_at FROM learned_models "
            "ORDER BY updated_at DESC LIMIT 10"
        ).fetchall()
        metrics["active_models"] = len(rows)
    except Exception:
        pass

    # Determine overall status
    if alerts:
        status = "DRIFT_DETECTED"
    else:
        status = "ANCHORED"

    conn.close()

    result = {
        "status": status,
        "alerts": alerts,
        "alert_count": len(alerts),
        "metrics": metrics,
        "anchors_version": anchors.get("version", 0),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    emit(result)

    # If drift detected, also send Telegram alert
    if alerts and not args.quiet:
        try:
            import subprocess
            alert_text = f"⚠️ DRIFT DETECTED — {len(alerts)} anchor violations:\n\n"
            for a in alerts[:5]:
                alert_text += f"• {a['type']}: {a.get('metric', '')} = {a.get('actual', a.get('consecutive', '?'))}\n"
            alert_text += "\nReview and re-anchor before next strategy update."
            subprocess.run(
                ["python3", os.path.join(REPO_ROOT, "tools", "telegram.py"), "alert", "--level", "warning", "--text", alert_text],
                capture_output=True, timeout=30,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Learning Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default=None, help="Override database path")
    sub = parser.add_subparsers(dest="command")

    # get-weights
    p = sub.add_parser("get-weights", help="Get current learned weights for a platform")
    p.add_argument("--platform", required=True)

    # log-action
    p = sub.add_parser("log-action", help="Log an outbound engagement action")
    p.add_argument("--type", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--platform", required=True)
    p.add_argument("--metadata", default=None)

    # log-content
    p = sub.add_parser("log-content", help="Log a published post")
    p.add_argument("--post-id", required=True)
    p.add_argument("--platform", required=True)
    p.add_argument("--metadata", default=None)

    # log-edit
    p = sub.add_parser("log-edit", help="Log Brad's edit to a draft")
    p.add_argument("--draft", required=True)
    p.add_argument("--final", required=True)

    # compute-weights
    sub.add_parser("compute-weights", help="Run full learning cascade (Sunday job)")

    # audience-update
    sub.add_parser("audience-update", help="Refresh audience clusters from recent events")

    # conversion-check
    sub.add_parser("conversion-check", help="List pending follow-back checks")

    # decay-check
    sub.add_parser("decay-check", help="Detect declining content patterns")

    # chain-update
    sub.add_parser("chain-update", help="Update touchpoint chain model")

    # status
    sub.add_parser("status", help="Learning engine status overview")

    # drift-check
    p = sub.add_parser("drift-check", help="Check system against baseline anchors for drift")
    p.add_argument("--quiet", action="store_true", help="Suppress Telegram alerts")

    return parser


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

COMMANDS = {
    "get-weights": cmd_get_weights,
    "log-action": cmd_log_action,
    "log-content": cmd_log_content,
    "log-edit": cmd_log_edit,
    "compute-weights": cmd_compute_weights,
    "audience-update": cmd_audience_update,
    "conversion-check": cmd_conversion_check,
    "decay-check": cmd_decay_check,
    "chain-update": cmd_chain_update,
    "status": cmd_status,
    "drift-check": cmd_drift_check,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    handler = COMMANDS.get(args.command)
    if not handler:
        fail(f"Unknown command: {args.command}")

    try:
        handler(args)
    except Exception as e:
        fail(f"Error: {e}")


if __name__ == "__main__":
    main()
