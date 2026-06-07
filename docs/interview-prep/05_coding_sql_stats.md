# 05 — Coding, SQL & Statistics

> DS/ML interviews test three practical skills: Python/pandas, SQL, and statistics.
> MLE/big-tech may add DSA. Below: what to know + a focused practice plan.

---

## PART A — Python / pandas / NumPy

### Must be fluent (write without thinking)
```python
import pandas as pd, numpy as np

df = pd.read_csv("data.csv")
df.head(); df.info(); df.describe(); df.isna().sum()

# select / filter
df[df["age"] > 50][["id", "age"]]
df.loc[df["sex"] == "F", "risk"]

# groupby aggregate  (very common in interviews)
df.groupby("city")["no_show"].mean().sort_values(ascending=False)
df.groupby("doctor").agg(n=("id","count"), rate=("no_show","mean"))

# missing values
df["age"].fillna(df["age"].median(), inplace=True)

# new features
df["lead_days"] = (df["appt"] - df["booked"]).dt.days
df["age_band"] = pd.cut(df["age"], [0,30,50,70,120])

# merge / join
pd.merge(appts, patients, on="patient_id", how="left")

# value counts / crosstab
df["status"].value_counts(normalize=True)
pd.crosstab(df["city"], df["no_show"])
```

### sklearn skeleton (know it cold)
```python
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, roc_auc_score
from xgboost import XGBClassifier

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2,
                                          stratify=y, random_state=42)
model = XGBClassifier(scale_pos_weight=ratio, eval_metric="aucpr")
model.fit(X_tr, y_tr)
proba = model.predict_proba(X_te)[:, 1]
print(roc_auc_score(y_te, proba))
print(classification_report(y_te, proba > 0.5))
```

### Common coding-screen tasks (DS flavor)
- Clean a messy dataframe; compute a grouped metric; find top-N per group; pivot; rolling average; dedupe; date diffs.
- Implement a metric from scratch (precision/recall, RMSE) — they check you *understand* it.

```python
def precision_recall(y_true, y_pred):
    tp = sum(t==1 and p==1 for t,p in zip(y_true,y_pred))
    fp = sum(t==0 and p==1 for t,p in zip(y_true,y_pred))
    fn = sum(t==1 and p==0 for t,p in zip(y_true,y_pred))
    prec = tp/(tp+fp) if tp+fp else 0
    rec  = tp/(tp+fn) if tp+fn else 0
    return prec, rec
```

---

## PART B — SQL ⭐ (heavily tested for DS)

### Core you must master
```sql
-- aggregation + filtering groups
SELECT city, COUNT(*) AS n, AVG(no_show::int) AS rate
FROM appointments
GROUP BY city
HAVING COUNT(*) > 100
ORDER BY rate DESC;

-- JOINs
SELECT a.id, p.city
FROM appointments a
LEFT JOIN patients p ON p.id = a.patient_id;

-- WINDOW FUNCTIONS (the #1 SQL interview topic)
SELECT id, doctor_id, scheduled_at,
       ROW_NUMBER() OVER (PARTITION BY doctor_id ORDER BY scheduled_at) AS visit_seq,
       RANK()       OVER (PARTITION BY doctor_id ORDER BY scheduled_at) AS rnk,
       LAG(scheduled_at) OVER (PARTITION BY patient_id ORDER BY scheduled_at) AS prev_visit,
       AVG(no_show::int) OVER (PARTITION BY doctor_id) AS doctor_rate
FROM appointments;

-- top-N per group (classic)
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY doctor_id ORDER BY scheduled_at DESC) rn
  FROM appointments
) t WHERE rn <= 3;

-- CTE + readability
WITH risky AS (
  SELECT patient_id, COUNT(*) c FROM appointments
  WHERE no_show GROUP BY patient_id HAVING COUNT(*) >= 3
)
SELECT p.* FROM patients p JOIN risky r ON r.patient_id = p.id;
```

### SQL topics to drill
- JOIN types (inner/left/right/full, self-join, anti-join via LEFT JOIN … IS NULL)
- GROUP BY + HAVING vs WHERE (WHERE before agg, HAVING after)
- Window functions: ROW_NUMBER / RANK / DENSE_RANK, LAG/LEAD, running totals, moving averages
- CTEs & subqueries, date functions, CASE WHEN, NULL handling
- Practice on **DataLemur** / **StrataScratch** (DS-targeted).

---

## PART C — Statistics & Probability

### Core concepts (be ready to explain + apply)
- **Descriptive:** mean/median/mode, variance/std, skew, percentiles, IQR.
- **Distributions:** Normal, Bernoulli/Binomial, Poisson, Uniform, Exponential. Know shapes & use cases.
- **CLT** — sample means approach Normal as n grows, regardless of population dist → basis of inference.
- **Law of large numbers** — sample mean → true mean as n→∞.
- **Confidence interval** — range that contains the true parameter X% of the time over repeated sampling.
- **Hypothesis testing** — H₀ (null) vs H₁; **p-value** = P(data this extreme | H₀ true). p < α (0.05) → reject H₀. Caveat: p-value is NOT P(H₀ true).
- **Type I error** (false positive, reject true H₀ = α) vs **Type II** (false negative, β); **power** = 1−β.
- **Tests:** t-test (compare means), chi-square (categorical), ANOVA (>2 groups).
- **Bayes' theorem:** P(A|B) = P(B|A)P(A)/P(B). Be ready for the classic disease-test problem (base rates matter!).
- **Correlation ≠ causation**; confounders; Simpson's paradox.

### A/B testing (very common for DS) ⭐
1. Hypothesis + metric (primary + guardrail).
2. **Power analysis** → required sample size (effect size, α=0.05, power=0.8).
3. Randomize; run long enough (avoid peeking / novelty effects).
4. Test significance (t-test / z-test for proportions); report effect size + CI, not just p.
5. Watch: multiple testing, network effects, sample ratio mismatch.

### Bayes worked example (memorize the reasoning)
> Disease prevalence 1%, test 99% sensitive & 99% specific. Positive test → P(disease)?
> P(D|+) = (0.99·0.01) / (0.99·0.01 + 0.01·0.99) = 0.0099/0.0198 = **50%**.
> Lesson: with rare conditions, even a "99% accurate" test gives many false positives. (Directly relevant to medical ML — ties to PR-AUC > accuracy.)

---

## PART D — DSA (only if targeting big-tech / MLE)

Don't grind 500 problems. Learn **patterns** (NeetCode 150):
- Arrays & Hashing, Two Pointers, Sliding Window
- Binary Search, Stack, Linked List
- Trees (BFS/DFS), Heaps, Graphs (basic)
- Dynamic Programming (basics)

Plan: 2–3 problems/day, easy→medium, **understand the pattern** > memorize solutions. Talk through brute-force → optimize → complexity (Big-O).

For DS-leaning roles, prioritize **pandas + SQL + stats** over LeetCode.

---

## Big-O quick reference
| Structure/op | Time |
|---|---|
| Hash lookup | O(1) |
| Binary search | O(log n) |
| Sort | O(n log n) |
| Nested loop | O(n²) |
| kNN predict | O(n·d) per query |
| Brute-force vector search | O(n·d) → why ANN/HNSW exists |

---

## Practice sources
- **SQL:** DataLemur, StrataScratch
- **Coding:** NeetCode 150, LeetCode
- **Stats/ML Qs:** Chip Huyen "Introduction to ML Interviews" (free), Glassdoor company questions
- **End-to-end:** keep extending MediSense (add the RAG eval harness, model metrics) — building beats grinding.
