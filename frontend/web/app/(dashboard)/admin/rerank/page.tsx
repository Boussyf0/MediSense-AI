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

interface SuiteAggregate {
  mean: number;
  median: number;
  std: number;
  min: number;
  max: number;
}

interface SuiteRow {
  query: string;
  rank_correlation: number;
  top3_overlap: number;
  mrr_rrf: number;
  ce_latency_ms: number;
  num_chunks: number;
}

interface RerankSuiteResponse {
  n_queries: number;
  n_evaluated: number;
  rank_correlation: SuiteAggregate;
  top3_overlap: SuiteAggregate;
  mrr_rrf: SuiteAggregate;
  ce_latency_ms: SuiteAggregate;
  rows: SuiteRow[];
  recommendation: string;
  verdict: 'rrf_ok' | 'ce_active' | 'ce_critical';
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

function SuiteMetricCard({
  label, sub, value, color,
}: { label: string; sub: string; value: string; color: string }) {
  return (
    <div style={{
      flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
    }}>
      <div style={{
        fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
        letterSpacing: '0.14em', textTransform: 'uppercase',
      }}>{label}</div>
      <div style={{
        fontFamily: 'var(--f-display)', fontSize: 26, fontWeight: 600, color,
        marginTop: 4, letterSpacing: '-0.02em',
      }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 2 }}>{sub}</div>
    </div>
  );
}

function SuiteResults({ suite }: { suite: RerankSuiteResponse }) {
  const verdictColor =
    suite.verdict === 'rrf_ok' ? '#22C55E'
    : suite.verdict === 'ce_active' ? '#38BDF8'
    : '#22C55E';
  const verdictLabel =
    suite.verdict === 'rrf_ok' ? 'RRF SUFFISANT'
    : suite.verdict === 'ce_active' ? 'CE ACTIF'
    : 'CE CRITIQUE';

  // Sort rows by rank_correlation ascending so worst queries surface first
  const sortedRows = [...suite.rows].sort((a, b) => a.rank_correlation - b.rank_correlation);

  return (
    <div style={{ marginBottom: 22 }}>
      {/* Header strip */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14,
      }}>
        <div style={{
          padding: '6px 12px', borderRadius: 99,
          background: `${verdictColor}22`, border: `1px solid ${verdictColor}55`,
          color: verdictColor, fontFamily: 'var(--f-mono)', fontSize: 10,
          fontWeight: 700, letterSpacing: '0.12em',
        }}>{verdictLabel}</div>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)',
          letterSpacing: '0.10em', textTransform: 'uppercase',
        }}>
          suite · {suite.n_evaluated}/{suite.n_queries} requêtes évaluées
        </div>
      </div>

      {/* Aggregate metrics */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 14 }}>
        <SuiteMetricCard
          label="Spearman ρ"
          sub={`médiane ${suite.rank_correlation.median.toFixed(2)} · σ ${suite.rank_correlation.std.toFixed(2)}`}
          value={suite.rank_correlation.mean.toFixed(2)}
          color="#22C55E"
        />
        <SuiteMetricCard
          label="Top-3 overlap"
          sub={`min ${(suite.top3_overlap.min * 3).toFixed(0)}/3 · max ${(suite.top3_overlap.max * 3).toFixed(0)}/3`}
          value={`${(suite.top3_overlap.mean * 3).toFixed(1)}/3`}
          color="#A78BFA"
        />
        <SuiteMetricCard
          label="MRR (RRF)"
          sub={`médiane ${suite.mrr_rrf.median.toFixed(2)}`}
          value={suite.mrr_rrf.mean.toFixed(2)}
          color="#38BDF8"
        />
        <SuiteMetricCard
          label="Latence CE"
          sub={`min ${suite.ce_latency_ms.min.toFixed(0)} · max ${suite.ce_latency_ms.max.toFixed(0)} ms`}
          value={`${suite.ce_latency_ms.mean.toFixed(0)}ms`}
          color="#F59E0B"
        />
      </div>

      {/* Per-query table */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
        overflow: 'hidden', marginBottom: 14,
      }}>
        <div style={{
          padding: '10px 16px', borderBottom: '1px solid var(--line)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
        }}>
          Per-query — trié par ρ croissant (pires en haut)
        </div>
        <div style={{ display: 'grid' }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 80px 80px 80px 80px',
            padding: '8px 16px', gap: 12,
            background: 'var(--s2)', borderBottom: '1px solid var(--line)',
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
            letterSpacing: '0.08em', textTransform: 'uppercase',
          }}>
            <div>Query</div>
            <div style={{ textAlign: 'right' }}>ρ</div>
            <div style={{ textAlign: 'right' }}>Top-3</div>
            <div style={{ textAlign: 'right' }}>MRR</div>
            <div style={{ textAlign: 'right' }}>CE ms</div>
          </div>
          {sortedRows.map((row) => {
            const rhoColor = row.rank_correlation >= 0.5 ? '#22C55E'
              : row.rank_correlation >= 0.2 ? '#F59E0B' : '#EF4444';
            return (
              <div key={row.query} style={{
                display: 'grid', gridTemplateColumns: '1fr 80px 80px 80px 80px',
                padding: '8px 16px', gap: 12, borderBottom: '1px solid var(--line)',
                fontSize: 12, color: 'var(--t1)', alignItems: 'center',
              }}>
                <div style={{
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{row.query}</div>
                <div style={{
                  textAlign: 'right', fontFamily: 'var(--f-mono)', fontWeight: 600, color: rhoColor,
                }}>{row.rank_correlation.toFixed(2)}</div>
                <div style={{ textAlign: 'right', fontFamily: 'var(--f-mono)' }}>
                  {Math.round(row.top3_overlap * 3)}/3
                </div>
                <div style={{ textAlign: 'right', fontFamily: 'var(--f-mono)' }}>
                  {row.mrr_rrf.toFixed(2)}
                </div>
                <div style={{ textAlign: 'right', fontFamily: 'var(--f-mono)', color: 'var(--t3)' }}>
                  {row.ce_latency_ms}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Data-driven recommendation */}
      <div style={{
        padding: '14px 16px',
        background: `${verdictColor}11`, border: `1px solid ${verdictColor}55`,
        borderRadius: 10, display: 'flex', alignItems: 'flex-start', gap: 12,
      }}>
        <div style={{ color: verdictColor, flexShrink: 0, marginTop: 2 }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {suite.verdict === 'rrf_ok' || suite.verdict === 'ce_critical'
              ? <><circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/></>
              : <><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></>}
          </svg>
        </div>
        <div style={{ fontSize: 13, color: 'var(--t1)', lineHeight: 1.55 }}>
          <strong style={{ color: 'var(--t0)' }}>Verdict :</strong> {suite.recommendation}
        </div>
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

  const suiteMutation = useMutation<RerankSuiteResponse, Error, void>({
    mutationFn: async () => {
      const { data } = await api.post('/admin/rerank-eval/suite', { top_k: 10 });
      return data as RerankSuiteResponse;
    },
  });

  const result = runMutation.data;
  const suite = suiteMutation.data;
  const errObj = runMutation.error as { response?: { data?: { detail?: string } }; message?: string } | null;
  const suiteErrObj = suiteMutation.error as { response?: { data?: { detail?: string } }; message?: string } | null;
  const errMsg = runMutation.isError
    ? (errObj?.response?.data?.detail || errObj?.message || 'Erreur inconnue')
    : null;
  const suiteErrMsg = suiteMutation.isError
    ? (suiteErrObj?.response?.data?.detail || suiteErrObj?.message || 'Erreur inconnue')
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
            aria-label="Requête médicale de test"
            placeholder="Ex: douleurs thoraciques essoufflement"
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
            aria-label="Nombre de résultats (top-k)"
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
          <DashButton
            kind="ghost"
            loading={suiteMutation.isPending}
            onClick={() => suiteMutation.mutate()}
            icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>}
          >
            Run suite (20)
          </DashButton>
        </div>
        <div style={{
          marginTop: 10, fontSize: 11, color: 'var(--t3)',
          fontFamily: 'var(--f-mono)', letterSpacing: '0.04em',
        }}>
          {suiteMutation.isPending
            ? 'Évaluation en cours sur 20 requêtes médicales — patientez ~10s…'
            : 'Suite = 20 requêtes médicales curées (cardio, triage, médicaments, chroniques) pour un verdict statistique.'}
        </div>
      </div>

      {/* Error */}
      {(errMsg || suiteErrMsg) && (
        <div style={{
          marginBottom: 18, padding: '12px 16px',
          background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.35)',
          color: '#EF4444', borderRadius: 10, fontSize: 13,
        }}>
          Erreur API : {errMsg || suiteErrMsg}
        </div>
      )}

      {/* Suite results — shown above the single-query block when available */}
      {suite && <SuiteResults suite={suite} />}

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
              title="Cross-Encoder · mmarco-mMiniLMv2"
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
              <strong style={{ color: 'var(--t0)' }}>Analyse :</strong> sur cette requête,
              RRF et CE partagent {Math.round(result.top3_overlap * 3)}/3 résultats dans le top-3.
              Le cross-encoder (actif dans le hot path) ajoute {result.ce_latency_ms}ms de latence
              pour corriger l&apos;ordre de classement.
            </div>
          </div>
        </>
      )}
    </DashPage>
  );
}
