# 02 — Deep Learning, LLMs & RAG  ⭐ (your specialty — go deepest here)

> This is the hottest area in hiring right now AND it's your project. Own it completely.

---

## PART A — Deep Learning foundations

### Neural network basics
- Neuron: output = activation(Σ wᵢxᵢ + b). Layers of these = MLP.
- **Activations:** ReLU (default, cheap, avoids vanishing gradient but "dying ReLU"), sigmoid (0–1, output prob, saturates), tanh (−1–1), softmax (multiclass output → probabilities), GELU (transformers).
- **Why non-linearity?** Without it, stacked linear layers collapse into one linear function — can't learn complex patterns.

### Backpropagation (one paragraph)
Forward pass computes predictions & loss. Backward pass applies the **chain rule** to compute the gradient of the loss w.r.t. every weight, propagating from output to input. Optimizer then updates weights via gradient descent. It's just efficient automatic differentiation.

### Vanishing / exploding gradients
- Deep nets: gradients shrink (→0) or blow up (→∞) through many layers.
- **Fixes:** ReLU activations, careful init (He/Xavier), **batch/layer normalization**, residual connections (ResNet), gradient clipping, and gated architectures (LSTM/GRU).

### Key architectures
- **CNN** — convolutional filters exploit spatial locality + weight sharing → images. Concepts: kernels, stride, pooling, feature maps.
- **RNN** — processes sequences with a hidden state; suffers vanishing gradients on long sequences.
- **LSTM** ⭐ (your anomaly model) — RNN with **gates** (forget, input, output) + a cell state that carries long-range info → solves vanishing gradients, learns long dependencies. GRU = simpler 2-gate variant.
- **Transformer** ⭐⭐ — no recurrence; pure **attention** + feed-forward, fully parallelizable → the backbone of all modern LLMs.

> One-liner: "I used an LSTM for biometric anomaly detection because vitals are sequential and gates let it retain long-range temporal patterns without vanishing gradients."

### Training hygiene
- **Batch norm** (stabilize/scale activations), **dropout** (regularize), **early stopping**, **LR scheduling/warmup**, **data augmentation**.
- **Loss:** cross-entropy (classification), MSE (regression), contrastive/triplet (embeddings).

---

## PART B — Transformers & Attention ⭐⭐

### Self-attention (the #1 GenAI question)
Each token is projected into **Query (Q), Key (K), Value (V)** vectors.
- Attention(Q,K,V) = softmax(QKᵀ / √dₖ) · V
- Intuition: each token's Query is compared (dot product) against every token's Key to get **attention weights** (how much to attend to each other token), then takes a weighted sum of Values.
- **√dₖ scaling** keeps dot products from getting huge and saturating softmax.
- **Multi-head attention:** run attention in parallel subspaces → capture different relationship types.
- **Positional encoding:** since there's no recurrence, inject token order (sinusoidal or learned/RoPE).

> Whiteboard this from memory — it's the most common GenAI interview ask.

### Architecture variants
- **Encoder-only** (BERT) — bidirectional, great for embeddings/classification.
- **Decoder-only** (GPT, Llama) — autoregressive next-token prediction → generation.
- **Encoder-decoder** (T5) — seq2seq (translation, summarization).

---

## PART C — LLMs

### Lifecycle
1. **Pretraining** — self-supervised next-token prediction on massive corpora → general knowledge.
2. **Supervised fine-tuning (SFT)** — instruction/response pairs → follows instructions.
3. **RLHF / DPO** — align to human preferences → helpful, harmless.

### Key concepts
- **Tokens:** text is split into subword tokens (BPE). Models bill & limit by tokens. ~4 chars ≈ 1 token (English).
- **Context window:** max tokens the model can attend to at once (prompt + output).
- **Temperature:** randomness of sampling (0 = deterministic/greedy, higher = creative). **top-p / top-k** = nucleus sampling.
- **Hallucination:** confident but false output. Mitigate with RAG (grounding), lower temperature, citations, guardrails, "say I don't know" prompting.
- **Parameters vs context** — params = learned weights (knowledge); context = working memory at inference.

### Adapt an LLM — 3 options (know the decision)
| Approach | What | When |
|---|---|---|
| **Prompt engineering** | Craft instructions / few-shot examples | Fast, cheap, no data; first thing to try |
| **RAG** | Retrieve external docs into the prompt | Need fresh/proprietary/factual grounding; reduce hallucination |
| **Fine-tuning** | Update weights (full or **LoRA/PEFT**) | Need a behavior/style/format the model can't be prompted into, or latency/cost at scale |

> Killer answer: "RAG injects *knowledge*; fine-tuning teaches *behavior*. For MediSense I chose RAG because medical content changes and must be grounded in source docs — I don't want the model inventing dosages."

- **LoRA/PEFT:** freeze base weights, train tiny low-rank adapters → cheap fine-tuning.
- **Quantization:** lower precision (int8/4-bit) → smaller, faster, less memory, slight quality loss.

---

## PART D — RAG end-to-end ⭐⭐ (your system — be the expert)

### Pipeline
```
Documents → Chunking → Embedding model → Vector DB (index)
                                              │
User query → Embed query → Similarity search (top-k) → [Rerank] →
   → Build prompt (query + retrieved context) → LLM → Grounded answer (+ citations)
```

### Each stage + the decisions
1. **Chunking** — split docs (by tokens/semantics, ~200–800 tokens, with overlap). Too big = noisy retrieval; too small = lost context.
2. **Embeddings** — map text to vectors so semantically similar text is close. Similarity via **cosine**.
3. **Vector DB** (Qdrant in your case) — stores vectors + does **ANN** (approximate nearest neighbor, e.g. HNSW) search at scale. Why not brute force? O(N) per query doesn't scale.
4. **Retrieval** — embed query, fetch top-k. **Hybrid search** = dense (semantic) + sparse (BM25 keyword) for best recall.
5. **Reranking** (optional) — a cross-encoder reorders top-k for precision.
6. **Generation** — LLM answers *using only* retrieved context; prompt it to cite and to refuse if context is insufficient.

### RAG failure modes (name them — shows depth)
- **Bad retrieval** (wrong/again missing chunks) → wrong answer. Fix: better chunking, hybrid search, reranking.
- **Lost in the middle** — LLM ignores mid-context info. Fix: rerank, fewer/better chunks.
- **Hallucination despite context** — Fix: instruct to ground + cite + abstain.
- **Stale index** — Fix: re-embed on doc updates.

### RAG evaluation
- **Retrieval:** recall@k, precision@k, MRR, hit rate.
- **Generation:** faithfulness/groundedness, answer relevance, **RAGAS** framework, LLM-as-judge.
- **End-to-end:** human eval, A/B test.

> One-liner: "I evaluate RAG in two halves — retrieval quality (recall@k) separately from generation faithfulness — because a wrong answer is usually a retrieval problem, not a model problem."

### Agents (bonus, increasingly asked)
- **Agent** = LLM + tools + a loop (reason → act → observe). Patterns: ReAct, tool/function calling, multi-agent.
- **MCP** (Model Context Protocol) — standard for connecting tools/data to LLMs.

---

## Rapid-fire GenAI Q&A
- *Embedding vs token?* Token = text unit; embedding = its dense vector representation.
- *Why cosine similarity not Euclidean for embeddings?* Direction (semantic) matters more than magnitude; cosine is scale-invariant.
- *Cut hallucination?* RAG grounding, citations, low temperature, abstention prompting, guardrails, output validation.
- *Context window full — what do you do?* Summarize history, retrieve only relevant chunks, sliding window, bigger-context model.
- *RAG vs fine-tuning in one line?* RAG = knowledge injection at inference; fine-tuning = behavior baked into weights.
- *What's a reranker?* A cross-encoder that scores (query, doc) pairs jointly for higher-precision ordering than embedding similarity.
- *Temperature 0 vs 1?* 0 = deterministic/factual; 1 = diverse/creative.
