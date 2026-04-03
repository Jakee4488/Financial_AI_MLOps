"""Export latest metrics to JSON files for the performance dashboard.

Usage:
    python scripts/financial/export_dashboard_metrics.py --output-dir dashboard/data/
"""

import argparse
import json
import os
import sys

from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def export_sample_data(output_dir: str) -> None:
    """Export sample dashboard data for demo/testing."""
    os.makedirs(output_dir, exist_ok=True)

    # Tournament results
    tournament = {
        "winner": "xgboost",
        "timestamp": "2026-04-03T16:00:00Z",
        "results": [
            {"model": "lightgbm", "metrics": {"pr_auc": 0.892, "f1_score": 0.761, "precision": 0.834, "recall": 0.699}, "training_time_s": 12.3},
            {"model": "xgboost", "metrics": {"pr_auc": 0.915, "f1_score": 0.783, "precision": 0.851, "recall": 0.724}, "training_time_s": 15.7},
            {"model": "random_forest", "metrics": {"pr_auc": 0.847, "f1_score": 0.712, "precision": 0.795, "recall": 0.645}, "training_time_s": 8.2},
            {"model": "isolation_forest", "metrics": {"pr_auc": 0.821, "f1_score": 0.689, "precision": 0.743, "recall": 0.642}, "training_time_s": 4.1},
        ],
    }
    _write_json(output_dir, "tournament_results.json", tournament)

    # Champion history
    champion = {
        "champion": {"model_type": "xgboost", "version": "12", "metrics": {"pr_auc": 0.908, "f1_score": 0.775, "precision": 0.842, "recall": 0.717}},
        "challenger": {"model_type": "xgboost", "version": "13", "metrics": {"pr_auc": 0.915, "f1_score": 0.783, "precision": 0.851, "recall": 0.724}},
        "decision": "PROMOTE",
        "improvement": {"pr_auc": 0.007, "f1_score": 0.008, "precision": 0.009, "recall": 0.007},
    }
    _write_json(output_dir, "champion_history.json", champion)

    # Drift metrics
    drift = {
        "psi": 0.12,
        "js_divergence": 0.06,
        "overall_drift": False,
        "drifted_features": [],
        "psi_threshold": 0.20,
        "js_threshold": 0.10,
    }
    _write_json(output_dir, "drift_metrics.json", drift)

    # Performance timeline
    timeline = [
        {"date": "2026-03-28", "pr_auc": 0.901, "f1_score": 0.758, "precision": 0.831, "recall": 0.696},
        {"date": "2026-03-29", "pr_auc": 0.905, "f1_score": 0.762, "precision": 0.836, "recall": 0.700},
        {"date": "2026-03-30", "pr_auc": 0.908, "f1_score": 0.775, "precision": 0.842, "recall": 0.717},
        {"date": "2026-03-31", "pr_auc": 0.903, "f1_score": 0.770, "precision": 0.838, "recall": 0.712},
        {"date": "2026-04-01", "pr_auc": 0.910, "f1_score": 0.779, "precision": 0.845, "recall": 0.721},
        {"date": "2026-04-02", "pr_auc": 0.912, "f1_score": 0.781, "precision": 0.848, "recall": 0.722},
        {"date": "2026-04-03", "pr_auc": 0.915, "f1_score": 0.783, "precision": 0.851, "recall": 0.724},
    ]
    _write_json(output_dir, "performance_timeline.json", timeline)

    # Deployment events
    events = [
        {"type": "deploy", "version": "13", "model": "xgboost", "time": "2h ago", "decision": "PROMOTE"},
        {"type": "rollback", "version": "11", "model": "lightgbm", "time": "1d ago", "reason": "Performance degradation"},
        {"type": "deploy", "version": "12", "model": "xgboost", "time": "3d ago", "decision": "PROMOTE"},
        {"type": "retrain", "version": "12", "model": "xgboost", "time": "3d ago", "reason": "Data drift detected"},
        {"type": "deploy", "version": "10", "model": "lightgbm", "time": "7d ago", "decision": "PROMOTE"},
    ]
    _write_json(output_dir, "deployment_events.json", events)

    logger.info(f"Exported 5 dashboard data files to {output_dir}")


def _write_json(directory: str, filename: str, data: dict | list) -> None:
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"  → {filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Dashboard Metrics")
    parser.add_argument("--output-dir", type=str, default="dashboard/data/", help="Output directory for JSON files")
    args = parser.parse_args()

    export_sample_data(args.output_dir)


if __name__ == "__main__":
    main()
