import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score, confusion_matrix


def evaluate(y, scores, threshold=.5):
    y, scores = np.asarray(y), np.asarray(scores)
    if not np.isfinite(scores).all():
        raise ValueError("Non-finite predictions")
    tn, fp, fn, tp = confusion_matrix(y, scores >= threshold, labels=[0, 1]).ravel()
    return {"auprc_average_precision": float(average_precision_score(y, scores)) if np.any(y == 1) else None,
            "sensitivity": float(tp/(tp+fn)) if tp+fn else None,
            "specificity": float(tn/(tn+fp)) if tn+fp else None,
            "auroc": float(roc_auc_score(y, scores)) if len(np.unique(y)) == 2 else None,
            "threshold": threshold, "count": len(y)}
