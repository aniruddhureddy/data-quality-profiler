"""Core data quality profiler: evaluates CSV data against YAML-defined rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def _is_missing(series: pd.Series) -> pd.Series:
    """True where values are null, NaN, or blank/whitespace strings."""
    if series.empty:
        return pd.Series(dtype=bool)
    as_string = series.astype(str)
    return series.isna() | as_string.str.strip().eq("") | as_string.str.lower().eq("nan")


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _bounds_pass_mask(
    missing_mask: pd.Series, numeric_series: pd.Series, bound_check: pd.Series
) -> pd.Series:
    """Pass rows that are missing, non-numeric, or valid numbers meeting the bound."""
    non_numeric = ~missing_mask & numeric_series.isna()
    valid_numeric = numeric_series.notna()
    return missing_mask | non_numeric | (valid_numeric & bound_check)


def _build_rule_result(
    column: str,
    rule_type: str,
    total_checked: int,
    pass_mask: pd.Series,
) -> dict[str, Any]:
    passed_count = int(pass_mask.sum())
    failed_count = total_checked - passed_count
    success_rate = (passed_count / total_checked * 100) if total_checked else 0.0
    return {
        "column": column,
        "rule_type": rule_type,
        "total_checked": total_checked,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "success_rate": round(success_rate, 2),
        "status": "Pass" if failed_count == 0 else "Fail",
    }


class DataProfiler:
    """Load a CSV, apply YAML validation rules, and produce summary and failure reports."""

    def __init__(self, csv_path: str | Path, rules_path: str | Path) -> None:
        self.csv_path = Path(csv_path)
        self.rules_path = Path(rules_path)
        self.df: pd.DataFrame = pd.DataFrame()
        self.rules: dict[str, dict[str, Any]] = {}
        self.summary_df: pd.DataFrame = pd.DataFrame()
        self.failures_df: pd.DataFrame = pd.DataFrame()
        self._loaded = False

    def load(self) -> None:
        """Load CSV data and YAML rules into memory."""
        self.df = pd.read_csv(self.csv_path, dtype=str, keep_default_na=True)
        with self.rules_path.open(encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        self.rules = config.get("columns", {})
        self._loaded = True

    def run(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Execute all rules and return (summary_df, failures_df)."""
        if not self._loaded:
            self.load()

        total_checked = len(self.df)
        summary_rows: list[dict[str, Any]] = []
        failure_rows: list[pd.DataFrame] = []

        for column, column_rules in self.rules.items():
            if column not in self.df.columns:
                continue

            series = self.df[column]
            missing_mask = _is_missing(series)

            if column_rules.get("not_null"):
                pass_mask = ~missing_mask
                summary_rows.append(
                    _build_rule_result(column, "not_null", total_checked, pass_mask)
                )
                failure_rows.append(self._extract_failures(series, pass_mask, column, "not_null"))

            if column_rules.get("unique"):
                duplicate_mask = series.duplicated(keep=False) & ~missing_mask
                pass_mask = ~duplicate_mask
                summary_rows.append(
                    _build_rule_result(column, "unique", total_checked, pass_mask)
                )
                failure_rows.append(self._extract_failures(series, pass_mask, column, "unique"))

            type_rule = column_rules.get("type")
            if type_rule:
                pass_mask = self._evaluate_type_rule(series, missing_mask, type_rule)
                summary_rows.append(
                    _build_rule_result(column, "type", total_checked, pass_mask)
                )
                failure_rows.append(
                    self._extract_failures(series, pass_mask, column, f"type:{type_rule}")
                )

            numeric_series = _to_numeric(series)

            if "min_value" in column_rules:
                min_value = column_rules["min_value"]
                pass_mask = _bounds_pass_mask(
                    missing_mask, numeric_series, numeric_series >= min_value
                )
                summary_rows.append(
                    _build_rule_result(column, "min_value", total_checked, pass_mask)
                )
                failure_rows.append(
                    self._extract_failures(series, pass_mask, column, "min_value")
                )

            if "max_value" in column_rules:
                max_value = column_rules["max_value"]
                pass_mask = _bounds_pass_mask(
                    missing_mask, numeric_series, numeric_series <= max_value
                )
                summary_rows.append(
                    _build_rule_result(column, "max_value", total_checked, pass_mask)
                )
                failure_rows.append(
                    self._extract_failures(series, pass_mask, column, "max_value")
                )

        self.summary_df = pd.DataFrame(summary_rows)
        self.failures_df = (
            pd.concat(failure_rows, ignore_index=True)
            if failure_rows
            else pd.DataFrame(columns=[*self.df.columns, "failed_column", "failed_rule"])
        )
        return self.summary_df, self.failures_df

    @property
    def global_score(self) -> float:
        """Average success rate across all evaluated rules."""
        if self.summary_df.empty:
            return 0.0
        return round(float(self.summary_df["success_rate"].mean()), 2)

    @staticmethod
    def _evaluate_type_rule(
        series: pd.Series, missing_mask: pd.Series, type_rule: str
    ) -> pd.Series:
        if type_rule == "numeric":
            converted = _to_numeric(series)
            return missing_mask | converted.notna()

        if type_rule == "date":
            converted = _to_datetime(series)
            return missing_mask | converted.notna()

        if type_rule == "text":
            # CSV values are string-like; defer emptiness checks to not_null.
            return pd.Series(True, index=series.index)

        raise ValueError(f"Unsupported type rule: {type_rule!r}")

    def _extract_failures(
        self,
        series: pd.Series,
        pass_mask: pd.Series,
        column: str,
        rule_type: str,
    ) -> pd.DataFrame:
        fail_mask = ~pass_mask
        if not fail_mask.any():
            return pd.DataFrame()

        failed = self.df.loc[fail_mask].copy()
        failed["failed_column"] = column
        failed["failed_rule"] = rule_type
        return failed.reset_index(drop=True)


def profile_dataset(
    csv_path: str | Path, rules_path: str | Path
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Convenience wrapper: run profiler and return summary, failures, and global score."""
    profiler = DataProfiler(csv_path, rules_path)
    profiler.load()
    summary_df, failures_df = profiler.run()
    return summary_df, failures_df, profiler.global_score


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    csv_file = base_dir / "sample_data.csv"
    rules_file = base_dir / "rules.yaml"

    profiler = DataProfiler(csv_file, rules_file)
    profiler.load()
    summary, failures = profiler.run()

    print(f"Global Data Quality Score: {profiler.global_score}%")
    print()
    print("Summary:")
    print(summary.to_string(index=False))
    print()
    print(f"Total failure records: {len(failures)}")
