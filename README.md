# 📊 Reusable Data Quality Profiler

**Live Dashboard:** [👉 Click here to try the live app!](https://data-quality-profiler-vgj8jsdmjypzujqvytx4kg.streamlit.app/)

A lightweight, YAML-driven data validation engine and interactive dashboard built to automate data quality checks for data engineering pipelines. 
Built for portfolio demonstration in Data Engineering, Analytics Engineering, and Data Quality management roles.

## Overview

This platform ingests raw CSV datasets, evaluates them against explicitly defined YAML schema rules, and generates both high-level quality scores and granular failure logs. It is designed to prevent silent type coercion issues common in automated pipelines and provides a user-friendly UI for data stewards to investigate anomalies.

| Capability | Description |
| :--- | :--- |
| **Validation Engine** | Python/Pandas core that evaluates data without silent type coercion. |
| **YAML Configuration** | Declarative rule definitions separating logic from code. |
| **Failure Explorer** | Granular log of every failed row, filterable by column or rule type. |
| **Metric Scoring** | Automated calculation of a Global Data Quality Score for alerting. |
| **Interactive UI** | Streamlit dashboard for real-time file upload and visual profiling. |

---

## Architecture

### Data Flow

```text
dataset.csv ──┐
rules.yaml  ──┼──► profiler.py (Validation Engine) ──► app.py (UI) ──► Streamlit Dashboard
```

### Project Structure

```text
data_quality_profiler/
├── app.py              # Streamlit frontend dashboard and UI logic
├── profiler.py         # Core backend: reads data, executes rules, calculates scores
├── rules.yaml          # Declarative configuration file for schema validation
├── requirements.txt    # Project dependencies
├── sample_data.csv     # Mock dataset with intentional edge cases for demoing
└── README.md           # Project documentation
```

---

## Quick Start

### 1. Install Dependencies
Clone the repository and install the required Python packages:

```bash
git clone https://github.com/aniruddhureddy/data-quality-profiler.git
cd data-quality-profiler
python -m pip install -r requirements.txt
```

### 2. Run the Dashboard locally
Launch the Streamlit interface:

```bash
python -m streamlit run app.py
```
*The app will automatically open in your browser at `http://localhost:8501`.*

### 3. Run the Engine via CLI (Headless Mode)
To integrate the profiler into a backend pipeline or test it via the terminal:
```bash
python profiler.py
```

---

## Supported Validation Rules

The engine reads configurations from a `columns:` block in a YAML file. 

| Rule | Functionality | Edge Case Handling |
| :--- | :--- | :--- |
| `not_null` | Flags missing, empty, or whitespace-only values. | Evaluated before type coercion. |
| `unique` | Flags duplicate values within a specific column. | Ignores `NaN` values to prevent false duplicates. |
| `type: numeric` | Explicitly coerces text to numeric. | Non-numeric strings (e.g., `"abc"`) are flagged as type failures. |
| `type: date` | Explicitly coerces text to datetime. | Invalid formats are flagged as type failures. |
| `min/max_value` | Boundary limits for numeric columns. | Safely ignores rows that already failed `type: numeric` checks. |

**Sample `rules.yaml` syntax:**
```yaml
columns:
  age:
    not_null: true
    type: numeric
    min_value: 18
    max_value: 100
  email:
    not_null: true
    unique: true
    type: text
```

---

## Sample Output (CLI)

Running the headless validation outputs a clean summary for CI/CD or logging systems:

```text
============================================================
  DATA QUALITY PROFILER — RUN COMPLETE
============================================================
  Global Data Quality Score: 96.32%
  Total Rules Evaluated:     144
  Total Failed Records:      15
============================================================
```

---



## License

MIT — Portfolio and educational use.