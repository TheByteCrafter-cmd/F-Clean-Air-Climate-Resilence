"""
VayuDrishti — LightGBM Pilot Model Training Script (Phase 1E-J2C)

Executes model training for +1h, +3h, and +6h PM2.5 forecasting over real Anand Vihar historical telemetry,
evaluates performance against persistence baseline, and saves model and evaluation artifacts.
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from ml.src.forecasting.trainer import LightGBMPilotTrainer


def main():
    print("================================================================================")
    print("VAYUDRISHTI — LIGHTGBM PILOT MODEL TRAINING (PHASE 1E-J2C)")
    print("================================================================================")

    trainer = LightGBMPilotTrainer()
    results = trainer.run_training_pipeline()

    print("\nScope Statement:")
    print(" ", results["scope_statement"])

    print(f"\nDerived Feature Count: {results['feature_count']}")
    print("Feature Columns:", results["feature_columns"])

    print("\n=== MODEL PERFORMANCE SUMMARY (TEST SET EVALUATION) ===")
    for h in ["+1h", "+3h", "+6h"]:
        res = results["horizon_models"][h]
        test_m = res["split_metrics"]["test"]
        pers_m = res["persistence_comparison"]
        overfit = res["overfitting_diagnostic"]

        print(f"\n--- HORIZON {h} ---")
        print(f"  Model Artifact  : {res['model_filename']}")
        print(f"  Best Iteration  : {res['best_iteration']}")
        print(f"  Split Rows      : Train={res['split_metrics']['train']['sample_count']}, Val={res['split_metrics']['validation']['sample_count']}, Test={test_m['sample_count']}")
        print(f"  Test Range      : {res['split_ranges']['test'][0]} to {res['split_ranges']['test'][1]}")
        print(f"  LightGBM Test   : MAE={test_m['mae']} µg/m³, RMSE={test_m['rmse']} µg/m³, sMAPE={test_m['smape']}%")
        print(f"  Persistence Test: MAE={pers_m['persistence_mae']} µg/m³, RMSE={pers_m['persistence_rmse']} µg/m³, sMAPE={pers_m['persistence_smape']}%")
        print(f"  MAE Improvement : {pers_m['mae_improvement_pct']}%")
        print(f"  RMSE Improvement: {pers_m['rmse_improvement_pct']}%")
        print(f"  Negative Preds  : {res['sanity_check']['negative_predictions_count']}")
        print(f"  Overfitting Flag: {overfit['flagged']} (Test/Train RMSE Ratio: {overfit['ratio_test_train_rmse']})")

        print("  Top 5 Features  :")
        for imp in res["feature_importance"][:5]:
            print(f"    - {imp['feature']}: {imp['importance']} ({imp['importance_type']})")

    print("\n=== ARTIFACTS CREATED ===")
    for k, v in results["artifacts"].items():
        print(f"  - {k}: {v}")

    print("\n================================================================================")
    print("TRAINING COMPLETE — MODEL AND EVALUATION ARTIFACTS SAVED")
    print("================================================================================")


if __name__ == "__main__":
    main()
