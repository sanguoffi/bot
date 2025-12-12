import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report, r2_score, mean_absolute_error
import joblib
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "students_sample.csv")
CLASS_MODEL_PATH = os.path.join(BASE_DIR, "model", "student_model.joblib")          # pass/fail
SCORE_MODEL_PATH = os.path.join(BASE_DIR, "model", "student_score_model.joblib")   # score
CONFIG_PATH = os.path.join(BASE_DIR, "model", "feature_config.json")


def main():
    print(f"Loading data from: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)

    # Features and targets
    feature_cols = [
        "hours_study_per_day",
        "past_average_score",
        "absences",
        "parent_education",
        "internet",
        "health",
    ]
    target_pass_col = "passed"
    target_score_col = "final_score"

    X = df[feature_cols]
    y_pass = df[target_pass_col]
    y_score = df[target_score_col]

    numeric_features = ["hours_study_per_day", "past_average_score", "absences", "health"]
    categorical_features = ["parent_education", "internet"]

    numeric_transformer = "passthrough"
    categorical_transformer = OneHotEncoder(handle_unknown="ignore")

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ]
    )

    # 1. Classification model (pass/fail)
    clf = RandomForestClassifier(
        n_estimators=150,
        random_state=42,
        class_weight="balanced",
    )
    clf_pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", clf),
        ]
    )

    X_train_c, X_test_c, y_train_c, y_test_c = train_test_split(
        X, y_pass, test_size=0.2, random_state=42, stratify=y_pass
    )

    print("Training classification model (pass/fail)...")
    clf_pipeline.fit(X_train_c, y_train_c)
    y_pred_c = clf_pipeline.predict(X_test_c)
    acc = accuracy_score(y_test_c, y_pred_c)
    print(f"[Classifier] Accuracy: {acc:.3f}")
    print("[Classifier] Classification report:")
    print(classification_report(y_test_c, y_pred_c))

    joblib.dump(clf_pipeline, CLASS_MODEL_PATH)
    print(f"Classification model saved to: {CLASS_MODEL_PATH}")

    # 2. Regression model (final score out of 100)
    reg = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
    )
    reg_pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", reg),
        ]
    )

    X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(
        X, y_score, test_size=0.2, random_state=42
    )

    print("Training regression model (final score)...")
    reg_pipeline.fit(X_train_r, y_train_r)
    y_pred_r = reg_pipeline.predict(X_test_r)
    r2 = r2_score(y_test_r, y_pred_r)
    mae = mean_absolute_error(y_test_r, y_pred_r)
    print(f"[Regressor] R² score: {r2:.3f}")
    print(f"[Regressor] MAE: {mae:.2f} points")

    joblib.dump(reg_pipeline, SCORE_MODEL_PATH)
    print(f"Score prediction model saved to: {SCORE_MODEL_PATH}")

    # Save feature config
    config = {
        "feature_order": feature_cols,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"Feature config saved to: {CONFIG_PATH}")


if __name__ == "__main__":
    main()
