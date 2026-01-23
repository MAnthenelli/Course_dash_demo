# Curricular Flows Demo (Cytoscape v4 — self-loops)

## What changed

- Added/normalized **self-loop edges (course → same course)** so that **each node's outgoing probabilities sum to 1**.
- Self-loops are shown as **looped arrows** with labels (retake/repeat share).
- No connectivity helpers UI.
- No Streamlit `use_container_width` warnings (Altair uses `width='stretch'`).

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Data

Balanced JSONs are in `data/`.
