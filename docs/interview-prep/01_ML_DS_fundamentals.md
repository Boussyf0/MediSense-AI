# 01 — ML & Data Science Fundamentals

> Bread-and-butter conceptual questions. Learn to answer each **out loud in 30–60s**.
> Format: **Q → crisp answer → "say this in an interview" one-liner.**

---

## 1. Learning paradigms

**Supervised** — labeled data, learn X→y. Classification (discrete) / regression (continuous).
**Unsupervised** — no labels; find structure. Clustering (k-means), dimensionality reduction (PCA), anomaly detection.
**Self-supervised** — labels generated from the data itself (next-token prediction in LLMs, masked LM).
**Reinforcement** — agent learns from reward signals via interaction.

> One-liner: "MediSense uses supervised (XGBoost no-show), a self-supervised LLM (RAG), and an LSTM trained on labeled vitals for anomaly detection."

---

## 2. Bias–Variance tradeoff ⭐ (asked constantly)

- **Bias** = error from wrong assumptions (model too simple) → **underfitting**.
- **Variance** = error from sensitivity to training data (model too complex) → **overfitting**.
- Total error = bias² + variance + irreducible noise.
- High bias → train & test both bad. High variance → train good, test bad (big gap).

**Fix high bias:** bigger/more complex model, more features, less regularization, train longer.
**Fix high variance:** more data, regularization, simpler model, dropout, early stopping, bagging.

> One-liner: "I diagnose by the train/val gap: small train error + large val error = variance problem → I add regularization or data."

---

## 3. Overfitting — how to prevent (name 5+)
1. More / augmented training data
2. Regularization (L1/L2, dropout)
3. Simpler model / fewer params
4. Early stopping (monitor val loss)
5. Cross-validation for honest estimates
6. Ensembling (bagging reduces variance)
7. Feature selection / reduce dimensionality

---

## 4. Regularization

- **L2 (Ridge):** penalty λ·Σw² → shrinks weights smoothly, keeps all features. Good default.
- **L1 (Lasso):** penalty λ·Σ|w| → drives some weights to **exactly 0** → feature selection / sparsity.
- **Elastic Net:** L1 + L2 combined.
- **Dropout (NN):** randomly zero neurons during training → prevents co-adaptation.
- **Why L1 → sparsity:** its gradient is constant (±λ), so it can push weights fully to zero; L2's gradient shrinks near zero so it never quite reaches it.

---

## 5. Train / Validation / Test & Cross-validation

- **Train** fits params, **validation** tunes hyperparams/model choice, **test** = final unbiased estimate (touch once).
- **k-fold CV:** split into k folds, train on k−1, validate on 1, rotate, average. Robust on small data.
- **Stratified k-fold:** preserves class ratios — use for imbalanced classification.
- **Time-series split:** never shuffle; train on past, validate on future (avoids leakage). ← relevant to vitals/appointments.
- **Data leakage:** test info sneaking into training (e.g., scaling before split, target-derived features). Causes great offline scores that collapse in prod.

---

## 6. Classification metrics ⭐⭐ (know cold)

Confusion matrix: TP, FP, TN, FN.

- **Accuracy** = (TP+TN)/all. Misleading on imbalance (99% accuracy predicting "no disease" when 1% sick).
- **Precision** = TP/(TP+FP) — "of predicted positives, how many right." Optimize when **false positives costly** (spam, flagging fraud to humans).
- **Recall (Sensitivity)** = TP/(TP+FN) — "of actual positives, how many caught." Optimize when **false negatives costly** (cancer screening, disease detection).
- **F1** = harmonic mean of precision & recall — single number when you need balance.
- **ROC-AUC** = P(model ranks a random positive above a random negative). Threshold-independent; 0.5 = random, 1.0 = perfect. Can look optimistic on heavy imbalance.
- **PR-AUC (Average Precision)** — better than ROC-AUC for **rare positives**.

> One-liner: "For no-show prediction the cost is asymmetric, so I looked at precision-recall and PR-AUC, not raw accuracy — the classes are imbalanced."

**Regression:** MAE (robust to outliers), MSE/RMSE (penalizes large errors), R² (variance explained), MAPE (% error).

---

## 7. Class imbalance (your no-show case)
- Metrics: use PR-AUC / F1 / recall, not accuracy.
- Resampling: **SMOTE** / oversample minority, undersample majority.
- **Class weights** (`scale_pos_weight` in XGBoost) — penalize minority errors more.
- Threshold tuning (move decision threshold off 0.5).
- Collect more minority data if possible.

---

## 8. Core algorithms (one-paragraph each)

**Linear Regression** — fit y = wᵀx + b minimizing MSE; closed-form or gradient descent. Assumes linearity, independence, homoscedasticity.

**Logistic Regression** — linear model + sigmoid → probability; trained with **cross-entropy** (log loss). Linear decision boundary; interpretable; strong baseline.

**Decision Tree** — recursively split features to maximize purity (Gini / entropy / info gain). Interpretable but high variance (overfits) → prune / limit depth.

**Random Forest** — **bagging** of many decorrelated trees on bootstrapped samples + random feature subsets; average/vote. Reduces variance; robust; little tuning.

**Gradient Boosting / XGBoost** ⭐ — **boosting**: trees added sequentially, each fitting the **residual errors** (gradient) of the ensemble. High accuracy on tabular data; regularization, handles missing values. Your no-show model.
- Bagging (parallel, reduces variance) vs Boosting (sequential, reduces bias) — common Q.

**SVM** — find max-margin separating hyperplane; kernel trick for non-linear. Strong on small/medium high-dim data.

**k-NN** — predict by majority/avg of k nearest points. No training; lazy; sensitive to scaling & curse of dimensionality.

**Naive Bayes** — Bayes' theorem + feature-independence assumption. Fast, great for text baselines.

**k-Means** — partition into k clusters minimizing within-cluster variance; pick k via elbow/silhouette. Sensitive to init (k-means++) & scale.

**PCA** — project to orthogonal directions of max variance (eigenvectors of covariance) → reduce dimensions while keeping variance. Unsupervised; needs scaling.

---

## 9. Feature engineering & preprocessing
- **Scaling:** standardization (z-score) for distance/gradient models (SVM, kNN, NN, k-means, logistic); trees don't need it.
- **Encoding:** one-hot (low cardinality), target/frequency encoding (high cardinality), embeddings (very high cardinality / NN).
- **Missing values:** drop, mean/median/mode impute, model-based, or "missingness as signal" (XGBoost handles natively).
- **Outliers:** clip/winsorize, log-transform, robust scalers.
- **Feature selection:** filter (correlation, mutual info), wrapper (RFE), embedded (L1, tree importance).

---

## 10. Gradient descent (you'll be asked)
- Minimize loss by stepping opposite the gradient: w ← w − η·∇L.
- **Batch** (all data, stable, slow), **Stochastic/SGD** (1 sample, noisy, fast), **Mini-batch** (best of both, standard).
- **Learning rate η:** too high → diverge; too low → slow. Use schedules / warmup.
- Optimizers: **Adam** (adaptive + momentum, default), RMSprop, SGD+momentum.

---

## 11. Rapid-fire Q&A (memorize)

- *Generative vs discriminative?* Generative models P(x,y) (Naive Bayes, GANs, LLMs); discriminative models P(y|x) (logistic, SVM).
- *Why cross-entropy not MSE for classification?* CE matches the probabilistic objective, gives stronger gradients, MSE+sigmoid → vanishing gradients & non-convex.
- *Curse of dimensionality?* As dims grow, data sparsity explodes, distances lose meaning → need exponentially more data.
- *Parametric vs non-parametric?* Parametric = fixed #params (linear reg); non-parametric grows with data (kNN, trees).
- *How pick k in k-means?* Elbow method (inertia), silhouette score.
- *Ensemble methods?* Bagging (RF), Boosting (XGBoost), Stacking (meta-model over base models).
- *What is the kernel trick?* Compute inner products in high-dim space without explicit mapping → non-linear SVM.
- *Precision-recall tradeoff?* Raising the threshold ↑precision ↓recall and vice versa; pick by business cost.
