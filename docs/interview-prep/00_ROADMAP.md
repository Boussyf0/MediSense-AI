# AI/ML Engineer & Data Scientist — Interview Mastery Roadmap

> Honest framing: you can't master 100% of this field — it's too broad and changes monthly.
> The realistic goal is **interview-strong**: solid fundamentals + deep expertise on GenAI/RAG +
> a project you can defend from any angle. This kit gets you there.

Your unfair advantage: **MediSense AI** — a real, deployed, end-to-end system (RAG + LSTM + XGBoost +
FastAPI + cloud). Most candidates only have notebooks. Lead with this.

---

## The recruitment funnel (what each stage tests)

| Stage | What they test | Your prep file |
|---|---|---|
| 1. Resume / CV screen | Relevant projects, keywords, impact | Case study + CV bullets (already done) |
| 2. Recruiter call | Communication, motivation, basic fit | `04` (pitch) |
| 3. Technical screen (ML concepts) | Fundamentals, can you reason | `01`, `02` |
| 4. Coding screen | Python / SQL / sometimes DSA | `05` |
| 5. ML/DL deep dive | Algorithms, DL, GenAI in depth | `01`, `02` |
| 6. ML system design | Design a real ML system | `03` |
| 7. Project deep dive | Defend YOUR work technically | `04` |
| 8. Behavioral | STAR stories, collaboration, ownership | `04` |

Not every company runs all 8. Startups → heavy project + practical. Big tech → heavy DSA + system design.

---

## 8-week study plan (adjust to your timeline)

**Weeks 1–2 — Fundamentals (file 01)**
- ML basics, bias-variance, metrics, classical algorithms.
- Daily: 1 concept written from memory + 5 flashcard Q&A.
- Output: you can derive logistic regression loss and explain ROC-AUC cold.

**Weeks 3–4 — Deep Learning + GenAI/RAG (file 02)** ← your strength, go deepest here
- NN/backprop, CNN/RNN/LSTM, Transformers/attention, embeddings.
- RAG end-to-end, fine-tuning vs RAG vs prompting, LLM evaluation.
- Output: whiteboard the RAG pipeline and self-attention from memory.

**Week 5 — MLOps + ML System Design (file 03)**
- Lifecycle, drift, monitoring, serving; practice 3 design prompts out loud.

**Week 6 — Coding / SQL / Stats (file 05)**
- 2–3 LeetCode-easy/medium daily (arrays, hashmaps, two pointers), SQL window functions, stats refresh.

**Week 7 — Project mastery (file 04)**
- Rehearse the MediSense pitch + 20 anticipated deep questions + 5 STAR stories.

**Week 8 — Mock interviews + gaps**
- Record yourself answering. Re-do weak topics. Do 2 full mock loops.

> Consistency > intensity. 2 focused hours/day beats 10 hours on Sunday.

---

## How to study (so it sticks)

1. **Active recall**: close the doc, write the answer, then check. Reading ≠ knowing.
2. **Feynman**: explain each concept out loud as if to a non-expert. If you stumble, you don't know it.
3. **Spaced repetition**: make Anki cards from the Q&A in these files.
4. **Practice out loud**: interviews are spoken. Rehearse talking, not just reading.
5. **Tie everything back to MediSense**: "We used XGBoost for no-show because…" — concrete beats abstract.

---

## Self-assessment checklist (tick when you can explain *out loud, from memory*)

**Fundamentals**
- [ ] Bias-variance tradeoff + how to fix high bias / high variance
- [ ] Precision vs recall vs F1 vs ROC-AUC vs PR-AUC — and when to optimize each
- [ ] Overfitting: 5 ways to prevent it
- [ ] How a decision tree splits; how random forest & gradient boosting differ
- [ ] L1 vs L2 regularization (and why L1 → sparsity)
- [ ] Handling class imbalance (your no-show problem)

**Deep learning / GenAI**
- [ ] Backpropagation in one paragraph
- [ ] Why LSTMs beat vanilla RNNs (vanishing gradients, gates)
- [ ] Self-attention: Q, K, V — what they do
- [ ] What an embedding is and why cosine similarity
- [ ] RAG pipeline end to end + 3 failure modes
- [ ] Fine-tuning vs RAG vs prompting — when each

**Production / design**
- [ ] Data drift vs concept drift + how you'd monitor
- [ ] How you'd serve a model at low latency
- [ ] Walk an ML system design from requirements → monitoring

**Project**
- [ ] 2-minute MediSense pitch
- [ ] Defend every architecture choice
- [ ] 5 STAR stories ready

---

## Resources (high-signal, don't drown)

- **Books:** *Hands-On ML* (Géron) · *Designing ML Systems* (Huyen) · *Deep Learning* (Goodfellow, reference)
- **GenAI:** Karpathy "Zero to Hero" (YouTube) · "RAG from scratch" (LangChain) · Hugging Face NLP course
- **Stats/ML Q&A:** *Cracking the ML Interview*, Chip Huyen's ML interview book (free online)
- **Coding:** NeetCode 150 (don't grind 500 — patterns matter more)
- **SQL:** StrataScratch / DataLemur (DS-focused SQL)
- **System design:** *Machine Learning System Design Interview* (Aminian & Xu)

---

## Files in this kit
- `01_ML_DS_fundamentals.md` — classical ML + DS concepts, metrics, algorithms (Q&A)
- `02_deep_learning_LLMs_RAG.md` — DL, Transformers, LLMs, RAG (your specialty)
- `03_mlops_ml_system_design.md` — production ML + design frameworks + worked examples
- `04_project_deep_dive_MediSense.md` — pitch, anticipated questions, STAR stories
- `05_coding_sql_stats.md` — Python/SQL/stats + DSA plan
