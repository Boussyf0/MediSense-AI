'use client';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashButton } from '@/components/dash-button';
import { ConfidenceBar } from '@/components/confidence-bar';
import { Play, Zap } from 'lucide-react';

interface RerankResult {
  query: string;
  rank_correlation: number;
  top3_overlap: number;
  mrr_rrf: number;
  rrf_items: Array<{ rank: number; doc: string; score: number }>;
  ce_items: Array<{ rank: number; doc: string; score: number }>;
  ce_latency_ms: number;
  num_chunks: number;
}

export default function SystemPage() {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);

  const evalMutation = useMutation<RerankResult, Error, void>({
    mutationFn: async () => {
      const { data } = await api.post('/admin/rerank-eval', { query, top_k: topK });
      return data;
    },
  });

  const result = evalMutation.data;

  const metricColor = (v: number) =>
    v >= 0.8 ? '#22C55E' : v >= 0.6 ? '#6366F1' : v >= 0.4 ? '#F97316' : '#EF4444';

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1000 }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <Zap size={18} style={{ color: '#6366F1' }} />
          <h1 style={{ fontFamily: 'var(--f-display)', fontSize: 24, fontWeight: 700, color: 'var(--t0)', margin: 0 }}>
            Évaluation RAG
          </h1>
        </div>
        <p style={{ color: 'var(--t2)', fontSize: 13, margin: 0 }}>
          Comparaison RRF vs Cross-Encoder · métriques de reranking
        </p>
      </div>

      {/* Query input */}
      <div style={{ background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, padding: 20, marginBottom: 20 }}>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
          Requête clinique
        </div>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ex: patient avec douleur thoracique et dyspnée à l'effort…"
          style={{
            width: '100%', minHeight: 80,
            background: 'var(--s2)', border: '1px solid var(--line-strong)',
            borderRadius: 8, padding: '10px 12px', color: 'var(--t0)',
            fontFamily: 'var(--f-body)', fontSize: 13, resize: 'vertical', outline: 'none',
            boxSizing: 'border-box', marginBottom: 12,
          }}
        />

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div>
            <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginRight: 8 }}>Top-K :</span>
            {[5, 10, 20].map(k => (
              <button
                key={k}
                onClick={() => setTopK(k)}
                style={{
                  padding: '5px 12px', borderRadius: 6, marginRight: 5,
                  background: topK === k ? 'rgba(99,102,241,0.20)' : 'var(--s2)',
                  border: topK === k ? '1px solid rgba(99,102,241,0.45)' : '1px solid var(--line-strong)',
                  color: topK === k ? '#6366F1' : 'var(--t2)',
                  fontFamily: 'var(--f-mono)', fontSize: 12, fontWeight: topK === k ? 700 : 400,
                  cursor: 'pointer', transition: 'all 0.12s',
                }}
              >
                {k}
              </button>
            ))}
          </div>

          <div style={{ flex: 1 }} />

          <DashButton
            kind="gradient"
            icon={<Play size={13} />}
            onClick={() => evalMutation.mutate()}
            loading={evalMutation.isPending}
            disabled={!query.trim()}
          >
            Lancer l&apos;évaluation
          </DashButton>
        </div>
      </div>

      {/* Error */}
      {evalMutation.isError && (
        <div style={{
          padding: '12px 16px', borderRadius: 10, marginBottom: 20,
          background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.35)',
          color: '#EF4444', fontSize: 13,
        }}>
          Erreur lors de l&apos;évaluation : {evalMutation.error.message}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ animation: 'slide-down 0.2s ease' }}>
          {/* Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
            {[
              { label: 'Rang Corrélation (Spearman ρ)', value: result.rank_correlation, desc: 'Corrélation entre ordres RRF et Cross-Encoder' },
              { label: 'Overlap Top-3', value: result.top3_overlap, desc: 'Documents en commun dans les 3 premiers' },
              { label: 'MRR (Mean Reciprocal Rank)', value: result.mrr_rrf, desc: 'Rang moyen du premier résultat pertinent' },
            ].map(m => (
              <div key={m.label} style={{
                background: 'var(--s1)', border: '1px solid var(--line)',
                borderRadius: 12, padding: 16,
              }}>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 8 }}>
                  {m.label}
                </div>
                <div style={{ fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 700, color: metricColor(m.value), marginBottom: 8 }}>
                  {m.value.toFixed(3)}
                </div>
                <ConfidenceBar value={m.value} />
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t4)', marginTop: 8 }}>
                  {m.desc}
                </div>
              </div>
            ))}
          </div>

          {/* Latency */}
          <div style={{ marginBottom: 20, fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)' }}>
            ⏱ Latence : <span style={{ color: result.ce_latency_ms < 200 ? '#22C55E' : result.ce_latency_ms < 500 ? '#F97316' : '#EF4444', fontWeight: 700 }}>
              {result.ce_latency_ms} ms
            </span>
            {' '}· Top-{topK} · requête : &ldquo;{result.query.slice(0, 60)}{result.query.length > 60 ? '…' : ''}&rdquo;
          </div>

          {/* Side-by-side results */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            {[
              { title: 'RRF (Reciprocal Rank Fusion)', results: result.rrf_items, color: '#6366F1' },
              { title: 'Cross-Encoder', results: result.ce_items, color: '#A78BFA' },
            ].map(col => (
              <div key={col.title} style={{ background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12, overflow: 'hidden' }}>
                <div style={{
                  padding: '12px 16px', borderBottom: '1px solid var(--line)',
                  fontFamily: 'var(--f-mono)', fontSize: 10, color: col.color,
                  letterSpacing: '0.10em', textTransform: 'uppercase', fontWeight: 600,
                  background: `${col.color}08`,
                }}>
                  {col.title}
                </div>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--line)' }}>
                      {['#', 'Document', 'Score'].map(h => (
                        <th key={h} style={{
                          padding: '8px 12px', textAlign: 'left',
                          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t4)',
                          letterSpacing: '0.10em', textTransform: 'uppercase', fontWeight: 500,
                        }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {col.results.slice(0, 3).map((r) => (
                      <tr key={r.rank} style={{ borderBottom: '1px solid var(--line)' }}>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{
                            fontFamily: 'var(--f-mono)', fontSize: 11, fontWeight: 700,
                            color: r.rank === 1 ? col.color : 'var(--t3)',
                          }}>
                            {r.rank}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px', fontSize: 12.5, color: 'var(--t1)', maxWidth: 200 }}>
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {r.doc}
                          </div>
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: metricColor(r.score) }}>
                            {r.score.toFixed(4)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Idle state */}
      {!result && !evalMutation.isPending && (
        <div style={{
          textAlign: 'center', padding: '60px 20px',
          color: 'var(--t4)', fontSize: 13,
        }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>🔬</div>
          Saisissez une requête et lancez l&apos;évaluation pour comparer RRF et Cross-Encoder
        </div>
      )}

      {evalMutation.isPending && (
        <div style={{ textAlign: 'center', padding: '60px 20px' }}>
          <div style={{ display: 'flex', gap: 5, justifyContent: 'center', marginBottom: 12 }}>
            {[0, 1, 2].map(i => (
              <span key={i} style={{
                width: 8, height: 8, borderRadius: '50%', background: '#6366F1', display: 'inline-block',
                animation: `typing-dot 1.2s ease ${i * 0.15}s infinite`,
              }} />
            ))}
          </div>
          <div style={{ color: 'var(--t3)', fontSize: 12 }}>Évaluation en cours…</div>
        </div>
      )}
    </div>
  );
}
