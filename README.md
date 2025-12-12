
# AI Student Performance Prediction System

This is a simple end‑to‑end machine learning project that predicts student performance (final grade / pass‑fail)
based on features like study time, previous scores, absences, etc.

## Features

- Data loading & preprocessing
- Model training using RandomForestClassifier
- Model evaluation (accuracy, classification report)
- REST API using FastAPI for online predictions
- Example synthetic dataset
- Reproducible via `requirements.txt`

## Project Structure

```text
.
├── app
│   └── main.py            # FastAPI app exposing /predict endpoint
├── model
│   ├── train_model.py     # Training script (reads CSV, trains, saves model & encoder)
│   └── __init__.py
├── data
│   └── students_sample.csv  # Synthetic example dataset
├── requirements.txt
└── README.md
```

## How to Run

1. Create and activate a virtual environment (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Train the model

```bash
python model/train_model.py
```

This will create `model/student_model.joblib` and `model/feature_config.json`.

4. Run the FastAPI server

```bash
uvicorn app.main:app --reload
```

The API will be available at:

- Docs (Swagger UI): http://127.0.0.1:8000/docs
- Prediction endpoint: POST http://127.0.0.1:8000/predict

## Example Request Body

```json
{
  "hours_study_per_day": 3,
  "past_average_score": 72,
  "absences": 4,
  "parent_education": "bachelor",
  "internet": "yes",
  "health": 4
}
```

## Notes

- The dataset here is synthetic and very small, just to make the project self‑contained.
- You can replace `data/students_sample.csv` with any real student performance dataset (ensure you adjust column names if needed).

## Frontend UI

A simple, modern web UI is available at:

- http://127.0.0.1:8000/        → Opens the predictor UI
- http://127.0.0.1:8000/static  → Also serves the same frontend (index.html)

The frontend is located in the `frontend/index.html` file and talks to the `/predict` API endpoint.
