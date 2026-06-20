"""Streamlit dashboard for the Reusable Data Quality Profiler."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from profiler import DataProfiler

BASE_DIR = Path(__file__).parent
DEFAULT_CSV = BASE_DIR / "sample_data.csv"
DEFAULT_RULES = BASE_DIR / "rules.yaml"

st.set_page_config(
    page_title="Data Quality Profiler",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _save_upload_to_temp(uploaded_file, suffix: str) -> Path:
    """Persist an uploaded file to a temporary path for the profiler."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getvalue())
    tmp.close()
    return Path(tmp.name)


def _validate_rules_file(rules_path: Path) -> dict:
    """Load and validate the rules YAML structure."""
    with rules_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if config is None:
        raise ValueError("Rules file is empty. Define a 'columns' section with validation rules.")

    if not isinstance(config, dict):
        raise ValueError("Rules file must be a YAML mapping with a top-level 'columns' key.")

    columns = config.get("columns")
    if not columns or not isinstance(columns, dict):
        raise ValueError("Rules file must include a non-empty 'columns' section.")

    return config


def _validate_csv_file(csv_path: Path) -> pd.DataFrame:
    """Load and validate the dataset CSV."""
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=True)
    if df.empty:
        raise ValueError("Dataset CSV is empty. Upload a file with at least one data row.")
    return df


def run_profiler(csv_path: Path, rules_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, float, pd.DataFrame]:
    """Validate inputs, execute the profiler, and return results plus the source dataset."""
    _validate_rules_file(rules_path)
    source_df = _validate_csv_file(csv_path)

    profiler = DataProfiler(csv_path, rules_path)
    profiler.load()
    summary_df, failures_df = profiler.run()
    return summary_df, failures_df, profiler.global_score, source_df


def count_unique_failed_rows(failures_df: pd.DataFrame) -> int:
    """Count distinct dataset rows that failed at least one rule."""
    if failures_df.empty:
        return 0

    meta_cols = {"failed_column", "failed_rule"}
    data_cols = [col for col in failures_df.columns if col not in meta_cols]
    return int(failures_df[data_cols].drop_duplicates().shape[0])


def format_summary_for_display(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the summary table with human-friendly formatting."""
    display_df = summary_df.copy()
    if "success_rate" in display_df.columns:
        display_df["success_rate"] = display_df["success_rate"].map(lambda value: f"{value:.1f}%")
    return display_df


def render_metrics(global_score: float, summary_df: pd.DataFrame, failures_df: pd.DataFrame) -> None:
    """Render the top-row metric cards."""
    total_rules = len(summary_df)
    failed_records = count_unique_failed_rows(failures_df)
    passing = global_score >= 90.0

    score_col, rules_col, failed_col = st.columns(3)

    with score_col:
        st.metric(
            label="Global Data Quality Score",
            value=f"{global_score:.1f}%",
            delta="Passing" if passing else "Needs attention",
            delta_color="normal" if passing else "inverse",
        )
        if passing:
            st.caption("Score is at or above the 90% quality threshold.")
        else:
            st.caption("Score is below the 90% quality threshold.")

    with rules_col:
        passed_rules = int((summary_df["status"] == "Pass").sum()) if not summary_df.empty else 0
        failed_rules = total_rules - passed_rules
        st.metric(
            label="Total Rules Evaluated",
            value=total_rules,
            delta=f"{passed_rules} passed / {failed_rules} failed",
            delta_color="off",
        )

    with failed_col:
        st.metric(
            label="Total Failed Records",
            value=failed_records,
            delta="Unique rows with violations",
            delta_color="off",
        )


def render_rule_summary(summary_df: pd.DataFrame) -> None:
    """Render the rule summary tab."""
    st.subheader("Rule Summary")
    st.dataframe(format_summary_for_display(summary_df), use_container_width=True, hide_index=True)

    if not summary_df.empty:
        st.markdown("##### Success Rate by Rule")
        chart_df = summary_df.copy()
        chart_df["rule_label"] = chart_df["column"] + " / " + chart_df["rule_type"]
        chart_df = chart_df.set_index("rule_label")[["success_rate"]].sort_values("success_rate")
        st.bar_chart(chart_df)


def render_failure_explorer(failures_df: pd.DataFrame) -> None:
    """Render the failure explorer tab with optional filters."""
    st.subheader("Detailed Validation Failures")

    if failures_df.empty:
        st.success("🎉 All checks passed! Your data is clean.")
        return

    filter_col, filter_rule = st.columns(2)

    column_options = ["All"] + sorted(failures_df["failed_column"].dropna().unique().tolist())
    rule_options = ["All"] + sorted(failures_df["failed_rule"].dropna().unique().tolist())

    with filter_col:
        selected_column = st.selectbox("Filter by Column", column_options, key="failure_column_filter")

    with filter_rule:
        selected_rule = st.selectbox("Filter by Rule Type", rule_options, key="failure_rule_filter")

    filtered = failures_df.copy()
    if selected_column != "All":
        filtered = filtered[filtered["failed_column"] == selected_column]
    if selected_rule != "All":
        filtered = filtered[filtered["failed_rule"] == selected_rule]

    st.caption(f"Showing {len(filtered)} of {len(failures_df)} failure records.")
    st.dataframe(filtered, use_container_width=True, hide_index=True)


def main() -> None:
    st.title("📊 Reusable Data Quality Profiler")
    st.markdown(
        "Upload a dataset and rules configuration, or use the bundled sample files to "
        "explore data quality checks instantly."
    )

    with st.sidebar:
        st.header("Configuration")

        csv_upload = st.file_uploader("Dataset (CSV)", type=["csv"])
        yaml_upload = st.file_uploader("Rules (YAML)", type=["yaml", "yml"])

        if csv_upload is None:
            st.info(f"Using default dataset: `{DEFAULT_CSV.name}`")
        if yaml_upload is None:
            st.info(f"Using default rules: `{DEFAULT_RULES.name}`")

        run_clicked = st.button("Run Profiler", type="primary", use_container_width=True)

    should_run = run_clicked or "profiler_results" not in st.session_state

    if should_run:
        temp_paths: list[Path] = []
        try:
            csv_path = _save_upload_to_temp(csv_upload, ".csv") if csv_upload else DEFAULT_CSV
            rules_path = _save_upload_to_temp(yaml_upload, ".yaml") if yaml_upload else DEFAULT_RULES

            if csv_upload:
                temp_paths.append(csv_path)
            if yaml_upload:
                temp_paths.append(rules_path)

            summary_df, failures_df, global_score, _ = run_profiler(csv_path, rules_path)
            st.session_state.profiler_results = {
                "summary_df": summary_df,
                "failures_df": failures_df,
                "global_score": global_score,
            }
            st.session_state.profiler_error = None
        except yaml.YAMLError as exc:
            st.session_state.profiler_error = f"Invalid YAML rules file: {exc}"
            st.session_state.profiler_results = None
        except pd.errors.EmptyDataError:
            st.session_state.profiler_error = "The uploaded CSV file is empty or could not be parsed."
            st.session_state.profiler_results = None
        except pd.errors.ParserError as exc:
            st.session_state.profiler_error = f"Could not parse CSV file: {exc}"
            st.session_state.profiler_results = None
        except ValueError as exc:
            st.session_state.profiler_error = str(exc)
            st.session_state.profiler_results = None
        except Exception as exc:
            st.session_state.profiler_error = f"Profiler failed: {exc}"
            st.session_state.profiler_results = None
        finally:
            for path in temp_paths:
                path.unlink(missing_ok=True)

    if st.session_state.get("profiler_error"):
        st.error(st.session_state.profiler_error)
        return

    results = st.session_state.get("profiler_results")
    if not results:
        st.info("Configure your inputs in the sidebar and click **Run Profiler** to begin.")
        return

    summary_df = results["summary_df"]
    failures_df = results["failures_df"]
    global_score = results["global_score"]

    render_metrics(global_score, summary_df, failures_df)

    summary_tab, failures_tab = st.tabs(["Rule Summary", "Failure Explorer"])

    with summary_tab:
        render_rule_summary(summary_df)

    with failures_tab:
        render_failure_explorer(failures_df)


if __name__ == "__main__":
    main()
