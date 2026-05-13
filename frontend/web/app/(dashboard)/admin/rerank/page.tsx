'use client';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashButton } from '@/components/dash-button';
import { DashPage } from '@/components/dashboard-shell';

interface RankItem {
  rank: number;
  doc: string;
  score: number;
}

interface RerankEvalResponse {
  query: string;
  rrf_items: RankItem[];
  ce_items: RankItem[];
  rank_correlation: number;
  top3_overlap: number;
  mrr_rrf: number;
  ce_latency_ms: number;
  num_chunks: number;
}

const DEFAULT_QUERY = 'douleurs thoraciques essoufflement insuffisance cardiaque';

function RankColumn({
  title, sub, items, color,
}: { title: string; sub: string; items: RankItem[]; color: string }) {
  return (
    <div style={{
      flex: 1, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
      padding: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{
          width: 8, height: 8, borderRadius: 99,
          background: color, boxShadow: `0 0 6px ${color}`,
        }} />
        <div>
          <div style={{
            fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 600, color: 'var(--t0)',
          }}>
            {title}
          </div>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
            letterSpacing: '0.10em', textTransform: 'uppercase',
          }}>
            {sub}
          </div>
        </div>
      </div>
      <div style={{ display: 'grid', gap: 8 }}>
        {items.map((it) => (
          <div key={it.rank} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
            background: 'var(--s2)', borderRadius: 8, border: '1px solid var(--line)',
          }}>
            <div style={{
              width: 22, height: 22, borderRadius: 99,
              background: 'var(--s3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600, color: 'var(--t1)',
            }}>
              {it.rank}
            </div>
            <div style={{ flex: 1, fontSize: 12, color: 'var(--t1)' }}>{it.doc}</div>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 11, color, fontWeight: 600,
            }}>
              {it.score.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AdminRerankPage() {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [topK, setTopK] = useState('5');

  const runMutation = useMutation<RerankEvalResponse, Error, void>({
    mutationFn: async () => {
      const { data } = await api.post('/admin/rerank-eval', { query, top_k: Number(topK) });
      return data as RerankEvalResponse;
    },
  });

  const result = runMutation.data;
  const errObj = runMutation.error as { response?: { data?: { detail?: string } }; message?: string } | null;
  const errMsg = runMutation.isError
    ? (errObj?.response?.data?.detail || errObj?.message || 'Erreur inconnue')
    : null;

  return (
    <DashPage
      breadcrumb="système · diagnostic rag"
      title="Évaluation Rerank — RRF vs Cross-Encoder"
      subtitle="Diagnostic qualité retrieval · sprint 3 · admin only"
    >
      {/* Query input */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
        padding: 18, marginBottom: 18,
      }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8,
        }}>
          Requête de test
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              flex: 1, padding: '11px 14px',
              background: 'var(--s2)', border: '1px solid var(--line-strong)', borderRadius: 10,
              color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12, outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          <select
            value={topK}
            onChange={(e) => setTopK(e.target.value)}
            style={{
              padding: '0 14px', background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 10,
              color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12,
            }}
          >
            <option value="5">Top-5</option>
            <option value="10">Top-10</option>
            <option value="20">Top-20</option>
          </select>
          <DashButton
            kind="gradient"
            loading={runMutation.isPending}
            onClick={() => runMutation.mutate()}
            icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M5 3l14 9-14 9z"/></svg>}
          >
            Lancer
          </DashButton>
        </div>
      </div>

      {/* Error */}
      {errMsg && (
        <div style={{
          marginBottom: 18, padding: '12px 16px',
          background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.35)',
          color: '#EF4444', borderRadius: 10, fontSize: 13,
        }}>
          Erreur API : {errMsg}
        </div>
      )}

      {/* Idle */}
      {!result && !runMutation.isPending && !errMsg && (
        <div style={{
          textAlign: 'center', padding: '60px 20px',
          color: 'var(--t4)', fontSize: 13,
        }}>
          Saisissez une requête et lancez l&apos;évaluation pour comparer RRF et Cross-Encoder.
        </div>
      )}

      {result && (
        <>
          {/* Metrics */}
          <div style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
            {[
              { label: 'Spearman ρ',     value: result.rank_correlation.toFixed(2),                       sub: 'corrélation des rangs', c: '#22C55E' },
              { label: 'Top-3 overlap',  value: `${Math.round(result.top3_overlap * 3)}/3`,               sub: 'documents communs',    c: '#A78BFA' },
              { label: 'MRR (RRF)',      value: result.mrr_rrf.toFixed(2),                                sub: 'mean reciprocal rank', c: '#38BDF8' },
              { label: 'Latence CE',     value: `${result.ce_latency_ms}ms`,                              sub: 'ms par requête',       c: '#F59E0B' },
            ].map((mc) => (
              <div key={mc.label} style={{
                flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
              }}>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
                  letterSpacing: '0.14em', textTransform: 'uppercase',
                }}>
                  {mc.label}
                </div>
                <div style={{
                  fontFamily: 'var(--f-display)', fontSize: 28, fontWeight: 600, color: mc.c,
                  marginTop: 4, letterSpacing: '-0.02em',
                }}>
                  {mc.value}
                </div>
                <div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 2 }}>{mc.sub}</div>
              </div>
            ))}
          </div>

          {/* Rank columns */}
          <div style={{ display: 'flex', gap: 14 }}>
            <RankColumn
              title="RRF · Reciprocal Rank Fusion"
              sub="rapide · pas de modèle"
              items={result.rrf_items}
              color="#A78BFA"
            />
            <RankColumn
              title="Cross-Encoder · BAAI/bge-reranker"
              sub={`précis · ${result.ce_latency_ms}ms/req`}
              items={result.ce_items}
              color="#38BDF8"
            />
          </div>

          {/* Recommendation */}
          <div style={{
            marginTop: 18, padding: '12px 16px',
            background: 'rgba(56,189,248,0.06)', border: '1px solid rgba(56,189,248,0.30)',
            borderRadius: 10, display: 'flex', alignItems: 'flex-start', gap: 12,
          }}>
            <div style={{ color: '#38BDF8', flexShrink: 0, marginTop: 2 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/>
              </svg>
            </div>
            <div style={{ fontSize: 12, color: 'var(--t1)', lineHeight: 1.55 }}>
              <strong style={{ color: 'var(--t0)' }}>Recommandation :</strong> sur cette requête,
              RRF maintient {Math.round(result.top3_overlap * 3)}/3 des résultats du cross-encoder dans le top-3 pour une latence
              {' '}{Math.max(1, Math.round(result.ce_latency_ms / 10))}× inférieure. Garder RRF en production ·
              CE uniquement pour l&apos;admin tooling.
            </div>
          </div>
        </>
      )}
    </DashPage>
  );
}
