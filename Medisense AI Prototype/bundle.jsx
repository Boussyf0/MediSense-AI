
// ─── design-canvas.jsx ───
{

// DesignCanvas.jsx — Figma-ish design canvas wrapper
// Warm gray grid bg + Sections + Artboards + PostIt notes.
// Artboards are reorderable (grip-drag), deletable, labels/titles are
// inline-editable, and any artboard can be opened in a fullscreen focus
// overlay (←/→/Esc). State persists to a .design-canvas.state.json sidecar
// via the host bridge. No assets, no deps.
//
// Usage:
//   <DesignCanvas>
//     <DCSection id="onboarding" title="Onboarding" subtitle="First-run variants">
//       <DCArtboard id="a" label="A · Dusk" width={260} height={480}>…</DCArtboard>
//       <DCArtboard id="b" label="B · Minimal" width={260} height={480}>…</DCArtboard>
//     </DCSection>
//   </DesignCanvas>

const DC = {
  bg: '#f0eee9',
  grid: 'rgba(0,0,0,0.06)',
  label: 'rgba(60,50,40,0.7)',
  title: 'rgba(40,30,20,0.85)',
  subtitle: 'rgba(60,50,40,0.6)',
  postitBg: '#fef4a8',
  postitText: '#5a4a2a',
  font: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
};

// One-time CSS injection (classes are dc-prefixed so they don't collide with
// the hosted design's own styles).
if (typeof document !== 'undefined' && !document.getElementById('dc-styles')) {
  const s = document.createElement('style');
  s.id = 'dc-styles';
  s.textContent = [
    '.dc-editable{cursor:text;outline:none;white-space:nowrap;border-radius:3px;padding:0 2px;margin:0 -2px}',
    '.dc-editable:focus{background:#fff;box-shadow:0 0 0 1.5px #c96442}',
    '[data-dc-slot]{transition:transform .18s cubic-bezier(.2,.7,.3,1)}',
    '[data-dc-slot].dc-dragging{transition:none;z-index:10;pointer-events:none}',
    '[data-dc-slot].dc-dragging .dc-card{box-shadow:0 12px 40px rgba(0,0,0,.25),0 0 0 2px #c96442;transform:scale(1.02)}',
    // isolation:isolate contains artboard content's z-indexes so a
    // z-indexed child (sticky navbar etc.) can't paint over .dc-header or
    // the .dc-menu popover that drops into the top of the card.
    '.dc-card{isolation:isolate;transition:box-shadow .15s,transform .15s}',
    '.dc-card *{scrollbar-width:none}',
    '.dc-card *::-webkit-scrollbar{display:none}',
    // Per-artboard header: grip + label on the left, delete/expand on the
    // right. Single flex row; when the artboard's on-screen width is too
    // narrow for both the label yields (ellipsis, then hidden entirely below
    // ~4ch via the container query) and the buttons stay on the row.
    '.dc-header{position:absolute;bottom:100%;left:-4px;margin-bottom:calc(4px * var(--dc-inv-zoom,1));z-index:2;',
    '  display:flex;align-items:center;container-type:inline-size}',
    '.dc-labelrow{display:flex;align-items:center;gap:4px;height:24px;flex:1 1 auto;min-width:0}',
    '.dc-grip{flex:0 0 auto;cursor:grab;display:flex;align-items:center;padding:5px 4px;border-radius:4px;transition:background .12s,opacity .12s}',
    '.dc-grip:hover{background:rgba(0,0,0,.08)}',
    '.dc-grip:active{cursor:grabbing}',
    '.dc-labeltext{flex:1 1 auto;min-width:0;cursor:pointer;border-radius:4px;padding:3px 6px;',
    '  display:flex;align-items:center;transition:background .12s;overflow:hidden}',
    // Below ~4ch of label room: hide the label entirely, and drop the grip to
    // hover-only (same reveal rule as .dc-btns) so a narrow header is clean
    // until the card is moused.
    '@container (max-width: 110px){',
    '  .dc-labeltext{display:none}',
    '  .dc-grip{opacity:0}',
    '  [data-dc-slot]:hover .dc-grip{opacity:1}',
    '}',
    '.dc-labeltext:hover{background:rgba(0,0,0,.05)}',
    '.dc-labeltext .dc-editable{overflow:hidden;text-overflow:ellipsis;max-width:100%}',
    '.dc-labeltext .dc-editable:focus{overflow:visible;text-overflow:clip}',
    '.dc-btns{flex:0 0 auto;margin-left:auto;display:flex;gap:2px;opacity:0;transition:opacity .12s}',
    '[data-dc-slot]:hover .dc-btns,.dc-btns:has(.dc-menu){opacity:1}',
    '.dc-expand,.dc-kebab{width:22px;height:22px;border-radius:5px;border:none;cursor:pointer;padding:0;',
    '  background:transparent;color:rgba(60,50,40,.7);display:flex;align-items:center;justify-content:center;',
    '  font:inherit;transition:background .12s,color .12s}',
    '.dc-expand:hover,.dc-kebab:hover{background:rgba(0,0,0,.06);color:#2a251f}',
    // Slot hosting an open menu floats above later siblings (which otherwise
    // paint on top — same z-index:auto, later DOM order) so the popup isn't
    // clipped by the next card.
    '[data-dc-slot]:has(.dc-menu){z-index:10}',
    '.dc-menu{position:absolute;top:100%;right:0;margin-top:4px;background:#fff;border-radius:8px;',
    '  box-shadow:0 8px 28px rgba(0,0,0,.18),0 0 0 1px rgba(0,0,0,.05);padding:4px;min-width:160px;z-index:10}',
    '.dc-menu button{display:block;width:100%;padding:7px 10px;border:0;background:transparent;',
    '  border-radius:5px;font-family:inherit;font-size:13px;font-weight:500;line-height:1.2;',
    '  color:#29261b;cursor:pointer;text-align:left;transition:background .12s;white-space:nowrap}',
    '.dc-menu button:hover{background:rgba(0,0,0,.05)}',
    '.dc-menu hr{border:0;border-top:1px solid rgba(0,0,0,.08);margin:4px 2px}',
    '.dc-menu .dc-danger{color:#c96442}',
    '.dc-menu .dc-danger:hover{background:rgba(201,100,66,.1)}',
    // Chrome (titles / labels / buttons) counter-scales against the viewport
    // zoom so it stays a constant on-screen size. --dc-inv-zoom is set by
    // DCViewport on every transform update and inherits to all descendants —
    // any overlay inside the world (e.g. a TweaksPanel on an artboard) can use
    // it the same way.
    //
    // The header uses transform:scale (out-of-flow, so layout impact doesn't
    // matter) with its world-space width set to card-width / inv-zoom so that
    // after counter-scaling its on-screen width exactly matches the card's —
    // that's what lets the container query + text-overflow behave against the
    // card's visible edge at every zoom level.
    //
    // The section head uses CSS zoom instead of transform so its layout box
    // grows with the counter-scale, pushing the card row down — otherwise the
    // constant-screen-size title would overflow into the (shrinking) world-
    // space gap and overlap the artboard headers at low zoom.
    '.dc-header{width:calc((100% + 4px) / var(--dc-inv-zoom,1));',
    '  transform:scale(var(--dc-inv-zoom,1));transform-origin:bottom left}',
    '.dc-sectionhead{zoom:var(--dc-inv-zoom,1)}',
  ].join('\n');
  document.head.appendChild(s);
}

const DCCtx = React.createContext(null);

// ─────────────────────────────────────────────────────────────
// DesignCanvas — stateful wrapper around the pan/zoom viewport.
// Owns runtime state (per-section order, renamed titles/labels, hidden
// artboards, focused artboard). Order/titles/labels/hidden persist to a
// .design-canvas.state.json
// sidecar next to the HTML. Reads go via plain fetch() so the saved
// arrangement is visible anywhere the HTML + sidecar are served together
// (omelette preview, direct link, downloaded zip). Writes go through the
// host's window.omelette bridge — editing requires the omelette runtime.
// Focus is ephemeral.
// ─────────────────────────────────────────────────────────────
const DC_STATE_FILE = '.design-canvas.state.json';

function DesignCanvas({ children, minScale, maxScale, style }) {
  const [state, setState] = React.useState({ sections: {}, focus: null });
  // Hold rendering until the sidecar read settles so the saved order/titles
  // appear on first paint (no source-order flash). didRead gates writes until
  // the read settles so the empty initial state can't clobber a slow read;
  // skipNextWrite suppresses the one echo-write that would otherwise follow
  // hydration.
  const [ready, setReady] = React.useState(false);
  const didRead = React.useRef(false);
  const skipNextWrite = React.useRef(false);

  React.useEffect(() => {
    let off = false;
    fetch('./' + DC_STATE_FILE)
      .then((r) => (r.ok ? r.json() : null))
      .then((saved) => {
        if (off || !saved || !saved.sections) return;
        skipNextWrite.current = true;
        setState((s) => ({ ...s, sections: saved.sections }));
      })
      .catch(() => {})
      .finally(() => { didRead.current = true; if (!off) setReady(true); });
    const t = setTimeout(() => { if (!off) setReady(true); }, 150);
    return () => { off = true; clearTimeout(t); };
  }, []);

  React.useEffect(() => {
    if (!didRead.current) return;
    if (skipNextWrite.current) { skipNextWrite.current = false; return; }
    const t = setTimeout(() => {
      window.omelette?.writeFile(DC_STATE_FILE, JSON.stringify({ sections: state.sections })).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [state.sections]);

  // Build registries synchronously from children so FocusOverlay can read
  // them in the same render. Only direct DCSection > DCArtboard children are
  // walked — wrapping them in other elements opts out of focus/reorder.
  const registry = {};     // slotId -> { sectionId, artboard }
  const sectionMeta = {};  // sectionId -> { title, subtitle, slotIds[] }
  const sectionOrder = [];
  React.Children.forEach(children, (sec) => {
    if (!sec || sec.type !== DCSection) return;
    const sid = sec.props.id ?? sec.props.title;
    if (!sid) return;
    sectionOrder.push(sid);
    const persisted = state.sections[sid] || {};
    const abs = [];
    React.Children.forEach(sec.props.children, (ab) => {
      if (!ab || ab.type !== DCArtboard) return;
      const aid = ab.props.id ?? ab.props.label;
      if (aid) abs.push([aid, ab]);
    });
    // hidden is scoped to one source revision — when the agent regenerates
    // (artboard-ID set changes), prior deletes don't apply to new content.
    const srcKey = abs.map(([k]) => k).join('\x1f');
    const hidden = persisted.srcKey === srcKey ? (persisted.hidden || []) : [];
    const srcIds = [];
    abs.forEach(([aid, ab]) => {
      if (hidden.includes(aid)) return;
      registry[`${sid}/${aid}`] = { sectionId: sid, artboard: ab };
      srcIds.push(aid);
    });
    const kept = (persisted.order || []).filter((k) => srcIds.includes(k));
    sectionMeta[sid] = {
      title: persisted.title ?? sec.props.title,
      subtitle: sec.props.subtitle,
      slotIds: [...kept, ...srcIds.filter((k) => !kept.includes(k))],
    };
  });

  const api = React.useMemo(() => ({
    state,
    section: (id) => state.sections[id] || {},
    patchSection: (id, p) => setState((s) => ({
      ...s,
      sections: { ...s.sections, [id]: { ...s.sections[id], ...(typeof p === 'function' ? p(s.sections[id] || {}) : p) } },
    })),
    setFocus: (slotId) => setState((s) => ({ ...s, focus: slotId })),
  }), [state]);

  // Esc exits focus; any outside pointerdown commits an in-progress rename.
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') api.setFocus(null); };
    const onPd = (e) => {
      const ae = document.activeElement;
      if (ae && ae.isContentEditable && !ae.contains(e.target)) ae.blur();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPd, true);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPd, true);
    };
  }, [api]);

  return (
    <DCCtx.Provider value={api}>
      <DCViewport minScale={minScale} maxScale={maxScale} style={style}>{ready && children}</DCViewport>
      {state.focus && registry[state.focus] && (
        <DCFocusOverlay entry={registry[state.focus]} sectionMeta={sectionMeta} sectionOrder={sectionOrder} />
      )}
    </DCCtx.Provider>
  );
}

// ─────────────────────────────────────────────────────────────
// DCViewport — transform-based pan/zoom (internal)
//
// Input mapping (Figma-style):
//   • trackpad pinch  → zoom   (ctrlKey wheel; Safari gesture* events)
//   • trackpad scroll → pan    (two-finger)
//   • mouse wheel     → zoom   (notched; distinguished from trackpad scroll)
//   • middle-drag / primary-drag-on-bg → pan
//
// Transform state lives in a ref and is written straight to the DOM
// (translate3d + will-change) so wheel ticks don't go through React —
// keeps pans at 60fps on dense canvases.
// ─────────────────────────────────────────────────────────────
function DCViewport({ children, minScale = 0.1, maxScale = 8, style = {} }) {
  const vpRef = React.useRef(null);
  const worldRef = React.useRef(null);
  const tf = React.useRef({ x: 0, y: 0, scale: 1 });
  // Persist viewport across reloads so the user lands back where they were
  // after an agent edit or browser refresh. The sandbox origin is already
  // per-project; pathname keeps multiple canvas files in one project apart.
  const tfKey = 'dc-viewport:' + location.pathname;
  const saveT = React.useRef(0);

  const lastPostedScale = React.useRef();
  const apply = React.useCallback(() => {
    const { x, y, scale } = tf.current;
    const el = worldRef.current;
    if (!el) return;
    el.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${scale})`;
    // Exposed for zoom-invariant chrome (labels, buttons, TweaksPanel).
    el.style.setProperty('--dc-inv-zoom', String(1 / scale));
    // Keep the host toolbar's % readout in sync with the canvas scale. Pan
    // ticks leave scale unchanged — skip the cross-frame post for those.
    if (lastPostedScale.current !== scale) {
      lastPostedScale.current = scale;
      window.parent.postMessage({ type: '__dc_zoom', scale }, '*');
    }
    clearTimeout(saveT.current);
    saveT.current = setTimeout(() => {
      try { localStorage.setItem(tfKey, JSON.stringify(tf.current)); } catch {}
    }, 200);
  }, [tfKey]);

  React.useLayoutEffect(() => {
    const flush = () => {
      clearTimeout(saveT.current);
      try { localStorage.setItem(tfKey, JSON.stringify(tf.current)); } catch {}
    };
    try {
      const s = JSON.parse(localStorage.getItem(tfKey) || 'null');
      if (s && Number.isFinite(s.x) && Number.isFinite(s.y) && Number.isFinite(s.scale)) {
        tf.current = { x: s.x, y: s.y, scale: Math.min(maxScale, Math.max(minScale, s.scale)) };
        apply();
      }
    } catch {}
    // Flush on pagehide and unmount so a reload within the 200ms debounce
    // window doesn't drop the last pan/zoom.
    window.addEventListener('pagehide', flush);
    return () => { window.removeEventListener('pagehide', flush); flush(); };
  }, []);

  React.useEffect(() => {
    const vp = vpRef.current;
    if (!vp) return;

    const zoomAt = (cx, cy, factor) => {
      const r = vp.getBoundingClientRect();
      const px = cx - r.left, py = cy - r.top;
      const t = tf.current;
      const next = Math.min(maxScale, Math.max(minScale, t.scale * factor));
      const k = next / t.scale;
      // keep the world point under the cursor fixed
      t.x = px - (px - t.x) * k;
      t.y = py - (py - t.y) * k;
      t.scale = next;
      apply();
    };

    // Mouse-wheel vs trackpad-scroll heuristic. A physical wheel sends
    // line-mode deltas (Firefox) or large integer pixel deltas with no X
    // component (Chrome/Safari, typically multiples of 100/120). Trackpad
    // two-finger scroll sends small/fractional pixel deltas, often with
    // non-zero deltaX. ctrlKey is set by the browser for trackpad pinch.
    const isMouseWheel = (e) =>
      e.deltaMode !== 0 ||
      (e.deltaX === 0 && Number.isInteger(e.deltaY) && Math.abs(e.deltaY) >= 40);

    const onWheel = (e) => {
      e.preventDefault();
      if (isGesturing) return; // Safari: gesture* owns the pinch — discard concurrent wheels
      if ((e.ctrlKey || e.metaKey) && !isMouseWheel(e)) {
        // trackpad pinch, or ctrl/cmd + smooth-scroll mouse. Notched
        // wheels fall through to the fixed-step branch below.
        zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * 0.01));
      } else if (isMouseWheel(e)) {
        // notched mouse wheel — fixed-ratio step per click
        zoomAt(e.clientX, e.clientY, Math.exp(-Math.sign(e.deltaY) * 0.18));
      } else {
        // trackpad two-finger scroll — pan
        tf.current.x -= e.deltaX;
        tf.current.y -= e.deltaY;
        apply();
      }
    };

    // Safari sends native gesture* events for trackpad pinch with a smooth
    // e.scale; preferring these over the ctrl+wheel fallback gives a much
    // better feel there. No-ops on other browsers. Safari also fires
    // ctrlKey wheel events during the same pinch — isGesturing makes
    // onWheel drop those entirely so they neither zoom nor pan.
    let gsBase = 1;
    let isGesturing = false;
    const onGestureStart = (e) => { e.preventDefault(); isGesturing = true; gsBase = tf.current.scale; };
    const onGestureChange = (e) => {
      e.preventDefault();
      zoomAt(e.clientX, e.clientY, (gsBase * e.scale) / tf.current.scale);
    };
    const onGestureEnd = (e) => { e.preventDefault(); isGesturing = false; };

    // Drag-pan: middle button anywhere, or primary button on canvas
    // background (anything that isn't an artboard or an inline editor).
    let drag = null;
    const onPointerDown = (e) => {
      const onBg = !e.target.closest('[data-dc-slot], .dc-editable');
      if (!(e.button === 1 || (e.button === 0 && onBg))) return;
      e.preventDefault();
      vp.setPointerCapture(e.pointerId);
      drag = { id: e.pointerId, lx: e.clientX, ly: e.clientY };
      vp.style.cursor = 'grabbing';
    };
    const onPointerMove = (e) => {
      if (!drag || e.pointerId !== drag.id) return;
      tf.current.x += e.clientX - drag.lx;
      tf.current.y += e.clientY - drag.ly;
      drag.lx = e.clientX; drag.ly = e.clientY;
      apply();
    };
    const onPointerUp = (e) => {
      if (!drag || e.pointerId !== drag.id) return;
      vp.releasePointerCapture(e.pointerId);
      drag = null;
      vp.style.cursor = '';
    };

    // Host-driven zoom (toolbar % menu). Zooms around viewport centre so the
    // visible midpoint stays fixed — matching the host's iframe-zoom feel.
    const onHostMsg = (e) => {
      const d = e.data;
      if (d && d.type === '__dc_set_zoom' && typeof d.scale === 'number') {
        const r = vp.getBoundingClientRect();
        zoomAt(r.left + r.width / 2, r.top + r.height / 2, d.scale / tf.current.scale);
      } else if (d && d.type === '__dc_probe') {
        // Host's [readyGen] reset asks whether a canvas is present; it
        // fires on the iframe's native 'load', which for canvases with
        // images/fonts is after our mount-time announce, so re-announce.
        // Clear the pan-tick guard so apply() re-posts the current scale
        // even if it's unchanged — the host just reset dcScale to 1.
        window.parent.postMessage({ type: '__dc_present' }, '*');
        lastPostedScale.current = undefined;
        apply();
      }
    };
    window.addEventListener('message', onHostMsg);
    // Announce canvas mode so the host toolbar proxies its % control here
    // instead of scaling the iframe element (which would just shrink the
    // viewport window of an infinite canvas). The apply() that follows emits
    // the initial __dc_zoom so the toolbar % is correct before first pinch.
    // lastPostedScale reset mirrors the __dc_probe handler: the layout
    // effect's restore-path apply() may already have posted the restored
    // scale (before __dc_present), so clear the guard to re-post it in order.
    window.parent.postMessage({ type: '__dc_present' }, '*');
    lastPostedScale.current = undefined;
    apply();

    vp.addEventListener('wheel', onWheel, { passive: false });
    vp.addEventListener('gesturestart', onGestureStart, { passive: false });
    vp.addEventListener('gesturechange', onGestureChange, { passive: false });
    vp.addEventListener('gestureend', onGestureEnd, { passive: false });
    vp.addEventListener('pointerdown', onPointerDown);
    vp.addEventListener('pointermove', onPointerMove);
    vp.addEventListener('pointerup', onPointerUp);
    vp.addEventListener('pointercancel', onPointerUp);
    return () => {
      window.removeEventListener('message', onHostMsg);
      vp.removeEventListener('wheel', onWheel);
      vp.removeEventListener('gesturestart', onGestureStart);
      vp.removeEventListener('gesturechange', onGestureChange);
      vp.removeEventListener('gestureend', onGestureEnd);
      vp.removeEventListener('pointerdown', onPointerDown);
      vp.removeEventListener('pointermove', onPointerMove);
      vp.removeEventListener('pointerup', onPointerUp);
      vp.removeEventListener('pointercancel', onPointerUp);
    };
  }, [apply, minScale, maxScale]);

  const gridSvg = `url("data:image/svg+xml,%3Csvg width='120' height='120' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M120 0H0v120' fill='none' stroke='${encodeURIComponent(DC.grid)}' stroke-width='1'/%3E%3C/svg%3E")`;
  return (
    <div
      ref={vpRef}
      className="design-canvas"
      style={{
        height: '100vh', width: '100vw',
        background: DC.bg,
        overflow: 'hidden',
        overscrollBehavior: 'none',
        touchAction: 'none',
        position: 'relative',
        fontFamily: DC.font,
        boxSizing: 'border-box',
        ...style,
      }}
    >
      <div
        ref={worldRef}
        style={{
          position: 'absolute', top: 0, left: 0,
          transformOrigin: '0 0',
          willChange: 'transform',
          width: 'max-content', minWidth: '100%',
          minHeight: '100%',
          padding: '60px 0 80px',
        }}
      >
        <div style={{ position: 'absolute', inset: -6000, backgroundImage: gridSvg, backgroundSize: '120px 120px', pointerEvents: 'none', zIndex: -1 }} />
        {children}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// DCSection — editable title + h-row of artboards in persisted order
// ─────────────────────────────────────────────────────────────
function DCSection({ id, title, subtitle, children, gap = 48 }) {
  const ctx = React.useContext(DCCtx);
  const sid = id ?? title;
  const all = React.Children.toArray(children);
  const artboards = all.filter((c) => c && c.type === DCArtboard);
  const rest = all.filter((c) => !(c && c.type === DCArtboard));
  const sec = (ctx && sid && ctx.section(sid)) || {};
  // Must match DesignCanvas's srcKey computation exactly (it filters falsy
  // IDs), or onDelete persists a srcKey that DesignCanvas never recognizes.
  const allIds = artboards.map((a) => a.props.id ?? a.props.label).filter(Boolean);
  const srcKey = allIds.join('\x1f');
  const hidden = sec.srcKey === srcKey ? (sec.hidden || []) : [];
  const srcOrder = allIds.filter((k) => !hidden.includes(k));

  const order = React.useMemo(() => {
    const kept = (sec.order || []).filter((k) => srcOrder.includes(k));
    return [...kept, ...srcOrder.filter((k) => !kept.includes(k))];
  }, [sec.order, srcOrder.join('|')]);

  const byId = Object.fromEntries(artboards.map((a) => [a.props.id ?? a.props.label, a]));

  // marginBottom counter-scales so the on-screen gap between sections stays
  // constant — otherwise at low zoom the (world-space) gap collapses while
  // the screen-constant sectionhead below it doesn't, and the title reads as
  // belonging to the section above. paddingBottom below is just enough for
  // the 24px artboard-header (abs-positioned above each card) plus ~8px, so
  // the title sits tight against its own row at every zoom.
  return (
    <div data-dc-section={sid}
      style={{ marginBottom: 'calc(80px * var(--dc-inv-zoom, 1))', position: 'relative' }}>
      <div style={{ padding: '0 60px' }}>
        <div className="dc-sectionhead" style={{ paddingBottom: 36 }}>
          <DCEditable tag="div" value={sec.title ?? title}
            onChange={(v) => ctx && sid && ctx.patchSection(sid, { title: v })}
            style={{ fontSize: 28, fontWeight: 600, color: DC.title, letterSpacing: -0.4, marginBottom: 6, display: 'inline-block' }} />
          {subtitle && <div style={{ fontSize: 16, color: DC.subtitle }}>{subtitle}</div>}
        </div>
      </div>
      <div style={{ display: 'flex', gap, padding: '0 60px', alignItems: 'flex-start', width: 'max-content' }}>
        {order.map((k) => (
          <DCArtboardFrame key={k} sectionId={sid} artboard={byId[k]} order={order}
            label={(sec.labels || {})[k] ?? byId[k].props.label}
            onRename={(v) => ctx && ctx.patchSection(sid, (x) => ({ labels: { ...x.labels, [k]: v } }))}
            onReorder={(next) => ctx && ctx.patchSection(sid, { order: next })}
            onDelete={() => ctx && ctx.patchSection(sid, (x) => ({
              hidden: [...(x.srcKey === srcKey ? (x.hidden || []) : []), k],
              srcKey,
            }))}
            onFocus={() => ctx && ctx.setFocus(`${sid}/${k}`)} />
        ))}
      </div>
      {rest}
    </div>
  );
}

// DCArtboard — marker; rendered by DCArtboardFrame via DCSection.
function DCArtboard() { return null; }

// Per-artboard export (kind: 'png' | 'html'). Both paths share the same
// self-contained clone: computed styles baked in, @font-face / <img> /
// inline-style background-image urls inlined as data URIs. PNG wraps the
// clone in foreignObject→canvas at 3× the artboard's natural width×height
// (same pipeline the host uses for page captures); HTML wraps it in a
// minimal standalone document. Both are independent of viewport zoom.
async function dcExport(node, w, h, name, kind) {
  try { await document.fonts.ready; } catch {}
  const toDataURL = (url) => fetch(url).then((r) => r.blob()).then((b) => new Promise((res) => {
    const fr = new FileReader(); fr.onload = () => res(fr.result); fr.onerror = () => res(url); fr.readAsDataURL(b);
  })).catch(() => url);

  // Collect @font-face rules. ss.cssRules throws SecurityError on
  // cross-origin sheets (e.g. fonts.googleapis.com) — in that case fetch
  // the CSS text directly (those endpoints send ACAO:*) and regex-extract
  // the blocks. @import and @media/@supports are walked so nested
  // @font-face rules aren't missed.
  const fontRules = [], pending = [], seen = new Set();
  const scrapeCss = (href) => {
    if (seen.has(href)) return; seen.add(href);
    pending.push(fetch(href).then((r) => r.text()).then((css) => {
      for (const m of css.match(/@font-face\s*{[^}]*}/g) || []) fontRules.push({ css: m, base: href });
      for (const m of css.matchAll(/@import\s+(?:url\()?['"]?([^'")\s;]+)/g))
        scrapeCss(new URL(m[1], href).href);
    }).catch(() => {}));
  };
  const walk = (rules, base) => {
    for (const r of rules) {
      if (r.type === CSSRule.FONT_FACE_RULE) fontRules.push({ css: r.cssText, base });
      else if (r.type === CSSRule.IMPORT_RULE && r.styleSheet) {
        const ibase = r.styleSheet.href || base;
        try { walk(r.styleSheet.cssRules, ibase); } catch { scrapeCss(ibase); }
      } else if (r.cssRules) walk(r.cssRules, base);
    }
  };
  for (const ss of document.styleSheets) {
    const base = ss.href || location.href;
    try { walk(ss.cssRules, base); } catch { if (ss.href) scrapeCss(ss.href); }
  }
  while (pending.length) await pending.shift();
  const fontCss = (await Promise.all(fontRules.map(async (rule) => {
    let out = rule.css, m; const re = /url\((['"]?)([^'")]+)\1\)/g;
    while ((m = re.exec(rule.css))) {
      if (m[2].indexOf('data:') === 0) continue;
      let abs; try { abs = new URL(m[2], rule.base).href; } catch { continue; }
      out = out.split(m[0]).join('url("' + await toDataURL(abs) + '")');
    }
    return out;
  }))).join('\n');

  const cloneStyled = (src) => {
    if (src.nodeType === 8 || (src.nodeType === 1 && src.tagName === 'SCRIPT')) return document.createTextNode('');
    const dst = src.cloneNode(false);
    if (src.nodeType === 1) {
      const cs = getComputedStyle(src); let txt = '';
      for (let i = 0; i < cs.length; i++) txt += cs[i] + ':' + cs.getPropertyValue(cs[i]) + ';';
      dst.setAttribute('style', txt + 'animation:none;transition:none;');
      if (src.tagName === 'CANVAS') try { const im = document.createElement('img'); im.src = src.toDataURL(); im.setAttribute('style', txt); return im; } catch {}
    }
    for (let c = src.firstChild; c; c = c.nextSibling) dst.appendChild(cloneStyled(c));
    return dst;
  };
  const clone = cloneStyled(node);
  clone.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
  // Drop the card's own shadow/radius so the export is a flush w×h rect;
  // the artboard's own background (if any) is already in the computed style.
  clone.style.boxShadow = 'none'; clone.style.borderRadius = '0';

  const jobs = [];
  clone.querySelectorAll('img').forEach((el) => {
    const s = el.getAttribute('src');
    if (s && s.indexOf('data:') !== 0) jobs.push(toDataURL(el.src).then((d) => el.setAttribute('src', d)));
  });
  [clone, ...clone.querySelectorAll('*')].forEach((el) => {
    const bg = el.style.backgroundImage; if (!bg) return;
    let m; const re = /url\(["']?([^"')]+)["']?\)/g;
    while ((m = re.exec(bg))) {
      const tok = m[0], url = m[1];
      if (url.indexOf('data:') === 0) continue;
      jobs.push(toDataURL(url).then((d) => { el.style.backgroundImage = el.style.backgroundImage.split(tok).join('url("' + d + '")'); }));
    }
  });
  await Promise.all(jobs);

  const xml = new XMLSerializer().serializeToString(clone);
  const save = (blob, ext) => {
    if (!blob) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name + '.' + ext; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  if (kind === 'html') {
    const html = '<!doctype html><html><head><meta charset="utf-8"><title>' + name + '</title>' +
      (fontCss ? '<style>' + fontCss + '</style>' : '') +
      '</head><body style="margin:0">' + xml + '</body></html>';
    return save(new Blob([html], { type: 'text/html' }), 'html');
  }

  // PNG: the SVG's own width/height must be the output resolution — an
  // <img>-loaded SVG rasterizes at its intrinsic size, so sizing it at 1×
  // and ctx.scale()-ing up would just upscale a 1× bitmap. viewBox maps the
  // w×h foreignObject onto the px·w × px·h SVG canvas so the browser renders
  // the HTML at full resolution.
  const px = 3;
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + w * px + '" height="' + h * px +
    '" viewBox="0 0 ' + w + ' ' + h + '"><foreignObject width="' + w + '" height="' + h + '">' +
    (fontCss ? '<style><![CDATA[' + fontCss + ']]></style>' : '') + xml + '</foreignObject></svg>';
  const img = new Image();
  await new Promise((res, rej) => {
    img.onload = res; img.onerror = () => rej(new Error('svg load failed'));
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  });
  const cv = document.createElement('canvas');
  cv.width = w * px; cv.height = h * px;
  cv.getContext('2d').drawImage(img, 0, 0);
  cv.toBlob((blob) => save(blob, 'png'), 'image/png');
}

function DCArtboardFrame({ sectionId, artboard, label, order, onRename, onReorder, onFocus, onDelete }) {
  const { id: rawId, label: rawLabel, width = 260, height = 480, children, style = {} } = artboard.props;
  const id = rawId ?? rawLabel;
  const ref = React.useRef(null);
  const cardRef = React.useRef(null);
  const menuRef = React.useRef(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);

  // ⋯ menu: close on any outside pointerdown. Two-click delete lives inside
  // the menu — first click arms the row, second commits; closing disarms.
  React.useEffect(() => {
    if (!menuOpen) { setConfirming(false); return; }
    const off = (e) => { if (!menuRef.current || !menuRef.current.contains(e.target)) setMenuOpen(false); };
    document.addEventListener('pointerdown', off, true);
    return () => document.removeEventListener('pointerdown', off, true);
  }, [menuOpen]);

  const doExport = (kind) => {
    setMenuOpen(false);
    if (!cardRef.current) return;
    const name = String(label || id || 'artboard').replace(/[^\w\s.-]+/g, '_');
    dcExport(cardRef.current, width, height, name, kind)
      .catch((e) => console.error('[design-canvas] export failed:', e));
  };

  // Live drag-reorder: dragged card sticks to cursor; siblings slide into
  // their would-be slots in real time via transforms. DOM order only
  // changes on drop.
  const onGripDown = (e) => {
    e.preventDefault(); e.stopPropagation();
    const me = ref.current;
    // translateX is applied in local (pre-scale) space but pointer deltas and
    // getBoundingClientRect().left are screen-space — divide by the viewport's
    // current scale so the dragged card tracks the cursor at any zoom level.
    const scale = me.getBoundingClientRect().width / me.offsetWidth || 1;
    const peers = Array.from(document.querySelectorAll(`[data-dc-section="${sectionId}"] [data-dc-slot]`));
    const homes = peers.map((el) => ({ el, id: el.dataset.dcSlot, x: el.getBoundingClientRect().left }));
    const slotXs = homes.map((h) => h.x);
    const startIdx = order.indexOf(id);
    const startX = e.clientX;
    let liveOrder = order.slice();
    me.classList.add('dc-dragging');

    const layout = () => {
      for (const h of homes) {
        if (h.id === id) continue;
        const slot = liveOrder.indexOf(h.id);
        h.el.style.transform = `translateX(${(slotXs[slot] - h.x) / scale}px)`;
      }
    };

    const move = (ev) => {
      const dx = ev.clientX - startX;
      me.style.transform = `translateX(${dx / scale}px)`;
      const cur = homes[startIdx].x + dx;
      let nearest = 0, best = Infinity;
      for (let i = 0; i < slotXs.length; i++) {
        const d = Math.abs(slotXs[i] - cur);
        if (d < best) { best = d; nearest = i; }
      }
      if (liveOrder.indexOf(id) !== nearest) {
        liveOrder = order.filter((k) => k !== id);
        liveOrder.splice(nearest, 0, id);
        layout();
      }
    };

    const up = () => {
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', up);
      const finalSlot = liveOrder.indexOf(id);
      me.classList.remove('dc-dragging');
      me.style.transform = `translateX(${(slotXs[finalSlot] - homes[startIdx].x) / scale}px)`;
      // After the settle transition, kill transitions + clear transforms +
      // commit the reorder in the same frame so there's no visual snap-back.
      setTimeout(() => {
        for (const h of homes) { h.el.style.transition = 'none'; h.el.style.transform = ''; }
        if (liveOrder.join('|') !== order.join('|')) onReorder(liveOrder);
        requestAnimationFrame(() => requestAnimationFrame(() => {
          for (const h of homes) h.el.style.transition = '';
        }));
      }, 180);
    };
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', up);
  };

  return (
    <div ref={ref} data-dc-slot={id} style={{ position: 'relative', flexShrink: 0 }}>
      <div className="dc-header" style={{ color: DC.label }} onPointerDown={(e) => e.stopPropagation()}>
        <div className="dc-labelrow">
          <div className="dc-grip" onPointerDown={onGripDown} title="Drag to reorder">
            <svg width="9" height="13" viewBox="0 0 9 13" fill="currentColor"><circle cx="2" cy="2" r="1.1"/><circle cx="7" cy="2" r="1.1"/><circle cx="2" cy="6.5" r="1.1"/><circle cx="7" cy="6.5" r="1.1"/><circle cx="2" cy="11" r="1.1"/><circle cx="7" cy="11" r="1.1"/></svg>
          </div>
          <div className="dc-labeltext" onClick={onFocus} title="Click to focus">
            <DCEditable value={label} onChange={onRename} onClick={(e) => e.stopPropagation()}
              style={{ fontSize: 15, fontWeight: 500, color: DC.label, lineHeight: 1 }} />
          </div>
        </div>
        <div className="dc-btns">
          <div ref={menuRef} style={{ position: 'relative' }}>
            <button className="dc-kebab" title="More" onClick={() => setMenuOpen((o) => !o)}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><circle cx="2.5" cy="6" r="1.1"/><circle cx="6" cy="6" r="1.1"/><circle cx="9.5" cy="6" r="1.1"/></svg>
            </button>
            {menuOpen && (
              <div className="dc-menu" onPointerDown={(e) => e.stopPropagation()}>
                <button onClick={() => doExport('png')}>Download PNG</button>
                <button onClick={() => doExport('html')}>Download HTML</button>
                <hr />
                <button className="dc-danger"
                  onClick={() => { if (confirming) { setMenuOpen(false); onDelete(); } else setConfirming(true); }}>
                  {confirming ? 'Click again to delete' : 'Delete'}
                </button>
              </div>
            )}
          </div>
          <button className="dc-expand" onClick={onFocus} title="Focus">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M7 1h4v4M5 11H1V7M11 1L7.5 4.5M1 11l3.5-3.5"/></svg>
          </button>
        </div>
      </div>
      <div ref={cardRef} className="dc-card"
        style={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,.08),0 4px 16px rgba(0,0,0,.06)', overflow: 'hidden', width, height, background: '#fff', ...style }}>
        {children || <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 13, fontFamily: DC.font }}>{id}</div>}
      </div>
    </div>
  );
}

// Inline rename — commits on blur or Enter.
function DCEditable({ value, onChange, style, tag = 'span', onClick }) {
  const T = tag;
  return (
    <T className="dc-editable" contentEditable suppressContentEditableWarning
      onClick={onClick}
      onPointerDown={(e) => e.stopPropagation()}
      onBlur={(e) => onChange && onChange(e.currentTarget.textContent)}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }}
      style={style}>{value}</T>
  );
}

// ─────────────────────────────────────────────────────────────
// Focus mode — overlay one artboard; ←/→ within section, ↑/↓ across
// sections, Esc or backdrop click to exit.
// ─────────────────────────────────────────────────────────────
function DCFocusOverlay({ entry, sectionMeta, sectionOrder }) {
  const ctx = React.useContext(DCCtx);
  const { sectionId, artboard } = entry;
  const sec = ctx.section(sectionId);
  const meta = sectionMeta[sectionId];
  const peers = meta.slotIds;
  const aid = artboard.props.id ?? artboard.props.label;
  const idx = peers.indexOf(aid);
  const secIdx = sectionOrder.indexOf(sectionId);

  const go = (d) => { const n = peers[(idx + d + peers.length) % peers.length]; if (n) ctx.setFocus(`${sectionId}/${n}`); };
  const goSection = (d) => {
    // Sections whose artboards are all deleted have slotIds:[] — step past
    // them to the next non-empty section so ↑/↓ doesn't dead-end.
    const n = sectionOrder.length;
    for (let i = 1; i < n; i++) {
      const ns = sectionOrder[(((secIdx + d * i) % n) + n) % n];
      const first = sectionMeta[ns] && sectionMeta[ns].slotIds[0];
      if (first) { ctx.setFocus(`${ns}/${first}`); return; }
    }
  };

  React.useEffect(() => {
    const k = (e) => {
      if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); go(1); }
      if (e.key === 'ArrowUp') { e.preventDefault(); goSection(-1); }
      if (e.key === 'ArrowDown') { e.preventDefault(); goSection(1); }
    };
    document.addEventListener('keydown', k);
    return () => document.removeEventListener('keydown', k);
  });

  const { width = 260, height = 480, children } = artboard.props;
  const [vp, setVp] = React.useState({ w: window.innerWidth, h: window.innerHeight });
  React.useEffect(() => { const r = () => setVp({ w: window.innerWidth, h: window.innerHeight }); window.addEventListener('resize', r); return () => window.removeEventListener('resize', r); }, []);
  const scale = Math.max(0.1, Math.min((vp.w - 200) / width, (vp.h - 260) / height, 2));

  const [ddOpen, setDd] = React.useState(false);
  const Arrow = ({ dir, onClick }) => (
    <button onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{ position: 'absolute', top: '50%', [dir]: 28, transform: 'translateY(-50%)',
        border: 'none', background: 'rgba(255,255,255,.08)', color: 'rgba(255,255,255,.9)',
        width: 44, height: 44, borderRadius: 22, fontSize: 18, cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background .15s' }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,.18)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,.08)')}>
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d={dir === 'left' ? 'M11 3L5 9l6 6' : 'M7 3l6 6-6 6'} /></svg>
    </button>
  );

  // Portal to body so position:fixed is the real viewport regardless of any
  // transform on DesignCanvas's ancestors (including the canvas zoom itself).
  return ReactDOM.createPortal(
    <div onClick={() => ctx.setFocus(null)}
      onWheel={(e) => e.preventDefault()}
      style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(24,20,16,.6)', backdropFilter: 'blur(14px)',
        fontFamily: DC.font, color: '#fff' }}>

      {/* top bar: section dropdown (left) · close (right) */}
      <div onClick={(e) => e.stopPropagation()}
        style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 72, display: 'flex', alignItems: 'flex-start', padding: '16px 20px 0', gap: 16 }}>
        <div style={{ position: 'relative' }}>
          <button onClick={() => setDd((o) => !o)}
            style={{ border: 'none', background: 'transparent', color: '#fff', cursor: 'pointer', padding: '6px 8px',
              borderRadius: 6, textAlign: 'left', fontFamily: 'inherit' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18, fontWeight: 600, letterSpacing: -0.3 }}>{meta.title}</span>
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" style={{ opacity: .7 }}><path d="M2 4l3.5 3.5L9 4"/></svg>
            </span>
            {meta.subtitle && <span style={{ display: 'block', fontSize: 13, opacity: .6, fontWeight: 400, marginTop: 2 }}>{meta.subtitle}</span>}
          </button>
          {ddOpen && (
            <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, background: '#2a251f', borderRadius: 8,
              boxShadow: '0 8px 32px rgba(0,0,0,.4)', padding: 4, minWidth: 200, zIndex: 10 }}>
              {sectionOrder.filter((sid) => sectionMeta[sid].slotIds.length).map((sid) => (
                <button key={sid} onClick={() => { setDd(false); const f = sectionMeta[sid].slotIds[0]; if (f) ctx.setFocus(`${sid}/${f}`); }}
                  style={{ display: 'block', width: '100%', textAlign: 'left', border: 'none', cursor: 'pointer',
                    background: sid === sectionId ? 'rgba(255,255,255,.1)' : 'transparent', color: '#fff',
                    padding: '8px 12px', borderRadius: 5, fontSize: 14, fontWeight: sid === sectionId ? 600 : 400, fontFamily: 'inherit' }}>
                  {sectionMeta[sid].title}
                </button>
              ))}
            </div>
          )}
        </div>
        <div style={{ flex: 1 }} />
        <button onClick={() => ctx.setFocus(null)}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,.12)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          style={{ border: 'none', background: 'transparent', color: 'rgba(255,255,255,.7)', width: 32, height: 32,
            borderRadius: 16, fontSize: 20, cursor: 'pointer', lineHeight: 1, transition: 'background .12s' }}>×</button>
      </div>

      {/* card centered, label + index below — only the card itself stops
          propagation so any backdrop click (including the margins around
          the card) exits focus */}
      <div
        style={{ position: 'absolute', top: 64, bottom: 56, left: 100, right: 100, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <div onClick={(e) => e.stopPropagation()} style={{ width: width * scale, height: height * scale, position: 'relative' }}>
          <div style={{ width, height, transform: `scale(${scale})`, transformOrigin: 'top left', background: '#fff', borderRadius: 2, overflow: 'hidden',
            boxShadow: '0 20px 80px rgba(0,0,0,.4)' }}>
            {children || <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb' }}>{aid}</div>}
          </div>
        </div>
        <div onClick={(e) => e.stopPropagation()} style={{ fontSize: 14, fontWeight: 500, opacity: .85, textAlign: 'center' }}>
          {(sec.labels || {})[aid] ?? artboard.props.label}
          <span style={{ opacity: .5, marginLeft: 10, fontVariantNumeric: 'tabular-nums' }}>{idx + 1} / {peers.length}</span>
        </div>
      </div>

      <Arrow dir="left" onClick={() => go(-1)} />
      <Arrow dir="right" onClick={() => go(1)} />

      {/* dots */}
      <div onClick={(e) => e.stopPropagation()}
        style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 8 }}>
        {peers.map((p, i) => (
          <button key={p} onClick={() => ctx.setFocus(`${sectionId}/${p}`)}
            style={{ border: 'none', padding: 0, cursor: 'pointer', width: 6, height: 6, borderRadius: 3,
              background: i === idx ? '#fff' : 'rgba(255,255,255,.3)' }} />
        ))}
      </div>
    </div>,
    document.body,
  );
}

// ─────────────────────────────────────────────────────────────
// Post-it — absolute-positioned sticky note
// ─────────────────────────────────────────────────────────────
function DCPostIt({ children, top, left, right, bottom, rotate = -2, width = 180 }) {
  return (
    <div style={{
      position: 'absolute', top, left, right, bottom, width,
      background: DC.postitBg, padding: '14px 16px',
      fontFamily: '"Comic Sans MS", "Marker Felt", "Segoe Print", cursive',
      fontSize: 14, lineHeight: 1.4, color: DC.postitText,
      boxShadow: '0 2px 8px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
      transform: `rotate(${rotate}deg)`,
      zIndex: 5,
    }}>{children}</div>
  );
}

Object.assign(window, { DesignCanvas, DCSection, DCArtboard, DCPostIt });


}

// ─── ios-frame.jsx ───
{

// iOS.jsx — Simplified iOS 26 (Liquid Glass) device frame
// Based on the iOS 26 UI Kit + Figma status bar spec. No assets, no deps.
// Exports: IOSDevice, IOSStatusBar, IOSNavBar, IOSGlassPill, IOSList, IOSListRow, IOSKeyboard

// ─────────────────────────────────────────────────────────────
// Status bar
// ─────────────────────────────────────────────────────────────
function IOSStatusBar({ dark = false, time = '9:41' }) {
  const c = dark ? '#fff' : '#000';
  return (
    <div style={{
      display: 'flex', gap: 154, alignItems: 'center', justifyContent: 'center',
      padding: '21px 24px 19px', boxSizing: 'border-box',
      position: 'relative', zIndex: 20, width: '100%',
    }}>
      <div style={{ flex: 1, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: 1.5 }}>
        <span style={{
          fontFamily: '-apple-system, "SF Pro", system-ui', fontWeight: 590,
          fontSize: 17, lineHeight: '22px', color: c,
        }}>{time}</span>
      </div>
      <div style={{ flex: 1, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, paddingTop: 1, paddingRight: 1 }}>
        <svg width="19" height="12" viewBox="0 0 19 12">
          <rect x="0" y="7.5" width="3.2" height="4.5" rx="0.7" fill={c}/>
          <rect x="4.8" y="5" width="3.2" height="7" rx="0.7" fill={c}/>
          <rect x="9.6" y="2.5" width="3.2" height="9.5" rx="0.7" fill={c}/>
          <rect x="14.4" y="0" width="3.2" height="12" rx="0.7" fill={c}/>
        </svg>
        <svg width="17" height="12" viewBox="0 0 17 12">
          <path d="M8.5 3.2C10.8 3.2 12.9 4.1 14.4 5.6L15.5 4.5C13.7 2.7 11.2 1.5 8.5 1.5C5.8 1.5 3.3 2.7 1.5 4.5L2.6 5.6C4.1 4.1 6.2 3.2 8.5 3.2Z" fill={c}/>
          <path d="M8.5 6.8C9.9 6.8 11.1 7.3 12 8.2L13.1 7.1C11.8 5.9 10.2 5.1 8.5 5.1C6.8 5.1 5.2 5.9 3.9 7.1L5 8.2C5.9 7.3 7.1 6.8 8.5 6.8Z" fill={c}/>
          <circle cx="8.5" cy="10.5" r="1.5" fill={c}/>
        </svg>
        <svg width="27" height="13" viewBox="0 0 27 13">
          <rect x="0.5" y="0.5" width="23" height="12" rx="3.5" stroke={c} strokeOpacity="0.35" fill="none"/>
          <rect x="2" y="2" width="20" height="9" rx="2" fill={c}/>
          <path d="M25 4.5V8.5C25.8 8.2 26.5 7.2 26.5 6.5C26.5 5.8 25.8 4.8 25 4.5Z" fill={c} fillOpacity="0.4"/>
        </svg>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Liquid glass pill — blur + tint + shine
// ─────────────────────────────────────────────────────────────
function IOSGlassPill({ children, dark = false, style = {} }) {
  return (
    <div style={{
      height: 44, minWidth: 44, borderRadius: 9999,
      position: 'relative', overflow: 'hidden',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      boxShadow: dark
        ? '0 2px 6px rgba(0,0,0,0.35), 0 6px 16px rgba(0,0,0,0.2)'
        : '0 1px 3px rgba(0,0,0,0.07), 0 3px 10px rgba(0,0,0,0.06)',
      ...style,
    }}>
      {/* blur + tint */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 9999,
        backdropFilter: 'blur(12px) saturate(180%)',
        WebkitBackdropFilter: 'blur(12px) saturate(180%)',
        background: dark ? 'rgba(120,120,128,0.28)' : 'rgba(255,255,255,0.5)',
      }} />
      {/* shine */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 9999,
        boxShadow: dark
          ? 'inset 1.5px 1.5px 1px rgba(255,255,255,0.15), inset -1px -1px 1px rgba(255,255,255,0.08)'
          : 'inset 1.5px 1.5px 1px rgba(255,255,255,0.7), inset -1px -1px 1px rgba(255,255,255,0.4)',
        border: dark ? '0.5px solid rgba(255,255,255,0.15)' : '0.5px solid rgba(0,0,0,0.06)',
      }} />
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center', padding: '0 4px' }}>
        {children}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Navigation bar — glass pills + large title
// ─────────────────────────────────────────────────────────────
function IOSNavBar({ title = 'Title', dark = false, trailingIcon = true }) {
  const muted = dark ? 'rgba(255,255,255,0.6)' : '#404040';
  const text = dark ? '#fff' : '#000';
  const pillIcon = (content) => (
    <IOSGlassPill dark={dark}>
      <div style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {content}
      </div>
    </IOSGlassPill>
  );
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 10,
      paddingTop: 62, paddingBottom: 10, position: 'relative', zIndex: 5,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px',
      }}>
        {/* back chevron */}
        {pillIcon(
          <svg width="12" height="20" viewBox="0 0 12 20" fill="none" style={{ marginLeft: -1 }}>
            <path d="M10 2L2 10l8 8" stroke={muted} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
        {/* trailing ellipsis */}
        {trailingIcon && pillIcon(
          <svg width="22" height="6" viewBox="0 0 22 6">
            <circle cx="3" cy="3" r="2.5" fill={muted}/>
            <circle cx="11" cy="3" r="2.5" fill={muted}/>
            <circle cx="19" cy="3" r="2.5" fill={muted}/>
          </svg>
        )}
      </div>
      {/* large title */}
      <div style={{
        padding: '0 16px',
        fontFamily: '-apple-system, system-ui',
        fontSize: 34, fontWeight: 700, lineHeight: '41px',
        color: text, letterSpacing: 0.4,
      }}>{title}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Grouped list (inset card, r:26) + row (52px)
// ─────────────────────────────────────────────────────────────
function IOSListRow({ title, detail, icon, chevron = true, isLast = false, dark = false }) {
  const text = dark ? '#fff' : '#000';
  const sec = dark ? 'rgba(235,235,245,0.6)' : 'rgba(60,60,67,0.6)';
  const ter = dark ? 'rgba(235,235,245,0.3)' : 'rgba(60,60,67,0.3)';
  const sep = dark ? 'rgba(84,84,88,0.65)' : 'rgba(60,60,67,0.12)';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', minHeight: 52,
      padding: '0 16px', position: 'relative',
      fontFamily: '-apple-system, system-ui', fontSize: 17,
      letterSpacing: -0.43,
    }}>
      {icon && (
        <div style={{
          width: 30, height: 30, borderRadius: 7, background: icon,
          marginRight: 12, flexShrink: 0,
        }} />
      )}
      <div style={{ flex: 1, color: text }}>{title}</div>
      {detail && <span style={{ color: sec, marginRight: 6 }}>{detail}</span>}
      {chevron && (
        <svg width="8" height="14" viewBox="0 0 8 14" style={{ flexShrink: 0 }}>
          <path d="M1 1l6 6-6 6" stroke={ter} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )}
      {!isLast && (
        <div style={{
          position: 'absolute', bottom: 0, right: 0,
          left: icon ? 58 : 16, height: 0.5, background: sep,
        }} />
      )}
    </div>
  );
}

function IOSList({ header, children, dark = false }) {
  const hc = dark ? 'rgba(235,235,245,0.6)' : 'rgba(60,60,67,0.6)';
  const bg = dark ? '#1C1C1E' : '#fff';
  return (
    <div>
      {header && (
        <div style={{
          fontFamily: '-apple-system, system-ui', fontSize: 13,
          color: hc, textTransform: 'uppercase',
          padding: '8px 36px 6px', letterSpacing: -0.08,
        }}>{header}</div>
      )}
      <div style={{
        background: bg, borderRadius: 26,
        margin: '0 16px', overflow: 'hidden',
      }}>{children}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Device frame
// ─────────────────────────────────────────────────────────────
function IOSDevice({
  children, width = 402, height = 874, dark = false,
  title, keyboard = false,
}) {
  return (
    <div style={{
      width, height, borderRadius: 48, overflow: 'hidden',
      position: 'relative', background: dark ? '#000' : '#F2F2F7',
      boxShadow: '0 40px 80px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.12)',
      fontFamily: '-apple-system, system-ui, sans-serif',
      WebkitFontSmoothing: 'antialiased',
    }}>
      {/* dynamic island */}
      <div style={{
        position: 'absolute', top: 11, left: '50%', transform: 'translateX(-50%)',
        width: 126, height: 37, borderRadius: 24, background: '#000', zIndex: 50,
      }} />
      {/* status bar (absolute) */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10 }}>
        <IOSStatusBar dark={dark} />
      </div>
      {/* nav + content */}
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {title !== undefined && <IOSNavBar title={title} dark={dark} />}
        <div style={{ flex: 1, overflow: 'auto' }}>{children}</div>
        {keyboard && <IOSKeyboard dark={dark} />}
      </div>
      {/* home indicator — always on top */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 60,
        height: 34, display: 'flex', justifyContent: 'center', alignItems: 'flex-end',
        paddingBottom: 8, pointerEvents: 'none',
      }}>
        <div style={{
          width: 139, height: 5, borderRadius: 100,
          background: dark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.25)',
        }} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Keyboard — iOS 26 liquid glass
// ─────────────────────────────────────────────────────────────
function IOSKeyboard({ dark = false }) {
  const glyph = dark ? 'rgba(255,255,255,0.7)' : '#595959';
  const sugg = dark ? 'rgba(255,255,255,0.6)' : '#333';
  const keyBg = dark ? 'rgba(255,255,255,0.22)' : 'rgba(255,255,255,0.85)';

  // special-key icons
  const icons = {
    shift: <svg width="19" height="17" viewBox="0 0 19 17"><path d="M9.5 1L1 9.5h4.5V16h8V9.5H18L9.5 1z" fill={glyph}/></svg>,
    del: <svg width="23" height="17" viewBox="0 0 23 17"><path d="M7 1h13a2 2 0 012 2v11a2 2 0 01-2 2H7l-6-7.5L7 1z" fill="none" stroke={glyph} strokeWidth="1.6" strokeLinejoin="round"/><path d="M10 5l7 7M17 5l-7 7" stroke={glyph} strokeWidth="1.6" strokeLinecap="round"/></svg>,
    ret: <svg width="20" height="14" viewBox="0 0 20 14"><path d="M18 1v6H4m0 0l4-4M4 7l4 4" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  };

  const key = (content, { w, flex, ret, fs = 25, k } = {}) => (
    <div key={k} style={{
      height: 42, borderRadius: 8.5,
      flex: flex ? 1 : undefined, width: w, minWidth: 0,
      background: ret ? '#08f' : keyBg,
      boxShadow: '0 1px 0 rgba(0,0,0,0.075)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: '-apple-system, "SF Compact", system-ui',
      fontSize: fs, fontWeight: 458, color: ret ? '#fff' : glyph,
    }}>{content}</div>
  );

  const row = (keys, pad = 0) => (
    <div style={{ display: 'flex', gap: 6.5, justifyContent: 'center', padding: `0 ${pad}px` }}>
      {keys.map(l => key(l, { flex: true, k: l }))}
    </div>
  );

  return (
    <div style={{
      position: 'relative', zIndex: 15, borderRadius: 27, overflow: 'hidden',
      padding: '11px 0 2px',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      boxShadow: dark
        ? '0 -2px 20px rgba(0,0,0,0.09)'
        : '0 -1px 6px rgba(0,0,0,0.018), 0 -3px 20px rgba(0,0,0,0.012)',
    }}>
      {/* liquid glass bg — same recipe as nav pills */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 27,
        backdropFilter: 'blur(12px) saturate(180%)',
        WebkitBackdropFilter: 'blur(12px) saturate(180%)',
        background: dark ? 'rgba(120,120,128,0.14)' : 'rgba(255,255,255,0.25)',
      }} />
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 27,
        boxShadow: dark
          ? 'inset 1.5px 1.5px 1px rgba(255,255,255,0.15)'
          : 'inset 1.5px 1.5px 1px rgba(255,255,255,0.7), inset -1px -1px 1px rgba(255,255,255,0.4)',
        border: dark ? '0.5px solid rgba(255,255,255,0.15)' : '0.5px solid rgba(0,0,0,0.06)',
        pointerEvents: 'none',
      }} />

      {/* autocorrect bar */}
      <div style={{
        display: 'flex', gap: 20, alignItems: 'center',
        padding: '8px 22px 13px', width: '100%', boxSizing: 'border-box',
        position: 'relative',
      }}>
        {['"The"', 'the', 'to'].map((w, i) => (
          <React.Fragment key={i}>
            {i > 0 && <div style={{ width: 1, height: 25, background: '#ccc', opacity: 0.3 }} />}
            <div style={{
              flex: 1, textAlign: 'center',
              fontFamily: '-apple-system, system-ui', fontSize: 17,
              color: sugg, letterSpacing: -0.43, lineHeight: '22px',
            }}>{w}</div>
          </React.Fragment>
        ))}
      </div>

      {/* key layout */}
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 13,
        padding: '0 6.5px', width: '100%', boxSizing: 'border-box',
        position: 'relative',
      }}>
        {row(['q','w','e','r','t','y','u','i','o','p'])}
        {row(['a','s','d','f','g','h','j','k','l'], 20)}
        <div style={{ display: 'flex', gap: 14.25, alignItems: 'center' }}>
          {key(icons.shift, { w: 45, k: 'shift' })}
          <div style={{ display: 'flex', gap: 6.5, flex: 1 }}>
            {['z','x','c','v','b','n','m'].map(l => key(l, { flex: true, k: l }))}
          </div>
          {key(icons.del, { w: 45, k: 'del' })}
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {key('ABC', { w: 92.25, fs: 18, k: 'abc' })}
          {key('', { flex: true, k: 'space' })}
          {key(icons.ret, { w: 92.25, ret: true, k: 'ret' })}
        </div>
      </div>

      {/* bottom spacer (emoji+mic area, icons omitted) */}
      <div style={{ height: 56, width: '100%', position: 'relative' }} />
    </div>
  );
}

Object.assign(window, {
  IOSDevice, IOSStatusBar, IOSNavBar, IOSGlassPill, IOSList, IOSListRow, IOSKeyboard,
});

}

// ─── tweaks-panel.jsx ───
{

// tweaks-panel.jsx
// Reusable Tweaks shell + form-control helpers.
//
// Owns the host protocol (listens for __activate_edit_mode / __deactivate_edit_mode,
// posts __edit_mode_available / __edit_mode_set_keys / __edit_mode_dismissed) so
// individual prototypes don't re-roll it. Ships a consistent set of controls so you
// don't hand-draw <input type="range">, segmented radios, steppers, etc.
//
// Usage (in an HTML file that loads React + Babel):
//
//   const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
//     "primaryColor": "#D97757",
//     "palette": ["#D97757", "#29261b", "#f6f4ef"],
//     "fontSize": 16,
//     "density": "regular",
//     "dark": false
//   }/*EDITMODE-END*/;
//
//   function App() {
//     const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
//     return (
//       <div style={{ fontSize: t.fontSize, color: t.primaryColor }}>
//         Hello
//         <TweaksPanel>
//           <TweakSection label="Typography" />
//           <TweakSlider label="Font size" value={t.fontSize} min={10} max={32} unit="px"
//                        onChange={(v) => setTweak('fontSize', v)} />
//           <TweakRadio  label="Density" value={t.density}
//                        options={['compact', 'regular', 'comfy']}
//                        onChange={(v) => setTweak('density', v)} />
//           <TweakSection label="Theme" />
//           <TweakColor  label="Primary" value={t.primaryColor}
//                        options={['#D97757', '#2A6FDB', '#1F8A5B', '#7A5AE0']}
//                        onChange={(v) => setTweak('primaryColor', v)} />
//           <TweakColor  label="Palette" value={t.palette}
//                        options={[['#D97757', '#29261b', '#f6f4ef'],
//                                  ['#475569', '#0f172a', '#f1f5f9']]}
//                        onChange={(v) => setTweak('palette', v)} />
//           <TweakToggle label="Dark mode" value={t.dark}
//                        onChange={(v) => setTweak('dark', v)} />
//         </TweaksPanel>
//       </div>
//     );
//   }
//
// ─────────────────────────────────────────────────────────────────────────────

const __TWEAKS_STYLE = `
  .twk-panel{position:fixed;right:16px;bottom:16px;z-index:2147483646;width:280px;
    max-height:calc(100vh - 32px);display:flex;flex-direction:column;
    transform:scale(var(--dc-inv-zoom,1));transform-origin:bottom right;
    background:rgba(250,249,247,.78);color:#29261b;
    -webkit-backdrop-filter:blur(24px) saturate(160%);backdrop-filter:blur(24px) saturate(160%);
    border:.5px solid rgba(255,255,255,.6);border-radius:14px;
    box-shadow:0 1px 0 rgba(255,255,255,.5) inset,0 12px 40px rgba(0,0,0,.18);
    font:11.5px/1.4 ui-sans-serif,system-ui,-apple-system,sans-serif;overflow:hidden}
  .twk-hd{display:flex;align-items:center;justify-content:space-between;
    padding:10px 8px 10px 14px;cursor:move;user-select:none}
  .twk-hd b{font-size:12px;font-weight:600;letter-spacing:.01em}
  .twk-x{appearance:none;border:0;background:transparent;color:rgba(41,38,27,.55);
    width:22px;height:22px;border-radius:6px;cursor:default;font-size:13px;line-height:1}
  .twk-x:hover{background:rgba(0,0,0,.06);color:#29261b}
  .twk-body{padding:2px 14px 14px;display:flex;flex-direction:column;gap:10px;
    overflow-y:auto;overflow-x:hidden;min-height:0;
    scrollbar-width:thin;scrollbar-color:rgba(0,0,0,.15) transparent}
  .twk-body::-webkit-scrollbar{width:8px}
  .twk-body::-webkit-scrollbar-track{background:transparent;margin:2px}
  .twk-body::-webkit-scrollbar-thumb{background:rgba(0,0,0,.15);border-radius:4px;
    border:2px solid transparent;background-clip:content-box}
  .twk-body::-webkit-scrollbar-thumb:hover{background:rgba(0,0,0,.25);
    border:2px solid transparent;background-clip:content-box}
  .twk-row{display:flex;flex-direction:column;gap:5px}
  .twk-row-h{flex-direction:row;align-items:center;justify-content:space-between;gap:10px}
  .twk-lbl{display:flex;justify-content:space-between;align-items:baseline;
    color:rgba(41,38,27,.72)}
  .twk-lbl>span:first-child{font-weight:500}
  .twk-val{color:rgba(41,38,27,.5);font-variant-numeric:tabular-nums}

  .twk-sect{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
    color:rgba(41,38,27,.45);padding:10px 0 0}
  .twk-sect:first-child{padding-top:0}

  .twk-field{appearance:none;width:100%;height:26px;padding:0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;
    background:rgba(255,255,255,.6);color:inherit;font:inherit;outline:none}
  .twk-field:focus{border-color:rgba(0,0,0,.25);background:rgba(255,255,255,.85)}
  select.twk-field{padding-right:22px;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='rgba(0,0,0,.5)' d='M0 0h10L5 6z'/></svg>");
    background-repeat:no-repeat;background-position:right 8px center}

  .twk-slider{appearance:none;-webkit-appearance:none;width:100%;height:4px;margin:6px 0;
    border-radius:999px;background:rgba(0,0,0,.12);outline:none}
  .twk-slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
    width:14px;height:14px;border-radius:50%;background:#fff;
    border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}
  .twk-slider::-moz-range-thumb{width:14px;height:14px;border-radius:50%;
    background:#fff;border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}

  .twk-seg{position:relative;display:flex;padding:2px;border-radius:8px;
    background:rgba(0,0,0,.06);user-select:none}
  .twk-seg-thumb{position:absolute;top:2px;bottom:2px;border-radius:6px;
    background:rgba(255,255,255,.9);box-shadow:0 1px 2px rgba(0,0,0,.12);
    transition:left .15s cubic-bezier(.3,.7,.4,1),width .15s}
  .twk-seg.dragging .twk-seg-thumb{transition:none}
  .twk-seg button{appearance:none;position:relative;z-index:1;flex:1;border:0;
    background:transparent;color:inherit;font:inherit;font-weight:500;min-height:22px;
    border-radius:6px;cursor:default;padding:4px 6px;line-height:1.2;
    overflow-wrap:anywhere}

  .twk-toggle{position:relative;width:32px;height:18px;border:0;border-radius:999px;
    background:rgba(0,0,0,.15);transition:background .15s;cursor:default;padding:0}
  .twk-toggle[data-on="1"]{background:#34c759}
  .twk-toggle i{position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;
    background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.25);transition:transform .15s}
  .twk-toggle[data-on="1"] i{transform:translateX(14px)}

  .twk-num{display:flex;align-items:center;height:26px;padding:0 0 0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;background:rgba(255,255,255,.6)}
  .twk-num-lbl{font-weight:500;color:rgba(41,38,27,.6);cursor:ew-resize;
    user-select:none;padding-right:8px}
  .twk-num input{flex:1;min-width:0;height:100%;border:0;background:transparent;
    font:inherit;font-variant-numeric:tabular-nums;text-align:right;padding:0 8px 0 0;
    outline:none;color:inherit;-moz-appearance:textfield}
  .twk-num input::-webkit-inner-spin-button,.twk-num input::-webkit-outer-spin-button{
    -webkit-appearance:none;margin:0}
  .twk-num-unit{padding-right:8px;color:rgba(41,38,27,.45)}

  .twk-btn{appearance:none;height:26px;padding:0 12px;border:0;border-radius:7px;
    background:rgba(0,0,0,.78);color:#fff;font:inherit;font-weight:500;cursor:default}
  .twk-btn:hover{background:rgba(0,0,0,.88)}
  .twk-btn.secondary{background:rgba(0,0,0,.06);color:inherit}
  .twk-btn.secondary:hover{background:rgba(0,0,0,.1)}

  .twk-swatch{appearance:none;-webkit-appearance:none;width:56px;height:22px;
    border:.5px solid rgba(0,0,0,.1);border-radius:6px;padding:0;cursor:default;
    background:transparent;flex-shrink:0}
  .twk-swatch::-webkit-color-swatch-wrapper{padding:0}
  .twk-swatch::-webkit-color-swatch{border:0;border-radius:5.5px}
  .twk-swatch::-moz-color-swatch{border:0;border-radius:5.5px}

  .twk-chips{display:flex;gap:6px}
  .twk-chip{position:relative;appearance:none;flex:1;min-width:0;height:46px;
    padding:0;border:0;border-radius:6px;overflow:hidden;cursor:default;
    box-shadow:0 0 0 .5px rgba(0,0,0,.12),0 1px 2px rgba(0,0,0,.06);
    transition:transform .12s cubic-bezier(.3,.7,.4,1),box-shadow .12s}
  .twk-chip:hover{transform:translateY(-1px);
    box-shadow:0 0 0 .5px rgba(0,0,0,.18),0 4px 10px rgba(0,0,0,.12)}
  .twk-chip[data-on="1"]{box-shadow:0 0 0 1.5px rgba(0,0,0,.85),
    0 2px 6px rgba(0,0,0,.15)}
  .twk-chip>span{position:absolute;top:0;bottom:0;right:0;width:34%;
    display:flex;flex-direction:column;box-shadow:-1px 0 0 rgba(0,0,0,.1)}
  .twk-chip>span>i{flex:1;box-shadow:0 -1px 0 rgba(0,0,0,.1)}
  .twk-chip>span>i:first-child{box-shadow:none}
  .twk-chip svg{position:absolute;top:6px;left:6px;width:13px;height:13px;
    filter:drop-shadow(0 1px 1px rgba(0,0,0,.3))}
`;

// ── useTweaks ───────────────────────────────────────────────────────────────
// Single source of truth for tweak values. setTweak persists via the host
// (__edit_mode_set_keys → host rewrites the EDITMODE block on disk).
function useTweaks(defaults) {
  const [values, setValues] = React.useState(defaults);
  // Accepts either setTweak('key', value) or setTweak({ key: value, ... }) so a
  // useState-style call doesn't write a "[object Object]" key into the persisted
  // JSON block.
  const setTweak = React.useCallback((keyOrEdits, val) => {
    const edits = typeof keyOrEdits === 'object' && keyOrEdits !== null
      ? keyOrEdits : { [keyOrEdits]: val };
    setValues((prev) => ({ ...prev, ...edits }));
    window.parent.postMessage({ type: '__edit_mode_set_keys', edits }, '*');
    // Same-window signal so in-page listeners (deck-stage rail thumbnails)
    // can react — the parent message only reaches the host, not peers.
    window.dispatchEvent(new CustomEvent('tweakchange', { detail: edits }));
  }, []);
  return [values, setTweak];
}

// ── TweaksPanel ─────────────────────────────────────────────────────────────
// Floating shell. Registers the protocol listener BEFORE announcing
// availability — if the announce ran first, the host's activate could land
// before our handler exists and the toolbar toggle would silently no-op.
// The close button posts __edit_mode_dismissed so the host's toolbar toggle
// flips off in lockstep; the host echoes __deactivate_edit_mode back which
// is what actually hides the panel.
function TweaksPanel({ title = 'Tweaks', noDeckControls = false, children }) {
  const [open, setOpen] = React.useState(false);
  const dragRef = React.useRef(null);
  // Auto-inject a rail toggle when a <deck-stage> is on the page. The
  // toggle drives the deck's per-viewer _railVisible via window message;
  // state is mirrored from the same localStorage key the deck reads so
  // the control reflects reality across reloads. The mechanism is the
  // message — authors who want custom placement can post it directly
  // and pass noDeckControls to suppress this one.
  const hasDeckStage = React.useMemo(
    () => typeof document !== 'undefined' && !!document.querySelector('deck-stage'),
    [],
  );
  // Hide the toggle until the host has actually enabled the rail (the
  // __omelette_rail_enabled window message, posted only when the
  // omelette_deck_rail_enabled flag is on for this user). The initial read
  // covers TweaksPanel mounting after the message already arrived; the
  // listener covers the common case of mounting first.
  const [railEnabled, setRailEnabled] = React.useState(
    () => hasDeckStage && !!document.querySelector('deck-stage')?._railEnabled,
  );
  React.useEffect(() => {
    if (!hasDeckStage || railEnabled) return undefined;
    const onMsg = (e) => {
      if (e.data && e.data.type === '__omelette_rail_enabled') setRailEnabled(true);
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, [hasDeckStage, railEnabled]);
  const [railVisible, setRailVisible] = React.useState(() => {
    try { return localStorage.getItem('deck-stage.railVisible') !== '0'; } catch (e) { return true; }
  });
  const toggleRail = (on) => {
    setRailVisible(on);
    window.postMessage({ type: '__deck_rail_visible', on }, '*');
  };
  const offsetRef = React.useRef({ x: 16, y: 16 });
  const PAD = 16;

  const clampToViewport = React.useCallback(() => {
    const panel = dragRef.current;
    if (!panel) return;
    const w = panel.offsetWidth, h = panel.offsetHeight;
    const maxRight = Math.max(PAD, window.innerWidth - w - PAD);
    const maxBottom = Math.max(PAD, window.innerHeight - h - PAD);
    offsetRef.current = {
      x: Math.min(maxRight, Math.max(PAD, offsetRef.current.x)),
      y: Math.min(maxBottom, Math.max(PAD, offsetRef.current.y)),
    };
    panel.style.right = offsetRef.current.x + 'px';
    panel.style.bottom = offsetRef.current.y + 'px';
  }, []);

  React.useEffect(() => {
    if (!open) return;
    clampToViewport();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', clampToViewport);
      return () => window.removeEventListener('resize', clampToViewport);
    }
    const ro = new ResizeObserver(clampToViewport);
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, [open, clampToViewport]);

  React.useEffect(() => {
    const onMsg = (e) => {
      const t = e?.data?.type;
      if (t === '__activate_edit_mode') setOpen(true);
      else if (t === '__deactivate_edit_mode') setOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);

  const dismiss = () => {
    setOpen(false);
    window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*');
  };

  const onDragStart = (e) => {
    const panel = dragRef.current;
    if (!panel) return;
    const r = panel.getBoundingClientRect();
    const sx = e.clientX, sy = e.clientY;
    const startRight = window.innerWidth - r.right;
    const startBottom = window.innerHeight - r.bottom;
    const move = (ev) => {
      offsetRef.current = {
        x: startRight - (ev.clientX - sx),
        y: startBottom - (ev.clientY - sy),
      };
      clampToViewport();
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  if (!open) return null;
  return (
    <>
      <style>{__TWEAKS_STYLE}</style>
      <div ref={dragRef} className="twk-panel" data-noncommentable=""
           style={{ right: offsetRef.current.x, bottom: offsetRef.current.y }}>
        <div className="twk-hd" onMouseDown={onDragStart}>
          <b>{title}</b>
          <button className="twk-x" aria-label="Close tweaks"
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={dismiss}>✕</button>
        </div>
        <div className="twk-body">
          {children}
          {hasDeckStage && railEnabled && !noDeckControls && (
            <TweakSection label="Deck">
              <TweakToggle label="Thumbnail rail" value={railVisible} onChange={toggleRail} />
            </TweakSection>
          )}
        </div>
      </div>
    </>
  );
}

// ── Layout helpers ──────────────────────────────────────────────────────────

function TweakSection({ label, children }) {
  return (
    <>
      <div className="twk-sect">{label}</div>
      {children}
    </>
  );
}

function TweakRow({ label, value, children, inline = false }) {
  return (
    <div className={inline ? 'twk-row twk-row-h' : 'twk-row'}>
      <div className="twk-lbl">
        <span>{label}</span>
        {value != null && <span className="twk-val">{value}</span>}
      </div>
      {children}
    </div>
  );
}

// ── Controls ────────────────────────────────────────────────────────────────

function TweakSlider({ label, value, min = 0, max = 100, step = 1, unit = '', onChange }) {
  return (
    <TweakRow label={label} value={`${value}${unit}`}>
      <input type="range" className="twk-slider" min={min} max={max} step={step}
             value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </TweakRow>
  );
}

function TweakToggle({ label, value, onChange }) {
  return (
    <div className="twk-row twk-row-h">
      <div className="twk-lbl"><span>{label}</span></div>
      <button type="button" className="twk-toggle" data-on={value ? '1' : '0'}
              role="switch" aria-checked={!!value}
              onClick={() => onChange(!value)}><i /></button>
    </div>
  );
}

function TweakRadio({ label, value, options, onChange }) {
  const trackRef = React.useRef(null);
  const [dragging, setDragging] = React.useState(false);
  // The active value is read by pointer-move handlers attached for the lifetime
  // of a drag — ref it so a stale closure doesn't fire onChange for every move.
  const valueRef = React.useRef(value);
  valueRef.current = value;

  // Segments wrap mid-word once per-segment width runs out. The track is
  // ~248px (280 panel − 28 body pad − 4 seg pad), each button loses 12px
  // to its own padding, and 11.5px system-ui averages ~6.3px/char — so 2
  // options fit ~16 chars each, 3 fit ~10. Past that (or >3 options), fall
  // back to a dropdown rather than wrap.
  const labelLen = (o) => String(typeof o === 'object' ? o.label : o).length;
  const maxLen = options.reduce((m, o) => Math.max(m, labelLen(o)), 0);
  const fitsAsSegments = maxLen <= ({ 2: 16, 3: 10 }[options.length] ?? 0);
  if (!fitsAsSegments) {
    // <select> emits strings — map back to the original option value so the
    // fallback stays type-preserving (numbers, booleans) like the segment path.
    const resolve = (s) => {
      const m = options.find((o) => String(typeof o === 'object' ? o.value : o) === s);
      return m === undefined ? s : typeof m === 'object' ? m.value : m;
    };
    return <TweakSelect label={label} value={value} options={options}
                        onChange={(s) => onChange(resolve(s))} />;
  }
  const opts = options.map((o) => (typeof o === 'object' ? o : { value: o, label: o }));
  const idx = Math.max(0, opts.findIndex((o) => o.value === value));
  const n = opts.length;

  const segAt = (clientX) => {
    const r = trackRef.current.getBoundingClientRect();
    const inner = r.width - 4;
    const i = Math.floor(((clientX - r.left - 2) / inner) * n);
    return opts[Math.max(0, Math.min(n - 1, i))].value;
  };

  const onPointerDown = (e) => {
    setDragging(true);
    const v0 = segAt(e.clientX);
    if (v0 !== valueRef.current) onChange(v0);
    const move = (ev) => {
      if (!trackRef.current) return;
      const v = segAt(ev.clientX);
      if (v !== valueRef.current) onChange(v);
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  return (
    <TweakRow label={label}>
      <div ref={trackRef} role="radiogroup" onPointerDown={onPointerDown}
           className={dragging ? 'twk-seg dragging' : 'twk-seg'}>
        <div className="twk-seg-thumb"
             style={{ left: `calc(2px + ${idx} * (100% - 4px) / ${n})`,
                      width: `calc((100% - 4px) / ${n})` }} />
        {opts.map((o) => (
          <button key={o.value} type="button" role="radio" aria-checked={o.value === value}>
            {o.label}
          </button>
        ))}
      </div>
    </TweakRow>
  );
}

function TweakSelect({ label, value, options, onChange }) {
  return (
    <TweakRow label={label}>
      <select className="twk-field" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => {
          const v = typeof o === 'object' ? o.value : o;
          const l = typeof o === 'object' ? o.label : o;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
    </TweakRow>
  );
}

function TweakText({ label, value, placeholder, onChange }) {
  return (
    <TweakRow label={label}>
      <input className="twk-field" type="text" value={value} placeholder={placeholder}
             onChange={(e) => onChange(e.target.value)} />
    </TweakRow>
  );
}

function TweakNumber({ label, value, min, max, step = 1, unit = '', onChange }) {
  const clamp = (n) => {
    if (min != null && n < min) return min;
    if (max != null && n > max) return max;
    return n;
  };
  const startRef = React.useRef({ x: 0, val: 0 });
  const onScrubStart = (e) => {
    e.preventDefault();
    startRef.current = { x: e.clientX, val: value };
    const decimals = (String(step).split('.')[1] || '').length;
    const move = (ev) => {
      const dx = ev.clientX - startRef.current.x;
      const raw = startRef.current.val + dx * step;
      const snapped = Math.round(raw / step) * step;
      onChange(clamp(Number(snapped.toFixed(decimals))));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  return (
    <div className="twk-num">
      <span className="twk-num-lbl" onPointerDown={onScrubStart}>{label}</span>
      <input type="number" value={value} min={min} max={max} step={step}
             onChange={(e) => onChange(clamp(Number(e.target.value)))} />
      {unit && <span className="twk-num-unit">{unit}</span>}
    </div>
  );
}

// Relative-luminance contrast pick — checkmarks drawn over a swatch need to
// read on both #111 and #fafafa without per-option configuration. Hex input
// only (#rgb / #rrggbb); named or rgb()/hsl() colors fall through to "light".
function __twkIsLight(hex) {
  const h = String(hex).replace('#', '');
  const x = h.length === 3 ? h.replace(/./g, (c) => c + c) : h.padEnd(6, '0');
  const n = parseInt(x.slice(0, 6), 16);
  if (Number.isNaN(n)) return true;
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return r * 299 + g * 587 + b * 114 > 148000;
}

const __TwkCheck = ({ light }) => (
  <svg viewBox="0 0 14 14" aria-hidden="true">
    <path d="M3 7.2 5.8 10 11 4.2" fill="none" strokeWidth="2.2"
          strokeLinecap="round" strokeLinejoin="round"
          stroke={light ? 'rgba(0,0,0,.78)' : '#fff'} />
  </svg>
);

// TweakColor — curated color/palette picker. Each option is either a single
// hex string or an array of 1-5 hex strings; the card adapts — a lone color
// renders solid, a palette renders colors[0] as the hero (left ~2/3) with the
// rest stacked in a sharp column on the right. onChange emits the
// option in the shape it was passed (string stays string, array stays array).
// Without options it falls back to the native color input for back-compat.
function TweakColor({ label, value, options, onChange }) {
  if (!options || !options.length) {
    return (
      <div className="twk-row twk-row-h">
        <div className="twk-lbl"><span>{label}</span></div>
        <input type="color" className="twk-swatch" value={value}
               onChange={(e) => onChange(e.target.value)} />
      </div>
    );
  }
  // Native <input type=color> emits lowercase hex per the HTML spec, so
  // compare case-insensitively. String() guards JSON.stringify(undefined),
  // which returns the primitive undefined (no .toLowerCase).
  const key = (o) => String(JSON.stringify(o)).toLowerCase();
  const cur = key(value);
  return (
    <TweakRow label={label}>
      <div className="twk-chips" role="radiogroup">
        {options.map((o, i) => {
          const colors = Array.isArray(o) ? o : [o];
          const [hero, ...rest] = colors;
          const sup = rest.slice(0, 4);
          const on = key(o) === cur;
          return (
            <button key={i} type="button" className="twk-chip" role="radio"
                    aria-checked={on} data-on={on ? '1' : '0'}
                    aria-label={colors.join(', ')} title={colors.join(' · ')}
                    style={{ background: hero }}
                    onClick={() => onChange(o)}>
              {sup.length > 0 && (
                <span>
                  {sup.map((c, j) => <i key={j} style={{ background: c }} />)}
                </span>
              )}
              {on && <__TwkCheck light={__twkIsLight(hero)} />}
            </button>
          );
        })}
      </div>
    </TweakRow>
  );
}

function TweakButton({ label, onClick, secondary = false }) {
  return (
    <button type="button" className={secondary ? 'twk-btn secondary' : 'twk-btn'}
            onClick={onClick}>{label}</button>
  );
}

Object.assign(window, {
  useTweaks, TweaksPanel, TweakSection, TweakRow,
  TweakSlider, TweakToggle, TweakRadio, TweakSelect,
  TweakText, TweakNumber, TweakColor, TweakButton,
});

}

// ─── icons.jsx ───
{
// Lightweight stroke icon set for MediSense
// All icons share size/stroke API: <Icon size={20} stroke={1.6} color="currentColor" />

const Ico = ({ size = 22, stroke = 1.6, color = 'currentColor', children, style }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
    style={style}>{children}</svg>
);

const IconChat = (p) => <Ico {...p}><path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.7-5.2A8 8 0 1 1 21 12Z"/></Ico>;
const IconHeart = (p) => <Ico {...p}><path d="M12 21s-7-4.5-9.5-9A5.5 5.5 0 0 1 12 6a5.5 5.5 0 0 1 9.5 6c-2.5 4.5-9.5 9-9.5 9Z"/></Ico>;
const IconActivity = (p) => <Ico {...p}><path d="M3 12h4l2-7 4 14 2-7h6"/></Ico>;
const IconCalendar = (p) => <Ico {...p}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></Ico>;
const IconUser = (p) => <Ico {...p}><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></Ico>;
const IconBack = (p) => <Ico {...p}><path d="M15 18l-6-6 6-6"/></Ico>;
const IconMore = (p) => <Ico {...p}><circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/></Ico>;
const IconMic = (p) => <Ico {...p}><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></Ico>;
const IconSend = (p) => <Ico {...p}><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z"/></Ico>;
const IconLock = (p) => <Ico {...p}><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></Ico>;
const IconShield = (p) => <Ico {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></Ico>;
const IconBell = (p) => <Ico {...p}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></Ico>;
const IconChevron = (p) => <Ico {...p}><path d="M9 6l6 6-6 6"/></Ico>;
const IconCheck = (p) => <Ico {...p}><path d="M5 12l5 5L20 7"/></Ico>;
const IconAlert = (p) => <Ico {...p}><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0Z"/></Ico>;
const IconBluetooth = (p) => <Ico {...p}><path d="m7 7 10 10-5 5V2l5 5L7 17"/></Ico>;
const IconSparkles = (p) => <Ico {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></Ico>;
const IconSettings = (p) => <Ico {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></Ico>;
const IconGlobe = (p) => <Ico {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></Ico>;
const IconLogout = (p) => <Ico {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></Ico>;
const IconPill = (p) => <Ico {...p}><rect x="2" y="8" width="20" height="8" rx="4" transform="rotate(-25 12 12)"/><path d="m9.5 6.3 8.2 11.4" transform="rotate(-25 12 12)"/></Ico>;
const IconQR = (p) => <Ico {...p}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3M21 17v4h-4M14 21h3"/></Ico>;
const IconClose = (p) => <Ico {...p}><path d="M18 6 6 18M6 6l12 12"/></Ico>;
const IconEye = (p) => <Ico {...p}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></Ico>;
const IconLung = (p) => <Ico {...p}><path d="M6.1 22a3.5 3.5 0 0 1-3.5-3.5V14c0-3 2-5.5 4.5-7l1.4-.8a2 2 0 0 1 3 1.7V18a4 4 0 0 1-4 4H6.1ZM17.9 22a3.5 3.5 0 0 0 3.5-3.5V14c0-3-2-5.5-4.5-7l-1.4-.8a2 2 0 0 0-3 1.7V18a4 4 0 0 0 4 4h1.4Z"/><path d="M12 4v8"/></Ico>;
const IconWave = (p) => <Ico {...p}><path d="M2 12h2l2-7 3 14 3-10 3 7 3-4h4"/></Ico>;
const IconStethoscope = (p) => <Ico {...p}><path d="M6 3v8a4 4 0 0 0 8 0V3M4 3h4M12 3h4M10 15v3a4 4 0 0 0 8 0v-1"/><circle cx="18" cy="14" r="2"/></Ico>;
const IconHistory = (p) => <Ico {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2"/></Ico>;
const IconLanguage = (p) => <Ico {...p}><path d="M3 5h12M9 3v2c0 6-3 8-6 8M5 9c0 4 4 6 8 6M14 21l4-10 4 10M16 18h4"/></Ico>;
const IconTrash = (p) => <Ico {...p}><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14"/></Ico>;
const IconDoc = (p) => <Ico {...p}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></Ico>;
const IconLink = (p) => <Ico {...p}><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></Ico>;

Object.assign(window, {
  IconChat, IconHeart, IconActivity, IconCalendar, IconUser,
  IconBack, IconMore, IconMic, IconSend, IconLock, IconShield, IconBell,
  IconChevron, IconCheck, IconAlert, IconBluetooth, IconSparkles, IconSettings,
  IconGlobe, IconLogout, IconPill, IconQR, IconClose, IconEye, IconLung,
  IconWave, IconStethoscope, IconHistory, IconLanguage, IconTrash, IconDoc, IconLink,
});

}

// ─── dashboard-shell.jsx ───
{
// Dashboard shell — sidebar + main content area for Next.js-style web dashboards
// Used by Doctor / Secretary / Admin

const { IconChat: _IC1 } = window;

function DashSidebar({ role, active, onChange, user }) {
  // role: 'doctor' | 'secretary' | 'admin'
  const items = role === 'doctor' ? [
    { key: 'agenda', label: 'Agenda', icon: 'cal' },
    { key: 'patients', label: 'Patients', icon: 'users' },
    { key: 'dpa', label: 'Résumés DPA', icon: 'doc' },
  ] : role === 'secretary' ? [
    { key: 'agenda', label: 'Agenda', icon: 'cal' },
    { key: 'crm', label: 'Tâches CRM', icon: 'sync' },
    { key: 'feedback', label: 'Feedback ML', icon: 'check' },
  ] : [
    { key: 'audit', label: 'Logs RGPD', icon: 'shield' },
    { key: 'users', label: 'Utilisateurs', icon: 'users' },
    { key: 'rerank', label: 'Rerank Eval', icon: 'flask' },
    { key: 'system', label: 'Système', icon: 'cpu' },
  ];

  const Icon = ({ k, color }) => {
    const s = { width: 18, height: 18, stroke: color, strokeWidth: 1.7, fill: 'none', strokeLinecap: 'round', strokeLinejoin: 'round' };
    if (k === 'cal') return <svg viewBox="0 0 24 24" {...s}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>;
    if (k === 'users') return <svg viewBox="0 0 24 24" {...s}><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 6a3 3 0 010 6M21 20c0-2.5-1.5-4.5-4-5.5"/></svg>;
    if (k === 'doc') return <svg viewBox="0 0 24 24" {...s}><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z"/><path d="M14 3v6h6M9 13h6M9 17h4"/></svg>;
    if (k === 'sync') return <svg viewBox="0 0 24 24" {...s}><path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5M21 12a9 9 0 01-15 6.7L3 16M3 21v-5h5"/></svg>;
    if (k === 'check') return <svg viewBox="0 0 24 24" {...s}><path d="M5 12l5 5L20 7"/></svg>;
    if (k === 'shield') return <svg viewBox="0 0 24 24" {...s}><path d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z"/><path d="M9 12l2 2 4-4"/></svg>;
    if (k === 'flask') return <svg viewBox="0 0 24 24" {...s}><path d="M9 3h6M10 3v6L5 19a2 2 0 002 2h10a2 2 0 002-2L14 9V3"/><path d="M7 15h10"/></svg>;
    if (k === 'cpu') return <svg viewBox="0 0 24 24" {...s}><rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M3 9h3M3 15h3M18 9h3M18 15h3M9 3v3M15 3v3M9 18v3M15 18v3"/></svg>;
    return null;
  };

  return (
    <div style={{
      width: 220, flexShrink: 0,
      background: 'var(--s1)',
      borderRight: '1px solid var(--line)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* logo */}
      <div style={{ padding: '20px 18px 18px', borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 18 }}>
            {[8, 14, 18, 14, 8].map((h, i) => (
              <div key={i} style={{
                width: 2.5, height: h, borderRadius: 2,
                background: 'var(--ai-grad)',
                opacity: 0.7 + (i === 2 ? 0.3 : 0),
              }}/>
            ))}
          </div>
          <div style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 14, color: 'var(--t0)', letterSpacing: '-0.01em' }}>
            MediSense<span className="grad-text"> AI</span>
          </div>
        </div>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)', letterSpacing: '0.16em', textTransform: 'uppercase', marginTop: 4 }}>
          {role === 'doctor' ? 'console clinique' : role === 'secretary' ? 'console secrétariat' : 'console admin'}
        </div>
      </div>

      {/* nav */}
      <div style={{ flex: 1, padding: '14px 10px', overflowY: 'auto' }} className="scroll-hide">
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)', letterSpacing: '0.16em', textTransform: 'uppercase', padding: '6px 8px 8px' }}>
          Navigation
        </div>
        {items.map(it => {
          const isActive = active === it.key;
          return (
            <button key={it.key} onClick={() => onChange(it.key)} style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 10,
              padding: '9px 10px', marginBottom: 2,
              background: isActive ? 'var(--s2)' : 'transparent',
              border: 'none', borderLeft: `2px solid ${isActive ? '#8B5CF6' : 'transparent'}`,
              color: isActive ? 'var(--t0)' : 'var(--t2)',
              fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: isActive ? 500 : 400,
              cursor: 'pointer', textAlign: 'left', borderRadius: 6,
              transition: 'all .15s',
            }}>
              <Icon k={it.icon} color={isActive ? '#A78BFA' : '#64748B'}/>
              <span>{it.label}</span>
            </button>
          );
        })}
      </div>

      {/* user */}
      <div style={{ borderTop: '1px solid var(--line)', padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 99,
          background: 'var(--ai-grad)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--f-display)', fontSize: 13, fontWeight: 600, color: '#fff',
        }}>{user.initial}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: 'var(--f-body)', fontSize: 12, fontWeight: 500, color: 'var(--t0)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{role}</div>
        </div>
        <button title="Logout" style={{
          background: 'transparent', border: '1px solid var(--line)', color: 'var(--t3)',
          width: 26, height: 26, borderRadius: 6, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>
        </button>
      </div>
    </div>
  );
}

function DashTopBar({ title, subtitle, breadcrumb, actions }) {
  return (
    <div style={{
      padding: '20px 28px 18px',
      borderBottom: '1px solid var(--line)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16,
      background: 'rgba(15, 22, 35, 0.3)',
    }}>
      <div style={{ minWidth: 0 }}>
        {breadcrumb && (
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
            {breadcrumb}
          </div>
        )}
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
          color: 'var(--t0)', margin: 0, letterSpacing: '-0.01em',
        }}>{title}</h1>
        {subtitle && (
          <div style={{ color: 'var(--t2)', fontSize: 12.5, marginTop: 4 }}>{subtitle}</div>
        )}
      </div>
      {actions && <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>{actions}</div>}
    </div>
  );
}

// Generic dashboard layout
function DashboardLayout({ role, active, onChange, user, title, subtitle, breadcrumb, actions, children }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'var(--s0)',
      display: 'flex', overflow: 'hidden',
      fontFamily: 'var(--f-body)',
    }}>
      <DashSidebar role={role} active={active} onChange={onChange} user={user}/>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <DashTopBar title={title} subtitle={subtitle} breadcrumb={breadcrumb} actions={actions}/>
        <div style={{ flex: 1, overflowY: 'auto', padding: '22px 28px' }} className="scroll-hide">
          {children}
        </div>
      </div>
    </div>
  );
}

// Risk pill
function RiskPill({ level, prob }) {
  // level: 'safe' | 'warn' | 'danger' | null
  const colors = {
    safe:   { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',  bd: 'rgba(34,197,94,0.40)',  glyph: '✓' },
    warn:   { c: '#F97316', bg: 'rgba(249,115,22,0.10)', bd: 'rgba(249,115,22,0.40)', glyph: '⚠' },
    danger: { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',  bd: 'rgba(239,68,68,0.45)',  glyph: '●' },
  };
  if (!level) {
    return <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px',
      borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
      background: 'var(--s2)', border: '1px solid var(--line)', whiteSpace: 'nowrap',
    }}>○ —</span>;
  }
  const s = colors[level];
  return <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px',
    borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 10.5, fontWeight: 600,
    color: s.c, background: s.bg, border: `1px solid ${s.bd}`, whiteSpace: 'nowrap',
  }}>{s.glyph} {Math.round(prob * 100)}%</span>;
}

// Status dot pill (CRM, audit, etc)
function StatusPill({ tone, label, pulse }) {
  const tones = {
    pending:  { c: '#F59E0B', bg: 'rgba(245,158,11,0.10)',  bd: 'rgba(245,158,11,0.40)' },
    sent:     { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)' },
    failed:   { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)' },
    skipped:  { c: '#64748B', bg: 'rgba(100,116,139,0.10)', bd: 'rgba(100,116,139,0.30)' },
    cb:       { c: '#F43F5E', bg: 'rgba(244,63,94,0.12)',   bd: 'rgba(244,63,94,0.45)' },
    approved: { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)' },
    modified: { c: '#38BDF8', bg: 'rgba(56,189,248,0.10)',  bd: 'rgba(56,189,248,0.40)' },
    rejected: { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)' },
    info:     { c: '#94A3B8', bg: 'rgba(148,163,184,0.08)', bd: 'rgba(148,163,184,0.20)' },
    ai:       { c: '#A78BFA', bg: 'rgba(167,139,250,0.10)', bd: 'rgba(167,139,250,0.40)' },
  };
  const s = tones[tone] || tones.info;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 9px',
      borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
      color: s.c, background: s.bg, border: `1px solid ${s.bd}`,
      letterSpacing: '0.06em', textTransform: 'uppercase', whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: 99, background: s.c,
        animation: pulse ? 'empty-pulse 1.5s ease-in-out infinite' : 'none',
        boxShadow: pulse ? `0 0 6px ${s.c}` : 'none',
      }}/>
      {label}
    </span>
  );
}

// Confidence bar
function ConfidenceBar({ value, label = 'Confiance', width = 160 }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{label}</span>
      <div style={{ width, height: 5, background: 'var(--s3)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{
          width: `${value * 100}%`, height: '100%',
          background: 'var(--ai-grad)',
          borderRadius: 99, transition: 'width .8s ease-out',
        }}/>
      </div>
      <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t0)', fontWeight: 600 }}>{Math.round(value * 100)}%</span>
    </div>
  );
}

// Compact button
function DashButton({ kind = 'ghost', icon, children, onClick, danger, small }) {
  const padY = small ? 6 : 8;
  const padX = small ? 11 : 14;
  const fs = small ? 11.5 : 12.5;

  let style;
  if (kind === 'gradient') {
    style = {
      background: 'var(--ai-grad)',
      color: '#fff',
      border: 'none',
      boxShadow: '0 4px 16px rgba(99,102,241,0.30)',
    };
  } else if (kind === 'solid') {
    style = {
      background: danger ? 'rgba(239,68,68,0.12)' : 'var(--s2)',
      color: danger ? '#FCA5A5' : 'var(--t0)',
      border: `1px solid ${danger ? 'rgba(239,68,68,0.40)' : 'var(--line-strong)'}`,
    };
  } else {
    style = {
      background: 'transparent',
      color: 'var(--t1)',
      border: '1px solid var(--line)',
    };
  }
  return (
    <button onClick={onClick} style={{
      ...style,
      padding: `${padY}px ${padX}px`, borderRadius: 8,
      fontFamily: 'var(--f-body)', fontSize: fs, fontWeight: 500,
      cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 7,
      whiteSpace: 'nowrap', transition: 'transform .12s, box-shadow .12s',
    }}>
      {icon}
      {children}
    </button>
  );
}

Object.assign(window, { DashSidebar, DashTopBar, DashboardLayout, RiskPill, StatusPill, ConfidenceBar, DashButton });

}

// ─── onboarding.jsx ───
{
// Splash + Onboarding + Login flow
// Exports: SplashScreen, OnboardingScreen, LoginScreen

const {
  IconWave, IconHeart, IconChat, IconShield, IconChevron,
  IconLock, IconSparkles, IconBack
} = window;

// ─────────────────────────────────────────────
// Animated waveform — 5 bars (used in splash + login)
// ─────────────────────────────────────────────
function Waveform({ size = 64, color = 'url(#aigrad)', bars = 5, animate = true }) {
  const w = size; const h = size * 0.95;
  const barW = w / (bars * 2 - 1);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id="aigrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6366F1"/>
          <stop offset="100%" stopColor="#8B5CF6"/>
        </linearGradient>
      </defs>
      {Array.from({ length: bars }).map((_, i) => {
        const x = i * barW * 2;
        return (
          <rect key={i}
            x={x} y={h/2 - h*0.1} width={barW} height={h*0.2} rx={barW/2}
            fill={color}
            style={{
              transformOrigin: `${x + barW/2}px ${h/2}px`,
              animation: animate ? `wave-bar 1.1s ease-in-out ${i * 0.13}s infinite` : 'none',
            }}
          />
        );
      })}
    </svg>
  );
}

// ─────────────────────────────────────────────
// Particle field background
// ─────────────────────────────────────────────
function ParticleField({ count = 28 }) {
  const dots = React.useMemo(() => Array.from({ length: count }).map((_, i) => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: 1 + Math.random() * 2,
    dx: -20 + Math.random() * 40,
    dy: -80 - Math.random() * 60,
    dur: 8 + Math.random() * 10,
    delay: Math.random() * 8,
  })), [count]);
  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      {dots.map((d, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: `${d.x}%`, top: `${d.y}%`,
          width: d.size, height: d.size, borderRadius: '50%',
          background: 'rgba(167, 139, 250, 0.55)',
          boxShadow: '0 0 6px rgba(139,92,246,0.6)',
          '--dx': `${d.dx}px`, '--dy': `${d.dy}px`,
          animation: `drift ${d.dur}s ease-in ${d.delay}s infinite`,
        }} />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// SPLASH
// ─────────────────────────────────────────────
function SplashScreen({ onDone }) {
  React.useEffect(() => {
    const t = setTimeout(() => onDone && onDone(), 2600);
    return () => clearTimeout(t);
  }, [onDone]);
  return (
    <div className="screen" style={{ background: '#0A0D14', alignItems: 'center', justifyContent: 'center' }}>
      <ParticleField count={20} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 28, paddingBottom: 60 }}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {/* pulse rings */}
          {[0, 1].map(i => (
            <div key={i} style={{
              position: 'absolute', width: 160, height: 160, borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(139,92,246,0.25), transparent 70%)',
              animation: `pulse-ring 2.4s ease-out ${i * 1.2}s infinite`,
            }} />
          ))}
          <div style={{
            width: 96, height: 96, borderRadius: 28,
            background: 'rgba(28,35,51,0.5)',
            border: '1px solid rgba(139,92,246,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            backdropFilter: 'blur(12px)',
            boxShadow: '0 8px 40px rgba(99,102,241,0.25)',
          }}>
            <Waveform size={56} />
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 26,
            letterSpacing: '0.18em', color: '#F8FAFC', lineHeight: 1.2,
            display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: '0.32em',
          }}>MEDISENSE<span style={{
            background: 'var(--ai-grad)', WebkitBackgroundClip: 'text',
            backgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>AI</span></div>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 9.5, color: '#64748B',
            letterSpacing: '0.16em', textTransform: 'uppercase', marginTop: 14,
            whiteSpace: 'nowrap',
          }}>Powered by RAG · XGBoost · LSTM</div>
        </div>
      </div>
      <div style={{
        position: 'absolute', bottom: 80, left: 0, right: 0,
        textAlign: 'center', fontFamily: 'var(--f-mono)', fontSize: 9, color: '#334155',
        letterSpacing: '0.14em',
      }}>v1.0.0 · build 4f8c2a · marrakech</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// ONBOARDING
// ─────────────────────────────────────────────
const ONBOARD_STEPS = [
  {
    icon: 'heart',
    title: 'Vos signes vitaux,\nen continu',
    desc: 'Synchronisez votre bracelet connecté pour suivre fréquence cardiaque, SpO₂ et HRV en temps réel.',
    tag: 'IoT · BLE',
  },
  {
    icon: 'chat',
    title: 'Une IA médicale\nen FR · AR · Darija',
    desc: 'Posez vos questions en langage naturel. Réponses sourcées avec score de confiance, jamais inventées.',
    tag: 'RAG · 30k corpus',
  },
  {
    icon: 'shield',
    title: 'Vos données,\nau Maroc',
    desc: 'Conforme RGPD et Loi 09-08. Hébergement local, modèle local, droit à l\'effacement en 1 tap.',
    tag: 'Loi 09-08',
  },
];

function OnboardCard({ step, idx }) {
  const Icon = step.icon === 'heart' ? IconHeart : step.icon === 'chat' ? IconChat : IconShield;
  return (
    <div style={{
      flex: '0 0 100%', display: 'flex', flexDirection: 'column',
      alignItems: 'center', textAlign: 'center', padding: '0 32px',
    }}>
      <div style={{
        width: 130, height: 130, borderRadius: 40,
        background: 'linear-gradient(160deg, rgba(99,102,241,0.18), rgba(139,92,246,0.06))',
        border: '1px solid rgba(139,92,246,0.25)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 36, position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', inset: -20,
          background: 'radial-gradient(circle at 30% 30%, rgba(99,102,241,0.4), transparent 60%)',
          filter: 'blur(20px)',
        }} />
        <div style={{ position: 'relative', color: '#C4B5FD' }}>
          <Icon size={56} stroke={1.4} />
        </div>
      </div>
      <div style={{
        fontFamily: 'var(--f-mono)', fontSize: 10, letterSpacing: '0.18em',
        color: 'var(--t3)', textTransform: 'uppercase', marginBottom: 14,
      }}>0{idx + 1} / 03 · {step.tag}</div>
      <h2 style={{
        fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 30,
        lineHeight: 1.15, color: 'var(--t0)', margin: '0 0 18px',
        whiteSpace: 'pre-line', letterSpacing: '-0.02em',
      }}>{step.title}</h2>
      <p style={{
        fontFamily: 'var(--f-body)', fontSize: 15, lineHeight: 1.55,
        color: 'var(--t2)', margin: 0, maxWidth: 320,
      }}>{step.desc}</p>
    </div>
  );
}

function OnboardingScreen({ onDone }) {
  const [idx, setIdx] = React.useState(0);
  const next = () => idx < ONBOARD_STEPS.length - 1 ? setIdx(idx + 1) : onDone();
  return (
    <div className="screen" style={{ background: '#0A0D14' }}>
      <ParticleField count={18} />
      <div style={{ height: 54 }} />
      <div style={{
        display: 'flex', justifyContent: 'flex-end', padding: '8px 24px 0',
        position: 'relative', zIndex: 2,
      }}>
        <button onClick={onDone} style={{
          background: 'transparent', border: 'none', color: 'var(--t2)',
          fontFamily: 'var(--f-body)', fontSize: 14, cursor: 'pointer', padding: 8,
        }}>Passer</button>
      </div>
      <div style={{
        flex: 1, overflow: 'hidden', position: 'relative', zIndex: 2,
        display: 'flex', alignItems: 'center',
      }}>
        <div style={{
          display: 'flex', width: '100%',
          transform: `translateX(-${idx * 100}%)`,
          transition: 'transform .5s cubic-bezier(.65,.05,.36,1)',
        }}>
          {ONBOARD_STEPS.map((s, i) => <OnboardCard key={i} step={s} idx={i} />)}
        </div>
      </div>
      <div style={{ padding: '0 24px 56px', position: 'relative', zIndex: 2 }}>
        {/* progress pill */}
        <div style={{
          height: 4, background: 'rgba(148,163,184,0.10)', borderRadius: 99,
          overflow: 'hidden', marginBottom: 24,
        }}>
          <div style={{
            height: '100%', width: `${((idx + 1) / ONBOARD_STEPS.length) * 100}%`,
            background: 'var(--ai-grad)', borderRadius: 99,
            transition: 'width .4s ease',
          }} />
        </div>
        <button onClick={next} style={{
          width: '100%', height: 54, borderRadius: 16,
          background: 'var(--ai-grad)', border: 'none', color: '#fff',
          fontFamily: 'var(--f-body)', fontSize: 15, fontWeight: 600,
          cursor: 'pointer', letterSpacing: '0.01em',
          boxShadow: '0 8px 24px rgba(99,102,241,0.35)',
        }}>{idx < ONBOARD_STEPS.length - 1 ? 'Continuer' : 'Commencer'}</button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// LOGIN
// ─────────────────────────────────────────────
function LoginField({ label, type = 'text', value, onChange, error }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{ marginBottom: 22 }}>
      <label style={{
        display: 'block', fontFamily: 'var(--f-mono)', fontSize: 10,
        color: error ? 'var(--pulse)' : 'var(--t3)',
        letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8,
        transition: 'color .2s',
      }}>{label}</label>
      <div style={{
        position: 'relative',
        animation: error ? 'shake .2s ease' : 'none',
      }}>
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            width: '100%', height: 44,
            background: 'rgba(17, 24, 39, 0.6)',
            border: 'none', outline: 'none',
            borderBottom: '1px solid var(--s2)',
            color: 'var(--t0)',
            fontFamily: 'var(--f-body)', fontSize: 16,
            padding: '0 14px', borderRadius: '8px 8px 0 0',
            transition: 'background .2s',
          }}
        />
        {/* gradient bottom line on focus */}
        <div style={{
          position: 'absolute', left: 0, right: 0, bottom: 0, height: 2,
          background: error ? 'var(--pulse)' : 'var(--ai-grad)',
          borderRadius: 2,
          transform: focus || error ? 'scaleX(1)' : 'scaleX(0)',
          transformOrigin: 'left',
          transition: 'transform .25s',
          boxShadow: focus ? '0 0 12px rgba(139,92,246,0.4)' : 'none',
        }} />
      </div>
    </div>
  );
}

function LoginScreen({ onLogin, onBack }) {
  const [email, setEmail] = React.useState('ahmed.benali@medisense.ma');
  const [pw, setPw] = React.useState('');
  const [err, setErr] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  const submit = () => {
    if (!pw) {
      setErr(true);
      setTimeout(() => setErr(false), 600);
      return;
    }
    setLoading(true);
    setTimeout(() => onLogin(), 700);
  };
  return (
    <div className="screen" style={{ background: '#0A0D14' }}>
      <ParticleField count={12} />
      <div style={{ height: 60 }} />
      {onBack && (
        <button onClick={onBack} style={{
          position: 'absolute', top: 64, left: 16, zIndex: 5,
          background: 'transparent', border: 'none', color: 'var(--t2)',
          padding: 10, cursor: 'pointer', display: 'flex', alignItems: 'center',
        }}><IconBack size={22} /></button>
      )}
      <div style={{
        flex: 1, padding: '24px 32px', display: 'flex', flexDirection: 'column',
        position: 'relative', zIndex: 2,
      }}>
        <div style={{
          width: 52, height: 52, borderRadius: 16,
          background: 'rgba(28,35,51,0.6)',
          border: '1px solid rgba(139,92,246,0.25)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 28,
        }}>
          <Waveform size={32} />
        </div>
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 32,
          letterSpacing: '-0.02em', margin: '0 0 8px', color: 'var(--t0)',
        }}>Connexion</h1>
        <p style={{
          fontFamily: 'var(--f-body)', fontSize: 14, color: 'var(--t2)',
          margin: '0 0 36px', lineHeight: 1.5,
        }}>Bon retour. Vos données restent au Maroc.</p>

        <LoginField label="Email" value={email} onChange={setEmail} />
        <LoginField label="Mot de passe" type="password" value={pw} onChange={setPw} error={err} />

        <div style={{ textAlign: 'right', marginTop: -6, marginBottom: 28 }}>
          <a style={{
            fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)',
            textDecoration: 'none', cursor: 'pointer',
          }}>Mot de passe oublié ?</a>
        </div>

        <button onClick={submit} disabled={loading} style={{
          width: '100%', height: 54, borderRadius: 99,
          background: 'var(--ai-grad)', border: 'none', color: '#fff',
          fontFamily: 'var(--f-body)', fontSize: 15, fontWeight: 600,
          cursor: 'pointer',
          boxShadow: '0 8px 24px rgba(99,102,241,0.35)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          opacity: loading ? 0.8 : 1,
        }}>
          {loading ? (
            <span style={{ display: 'flex', gap: 4 }}>
              {[0,1,2].map(i => <span key={i} style={{
                width: 6, height: 6, borderRadius: '50%', background: '#fff',
                animation: `typing-dot 1s ease ${i*0.15}s infinite`,
              }} />)}
            </span>
          ) : 'Se connecter'}
        </button>

        <div style={{
          textAlign: 'center', marginTop: 24,
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)',
          letterSpacing: '0.12em', textTransform: 'uppercase',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          whiteSpace: 'nowrap',
        }}>
          <IconLock size={11} stroke={2} />
          chiffré · loi 09-08
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Waveform, ParticleField, SplashScreen, OnboardingScreen, LoginScreen });

}

// ─── chat.jsx ───
{
// Chat screen — soutenance centerpiece
// Streaming AI bubble, urgency banner, voice waveform, sources sheet

const {
  IconBack, IconMore, IconMic, IconSend, IconAlert, IconSparkles,
  IconClose, IconDoc, IconLink, IconCheck,
} = window;

// Mock conversation
const CHAT_INIT = [
  {
    id: 'ai1',
    role: 'ai', lang: 'FR', confidence: 0.91,
    sources: [
      { title: 'Dyspnée — symptômes & causes', src: 'sante.gov.ma', date: '2024' },
      { title: 'Guide IDM — Société Marocaine de Cardiologie', src: 'smc.ma', date: '2023' },
      { title: 'Référentiel SAMU urgences cardiaques', src: 'samu.ma', date: '2024' },
    ],
    text: "Bonjour Ahmed. Vous décrivez une douleur thoracique avec essoufflement depuis 30 minutes — c'est un signe à ne pas négliger. Avez-vous déjà eu ce type de douleur, ou des antécédents cardiaques ?",
    urgent: true,
  },
];

// Streaming text used for the demo
const STREAM_TEXT = "Compris. La douleur en barre qui irradie dans le bras gauche, associée à un essoufflement, peut évoquer un syndrome coronarien aigu. Étant donné votre profil (HTA traitée, 58 ans), j'ai contacté le SAMU. En attendant : asseyez-vous, desserrez vos vêtements, et croquez l'aspirine 300mg que je vous indique ci-dessous.";

function MetaPill({ children, color = 'rgba(28,35,51,0.85)', mono = true, onClick, glow }) {
  return (
    <span onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '4px 9px', borderRadius: 99,
      background: color, color: 'var(--t1)',
      fontFamily: mono ? 'var(--f-mono)' : 'var(--f-body)',
      fontSize: 10, fontWeight: 500, letterSpacing: '0.04em',
      border: '1px solid var(--line)',
      cursor: onClick ? 'pointer' : 'default',
      boxShadow: glow ? '0 0 12px rgba(139,92,246,0.25)' : 'none',
      whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        width: 36, height: 4, borderRadius: 99,
        background: 'rgba(148,163,184,0.18)', overflow: 'hidden', display: 'inline-block',
      }}>
        <span style={{
          display: 'block', height: '100%', width: `${pct}%`,
          background: 'var(--ai-grad)', borderRadius: 99,
        }} />
      </span>
      <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t1)' }}>{pct}%</span>
    </span>
  );
}

function UrgencyBanner({ onCall }) {
  return (
    <div style={{
      margin: '8px 16px 0',
      borderRadius: 14, overflow: 'hidden',
      background: 'linear-gradient(95deg, #F43F5E 0%, #DC2626 100%)',
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 14px',
      boxShadow: '0 8px 28px rgba(244,63,94,0.35)',
      animation: 'slide-down .4s cubic-bezier(.2,.8,.2,1)',
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 10,
        background: 'rgba(255,255,255,0.18)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'scale-pulse 1.5s ease-in-out infinite',
      }}>
        <IconAlert size={20} stroke={2} color="#fff" />
      </div>
      <div style={{ flex: 1, color: '#fff' }}>
        <div style={{ fontFamily: 'var(--f-body)', fontWeight: 600, fontSize: 13 }}>
          Urgence détectée — appelez maintenant
        </div>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, opacity: 0.85,
          letterSpacing: '0.06em', marginTop: 2,
        }}>141 · SAMU MAROC</div>
      </div>
      <button onClick={onCall} style={{
        background: '#fff', color: '#DC2626', border: 'none',
        padding: '7px 14px', borderRadius: 99,
        fontFamily: 'var(--f-body)', fontSize: 12, fontWeight: 700,
        cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
      }}>Appeler 141</button>
    </div>
  );
}

function AIBubble({ msg, streaming }) {
  return (
    <div style={{ animation: 'bubble-in .25s cubic-bezier(.34,1.36,.64,1)' }}>
      <div style={{
        position: 'relative',
        background: 'var(--s1)',
        borderRadius: '4px 16px 16px 16px',
        padding: '12px 14px',
        marginRight: 56, marginLeft: 16,
        overflow: 'hidden',
      }}>
        {/* gradient left border */}
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
          background: 'var(--ai-grad)',
          overflow: 'hidden',
        }}>
          {streaming && (
            <div style={{
              position: 'absolute', left: 0, right: 0, height: '40%',
              background: 'linear-gradient(180deg, transparent, #fff, transparent)',
              animation: 'border-travel 1.4s ease-in-out infinite',
            }} />
          )}
        </div>
        <div style={{
          fontFamily: 'var(--f-body)', fontSize: 14, lineHeight: 1.55,
          color: 'var(--t0)',
        }}>
          {msg.text}
          {streaming && (
            <span style={{
              display: 'inline-block', width: 8, height: 16,
              background: 'var(--ai-to)',
              marginLeft: 2, verticalAlign: '-2px',
              animation: 'streaming-cursor 1s steps(1) infinite',
            }} />
          )}
        </div>
      </div>
      {/* meta row */}
      {!streaming && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
          marginLeft: 20, marginTop: 8, marginRight: 16,
        }}>
          <MetaPill>{msg.lang}</MetaPill>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '4px 9px', borderRadius: 99,
            background: 'rgba(28,35,51,0.85)',
            border: '1px solid var(--line)',
          }}><ConfidenceBar value={msg.confidence}/></span>
          {msg.sources && (
            <MetaPill onClick={msg.onSourcesClick} glow>
              <IconLink size={10} stroke={2}/> rag · {msg.sources.length} sources
            </MetaPill>
          )}
        </div>
      )}
    </div>
  );
}

function UserBubble({ text }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0 16px',
      animation: 'bubble-in .2s cubic-bezier(.34,1.36,.64,1)' }}>
      <div style={{
        maxWidth: '78%',
        background: 'var(--ai-grad)',
        borderRadius: '20px 4px 20px 20px',
        padding: '10px 14px',
        color: '#fff',
        fontFamily: 'var(--f-body)', fontSize: 14, lineHeight: 1.5,
        boxShadow: '0 6px 20px rgba(99,102,241,0.3)',
      }}>{text}</div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div style={{
      background: 'var(--s1)',
      borderRadius: '4px 16px 16px 16px',
      padding: '14px 16px',
      marginRight: 200, marginLeft: 16,
      display: 'flex', alignItems: 'center', gap: 5,
      borderLeft: '3px solid transparent',
      borderImage: 'linear-gradient(180deg, #6366F1, #8B5CF6) 1',
      width: 'fit-content',
    }}>
      {[0,1,2].map(i => <span key={i} style={{
        width: 5, height: 5, borderRadius: '50%',
        background: 'var(--ai-to)',
        animation: `typing-dot 1.2s ease ${i*0.15}s infinite`,
      }}/>)}
    </div>
  );
}

// Voice recording bars (animated, pseudo-amplitude)
function VoiceBars() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 22 }}>
      {[0,1,2,3,4].map(i => (
        <div key={i} style={{
          width: 3, borderRadius: 2,
          background: 'var(--ai-grad)',
          height: '100%',
          transformOrigin: 'center',
          animation: `wave-bar 0.${5+i}s ease-in-out ${i*0.07}s infinite`,
        }}/>
      ))}
    </div>
  );
}

// Suggestion chip with gradient border
function ChipSuggest({ label, onClick }) {
  return (
    <button onClick={onClick} className="grad-border" style={{
      padding: '9px 14px', borderRadius: 99,
      background: 'rgba(17,24,39,0.7)',
      border: 'none', color: 'var(--t0)',
      fontFamily: 'var(--f-body)', fontSize: 12.5, fontWeight: 500,
      cursor: 'pointer', whiteSpace: 'nowrap',
    }}>{label}</button>
  );
}

// Empty state — first open
function ChatEmpty({ onSuggest }) {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '0 24px', textAlign: 'center',
    }}>
      <div style={{
        width: 96, height: 96, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(139,92,246,0.4), rgba(99,102,241,0.1) 70%, transparent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 20, animation: 'empty-pulse 2.4s ease-in-out infinite',
      }}>
        <div style={{ color: '#C4B5FD' }}><IconSparkles size={32} stroke={1.5}/></div>
      </div>
      <h2 style={{
        fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 26,
        margin: '0 0 8px', color: 'var(--t0)', letterSpacing: '-0.01em',
      }}>Bonjour Ahmed <span style={{ display: 'inline-block', animation: 'wave-bar 2s ease-in-out infinite' }}>👋</span></h2>
      <p style={{
        fontFamily: 'var(--f-body)', fontSize: 14, color: 'var(--t2)',
        margin: '0 0 28px', lineHeight: 1.5, maxWidth: 280,
      }}>Décrivez vos symptômes ou posez une question médicale. Je réponds en FR, AR ou darija.</p>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
        <ChipSuggest label="Mes symptômes" onClick={() => onSuggest('Je sens une douleur dans la poitrine depuis 30 minutes, et j\'ai du mal à respirer.')}/>
        <ChipSuggest label="Mon traitement" onClick={() => onSuggest('Quels effets secondaires pour le Coversyl 5mg ?')}/>
        <ChipSuggest label="Urgence" onClick={() => onSuggest('Mon père a une douleur thoracique aiguë, que faire ?')}/>
      </div>
    </div>
  );
}

// Sources bottom sheet
function SourcesSheet({ sources, onClose }) {
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 50,
      background: 'rgba(0,0,0,0.55)',
      animation: 'fadeIn .2s', display: 'flex', alignItems: 'flex-end',
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', background: 'var(--s1)',
        borderRadius: '20px 20px 0 0',
        padding: '20px 20px 32px',
        animation: 'slide-up .3s cubic-bezier(.2,.8,.2,1)',
        borderTop: '1px solid var(--line-strong)',
      }}>
        <div style={{
          width: 40, height: 4, borderRadius: 99, background: 'var(--s3)',
          margin: '0 auto 18px',
        }}/>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div style={{ color: '#A5B4FC' }}><IconDoc size={18} stroke={1.6}/></div>
          <h3 style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 17,
            color: 'var(--t0)', margin: 0,
          }}>Sources citées · RAG</h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {sources.map((s, i) => (
            <div key={i} style={{
              padding: '12px 14px', borderRadius: 12,
              background: 'var(--s2)', border: '1px solid var(--line)',
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: 'rgba(99,102,241,0.18)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--f-mono)', fontSize: 11, fontWeight: 700,
                color: '#A5B4FC',
              }}>0{i+1}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: 500,
                  color: 'var(--t0)', overflow: 'hidden', textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>{s.title}</div>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
                  marginTop: 3, letterSpacing: '0.02em',
                }}>{s.src} · {s.date}</div>
              </div>
              <IconLink size={14} color="var(--t3)" stroke={1.7}/>
            </div>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes fadeIn { from{opacity:0} to{opacity:1} }
        @keyframes slide-up { from{transform:translateY(100%)} to{transform:translateY(0)} }
      `}</style>
    </div>
  );
}

function ChatScreen({ initialUrgent = true, initialEmpty = false }) {
  const [empty, setEmpty] = React.useState(initialEmpty);
  const [messages, setMessages] = React.useState(initialEmpty ? [] : CHAT_INIT);
  const [urgent, setUrgent] = React.useState(initialUrgent);
  const [input, setInput] = React.useState('');
  const [recording, setRecording] = React.useState(false);
  const [showSources, setShowSources] = React.useState(null);
  const [streamingMsg, setStreamingMsg] = React.useState(null);
  const [typing, setTyping] = React.useState(false);
  const scrollRef = React.useRef();

  const scrollDown = () => {
    requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    });
  };

  React.useEffect(scrollDown, [messages, streamingMsg, typing]);

  const send = (text) => {
    if (!text.trim()) return;
    setEmpty(false);
    const userMsg = { id: 'u' + Date.now(), role: 'user', text };
    setMessages(m => [...m, userMsg]);
    setInput('');

    // simulate AI response
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      const targetText = STREAM_TEXT;
      let i = 0;
      setStreamingMsg({ text: '', role: 'ai' });
      const tick = () => {
        i += Math.max(1, Math.floor(Math.random() * 4));
        if (i >= targetText.length) {
          setStreamingMsg(null);
          setMessages(m => [...m, {
            id: 'a' + Date.now(), role: 'ai',
            text: targetText, lang: 'FR', confidence: 0.87,
            sources: [
              { title: 'Aspirine — protocole urgence cardiaque', src: 'medicament.ma', date: '2025' },
              { title: 'Syndrome coronarien aigu — guide SMC', src: 'smc.ma', date: '2024' },
            ],
          }]);
          if (text.toLowerCase().includes('thoracique') || text.toLowerCase().includes('poitrine')) setUrgent(true);
          return;
        }
        setStreamingMsg({ text: targetText.slice(0, i), role: 'ai' });
        scrollDown();
        setTimeout(tick, 26);
      };
      tick();
    }, 700);
  };

  const sourcesForCurrent = showSources;

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', background: 'var(--s0)', overflow: 'hidden' }}>
      {/* header */}
      <div style={{
        paddingTop: 54, paddingBottom: 12, paddingLeft: 8, paddingRight: 12,
        display: 'flex', alignItems: 'center', gap: 4,
        background: 'rgba(10,13,20,0.85)', backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--line)', zIndex: 5,
      }}>
        <button style={{
          width: 40, height: 40, background: 'transparent', border: 'none',
          color: 'var(--t1)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><IconBack size={22}/></button>
        <div style={{ flex: 1 }}>
          <div style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 16,
            color: 'var(--t0)', letterSpacing: '-0.01em',
          }}>Assistant IA</div>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
            display: 'flex', alignItems: 'center', gap: 5, marginTop: 1,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', background: 'var(--safe)',
              boxShadow: '0 0 6px rgba(34,197,94,0.6)',
            }}/>
            en ligne · mistral-7B
          </div>
        </div>
        <button style={{
          width: 40, height: 40, background: 'transparent', border: 'none',
          color: 'var(--t1)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><IconMore size={20}/></button>
      </div>

      {urgent && !empty && <UrgencyBanner onCall={() => setUrgent(false)} />}

      <div ref={scrollRef} className="scroll-hide" style={{
        flex: 1, overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: 14,
        padding: '14px 0 8px',
      }}>
        {empty ? (
          <ChatEmpty onSuggest={(t) => send(t)} />
        ) : (
          <>
            {messages.map(m => m.role === 'ai' ? (
              <AIBubble key={m.id} msg={{ ...m, onSourcesClick: () => setShowSources(m.sources) }} />
            ) : (
              <UserBubble key={m.id} text={m.text} />
            ))}
            {typing && <TypingBubble/>}
            {streamingMsg && <AIBubble msg={{ ...streamingMsg, lang: 'FR', confidence: 0 }} streaming />}
          </>
        )}
        <div style={{ height: 4 }}/>
      </div>

      {/* input */}
      <div style={{
        padding: '10px 12px 92px',
        borderTop: '1px solid var(--line)',
        background: 'rgba(10,13,20,0.92)', backdropFilter: 'blur(12px)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--s1)', borderRadius: 24,
          border: '1px solid var(--line)',
          padding: 4, paddingLeft: 14,
        }}>
          {recording ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0' }}>
              <VoiceBars />
              <span style={{
                fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t2)',
                letterSpacing: '0.04em',
              }}>écoute · 00:0{Math.floor(Date.now()/1000)%10}</span>
            </div>
          ) : (
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send(input)}
              placeholder="Décrivez vos symptômes…"
              style={{
                flex: 1, height: 40, background: 'transparent',
                border: 'none', outline: 'none', color: 'var(--t0)',
                fontFamily: 'var(--f-body)', fontSize: 14,
              }}
            />
          )}
          <button onClick={() => setRecording(r => !r)} style={{
            width: 40, height: 40, borderRadius: 99,
            border: 'none', cursor: 'pointer',
            background: recording ? 'var(--ai-grad)' : 'transparent',
            color: recording ? '#fff' : 'var(--t2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: recording ? '0 0 16px rgba(139,92,246,0.5)' : 'none',
          }}><IconMic size={18}/></button>
          <button onClick={() => send(input)} disabled={!input.trim() && !recording} style={{
            width: 40, height: 40, borderRadius: 99,
            border: 'none', cursor: 'pointer',
            background: (input.trim() || recording) ? 'var(--ai-grad)' : 'rgba(28,35,51,0.6)',
            color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: (input.trim() || recording) ? 1 : 0.5,
            transition: 'all .2s',
          }}><IconSend size={16}/></button>
        </div>
      </div>

      {showSources && <SourcesSheet sources={showSources} onClose={() => setShowSources(null)}/>}
    </div>
  );
}

Object.assign(window, { ChatScreen });

}

// ─── vitals.jsx ───
{
// Vitals / IoT dashboard

const { IconHeart, IconLung, IconWave, IconBluetooth, IconQR, IconSparkles, IconMore } = window;

const VITALS = [
  { key: 'hr', label: 'BPM', name: 'Fréquence cardiaque', value: 72, unit: '', color: '#F43F5E', icon: 'heart', trend: 'Normal · stable', trendDir: '↗' },
  { key: 'spo2', label: 'SpO₂', name: 'Saturation O₂', value: 98, unit: '%', color: '#38BDF8', icon: 'lung', trend: 'Excellent', trendDir: '✓' },
  { key: 'hrv', label: 'HRV', name: 'Variabilité', value: 42, unit: 'ms', color: '#A78BFA', icon: 'wave', trend: 'Bas · repos requis', trendDir: '↘' },
];

function CountUp({ to, dur = 1000 }) {
  const [n, setN] = React.useState(0);
  React.useEffect(() => {
    let raf, start; const from = 0;
    const tick = (t) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(from + (to - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, dur]);
  return n;
}

function VitalCard({ v, active, onClick }) {
  const Icon = v.icon === 'heart' ? IconHeart : v.icon === 'lung' ? IconLung : IconWave;
  const display = v.key === 'spo2' ? <><CountUp to={v.value}/>{v.unit}</> : <><CountUp to={v.value}/>{v.unit && <span style={{fontSize:'0.6em',marginLeft:2,color:'var(--t2)'}}>{v.unit}</span>}</>;
  return (
    <div onClick={onClick} style={{
      flex: '0 0 auto', width: 168, padding: 16,
      background: 'var(--s1)', borderRadius: 18,
      border: active ? `1px solid ${v.color}55` : '1px solid var(--line)',
      cursor: 'pointer', position: 'relative', overflow: 'hidden',
      boxShadow: active ? `0 0 0 1px ${v.color}40, 0 12px 32px ${v.color}22` : 'none',
      transition: 'all .25s',
    }}>
      <div style={{
        position: 'absolute', top: -12, right: -12, width: 80, height: 80,
        borderRadius: '50%', background: `radial-gradient(circle, ${v.color}33, transparent 70%)`, filter: 'blur(8px)',
      }}/>
      <div style={{
        width: 32, height: 32, borderRadius: 10,
        background: `${v.color}22`, color: v.color,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 16, position: 'relative',
      }}><Icon size={18} stroke={1.8}/></div>
      <div style={{
        fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 40,
        lineHeight: 1, color: v.color, letterSpacing: '-0.02em',
        textShadow: `0 0 20px ${v.color}55`,
      }}>{display}</div>
      <div style={{
        fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
        letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 6,
      }}>{v.label}</div>
      <div style={{
        fontFamily: 'var(--f-body)', fontSize: 11, color: 'var(--t1)', marginTop: 10,
        display: 'flex', alignItems: 'center', gap: 4,
      }}><span style={{ color: v.color }}>{v.trendDir}</span> {v.trend}</div>
    </div>
  );
}

function VitalsChart({ color }) {
  // generate a dummy waveform path
  const w = 320, h = 140;
  const pts = React.useMemo(() => {
    const arr = []; const n = 48;
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * w;
      const baseline = h * 0.55;
      const y = baseline - (Math.sin(i * 0.55) * 22) - (Math.random() * 18 - 9);
      arr.push([x, y]);
    }
    return arr;
  }, [color]);
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  const areaPath = path + ` L ${w} ${h} L 0 ${h} Z`;
  const id = 'g_' + color.replace('#', '');
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.4"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
        <linearGradient id={id + 'l'} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={color} stopOpacity="0.9"/>
          <stop offset="100%" stopColor={color} stopOpacity="0.5"/>
        </linearGradient>
      </defs>
      {/* faint grid dashes */}
      {[0.25, 0.5, 0.75].map((p, i) => (
        <line key={i} x1="0" x2={w} y1={h * p} y2={h * p}
          stroke="rgba(148,163,184,0.08)" strokeDasharray="3 6" />
      ))}
      <path d={areaPath} fill={`url(#${id})`}/>
      <path d={path} fill="none" stroke={`url(#${id + 'l'})`} strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  );
}

function VitalsScreen() {
  const [active, setActive] = React.useState('hr');
  const [range, setRange] = React.useState('24h');
  const cur = VITALS.find(v => v.key === active);
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* header */}
      <div style={{ paddingTop: 60, padding: '60px 20px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
              letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
              whiteSpace: 'nowrap',
            }}>iot · sync il y a 12s</div>
            <h1 style={{
              fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 28,
              margin: 0, letterSpacing: '-0.02em', color: 'var(--t0)',
            }}>Signes vitaux</h1>
          </div>
          <button style={{
            width: 38, height: 38, borderRadius: 12,
            background: 'var(--s1)', border: '1px solid var(--line)',
            color: 'var(--t1)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}><IconMore size={18}/></button>
        </div>
      </div>

      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto' }}>
        {/* metric cards horizontal scroll */}
        <div className="scroll-hide" style={{
          display: 'flex', gap: 12, overflowX: 'auto', padding: '14px 20px',
        }}>
          {VITALS.map(v => <VitalCard key={v.key} v={v} active={v.key === active} onClick={() => setActive(v.key)}/>)}
        </div>

        {/* chart card */}
        <div style={{ padding: '8px 20px' }}>
          <div style={{
            background: 'var(--s1)', borderRadius: 20,
            border: '1px solid var(--line)', padding: 18,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <div>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                }}>{cur.name}</div>
                <div style={{
                  fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
                  color: cur.color, marginTop: 4,
                }}>{cur.value}{cur.unit} <span style={{
                  fontSize: 11, color: 'var(--t2)', fontFamily: 'var(--f-body)', fontWeight: 400,
                  marginLeft: 4,
                }}>moy. {Math.round(cur.value * 0.94)}{cur.unit}</span></div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                {['1h','24h','7j'].map(r => (
                  <button key={r} onClick={() => setRange(r)} style={{
                    padding: '6px 11px', borderRadius: 99,
                    background: range === r ? 'var(--ai-grad)' : 'rgba(28,35,51,0.6)',
                    border: range === r ? 'none' : '1px solid var(--line)',
                    color: range === r ? '#fff' : 'var(--t1)',
                    fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                    cursor: 'pointer', letterSpacing: '0.04em',
                  }}>{r}</button>
                ))}
              </div>
            </div>
            <div style={{ marginLeft: -8, marginRight: -8, marginTop: 14 }}>
              <VitalsChart color={cur.color}/>
            </div>
            {/* x-axis labels */}
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)',
              marginTop: 6, padding: '0 4px', letterSpacing: '0.04em',
            }}>
              <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>maint.</span>
            </div>
          </div>
        </div>

        {/* AI insight */}
        <div style={{ padding: '14px 20px 0' }}>
          <div style={{
            background: 'var(--s1)', borderRadius: 16,
            border: '1px solid var(--line)', padding: 14,
            display: 'flex', gap: 12,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 12,
              background: 'rgba(139,92,246,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#A78BFA', flexShrink: 0,
            }}><IconSparkles size={18} stroke={1.7}/></div>
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9.5, color: '#A5B4FC',
                letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
              }}>insight ia · xgboost</div>
              <div style={{
                fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t0)', lineHeight: 1.5,
              }}>Votre HRV diurne est en baisse de 18% sur 7 jours. Compatible avec un déficit de sommeil — visez 7h cette nuit.</div>
            </div>
          </div>
        </div>

        {/* device status */}
        <div style={{ padding: '14px 20px 110px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '12px 14px', borderRadius: 14,
            background: 'rgba(28,35,51,0.5)', border: '1px solid var(--line)',
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 10,
              background: 'rgba(56,189,248,0.15)', color: 'var(--oxy)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}><IconBluetooth size={16}/></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>Mi Band 8 Pro</div>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
                letterSpacing: '0.06em', marginTop: 2,
              }}>connecté · batterie 84% · 4f8c…2a91</div>
            </div>
            <div style={{
              width: 8, height: 8, borderRadius: '50%', background: 'var(--safe)',
              boxShadow: '0 0 6px rgba(34,197,94,0.6)',
            }}/>
          </div>
        </div>
      </div>
    </div>
  );
}

// "No device" state — used in tweaks
function NoDeviceScreen() {
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 32px', textAlign: 'center' }}>
      <div style={{ position: 'relative', width: 140, height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24 }}>
        {[0,1,2].map(i => (
          <div key={i} style={{
            position: 'absolute', width: 60, height: 60, borderRadius: '50%',
            border: '1px solid rgba(56,189,248,0.4)',
            animation: `pulse-ring 2.4s ease-out ${i*0.8}s infinite`,
          }}/>
        ))}
        <div style={{
          width: 64, height: 64, borderRadius: 18,
          background: 'rgba(56,189,248,0.12)', color: 'var(--oxy)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><IconBluetooth size={28} stroke={1.5}/></div>
      </div>
      <h2 style={{
        fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 24,
        margin: '0 0 8px', color: 'var(--t0)',
      }}>Connectez votre bracelet</h2>
      <p style={{
        fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t2)',
        margin: '0 0 28px', maxWidth: 280, lineHeight: 1.5,
      }}>Scannez le QR sur votre bracelet pour synchroniser fréquence cardiaque, SpO₂ et HRV.</p>
      <div style={{
        width: 120, height: 120, background: 'var(--s1)', borderRadius: 16,
        border: '1px solid var(--line)', padding: 16,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--t1)',
      }}><IconQR size={84} stroke={1.4}/></div>
    </div>
  );
}

Object.assign(window, { VitalsScreen, NoDeviceScreen });

}

// ─── appointments.jsx ───
{
// Appointments screen — risk-coded list

const { IconCalendar, IconChevron, IconMore } = window;

const RISK = {
  high: { color: '#EF4444', label: 'Risque élevé', dot: '#F43F5E' },
  med: { color: '#F97316', label: 'Risque modéré', dot: '#F97316' },
  low: { color: '#22C55E', label: 'Risque faible', dot: '#22C55E' },
};

const APPOINTMENTS = [
  { time: '09:30', name: 'Ahmed Benali', age: 58, doc: 'Dr. Merrouni · Cardiologie', risk: 'high', score: 67, reason: 'Suivi post-IDM · récidive douleur thoracique' },
  { time: '10:15', name: 'Fatima Zahra El Idrissi', age: 42, doc: 'Dr. Merrouni · Cardiologie', risk: 'med', score: 41, reason: 'HTA · ajustement Coversyl 5mg' },
  { time: '11:00', name: 'Youssef Tazi', age: 31, doc: 'Dr. Bennani · Médecine gén.', risk: 'low', score: 12, reason: 'Bilan annuel' },
  { time: '11:45', name: 'Khadija Amrani', age: 67, doc: 'Dr. Merrouni · Cardiologie', risk: 'high', score: 73, reason: 'Insuffisance cardiaque · dyspnée stade III' },
  { time: '14:00', name: 'Omar Chraibi', age: 52, doc: 'Dr. Bennani · Médecine gén.', risk: 'med', score: 38, reason: 'Diabète T2 · HbA1c 8.1%' },
  { time: '14:45', name: 'Salma Ouazzani', age: 28, doc: 'Dr. Bennani · Médecine gén.', risk: 'low', score: 8, reason: 'Renouvellement ordonnance' },
];

function ApptCard({ a, idx }) {
  const r = RISK[a.risk];
  return (
    <div style={{
      background: 'var(--s1)', borderRadius: 16,
      border: '1px solid var(--line)', padding: '14px 16px',
      display: 'flex', alignItems: 'flex-start', gap: 14,
      animation: `bubble-in .35s cubic-bezier(.34,1.36,.64,1) ${idx * 0.04}s both`,
    }}>
      {/* glowing dot */}
      <div style={{ paddingTop: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: r.dot,
          boxShadow: `0 0 10px 2px ${r.dot}80`,
          flexShrink: 0,
        }}/>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)', fontWeight: 600,
          letterSpacing: '0.04em', writingMode: 'horizontal-tb',
        }}>{a.time}</div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: 'var(--f-display)', fontSize: 15, fontWeight: 600,
          color: 'var(--t0)', letterSpacing: '-0.005em',
        }}>{a.name} <span style={{
          fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)',
          fontWeight: 400, marginLeft: 4,
        }}>· {a.age}a</span></div>
        <div style={{
          fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)', marginTop: 2,
        }}>{a.doc}</div>
        <div style={{
          fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t1)', marginTop: 8,
          lineHeight: 1.4,
        }}>{a.reason}</div>
        <div style={{
          marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 10px', borderRadius: 99, whiteSpace: 'nowrap',
          background: `${r.color}1a`,
          border: `1px solid ${r.color}40`,
          animation: `spring-in .4s cubic-bezier(.34,1.36,.64,1) ${0.2 + idx*0.04}s both`,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: r.color }}/>
          <span style={{
            fontFamily: 'var(--f-body)', fontSize: 11, fontWeight: 600,
            color: r.color, letterSpacing: '0.01em',
          }}>{r.label}</span>
          <span style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: r.color, opacity: 0.85,
          }}>· {a.score}%</span>
        </div>
      </div>
      <IconChevron size={16} color="var(--t3)" stroke={1.6}/>
    </div>
  );
}

function AppointmentsScreen() {
  const totals = APPOINTMENTS.reduce((acc, a) => { acc[a.risk]++; acc.total++; return acc; }, { high: 0, med: 0, low: 0, total: 0 });
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '60px 20px 8px' }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
        }}>vendredi 15 mai · cabinet</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <h1 style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 28,
            margin: 0, letterSpacing: '-0.02em', color: 'var(--t0)',
          }}>Agenda</h1>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)', letterSpacing: '0.04em',
          }}>{totals.total} pat.</div>
        </div>
      </div>

      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 110px' }}>
        {/* summary card with 3 sections */}
        <div style={{
          background: 'var(--s1)', borderRadius: 20,
          border: '1px solid var(--line)', padding: '16px 0',
          display: 'flex', marginBottom: 16,
        }}>
          {[
            { color: RISK.high.color, n: totals.high, label: 'Élevé' },
            { color: RISK.med.color, n: totals.med, label: 'Modéré' },
            { color: RISK.low.color, n: totals.low, label: 'Faible' },
          ].map((s, i, arr) => (
            <div key={i} style={{
              flex: 1, textAlign: 'center', padding: '0 8px',
              borderRight: i < arr.length - 1 ? '1px solid var(--line)' : 'none',
            }}>
              <div style={{
                fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 36,
                lineHeight: 1, color: s.color,
                textShadow: `0 0 18px ${s.color}55`,
                animation: `spring-in .6s cubic-bezier(.34,1.36,.64,1) ${i*0.08}s both`,
              }}>{s.n}</div>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
                letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 7,
              }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* timeline */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {APPOINTMENTS.map((a, i) => <ApptCard key={i} a={a} idx={i}/>)}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AppointmentsScreen });

}

// ─── profile.jsx ───
{
// Profile screen — settings groups

const { IconChevron, IconShield, IconBell, IconLanguage, IconLock,
  IconHistory, IconStethoscope, IconTrash, IconLogout, IconPill, IconUser } = window;

function SettingRow({ icon: Icon, label, sub, danger, last, onClick }) {
  return (
    <button onClick={onClick} style={{
      width: '100%', display: 'flex', alignItems: 'center', gap: 14,
      padding: '12px 14px', background: 'transparent', border: 'none',
      borderBottom: last ? 'none' : '1px solid var(--line)',
      color: danger ? 'var(--pulse)' : 'var(--t0)',
      cursor: 'pointer', textAlign: 'left',
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 9,
        background: danger ? 'rgba(244,63,94,0.12)' : 'var(--s2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: danger ? 'var(--pulse)' : 'var(--t1)',
        flexShrink: 0,
      }}><Icon size={16} stroke={1.7}/></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--f-body)', fontSize: 14, fontWeight: 500 }}>{label}</div>
        {sub && <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          marginTop: 2, letterSpacing: '0.04em',
        }}>{sub}</div>}
      </div>
      {!danger && <IconChevron size={14} color="var(--t3)" stroke={1.6}/>}
    </button>
  );
}

function SettingGroup({ title, children }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{
        fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
        letterSpacing: '0.16em', textTransform: 'uppercase',
        marginBottom: 8, padding: '0 16px',
      }}>{title}</div>
      <div style={{
        background: 'var(--s1)', borderRadius: 16,
        border: '1px solid var(--line)', overflow: 'hidden',
      }}>{children}</div>
    </div>
  );
}

function ProfileScreen() {
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto' }}>
        {/* gradient mesh header */}
        <div style={{
          position: 'relative', paddingTop: 60, paddingBottom: 24,
          overflow: 'hidden',
        }}>
          {/* mesh blobs */}
          <div style={{
            position: 'absolute', top: -40, left: -40, width: 240, height: 240,
            background: 'radial-gradient(circle, rgba(99,102,241,0.4), transparent 60%)',
            filter: 'blur(40px)',
          }}/>
          <div style={{
            position: 'absolute', top: 20, right: -60, width: 220, height: 220,
            background: 'radial-gradient(circle, rgba(139,92,246,0.4), transparent 60%)',
            filter: 'blur(40px)',
          }}/>
          <div style={{
            position: 'absolute', inset: 0, background: 'rgba(10,13,20,0.55)',
          }}/>

          <div style={{ position: 'relative', zIndex: 2, padding: '20px 20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
            {/* avatar with gradient ring */}
            <div style={{
              width: 84, height: 84, borderRadius: '50%',
              background: 'var(--ai-grad)',
              padding: 3, marginBottom: 14,
              boxShadow: '0 8px 32px rgba(99,102,241,0.4)',
            }}>
              <div style={{
                width: '100%', height: '100%', borderRadius: '50%',
                background: 'var(--s0)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 600,
                color: 'var(--t0)',
              }}>A</div>
            </div>
            <h1 style={{
              fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
              margin: '0 0 6px', letterSpacing: '-0.01em', color: 'var(--t0)',
              lineHeight: 1.2, display: 'block', whiteSpace: 'nowrap',
            }}>Ahmed Benali</h1>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
              letterSpacing: '0.06em', marginBottom: 14, lineHeight: 1.4,
              whiteSpace: 'nowrap',
            }}>uid · 4f8c2a91 · marrakech</div>
            <div className="grad-border" style={{
              padding: '6px 14px', borderRadius: 99,
              background: 'rgba(28,35,51,0.6)', backdropFilter: 'blur(8px)',
              fontFamily: 'var(--f-body)', fontSize: 11, fontWeight: 600,
              color: 'var(--t0)', display: 'inline-flex', alignItems: 'center', gap: 6,
              whiteSpace: 'nowrap',
            }}><IconStethoscope size={12} stroke={2}/> Patient · suivi cardio</div>
          </div>
        </div>

        {/* quick stats */}
        <div style={{ padding: '0 20px 4px', display: 'flex', gap: 8, marginTop: 4 }}>
          {[
            { label: 'sessions', n: '128' },
            { label: 'jours actifs', n: '47' },
            { label: 'urgences', n: '02' },
          ].map((s, i) => (
            <div key={i} style={{
              flex: 1, padding: '12px 10px',
              background: 'var(--s1)', borderRadius: 12,
              border: '1px solid var(--line)', textAlign: 'center',
            }}>
              <div style={{
                fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
                color: 'var(--t0)', lineHeight: 1,
              }}>{s.n}</div>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t3)',
                letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 6,
              }}>{s.label}</div>
            </div>
          ))}
        </div>

        <div style={{ padding: '20px 4px 110px' }}>
          <SettingGroup title="Médical">
            <SettingRow icon={IconStethoscope} label="Mon dossier patient" sub="3 antécédents · HTA · diabète T2"/>
            <SettingRow icon={IconPill} label="Mes traitements" sub="2 actifs · coversyl · metformine"/>
            <SettingRow icon={IconHistory} label="Historique consultations" sub="12 sessions · dernière 2 jours" last/>
          </SettingGroup>

          <SettingGroup title="Préférences">
            <SettingRow icon={IconLanguage} label="Langue" sub="français · darija · العربية"/>
            <SettingRow icon={IconBell} label="Notifications" sub="urgences · médicaments"/>
            <SettingRow icon={IconUser} label="Compte & sécurité" sub="biométrie activée" last/>
          </SettingGroup>

          <SettingGroup title="Confidentialité · Loi 09-08">
            <SettingRow icon={IconShield} label="Politique de données" sub="hébergement maroc · jamais partagé"/>
            <SettingRow icon={IconLock} label="Chiffrement & journaux" sub="aes-256 · audit log"/>
            <SettingRow icon={IconTrash} label="Effacer toutes mes données" sub="droit à l'effacement · rgpd art. 17" danger last/>
          </SettingGroup>

          <SettingGroup title="Compte">
            <SettingRow icon={IconLogout} label="Se déconnecter" danger last/>
          </SettingGroup>

          <div style={{
            textAlign: 'center', fontFamily: 'var(--f-mono)', fontSize: 9.5,
            color: 'var(--t4)', letterSpacing: '0.14em', marginTop: 8,
          }}>medisense ai · v1.0.0 · build 4f8c2a</div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ProfileScreen });

}

// ─── patient-extras.jsx ───
{
// Patient extras: Consent (RGPD), Conversations history, Reminders

const { IconShield, IconCheck, IconChevron, IconBell, IconPill,
  IconHistory, IconChat: _PIc, IconTrash, IconBack, IconClose } = window;

// ───────── CONSENT (RGPD onboarding step) ─────────
const CONSENT_ITEMS = [
  { key: 'data', title: 'Stockage de mes données médicales',
    desc: 'Vos symptômes, conversations et signes vitaux sont stockés au Maroc, chiffrés (AES-256).',
    required: true },
  { key: 'iot', title: 'Synchronisation bracelet connecté',
    desc: 'Fréquence cardiaque, SpO₂ et HRV. Vous pouvez révoquer à tout moment.',
    required: false },
  { key: 'ml', title: 'Amélioration du modèle IA',
    desc: 'Vos retours anonymisés aident à améliorer la qualité des réponses. Aucune donnée nominative.',
    required: false },
  { key: 'urgency', title: 'Alertes d\'urgence (SAMU 141)',
    desc: 'Si l\'IA détecte un risque vital, elle peut appeler le SAMU à votre place.',
    required: false },
];

function ConsentScreen({ onDone }) {
  const [accepted, setAccepted] = React.useState({ data: true, iot: true, ml: false, urgency: true });
  const allRequired = CONSENT_ITEMS.filter(i => i.required).every(i => accepted[i.key]);
  return (
    <div className="screen" style={{ background: 'var(--s0)' }}>
      <div style={{ padding: '60px 24px 16px' }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: 'rgba(34,197,94,0.12)', color: 'var(--safe)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 18,
        }}><IconShield size={22} stroke={1.7}/></div>
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 26,
          margin: '0 0 6px', letterSpacing: '-0.02em', color: 'var(--t0)',
        }}>Vos données, votre choix</h1>
        <p style={{
          fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t2)',
          margin: 0, lineHeight: 1.5,
        }}>Conforme <strong style={{color:'var(--t1)'}}>Loi 09-08</strong> et <strong style={{color:'var(--t1)'}}>RGPD</strong>. Vous pouvez modifier ces choix à tout moment dans Profil → Confidentialité.</p>
      </div>
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '8px 16px 0' }}>
        {CONSENT_ITEMS.map(item => (
          <div key={item.key} style={{
            background: 'var(--s1)', borderRadius: 14,
            border: `1px solid ${accepted[item.key] ? 'rgba(99,102,241,0.35)' : 'var(--line)'}`,
            padding: 14, marginBottom: 10,
            transition: 'border-color .2s',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <button
                onClick={() => !item.required && setAccepted(a => ({ ...a, [item.key]: !a[item.key] }))}
                disabled={item.required}
                style={{
                  width: 44, height: 26, borderRadius: 99,
                  background: accepted[item.key] ? 'var(--ai-grad)' : 'rgba(148,163,184,0.18)',
                  border: 'none', cursor: item.required ? 'not-allowed' : 'pointer',
                  flexShrink: 0, position: 'relative', padding: 0,
                  opacity: item.required ? 0.7 : 1,
                  transition: 'background .2s',
                }}>
                <span style={{
                  position: 'absolute', top: 3, left: accepted[item.key] ? 21 : 3,
                  width: 20, height: 20, borderRadius: '50%', background: '#fff',
                  transition: 'left .2s',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
                }}/>
              </button>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{
                    fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: 600, color: 'var(--t0)',
                  }}>{item.title}</div>
                  {item.required && <span style={{
                    fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t3)',
                    letterSpacing: '0.12em', textTransform: 'uppercase',
                  }}>requis</span>}
                </div>
                <div style={{
                  fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)',
                  marginTop: 4, lineHeight: 1.4,
                }}>{item.desc}</div>
              </div>
            </div>
          </div>
        ))}
        <div style={{
          marginTop: 6, padding: 12, borderRadius: 12,
          background: 'rgba(28,35,51,0.5)', border: '1px solid var(--line)',
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
          letterSpacing: '0.04em', lineHeight: 1.5,
        }}>
          <span style={{ color: 'var(--safe)' }}>●</span> droit d'accès · rectification · effacement · portabilité<br/>
          <span style={{ color: 'var(--safe)' }}>●</span> hébergement maroc (datacenter casablanca-tier3)<br/>
          <span style={{ color: 'var(--safe)' }}>●</span> jamais de partage tiers · jamais d'usage commercial
        </div>
      </div>
      <div style={{ padding: '14px 24px 36px' }}>
        <button onClick={onDone} disabled={!allRequired} style={{
          width: '100%', height: 52, borderRadius: 99,
          background: allRequired ? 'var(--ai-grad)' : 'rgba(28,35,51,0.6)',
          border: 'none', color: '#fff',
          fontFamily: 'var(--f-body)', fontSize: 15, fontWeight: 600,
          cursor: allRequired ? 'pointer' : 'not-allowed',
          opacity: allRequired ? 1 : 0.5,
          boxShadow: allRequired ? '0 8px 24px rgba(99,102,241,0.35)' : 'none',
        }}>J'accepte et je continue</button>
      </div>
    </div>
  );
}

// ───────── CONVERSATIONS HISTORY ─────────
const CONVOS = [
  { id: 1, title: 'Douleur thoracique aiguë', preview: 'L\'IA a contacté le SAMU 141. Vous avez reçu un protocole d\'urgence aspirine 300mg.', date: 'Aujourd\'hui · 14:22', tag: 'urgence', urgent: true, sources: 5 },
  { id: 2, title: 'Effets secondaires Coversyl', preview: 'Toux sèche persistante : effet possible de l\'IEC. Discutez avec Dr. Merrouni d\'un changement.', date: 'Hier · 09:48', tag: 'traitement', sources: 3 },
  { id: 3, title: 'Mal de tête + nuque raide', preview: 'Probable céphalée de tension. Repos, hydratation. Si persiste >48h ou fièvre → consultation.', date: '08 mai · 18:15', tag: 'symptômes', sources: 4 },
  { id: 4, title: 'Tension à 14/9 ce matin', preview: 'Légèrement élevée. Tendance stable sur 7j. Pas d\'action immédiate, surveillance demain.', date: '06 mai · 07:30', tag: 'mesure', sources: 2 },
  { id: 5, title: 'Régime diabète type 2', preview: 'Plan alimentaire darija : pain complet, légumineuses, éviter pâtisseries marocaines au miel.', date: '03 mai · 20:02', tag: 'nutrition', sources: 6 },
  { id: 6, title: 'Vaccin grippe nécessaire ?', preview: 'Oui, recommandé pour profil HTA + 58 ans. Centre santé Gueliz proche, créneaux libres.', date: '28 avr · 11:40', tag: 'prévention', sources: 2 },
];

const TAG_COLORS = {
  'urgence': { c: '#F43F5E', bg: 'rgba(244,63,94,0.12)' },
  'traitement': { c: '#A78BFA', bg: 'rgba(167,139,250,0.12)' },
  'symptômes': { c: '#38BDF8', bg: 'rgba(56,189,248,0.12)' },
  'mesure': { c: '#22C55E', bg: 'rgba(34,197,94,0.12)' },
  'nutrition': { c: '#F59E0B', bg: 'rgba(245,158,11,0.12)' },
  'prévention': { c: '#94A3B8', bg: 'rgba(148,163,184,0.12)' },
};

function HistoryScreen() {
  const [filter, setFilter] = React.useState('all');
  const filters = ['all', ...Object.keys(TAG_COLORS)];
  const list = filter === 'all' ? CONVOS : CONVOS.filter(c => c.tag === filter);
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '60px 20px 8px' }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
        }}>{CONVOS.length} conversations · 30j</div>
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 28,
          margin: 0, letterSpacing: '-0.02em', color: 'var(--t0)',
        }}>Historique</h1>
      </div>
      <div className="scroll-hide" style={{
        display: 'flex', gap: 6, padding: '14px 20px 6px', overflowX: 'auto',
      }}>
        {filters.map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: '6px 12px', borderRadius: 99,
            background: filter === f ? 'var(--ai-grad)' : 'rgba(28,35,51,0.6)',
            border: filter === f ? 'none' : '1px solid var(--line)',
            color: filter === f ? '#fff' : 'var(--t1)',
            fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
            letterSpacing: '0.06em', textTransform: 'uppercase',
            cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
          }}>{f === 'all' ? 'tout' : f}</button>
        ))}
      </div>
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '8px 16px 110px' }}>
        {list.map((c, idx) => {
          const t = TAG_COLORS[c.tag];
          return (
            <div key={c.id} style={{
              background: 'var(--s1)', borderRadius: 14,
              border: `1px solid ${c.urgent ? 'rgba(244,63,94,0.35)' : 'var(--line)'}`,
              padding: 14, marginBottom: 8,
              animation: `bubble-in .3s cubic-bezier(.34,1.36,.64,1) ${idx*0.04}s both`,
              position: 'relative', overflow: 'hidden',
            }}>
              {c.urgent && <div style={{
                position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
                background: 'var(--pulse)',
                boxShadow: '0 0 12px rgba(244,63,94,0.5)',
              }}/>}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{
                  padding: '3px 8px', borderRadius: 99,
                  background: t.bg, color: t.c,
                  fontFamily: 'var(--f-mono)', fontSize: 9, fontWeight: 600,
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                }}>{c.tag}</span>
                <span style={{
                  fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
                  letterSpacing: '0.04em', marginLeft: 'auto',
                }}>{c.date}</span>
              </div>
              <div style={{
                fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 600,
                color: 'var(--t0)', marginBottom: 4, letterSpacing: '-0.005em',
              }}>{c.title}</div>
              <div style={{
                fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)',
                lineHeight: 1.5,
              }}>{c.preview}</div>
              <div style={{
                marginTop: 10, display: 'flex', alignItems: 'center', gap: 12,
                fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
              }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#A5B4FC' }}/>
                  {c.sources} sources rag
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ───────── REMINDERS ─────────
const REMINDERS = [
  { time: '08:00', name: 'Coversyl 5mg', sub: 'IEC · 1 comprimé · à jeun', taken: true, type: 'pill' },
  { time: '12:30', name: 'Metformine 850mg', sub: 'Antidiabétique · pendant repas', taken: true, type: 'pill' },
  { time: '14:00', name: 'Mesure tension', sub: 'Brassard · noter dans l\'app', taken: false, type: 'measure' },
  { time: '20:00', name: 'Metformine 850mg', sub: 'Antidiabétique · pendant repas', taken: false, type: 'pill' },
  { time: '22:00', name: 'Aspirine 75mg', sub: 'Antiagrégant · au coucher', taken: false, type: 'pill' },
];

function RemindersScreen() {
  const [items, setItems] = React.useState(REMINDERS);
  const taken = items.filter(i => i.taken).length;
  const pct = Math.round((taken / items.length) * 100);
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '60px 20px 8px' }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
        }}>aujourd'hui · 5 rappels</div>
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 28,
          margin: 0, letterSpacing: '-0.02em', color: 'var(--t0)',
        }}>Mes rappels</h1>
      </div>
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 110px' }}>
        {/* progress card */}
        <div style={{
          background: 'var(--s1)', borderRadius: 18,
          border: '1px solid var(--line)', padding: 18, marginBottom: 16,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: -30, right: -30, width: 140, height: 140,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(34,197,94,0.25), transparent 70%)',
            filter: 'blur(20px)',
          }}/>
          <div style={{ position: 'relative' }}>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
              letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8,
            }}>observance</div>
            <div style={{
              fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 44,
              color: 'var(--safe)', lineHeight: 1, letterSpacing: '-0.02em',
              textShadow: '0 0 20px rgba(34,197,94,0.4)',
            }}>{pct}%</div>
            <div style={{
              fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)',
              marginTop: 6,
            }}>{taken} / {items.length} rappels validés</div>
            <div style={{
              marginTop: 14, height: 6, borderRadius: 99,
              background: 'rgba(148,163,184,0.15)', overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', width: `${pct}%`,
                background: 'linear-gradient(90deg, var(--safe), #16A34A)',
                borderRadius: 99,
                transition: 'width .4s ease',
                boxShadow: '0 0 8px rgba(34,197,94,0.4)',
              }}/>
            </div>
          </div>
        </div>
        {/* timeline */}
        <div style={{ position: 'relative' }}>
          <div style={{
            position: 'absolute', left: 22, top: 8, bottom: 8, width: 2,
            background: 'linear-gradient(180deg, rgba(99,102,241,0.5), rgba(99,102,241,0.05))',
          }}/>
          {items.map((r, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 12,
              marginBottom: 10, position: 'relative',
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
                background: r.taken ? 'var(--safe)' : 'var(--s1)',
                border: r.taken ? 'none' : '2px solid var(--line-strong)',
                color: r.taken ? '#fff' : 'var(--t2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--f-mono)', fontSize: 9, fontWeight: 700,
                letterSpacing: '0.04em',
                boxShadow: r.taken ? '0 0 0 4px rgba(34,197,94,0.15)' : 'none',
                position: 'relative', zIndex: 1,
              }}>
                {r.taken ? <IconCheck size={18} stroke={2.4}/> : r.time}
              </div>
              <div style={{
                flex: 1, padding: '12px 14px', borderRadius: 12,
                background: 'var(--s1)',
                border: '1px solid var(--line)',
                opacity: r.taken ? 0.6 : 1,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <div>
                    <div style={{
                      fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: 600,
                      color: 'var(--t0)',
                      textDecoration: r.taken ? 'line-through' : 'none',
                    }}>{r.name}</div>
                    <div style={{
                      fontFamily: 'var(--f-body)', fontSize: 11, color: 'var(--t2)', marginTop: 2,
                    }}>{r.sub}</div>
                  </div>
                  {r.taken ? (
                    <div style={{
                      fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--safe)',
                      letterSpacing: '0.1em', textTransform: 'uppercase',
                    }}>{r.time} · pris</div>
                  ) : (
                    <button onClick={() => setItems(arr => arr.map((x, j) => j===i ? {...x, taken: true} : x))} style={{
                      padding: '6px 12px', borderRadius: 99,
                      background: 'var(--ai-grad)', border: 'none', color: '#fff',
                      fontFamily: 'var(--f-body)', fontSize: 11, fontWeight: 600,
                      cursor: 'pointer',
                      boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
                    }}>Valider</button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ConsentScreen, HistoryScreen, RemindersScreen });

}

// ─── doctor.jsx ───
{
// Doctor screens: Login, Agenda, DPA 3-column

const { DashboardLayout, DashButton, RiskPill, StatusPill, ConfidenceBar } = window;

// Doctor-specific login (web-style centered card)
function DoctorLogin() {
  const [pw, setPw] = React.useState('••••••••••••');
  const [focusEmail, setFE] = React.useState(false);
  const [focusPw, setFP] = React.useState(false);
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: 'var(--s0)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--f-body)',
    }}>
      {/* glow */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(700px 400px at 70% 30%, rgba(99,102,241,0.10), transparent 60%), radial-gradient(500px 400px at 20% 80%, rgba(139,92,246,0.07), transparent 60%)',
        pointerEvents: 'none',
      }}/>

      <div style={{ width: 420, position: 'relative', zIndex: 1 }}>
        {/* logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ display: 'inline-flex', alignItems: 'flex-end', gap: 3, height: 24, marginBottom: 12 }}>
            {[10, 18, 24, 18, 10].map((h, i) => (
              <div key={i} style={{
                width: 3.5, height: h, borderRadius: 2,
                background: 'var(--ai-grad)',
                animation: `wave-bar 1.4s ease-in-out ${i * 0.15}s infinite`,
                transformOrigin: 'bottom',
              }}/>
            ))}
          </div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em' }}>
            MediSense<span className="grad-text"> AI</span>
          </div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 4 }}>
            Console clinique
          </div>
        </div>

        {/* card */}
        <div style={{
          background: 'var(--s1)',
          border: '1px solid var(--line)',
          borderRadius: 16, padding: 28,
          boxShadow: '0 12px 48px rgba(0,0,0,0.4)',
        }}>
          <h2 style={{ fontFamily: 'var(--f-display)', fontSize: 24, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.01em' }}>Connexion</h2>
          <div style={{ color: 'var(--t2)', fontSize: 13, marginBottom: 22 }}>Accès médecin · authentification SSO</div>

          {/* email */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>Email professionnel</div>
            <div style={{ position: 'relative' }}>
              <input
                type="email"
                defaultValue="dr.merrouni@clinique.ma"
                onFocus={() => setFE(true)} onBlur={() => setFE(false)}
                style={{
                  width: '100%', padding: '11px 13px',
                  background: 'var(--s2)',
                  border: 'none', borderBottom: '1px solid var(--line-strong)',
                  borderRadius: '8px 8px 0 0', color: 'var(--t0)',
                  fontFamily: 'var(--f-body)', fontSize: 13.5, outline: 'none',
                }}
              />
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                height: 2, borderRadius: 99,
                background: 'var(--ai-grad)',
                transform: focusEmail ? 'scaleX(1)' : 'scaleX(0)',
                transformOrigin: 'left', transition: 'transform .25s ease',
                boxShadow: focusEmail ? '0 0 12px rgba(139,92,246,0.5)' : 'none',
              }}/>
            </div>
          </div>

          {/* password */}
          <div style={{ marginBottom: 22 }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>Mot de passe</div>
            <div style={{ position: 'relative' }}>
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                onFocus={() => setFP(true)} onBlur={() => setFP(false)}
                style={{
                  width: '100%', padding: '11px 40px 11px 13px',
                  background: 'var(--s2)',
                  border: 'none', borderBottom: '1px solid var(--line-strong)',
                  borderRadius: '8px 8px 0 0', color: 'var(--t0)',
                  fontFamily: 'var(--f-body)', fontSize: 13.5, outline: 'none',
                }}
              />
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                height: 2, borderRadius: 99,
                background: 'var(--ai-grad)',
                transform: focusPw ? 'scaleX(1)' : 'scaleX(0)',
                transformOrigin: 'left', transition: 'transform .25s ease',
                boxShadow: focusPw ? '0 0 12px rgba(139,92,246,0.5)' : 'none',
              }}/>
              <button style={{
                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                background: 'transparent', border: 'none', color: 'var(--t3)', cursor: 'pointer',
                width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
            <div style={{ marginTop: 8, fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>
              <a href="#" style={{ color: '#A78BFA', textDecoration: 'none' }}>Mot de passe oublié ?</a>
            </div>
          </div>

          <button style={{
            width: '100%', padding: '12px', borderRadius: 99,
            background: 'var(--ai-grad)', color: '#fff', border: 'none',
            fontFamily: 'var(--f-body)', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', boxShadow: '0 8px 24px rgba(99,102,241,0.30)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
            Se connecter
            <span>→</span>
          </button>
        </div>

        <div style={{
          textAlign: 'center', marginTop: 18,
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t4)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
        }}>
          v1.0 · n.synergy · EMSI Marrakech
        </div>
      </div>
    </div>
  );
}

// ───────────────── Doctor Agenda ─────────────────
const DOCTOR_USER = { initial: 'M', name: 'Dr. Merrouni' };

const APPTS = [
  { time: '09:00', uid: 'a1b2c3d4', name: 'Ahmed Benali',     type: 'Consultation cardiologie', risk: 'danger', prob: 0.67, status: 'pending', sms: 0 },
  { time: '09:30', uid: 'e5f6g7h8', name: 'Salma Idrissi',    type: 'Suivi diabète',            risk: 'safe',   prob: 0.08, status: 'confirmed', sms: 1 },
  { time: '10:00', uid: 'i9j0k1l2', name: 'Karim Ouahbi',     type: 'Bilan annuel',             risk: 'warn',   prob: 0.34, status: 'confirmed', sms: 1 },
  { time: '10:30', uid: 'm3n4o5p6', name: 'Fatima El Amrani', type: 'Renouvellement traitement',risk: 'safe',   prob: 0.12, status: 'pending',  sms: 0 },
  { time: '11:00', uid: 'q7r8s9t0', name: 'Youssef Tazi',     type: 'Téléconsultation',         risk: 'danger', prob: 0.71, status: 'pending',  sms: 0 },
  { time: '11:30', uid: 'u1v2w3x4', name: 'Nadia Berrada',    type: 'Consultation générale',    risk: 'safe',   prob: 0.14, status: 'confirmed', sms: 1 },
  { time: '14:00', uid: 'y5z6a7b8', name: 'Hamza Saidi',      type: 'Échographie cardiaque',    risk: 'warn',   prob: 0.28, status: 'confirmed', sms: 1 },
];

function StatCard({ count, color, glow, label, sublabel }) {
  return (
    <div style={{
      flex: 1,
      background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
      padding: '18px 20px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{
          width: 8, height: 8, borderRadius: 99, background: color,
          boxShadow: `0 0 8px ${glow}`,
        }}/>
        <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{label}</span>
      </div>
      <div style={{ fontFamily: 'var(--f-display)', fontSize: 36, fontWeight: 600, color: 'var(--t0)', lineHeight: 1, letterSpacing: '-0.02em' }}>
        {count}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--t2)', marginTop: 6 }}>{sublabel}</div>
    </div>
  );
}

function DoctorAgenda({ onOpenDpa }) {
  const counts = APPTS.reduce((acc, a) => { acc[a.risk]++; return acc; }, { safe: 0, warn: 0, danger: 0 });
  const totalSms = APPTS.filter(a => a.sms).length;

  return (
    <DashboardLayout
      role="doctor" active="agenda" onChange={() => {}}
      user={DOCTOR_USER}
      breadcrumb="agenda · 10 mai 2026"
      title="Agenda intelligent"
      subtitle="Prédiction no-show · XGBoost v2.1 · 7 rendez-vous aujourd'hui"
      actions={[
        <DashButton key="d" kind="solid" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>}>10 mai 2026</DashButton>,
        <DashButton key="r" kind="solid" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5M21 12a9 9 0 01-15 6.7L3 16M3 21v-5h5"/></svg>}>Actualiser</DashButton>,
        <DashButton key="s" kind="gradient" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8l9 6 9-6M3 8v10a2 2 0 002 2h14a2 2 0 002-2V8M3 8l2-3h14l2 3"/></svg>}>SMS de rappel ({counts.danger + counts.warn})</DashButton>,
      ]}
    >
      {/* stat row */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 20 }}>
        <StatCard count={counts.safe}   color="#22C55E" glow="rgba(34,197,94,0.55)"   label="Faible"  sublabel="probabilité < 20% — pas d'action"/>
        <StatCard count={counts.warn}   color="#F97316" glow="rgba(249,115,22,0.55)"  label="Modéré"  sublabel="20–40% — SMS recommandé"/>
        <StatCard count={counts.danger} color="#EF4444" glow="rgba(239,68,68,0.55)"   label="Élevé"   sublabel="> 40% — appel + SMS"/>
        <StatCard count={totalSms}      color="#A78BFA" glow="rgba(167,139,250,0.55)" label="SMS env" sublabel="rappels déjà dispatchés"/>
      </div>

      {/* table */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
        overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '90px 1fr 200px 140px 130px 100px 80px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 500,
          borderBottom: '1px solid var(--line)',
        }}>
          <div>Heure</div>
          <div>Patient</div>
          <div>Motif</div>
          <div>No-show</div>
          <div>Statut</div>
          <div>SMS</div>
          <div></div>
        </div>
        {APPTS.map((a, i) => (
          <button key={a.uid} onClick={onOpenDpa}
            style={{
              all: 'unset',
              cursor: 'pointer',
              display: 'grid', gridTemplateColumns: '90px 1fr 200px 140px 130px 100px 80px',
              padding: '13px 18px', alignItems: 'center',
              borderBottom: i < APPTS.length - 1 ? '1px solid var(--line)' : 'none',
              transition: 'background .14s',
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(99,102,241,0.06)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <div style={{ fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 500, color: 'var(--t0)' }}>{a.time}</div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>{a.name}</div>
              <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>uid · {a.uid}</div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--t2)' }}>{a.type}</div>
            <div><RiskPill level={a.risk} prob={a.prob}/></div>
            <div>
              <StatusPill tone={a.status === 'pending' ? 'pending' : 'approved'} label={a.status === 'pending' ? 'En attente' : 'Confirmé'} pulse={a.status === 'pending'}/>
            </div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: a.sms ? '#22C55E' : 'var(--t4)' }}>
              {a.sms ? '✓ envoyé' : '— '}
            </div>
            <div style={{ textAlign: 'right', color: 'var(--t3)' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 6l6 6-6 6"/></svg>
            </div>
          </button>
        ))}
      </div>

      <div style={{
        marginTop: 22, padding: '14px 18px',
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8,
          background: 'rgba(167,139,250,0.10)',
          border: '1px solid rgba(167,139,250,0.30)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#A78BFA',
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4l3 2"/></svg>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12.5, color: 'var(--t0)', fontWeight: 500 }}>Modèle XGBoost re-entraîné <span style={{ fontFamily: 'var(--f-mono)', color: 'var(--t3)' }}>il y a 4h</span></div>
          <div style={{ fontSize: 11.5, color: 'var(--t2)' }}>AUC 0.847 · F1 0.79 · entrainé sur 14 728 RDVs (90 derniers jours).</div>
        </div>
        <DashButton kind="solid" small>Voir métriques</DashButton>
      </div>
    </DashboardLayout>
  );
}

// ───────────────── DPA 3-column ─────────────────
function DpaCol({ tag, title, count, children }) {
  return (
    <div style={{
      background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
      display: 'flex', flexDirection: 'column', minHeight: 0,
    }}>
      <div style={{
        padding: '14px 18px', borderBottom: '1px solid var(--line)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.16em', textTransform: 'uppercase' }}>{tag}</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 15, fontWeight: 600, color: 'var(--t0)', marginTop: 2 }}>{title}</div>
        </div>
        {count !== undefined && (
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
            padding: '2px 8px', background: 'var(--s2)', borderRadius: 99,
            border: '1px solid var(--line)',
          }}>{count}</div>
        )}
      </div>
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }} className="scroll-hide">
        {children}
      </div>
    </div>
  );
}

function SymptomItem({ text, severity, since }) {
  const sevColors = { high: '#EF4444', med: '#F97316', low: '#22C55E' };
  return (
    <div style={{
      display: 'flex', gap: 10, padding: '11px 12px',
      background: 'var(--s2)', borderRadius: 10, border: '1px solid var(--line)',
    }}>
      <div style={{
        width: 6, alignSelf: 'stretch', borderRadius: 99,
        background: sevColors[severity], boxShadow: `0 0 6px ${sevColors[severity]}80`, flexShrink: 0,
      }}/>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12.5, color: 'var(--t0)', fontWeight: 500 }}>{text}</div>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>{since}</div>
      </div>
    </div>
  );
}

function VitalItem({ label, value, unit, status, threshold, ago, tone }) {
  const tones = {
    critical: { c: '#EF4444', bg: 'rgba(239,68,68,0.10)', bd: 'rgba(239,68,68,0.45)' },
    warn:     { c: '#F97316', bg: 'rgba(249,115,22,0.10)', bd: 'rgba(249,115,22,0.45)' },
    normal:   { c: '#22C55E', bg: 'rgba(34,197,94,0.08)',  bd: 'rgba(34,197,94,0.30)' },
  };
  const t = tones[tone];
  return (
    <div style={{
      padding: '12px 14px', background: 'var(--s2)', borderRadius: 10,
      border: `1px solid ${t.bd}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <div style={{ fontSize: 12, color: 'var(--t2)' }}>{label}</div>
        <StatusPill tone={tone === 'critical' ? 'failed' : tone === 'warn' ? 'pending' : 'sent'} label={status}/>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: 'var(--f-display)', fontSize: 26, fontWeight: 600, color: t.c, letterSpacing: '-0.02em' }}>{value}</span>
        <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)' }}>{unit}</span>
      </div>
      <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 4 }}>{threshold} · {ago}</div>
    </div>
  );
}

function ActionCard({ kind, title, description, rationale, confidence, state, onApprove, onReject, onEdit }) {
  // kind: prescribe | refer | monitor | alert
  const kinds = {
    prescribe: { c: '#38BDF8', label: 'PRESCRIRE', icon: '℞' },
    refer:     { c: '#A78BFA', label: 'RÉFÉRER',   icon: '↗' },
    monitor:   { c: '#FBBF24', label: 'MONITORER', icon: '◔' },
    alert:     { c: '#EF4444', label: 'ALERTER',   icon: '⚠' },
  };
  const k = kinds[kind];
  const isApproved = state === 'approved';
  const isRejected = state === 'rejected';
  const opacity = isRejected ? 0.5 : 1;
  return (
    <div style={{
      background: isApproved ? 'rgba(34,197,94,0.06)' : isRejected ? 'rgba(239,68,68,0.05)' : 'var(--s2)',
      border: `1px solid ${isApproved ? 'rgba(34,197,94,0.30)' : isRejected ? 'rgba(239,68,68,0.30)' : 'var(--line)'}`,
      borderRadius: 12, padding: 14, opacity,
      transition: 'all .25s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '3px 9px', borderRadius: 99,
          fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
          color: k.c, background: `${k.c}1A`, border: `1px solid ${k.c}66`,
          letterSpacing: '0.08em',
        }}>
          <span>{k.icon}</span>{k.label}
        </span>
        <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t1)', fontWeight: 600 }}>
          {Math.round(confidence * 100)}%
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{ flex: 1, height: 4, background: 'var(--s3)', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{ width: `${confidence * 100}%`, height: '100%', background: 'var(--ai-grad)' }}/>
        </div>
      </div>
      <div style={{ fontSize: 13.5, color: 'var(--t0)', fontWeight: 600, marginBottom: 4, lineHeight: 1.3, textDecoration: isRejected ? 'line-through' : 'none' }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--t1)', marginBottom: 8, lineHeight: 1.5 }}>{description}</div>
      <div style={{ fontSize: 11.5, color: 'var(--t3)', fontStyle: 'italic', lineHeight: 1.5, marginBottom: 12, paddingLeft: 10, borderLeft: '2px solid var(--s3)' }}>
        {rationale}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={onApprove} style={{
          flex: 1, padding: '7px 8px', borderRadius: 8, cursor: 'pointer',
          background: isApproved ? 'rgba(34,197,94,0.20)' : 'rgba(34,197,94,0.08)',
          border: `1px solid ${isApproved ? 'rgba(34,197,94,0.6)' : 'rgba(34,197,94,0.30)'}`,
          color: '#22C55E', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 600,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M5 12l5 5L20 7"/></svg>
          {isApproved ? 'Approuvé' : 'Approuver'}
        </button>
        <button onClick={onReject} style={{
          flex: 1, padding: '7px 8px', borderRadius: 8, cursor: 'pointer',
          background: isRejected ? 'rgba(239,68,68,0.18)' : 'rgba(239,68,68,0.06)',
          border: `1px solid ${isRejected ? 'rgba(239,68,68,0.6)' : 'rgba(239,68,68,0.25)'}`,
          color: '#EF4444', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 600,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M6 6l12 12M18 6L6 18"/></svg>
          Rejeter
        </button>
        <button onClick={onEdit} style={{
          padding: '7px 10px', borderRadius: 8, cursor: 'pointer',
          background: 'var(--s3)', border: '1px solid var(--line-strong)',
          color: 'var(--t1)', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 500,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 113 3L7 19l-4 1 1-4z"/></svg>
        </button>
      </div>
    </div>
  );
}

function DoctorDpa({ onBack }) {
  const [actions, setActions] = React.useState({
    a1: 'approved', a2: 'pending', a3: 'pending', a4: 'pending',
  });
  const [note, setNote] = React.useState('');

  const setA = (k, v) => setActions(prev => ({ ...prev, [k]: v }));

  return (
    <DashboardLayout
      role="doctor" active="agenda" onChange={() => {}}
      user={DOCTOR_USER}
      breadcrumb="agenda › ahmed benali · 09:00"
      title="Résumé DPA — Ahmed Benali"
      subtitle="Patient ID a1b2c3d4 · cardiologie · généré il y a 3 min par le pipeline RAG"
      actions={[
        <DashButton key="b" kind="ghost" onClick={onBack} icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>}>Retour à l'agenda</DashButton>,
        <DashButton key="r" kind="solid" small>Rejeter le résumé</DashButton>,
        <DashButton key="v" kind="gradient" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12l5 5L20 7"/></svg>}>Valider et signer</DashButton>,
      ]}
    >
      {/* status banner */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 18,
        padding: '14px 18px',
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
        marginBottom: 16,
      }}>
        <StatusPill tone="pending" label="En attente · 1 action approuvée" pulse/>
        <ConfidenceBar value={0.78} label="Confiance globale" width={200}/>
        <div style={{ flex: 1 }}/>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)' }}>
          rag · 3 sources · maj il y a 3 min
        </div>
      </div>

      {/* 3 columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.2fr', gap: 14, height: 'calc(100% - 80px)', minHeight: 480 }}>
        <DpaCol tag="rag · sprint 3" title="Symptômes rapportés" count="4">
          <SymptomItem text="Douleurs thoraciques à l'effort" severity="high" since="depuis 5 jours · échelle 7/10"/>
          <SymptomItem text="Essoufflement nocturne" severity="med" since="depuis 2 semaines · épisodique"/>
          <SymptomItem text="Toux persistante (sèche)" severity="med" since="depuis 3 jours"/>
          <SymptomItem text="Fatigue inhabituelle" severity="low" since="depuis 1 semaine"/>
          <div style={{
            padding: '10px 12px', background: 'rgba(99,102,241,0.06)',
            borderRadius: 10, border: '1px solid rgba(99,102,241,0.30)',
            marginTop: 4,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--f-mono)', fontSize: 9.5, color: '#A78BFA', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>
              <span>≋</span>Synthèse RAG
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--t1)', lineHeight: 1.5 }}>
              Tableau évocateur d'une <strong style={{ color: 'var(--t0)' }}>insuffisance cardiaque débutante</strong>. À corréler avec la biométrie et l'ECG.
            </div>
          </div>
        </DpaCol>

        <DpaCol tag="iot · sprint 7" title="Biométrie 24h" count="3 anomalies">
          <VitalItem label="Saturation O₂" value="91" unit="% SpO2" status="critique" threshold="< 95% — anormal" ago="il y a 2 h" tone="critical"/>
          <VitalItem label="Variabilité HRV" value="28" unit="ms" status="modéré" threshold="< 35 ms — bas" ago="moy. 24h" tone="warn"/>
          <VitalItem label="Fréquence cardiaque" value="72" unit="bpm" status="normal" threshold="60–100 bpm" ago="repos · stable" tone="normal"/>
          <div style={{
            padding: '10px 12px', background: 'var(--s2)', borderRadius: 10,
            border: '1px solid var(--line)',
          }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>Tendance 7 jours</div>
            {/* sparkline */}
            <svg width="100%" height="40" viewBox="0 0 200 40" preserveAspectRatio="none">
              <defs>
                <linearGradient id="dpa-spark" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0" stopColor="#EF4444" stopOpacity="0.5"/>
                  <stop offset="1" stopColor="#EF4444" stopOpacity="0"/>
                </linearGradient>
              </defs>
              <path d="M 0 8 L 25 12 L 50 18 L 75 14 L 100 22 L 125 28 L 150 32 L 175 35 L 200 38" fill="none" stroke="#EF4444" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M 0 8 L 25 12 L 50 18 L 75 14 L 100 22 L 125 28 L 150 32 L 175 35 L 200 38 L 200 40 L 0 40 Z" fill="url(#dpa-spark)"/>
            </svg>
            <div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 4 }}>SpO₂ ↓ progressif sur 7 jours · −5 pts</div>
          </div>
        </DpaCol>

        <DpaCol tag="xgboost · sprint 5" title="Actions IA suggérées" count="4 actions">
          <ActionCard kind="prescribe"
            title="Prescrire Furosémide 40 mg"
            description="1 cp par jour le matin pendant 14 jours, surveillance kaliémie à J7"
            rationale="Tableau d'IC débutante avec congestion (SpO2 ↓, essoufflement) · adapté au profil rénal du patient"
            confidence={0.85}
            state={actions.a1}
            onApprove={() => setA('a1', actions.a1 === 'approved' ? 'pending' : 'approved')}
            onReject={() => setA('a1', 'rejected')}
            onEdit={() => {}}
          />
          <ActionCard kind="refer"
            title="Référer en cardiologie"
            description="ETT (échographie cardiaque) sous 72h pour évaluer la fraction d'éjection"
            rationale="Signes cliniques + biométrie suggèrent une atteinte structurelle à confirmer par imagerie"
            confidence={0.62}
            state={actions.a2}
            onApprove={() => setA('a2', actions.a2 === 'approved' ? 'pending' : 'approved')}
            onReject={() => setA('a2', 'rejected')}
            onEdit={() => {}}
          />
          <ActionCard kind="monitor"
            title="Monitoring SpO₂ rapproché"
            description="Bracelet IoT actif · alerte palier si SpO₂ < 90% · seuil HRV à 25 ms"
            rationale="Tendance baissière sur 7 jours nécessite surveillance avant réévaluation"
            confidence={0.91}
            state={actions.a3}
            onApprove={() => setA('a3', actions.a3 === 'approved' ? 'pending' : 'approved')}
            onReject={() => setA('a3', 'rejected')}
            onEdit={() => {}}
          />
          <ActionCard kind="alert"
            title="Alerter en cas d'aggravation"
            description="Notification SAMU 141 si SpO2 < 88% pendant > 5 min ou nouvelle douleur"
            rationale="Sécurisation du suivi entre les consultations · seuils conformes recommandations ESC 2024"
            confidence={0.74}
            state={actions.a4}
            onApprove={() => setA('a4', actions.a4 === 'approved' ? 'pending' : 'approved')}
            onReject={() => setA('a4', 'rejected')}
            onEdit={() => {}}
          />
        </DpaCol>
      </div>

      {/* note */}
      <div style={{
        marginTop: 16,
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
        padding: 14,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 113 3L7 19l-4 1 1-4z"/></svg>
          <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Note du médecin (optionnel · audité)</span>
        </div>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Observations cliniques, contexte du patient, justification d'une modification…"
          style={{
            width: '100%', minHeight: 60, resize: 'vertical',
            background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
            color: 'var(--t0)', padding: 10,
            fontFamily: 'var(--f-body)', fontSize: 13, outline: 'none',
          }}
        />
      </div>
    </DashboardLayout>
  );
}

Object.assign(window, { DoctorLogin, DoctorAgenda, DoctorDpa });

}

// ─── secretary.jsx ───
{
// Secretary screens: Agenda+feedback, CRM Tasks

const { DashboardLayout, DashButton, RiskPill, StatusPill } = window;
const SECRETARY_USER = { initial: 'L', name: 'Laila Bennis' };

const SECR_APPTS = [
  { time: '09:00', uid: 'a1b2c3d4', name: 'Ahmed Benali',     doctor: 'Dr. Merrouni', risk: 'danger', prob: 0.67, outcome: null },
  { time: '09:30', uid: 'e5f6g7h8', name: 'Salma Idrissi',    doctor: 'Dr. Merrouni', risk: 'safe',   prob: 0.08, outcome: 'completed' },
  { time: '10:00', uid: 'i9j0k1l2', name: 'Karim Ouahbi',     doctor: 'Dr. Bennis',   risk: 'warn',   prob: 0.34, outcome: 'no_show' },
  { time: '10:30', uid: 'm3n4o5p6', name: 'Fatima El Amrani', doctor: 'Dr. Merrouni', risk: 'safe',   prob: 0.12, outcome: 'completed' },
  { time: '11:00', uid: 'q7r8s9t0', name: 'Youssef Tazi',     doctor: 'Dr. Bennis',   risk: 'danger', prob: 0.71, outcome: null },
  { time: '11:30', uid: 'u1v2w3x4', name: 'Nadia Berrada',    doctor: 'Dr. Merrouni', risk: 'safe',   prob: 0.14, outcome: null },
];

function FeedbackPill({ outcome, onChange }) {
  if (outcome === 'completed') return <StatusPill tone="approved" label="Présenté"/>;
  if (outcome === 'no_show')   return <StatusPill tone="failed" label="Absent"/>;
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <button onClick={() => onChange('completed')} style={{
        padding: '4px 9px', borderRadius: 99, cursor: 'pointer',
        background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.30)',
        color: '#22C55E', fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600, letterSpacing: '0.06em',
      }}>✓ présenté</button>
      <button onClick={() => onChange('no_show')} style={{
        padding: '4px 9px', borderRadius: 99, cursor: 'pointer',
        background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.30)',
        color: '#EF4444', fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600, letterSpacing: '0.06em',
      }}>✗ absent</button>
    </div>
  );
}

function SecretaryAgenda() {
  const [outcomes, setOutcomes] = React.useState(
    Object.fromEntries(SECR_APPTS.map(a => [a.uid, a.outcome]))
  );
  const dispatched = SECR_APPTS.filter(a => outcomes[a.uid] !== null).length;

  return (
    <DashboardLayout
      role="secretary" active="agenda" onChange={() => {}}
      user={SECRETARY_USER}
      breadcrumb="agenda · 10 mai 2026"
      title="Agenda — feedback ML"
      subtitle="Confirmation des résultats pour le re-entraînement du modèle no-show"
      actions={[
        <DashButton key="d" kind="solid" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18"/></svg>}>10 mai 2026</DashButton>,
        <DashButton key="b" kind="gradient" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12l5 5L20 7"/></svg>}>Soumettre lot ({dispatched}/{SECR_APPTS.length})</DashButton>,
      ]}
    >
      <div style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
        <div style={{ flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Total RDV jour</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 600, color: 'var(--t0)', marginTop: 2 }}>{SECR_APPTS.length}</div>
        </div>
        <div style={{ flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Feedback fourni</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 600, color: '#22C55E', marginTop: 2 }}>{dispatched}</div>
        </div>
        <div style={{ flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>En attente</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 600, color: '#F59E0B', marginTop: 2 }}>{SECR_APPTS.length - dispatched}</div>
        </div>
        <div style={{ flex: 2, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Modèle XGBoost</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 4 }}>
            <span style={{ fontFamily: 'var(--f-display)', fontSize: 22, fontWeight: 600, color: 'var(--t0)' }}>v2.1</span>
            <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: '#22C55E' }}>AUC 0.847</span>
            <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t2)' }}>F1 0.79</span>
            <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)' }}>réentr. il y a 4h</span>
          </div>
        </div>
      </div>

      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '90px 1fr 160px 130px 1fr',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
          borderBottom: '1px solid var(--line)',
        }}>
          <div>Heure</div>
          <div>Patient · médecin</div>
          <div>Prédit no-show</div>
          <div>Statut auto</div>
          <div>Résultat réel · feedback</div>
        </div>
        {SECR_APPTS.map((a, i) => (
          <div key={a.uid} style={{
            display: 'grid', gridTemplateColumns: '90px 1fr 160px 130px 1fr',
            padding: '13px 18px', alignItems: 'center',
            borderBottom: i < SECR_APPTS.length - 1 ? '1px solid var(--line)' : 'none',
          }}>
            <div style={{ fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 500, color: 'var(--t0)' }}>{a.time}</div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>{a.name}</div>
              <div style={{ fontSize: 11.5, color: 'var(--t2)' }}>{a.doctor} · <span style={{ fontFamily: 'var(--f-mono)', color: 'var(--t3)' }}>{a.uid}</span></div>
            </div>
            <div><RiskPill level={a.risk} prob={a.prob}/></div>
            <div>
              <StatusPill tone={a.risk === 'danger' ? 'failed' : a.risk === 'warn' ? 'pending' : 'sent'}
                label={a.risk === 'danger' ? 'À rappeler' : a.risk === 'warn' ? 'SMS envoyé' : 'Confirmé'}/>
            </div>
            <div><FeedbackPill outcome={outcomes[a.uid]} onChange={(v) => setOutcomes(o => ({ ...o, [a.uid]: v }))}/></div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 16, padding: '12px 16px',
        background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.30)',
        borderRadius: 10, display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{ color: '#A78BFA' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>
        </div>
        <div style={{ flex: 1, fontSize: 12.5, color: 'var(--t1)' }}>
          Chaque feedback alimente directement le ré-entraînement nocturne du modèle XGBoost. Les données sont anonymisées et soumises à <span style={{ fontFamily: 'var(--f-mono)', color: '#A78BFA' }}>POST /predict/feedback</span>.
        </div>
      </div>
    </DashboardLayout>
  );
}

// ───────────────── CRM Tasks ─────────────────
const CRM_TASKS = [
  { uid: 'a1b2c3d4', name: 'Ahmed Benali', time: '09:00', status: 'sent',    error: null,                  attempts: 1, sf: 'A-2814' },
  { uid: 'e5f6g7h8', name: 'Salma Idrissi', time: '09:30', status: 'sent',    error: null,                  attempts: 1, sf: 'A-2815' },
  { uid: 'i9j0k1l2', name: 'Karim Ouahbi',  time: '10:00', status: 'failed',  error: 'Timeout (30s)',       attempts: 3, sf: null },
  { uid: 'm3n4o5p6', name: 'Fatima El Amrani', time: '10:30', status: 'pending', error: null,               attempts: 0, sf: null },
  { uid: 'q7r8s9t0', name: 'Youssef Tazi',  time: '11:00', status: 'cb',      error: 'Circuit breaker open',attempts: 5, sf: null },
  { uid: 'u1v2w3x4', name: 'Nadia Berrada', time: '11:30', status: 'sent',    error: null,                  attempts: 1, sf: 'A-2818' },
  { uid: 'y5z6a7b8', name: 'Hamza Saidi',   time: '14:00', status: 'skipped', error: 'consent OFF (NLP)',   attempts: 0, sf: null },
  { uid: 'c9d0e1f2', name: 'Imane Lahlou',  time: '14:30', status: 'pending', error: null,                  attempts: 0, sf: null },
];

const CRM_LABELS = {
  pending: 'En attente',
  sent:    'Synchronisé',
  failed:  'Échec',
  skipped: 'Ignoré',
  cb:      'Circuit ouvert',
};

function SecretaryCrm() {
  const [filter, setFilter] = React.useState('all');
  const [tasks, setTasks] = React.useState(CRM_TASKS);

  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.status === filter);
  const counts = tasks.reduce((acc, t) => { acc[t.status] = (acc[t.status] || 0) + 1; return acc; }, {});

  const retry = (uid) => {
    setTasks(prev => prev.map(t => t.uid === uid ? { ...t, status: 'pending', attempts: t.attempts + 1, error: null } : t));
  };

  return (
    <DashboardLayout
      role="secretary" active="crm" onChange={() => {}}
      user={SECRETARY_USER}
      breadcrumb="intégrations · salesforce"
      title="Tâches CRM Salesforce"
      subtitle="Synchronisation automatique des RDV · Sprint 6 · circuit breaker actif"
      actions={[
        <DashButton key="r" kind="solid" small icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5"/></svg>}>Actualiser</DashButton>,
        <DashButton key="e" kind="gradient" small>Exporter CSV</DashButton>,
      ]}
    >
      {/* status row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        {[
          { key: 'all',     label: 'Tous',    count: tasks.length, tone: 'info' },
          { key: 'sent',    label: 'Envoyés', count: counts.sent || 0, tone: 'sent' },
          { key: 'pending', label: 'En attente', count: counts.pending || 0, tone: 'pending' },
          { key: 'failed',  label: 'Échecs', count: counts.failed || 0, tone: 'failed' },
          { key: 'cb',      label: 'CB ouverts', count: counts.cb || 0, tone: 'cb' },
          { key: 'skipped', label: 'Ignorés', count: counts.skipped || 0, tone: 'skipped' },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)} style={{
            padding: '8px 14px', borderRadius: 99, cursor: 'pointer',
            background: filter === f.key ? 'var(--ai-grad-soft)' : 'var(--s1)',
            border: `1px solid ${filter === f.key ? 'rgba(139,92,246,0.55)' : 'var(--line)'}`,
            color: 'var(--t0)', fontFamily: 'var(--f-body)', fontSize: 12,
            display: 'inline-flex', alignItems: 'center', gap: 8,
          }}>
            <span>{f.label}</span>
            <span style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
              color: 'var(--t1)',
              background: 'var(--s2)', padding: '1px 7px', borderRadius: 99,
            }}>{f.count}</span>
          </button>
        ))}
      </div>

      {/* circuit breaker banner */}
      {counts.cb > 0 && (
        <div style={{
          padding: '12px 16px', borderRadius: 12,
          background: 'linear-gradient(135deg, rgba(244,63,94,0.10), rgba(244,63,94,0.04))',
          border: '1px solid rgba(244,63,94,0.40)',
          marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'rgba(244,63,94,0.18)', border: '1px solid rgba(244,63,94,0.40)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#F43F5E',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 600 }}>Circuit breaker ouvert · API Salesforce</div>
            <div style={{ fontSize: 12, color: 'var(--t2)', marginTop: 2 }}>
              Re-fermeture automatique dans <span style={{ fontFamily: 'var(--f-mono)', color: '#F43F5E' }}>02:14</span> · taux d'erreur 87% sur 5 min
            </div>
          </div>
          <DashButton kind="solid" small>Forcer la fermeture</DashButton>
        </div>
      )}

      {/* table */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '70px 1fr 1fr 120px 1fr 90px 110px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
          borderBottom: '1px solid var(--line)',
        }}>
          <div>RDV</div>
          <div>Patient</div>
          <div>Salesforce ID</div>
          <div>Statut</div>
          <div>Erreur</div>
          <div>Tentatives</div>
          <div></div>
        </div>
        {filtered.map((t, i) => (
          <div key={t.uid} style={{
            display: 'grid', gridTemplateColumns: '70px 1fr 1fr 120px 1fr 90px 110px',
            padding: '13px 18px', alignItems: 'center',
            borderBottom: i < filtered.length - 1 ? '1px solid var(--line)' : 'none',
          }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>{t.time}</div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>{t.name}</div>
              <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>uid · {t.uid}</div>
            </div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: t.sf ? 'var(--t1)' : 'var(--t4)' }}>
              {t.sf ? `sf · ${t.sf}` : '— '}
            </div>
            <div>
              <StatusPill
                tone={t.status}
                label={CRM_LABELS[t.status]}
                pulse={t.status === 'pending' || t.status === 'cb'}
              />
            </div>
            <div style={{ fontSize: 11.5, color: t.error ? '#FCA5A5' : 'var(--t4)', fontFamily: t.error ? 'var(--f-mono)' : 'inherit' }}>
              {t.error || '—'}
            </div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: t.attempts >= 3 ? '#F59E0B' : 'var(--t2)' }}>
              {t.attempts}/5
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              {(t.status === 'failed' || t.status === 'cb') && (
                <button onClick={() => retry(t.uid)} style={{
                  padding: '5px 10px', borderRadius: 6, cursor: 'pointer',
                  background: 'var(--ai-grad-soft)', border: '1px solid rgba(139,92,246,0.40)',
                  color: '#C4B5FD', fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                  letterSpacing: '0.08em', textTransform: 'uppercase',
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M3 12a9 9 0 0115-6.7L21 8"/></svg>
                  Retry
                </button>
              )}
              {t.status === 'pending' && (
                <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>en file…</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}

Object.assign(window, { SecretaryAgenda, SecretaryCrm });

}

// ─── admin.jsx ───
{
// Admin screens: Audit Logs (RGPD), Users, Rerank Eval

const { DashboardLayout, DashButton, StatusPill } = window;
const ADMIN_USER = { initial: 'A', name: 'admin@medisense.ai' };

// ───────────────── Audit Logs ─────────────────
const AUDIT_LOGS = [
  { ts: '10/05 14:32:18', action: 'LOGIN',   role: 'admin',     resource: 'user',    target: 'a1b2c3d4', ip: '127.0.0.1',  ua: 'Chrome 124 · macOS' },
  { ts: '10/05 14:31:02', action: 'EXPORT',  role: 'admin',     resource: 'patient', target: 'e5f6g7h8', ip: '127.0.0.1',  ua: 'Chrome 124 · macOS' },
  { ts: '10/05 14:28:44', action: 'WRITE',   role: 'doctor',    resource: 'dpa',     target: 'q7r8s9t0', ip: '10.0.2.18',  ua: 'Edge 119 · Windows' },
  { ts: '10/05 14:21:09', action: 'READ',    role: 'doctor',    resource: 'patient', target: 'a1b2c3d4', ip: '10.0.2.18',  ua: 'Edge 119 · Windows' },
  { ts: '10/05 13:54:30', action: 'CONSENT', role: 'patient',   resource: 'consent', target: 'm3n4o5p6', ip: '105.66.4.81', ua: 'Flutter Mobile · iOS 17' },
  { ts: '10/05 13:42:11', action: 'DELETE',  role: 'admin',     resource: 'patient', target: 'z9y8x7w6', ip: '127.0.0.1',  ua: 'Chrome 124 · macOS' },
  { ts: '10/05 13:38:55', action: 'WRITE',   role: 'secretary', resource: 'feedback',target: 'i9j0k1l2', ip: '10.0.2.04',  ua: 'Firefox 122 · Windows' },
  { ts: '10/05 13:12:00', action: 'LOGIN',   role: 'doctor',    resource: 'user',    target: 'doctor-merrouni', ip: '10.0.2.18', ua: 'Edge 119 · Windows' },
  { ts: '10/05 12:48:22', action: 'READ',    role: 'patient',   resource: 'iot',     target: 'a1b2c3d4', ip: '105.66.4.81', ua: 'Flutter Mobile · iOS 17' },
  { ts: '10/05 12:31:14', action: 'EXPORT',  role: 'patient',   resource: 'data',    target: 'a1b2c3d4', ip: '105.66.4.81', ua: 'Flutter Mobile · iOS 17' },
  { ts: '10/05 11:55:08', action: 'CONSENT', role: 'patient',   resource: 'consent', target: 'e5f6g7h8', ip: '105.66.4.92', ua: 'Flutter Mobile · Android 14' },
];

const ACTION_TONES = {
  LOGIN:   { c: '#38BDF8', bg: 'rgba(56,189,248,0.10)',  bd: 'rgba(56,189,248,0.40)',  glyph: '⊙' },
  READ:    { c: '#94A3B8', bg: 'rgba(148,163,184,0.10)', bd: 'rgba(148,163,184,0.30)', glyph: '○' },
  WRITE:   { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)',   glyph: '●' },
  DELETE:  { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)',   glyph: '✕' },
  EXPORT:  { c: '#A78BFA', bg: 'rgba(167,139,250,0.10)', bd: 'rgba(167,139,250,0.40)', glyph: '↓' },
  CONSENT: { c: '#F59E0B', bg: 'rgba(245,158,11,0.10)',  bd: 'rgba(245,158,11,0.40)',  glyph: '⚙' },
};

function ActionBadge({ action }) {
  const a = ACTION_TONES[action];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px',
      borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 9.5, fontWeight: 600,
      letterSpacing: '0.10em',
      color: a.c, background: a.bg, border: `1px solid ${a.bd}`,
    }}>{a.glyph} {action}</span>
  );
}

function AdminAudit() {
  const [expanded, setExpanded] = React.useState(null);
  return (
    <DashboardLayout
      role="admin" active="audit" onChange={() => {}}
      user={ADMIN_USER}
      breadcrumb="conformité · journal immuable"
      title="Logs d'audit RGPD"
      subtitle="Article 30 RGPD · 4 821 entrées · stocké chiffré (AES-256) · backup quotidien"
      actions={[
        <DashButton key="f" kind="solid" small icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 3H2l8 9v7l4 2v-9l8-9z"/></svg>}>Filtrer</DashButton>,
        <DashButton key="e" kind="solid" small icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>}>Export CSV</DashButton>,
      ]}
    >
      {/* metric strip */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
        {[
          { label: 'Entrées 24h', value: '342', tone: '#A78BFA' },
          { label: 'Suppressions', value: '3',   tone: '#EF4444' },
          { label: 'Exports RGPD', value: '12',  tone: '#A78BFA' },
          { label: 'Échecs auth.',  value: '7',   tone: '#F97316' },
          { label: 'Hash chain',   value: 'OK',  tone: '#22C55E', mono: true },
        ].map(m => (
          <div key={m.label} style={{ flex: 1, padding: 14, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{m.label}</div>
            <div style={{
              fontFamily: m.mono ? 'var(--f-mono)' : 'var(--f-display)',
              fontSize: m.mono ? 22 : 28, fontWeight: 600, color: m.tone, marginTop: 4,
              letterSpacing: m.mono ? 0 : '-0.02em',
            }}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* search */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <input
            placeholder="Rechercher par UUID patient, IP, ressource…"
            style={{
              width: '100%', padding: '10px 12px 10px 36px',
              background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 10,
              color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12, outline: 'none',
            }}
          />
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }}>
            <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>
          </svg>
        </div>
        {['Toutes', 'LOGIN', 'WRITE', 'DELETE', 'EXPORT', 'CONSENT'].map((f, i) => (
          <button key={f} style={{
            padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
            background: i === 0 ? 'var(--ai-grad-soft)' : 'var(--s1)',
            border: `1px solid ${i === 0 ? 'rgba(139,92,246,0.45)' : 'var(--line)'}`,
            color: 'var(--t1)', fontFamily: 'var(--f-mono)', fontSize: 10.5,
            letterSpacing: '0.08em', fontWeight: 600,
          }}>{f}</button>
        ))}
      </div>

      {/* table */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '170px 110px 100px 110px 1fr 130px 30px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
          borderBottom: '1px solid var(--line)',
        }}>
          <div>Horodatage</div>
          <div>Action</div>
          <div>Rôle</div>
          <div>Ressource</div>
          <div>Cible (uuid)</div>
          <div>IP</div>
          <div></div>
        </div>
        {AUDIT_LOGS.map((l, i) => {
          const isExp = expanded === i;
          return (
            <React.Fragment key={i}>
              <button onClick={() => setExpanded(isExp ? null : i)} style={{
                all: 'unset', cursor: 'pointer', width: '100%',
                display: 'grid', gridTemplateColumns: '170px 110px 100px 110px 1fr 130px 30px',
                padding: '11px 18px', alignItems: 'center',
                borderBottom: '1px solid var(--line)',
                transition: 'background .14s',
                background: isExp ? 'rgba(99,102,241,0.06)' : 'transparent',
              }}>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>{l.ts}</div>
                <div><ActionBadge action={l.action}/></div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{l.role}</div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>{l.resource}</div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t2)' }}>{l.target}</div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)' }}>{l.ip}</div>
                <div style={{ color: 'var(--t3)', transform: isExp ? 'rotate(90deg)' : 'rotate(0)', transition: 'transform .2s' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 6l6 6-6 6"/></svg>
                </div>
              </button>
              {isExp && (
                <div style={{
                  padding: '14px 18px 14px 188px', background: 'rgba(15,22,35,0.50)',
                  borderBottom: '1px solid var(--line)',
                  display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16,
                  fontFamily: 'var(--f-mono)', fontSize: 11,
                }}>
                  <div>
                    <div style={{ fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>User Agent</div>
                    <div style={{ color: 'var(--t1)' }}>{l.ua}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>Hash chain</div>
                    <div style={{ color: '#22C55E' }}>0x7f3a · linked ✓</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>Conformité</div>
                    <div style={{ color: 'var(--t1)' }}>RGPD Art. 30 · Loi 09-08 ✓</div>
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* pagination */}
      <div style={{
        marginTop: 14, padding: '10px 16px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)' }}>
          1–11 sur 4 821 · Page 1 / 439
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <DashButton kind="solid" small>◀ précédent</DashButton>
          <DashButton kind="solid" small>suivant ▶</DashButton>
        </div>
      </div>
    </DashboardLayout>
  );
}

// ───────────────── Users ─────────────────
const USERS = [
  { email: 'admin@medisense.ai',     role: 'admin',     active: true,  last: '14:32 aujourd\'hui',     mfa: true },
  { email: 'dr.merrouni@clinique.ma',role: 'doctor',    active: true,  last: '14:21 aujourd\'hui',     mfa: true },
  { email: 'dr.bennis@clinique.ma',  role: 'doctor',    active: true,  last: 'hier · 18:42',           mfa: true },
  { email: 'l.bennis@clinique.ma',   role: 'secretary', active: true,  last: '13:38 aujourd\'hui',     mfa: false },
  { email: 'a.benali@email.ma',      role: 'patient',   active: true,  last: '13:42 aujourd\'hui',     mfa: false },
  { email: 's.idrissi@email.ma',     role: 'patient',   active: true,  last: '8 mai · 09:12',          mfa: false },
  { email: 'old.account@clinique.ma',role: 'doctor',    active: false, last: 'il y a 4 mois',          mfa: false },
];

function AdminUsers() {
  const [showCreate, setShowCreate] = React.useState(false);
  return (
    <DashboardLayout
      role="admin" active="users" onChange={() => {}}
      user={ADMIN_USER}
      breadcrumb="comptes · gestion"
      title="Gestion des utilisateurs"
      subtitle="Création, désactivation, MFA · 7 comptes au total"
      actions={[
        <DashButton key="i" kind="solid" small>Inviter par email</DashButton>,
        <DashButton key="c" kind="gradient" small onClick={() => setShowCreate(true)} icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14"/></svg>}>Créer un compte</DashButton>,
      ]}
    >
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '40px 1.5fr 110px 90px 80px 1fr 60px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
          borderBottom: '1px solid var(--line)',
        }}>
          <div></div>
          <div>Email</div>
          <div>Rôle</div>
          <div>Statut</div>
          <div>MFA</div>
          <div>Dernière connexion</div>
          <div></div>
        </div>
        {USERS.map((u, i) => (
          <div key={u.email} style={{
            display: 'grid', gridTemplateColumns: '40px 1.5fr 110px 90px 80px 1fr 60px',
            padding: '13px 18px', alignItems: 'center',
            borderBottom: i < USERS.length - 1 ? '1px solid var(--line)' : 'none',
            opacity: u.active ? 1 : 0.55,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 99,
              background: u.role === 'admin' ? 'var(--ai-grad)' : u.role === 'doctor' ? 'rgba(56,189,248,0.20)' : u.role === 'secretary' ? 'rgba(167,139,250,0.20)' : 'rgba(34,197,94,0.20)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--f-display)', fontSize: 12, fontWeight: 600,
              color: u.role === 'admin' ? '#fff' : u.role === 'doctor' ? '#38BDF8' : u.role === 'secretary' ? '#A78BFA' : '#22C55E',
            }}>{u.email[0].toUpperCase()}</div>
            <div style={{ fontSize: 13, color: 'var(--t0)', fontFamily: 'var(--f-mono)' }}>{u.email}</div>
            <div>
              <span style={{
                fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                letterSpacing: '0.10em', textTransform: 'uppercase',
                padding: '3px 9px', borderRadius: 99,
                color: u.role === 'admin' ? '#fff' : u.role === 'doctor' ? '#38BDF8' : u.role === 'secretary' ? '#A78BFA' : '#22C55E',
                background: u.role === 'admin' ? 'rgba(139,92,246,0.20)' : u.role === 'doctor' ? 'rgba(56,189,248,0.10)' : u.role === 'secretary' ? 'rgba(167,139,250,0.10)' : 'rgba(34,197,94,0.10)',
                border: `1px solid ${u.role === 'admin' ? 'rgba(139,92,246,0.40)' : u.role === 'doctor' ? 'rgba(56,189,248,0.40)' : u.role === 'secretary' ? 'rgba(167,139,250,0.40)' : 'rgba(34,197,94,0.40)'}`,
              }}>{u.role}</span>
            </div>
            <div>
              <StatusPill tone={u.active ? 'sent' : 'skipped'} label={u.active ? 'Actif' : 'Désactivé'}/>
            </div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: u.mfa ? '#22C55E' : 'var(--t4)' }}>
              {u.mfa ? '✓ activé' : '— off'}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--t2)' }}>{u.last}</div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={{
                width: 28, height: 28, borderRadius: 6, cursor: 'pointer',
                background: 'transparent', border: '1px solid var(--line)',
                color: 'var(--t3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
              </button>
            </div>
          </div>
        ))}
      </div>

      {showCreate && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 100,
          background: 'rgba(0,0,0,0.60)', backdropFilter: 'blur(6px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowCreate(false)}>
          <div onClick={(e) => e.stopPropagation()} style={{
            width: 420, background: 'var(--s1)', border: '1px solid var(--line-strong)',
            borderRadius: 16, padding: 24, boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
          }}>
            <h3 style={{ fontFamily: 'var(--f-display)', fontSize: 18, fontWeight: 600, margin: '0 0 14px' }}>Créer un compte</h3>
            <div style={{ display: 'grid', gap: 12 }}>
              <input placeholder="email@medisense.ma" style={{
                padding: 10, background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
                color: 'var(--t0)', fontFamily: 'var(--f-body)', fontSize: 13, outline: 'none',
              }}/>
              <select style={{
                padding: 10, background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
                color: 'var(--t0)', fontSize: 13,
              }}>
                <option>doctor</option><option>secretary</option><option>admin</option>
              </select>
              <label style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--t1)' }}>
                <input type="checkbox" defaultChecked/> Forcer l'activation MFA
              </label>
              <label style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--t1)' }}>
                <input type="checkbox" defaultChecked/> Envoyer email d'invitation
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 18, justifyContent: 'flex-end' }}>
              <DashButton kind="ghost" onClick={() => setShowCreate(false)}>Annuler</DashButton>
              <DashButton kind="gradient" onClick={() => setShowCreate(false)}>Créer le compte</DashButton>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

// ───────────────── Rerank Eval ─────────────────
const RERANK_RRF = [
  { rank: 1, doc: 'Cardiologie · Insuffisance cardiaque ESC 2024', score: 0.94 },
  { rank: 2, doc: 'Protocole ECG · Douleur thoracique aiguë',       score: 0.91 },
  { rank: 3, doc: 'Chest pain triage · ESC guidelines',             score: 0.87 },
  { rank: 4, doc: 'BNP/NT-proBNP · interprétation clinique',        score: 0.82 },
  { rank: 5, doc: 'Furosémide · indications & posologie',           score: 0.78 },
];
const RERANK_CE = [
  { rank: 1, doc: 'Cardiologie · Insuffisance cardiaque ESC 2024', score: 0.94 },
  { rank: 2, doc: 'Protocole ECG · Douleur thoracique aiguë',       score: 0.91 },
  { rank: 3, doc: 'HF guidelines · ACC/AHA 2023',                   score: 0.87 },
  { rank: 4, doc: 'Chest pain triage · ESC guidelines',             score: 0.83 },
  { rank: 5, doc: 'BNP/NT-proBNP · interprétation clinique',        score: 0.79 },
];

function RankColumn({ title, sub, items, color }) {
  return (
    <div style={{
      flex: 1, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
      padding: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ width: 8, height: 8, borderRadius: 99, background: color, boxShadow: `0 0 6px ${color}` }}/>
        <div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 600, color: 'var(--t0)' }}>{title}</div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>{sub}</div>
        </div>
      </div>
      <div style={{ display: 'grid', gap: 8 }}>
        {items.map(it => (
          <div key={it.rank} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
            background: 'var(--s2)', borderRadius: 8, border: '1px solid var(--line)',
          }}>
            <div style={{
              width: 22, height: 22, borderRadius: 99,
              background: 'var(--s3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600, color: 'var(--t1)',
            }}>{it.rank}</div>
            <div style={{ flex: 1, fontSize: 12, color: 'var(--t1)' }}>{it.doc}</div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color, fontWeight: 600 }}>{it.score.toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AdminRerank() {
  return (
    <DashboardLayout
      role="admin" active="rerank" onChange={() => {}}
      user={ADMIN_USER}
      breadcrumb="système · diagnostic rag"
      title="Évaluation Rerank — RRF vs Cross-Encoder"
      subtitle="Diagnostic qualité retrieval · sprint 3 · admin only"
    >
      {/* query input */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
        padding: 18, marginBottom: 18,
      }}>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
          Requête de test
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            defaultValue="douleurs thoraciques essoufflement insuffisance cardiaque"
            style={{
              flex: 1, padding: '11px 14px',
              background: 'var(--s2)', border: '1px solid var(--line-strong)', borderRadius: 10,
              color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12, outline: 'none',
            }}
          />
          <select style={{
            padding: '0 14px', background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 10,
            color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12,
          }}>
            <option>Top-5</option><option>Top-10</option><option>Top-20</option>
          </select>
          <DashButton kind="gradient" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M5 3l14 9-14 9z"/></svg>}>Lancer</DashButton>
        </div>
      </div>

      {/* metrics */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
        {[
          { label: 'Spearman ρ', value: '0.87', sub: 'corrélation des rangs',  c: '#22C55E' },
          { label: 'Top-3 overlap', value: '2/3', sub: 'documents communs',     c: '#A78BFA' },
          { label: 'MRR (RRF)',  value: '0.82', sub: 'mean reciprocal rank',   c: '#38BDF8' },
          { label: 'Latence CE', value: '142ms', sub: 'ms par requête',        c: '#F59E0B' },
        ].map(m => (
          <div key={m.label} style={{ flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{m.label}</div>
            <div style={{ fontFamily: 'var(--f-display)', fontSize: 28, fontWeight: 600, color: m.c, marginTop: 4, letterSpacing: '-0.02em' }}>{m.value}</div>
            <div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 2 }}>{m.sub}</div>
          </div>
        ))}
      </div>

      {/* two columns */}
      <div style={{ display: 'flex', gap: 14 }}>
        <RankColumn title="RRF · Reciprocal Rank Fusion" sub="rapide · pas de modèle" items={RERANK_RRF} color="#A78BFA"/>
        <RankColumn title="Cross-Encoder · BAAI/bge-reranker" sub="précis · 142ms/req" items={RERANK_CE} color="#38BDF8"/>
      </div>

      <div style={{
        marginTop: 18, padding: '12px 16px',
        background: 'rgba(56,189,248,0.06)', border: '1px solid rgba(56,189,248,0.30)',
        borderRadius: 10, display: 'flex', alignItems: 'flex-start', gap: 12,
      }}>
        <div style={{ color: '#38BDF8', flexShrink: 0, marginTop: 2 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>
        </div>
        <div style={{ fontSize: 12, color: 'var(--t1)', lineHeight: 1.55 }}>
          <strong style={{ color: 'var(--t0)' }}>Recommandation :</strong> sur cette requête, RRF maintient 2/3 des résultats du cross-encoder dans le top-3 pour une latence 14× inférieure. Garder RRF en production · CE uniquement pour l'admin tooling.
        </div>
      </div>
    </DashboardLayout>
  );
}

Object.assign(window, { AdminAudit, AdminUsers, AdminRerank });

}

// ─── app.jsx ───
{
// Top-level App — Design Canvas with all 4 roles + patient mobile prototype

const {
  DesignCanvas, DCSection, DCArtboard, DCPostIt,
  IOSDevice,
  TweaksPanel, useTweaks, TweakSection, TweakRadio, TweakToggle, TweakButton,
  IconChat, IconHeart, IconCalendar, IconUser, IconShield, IconHistory, IconBell,
  SplashScreen, OnboardingScreen, LoginScreen,
  ChatScreen, VitalsScreen, NoDeviceScreen, AppointmentsScreen, ProfileScreen,
  ConsentScreen, HistoryScreen, RemindersScreen,
  DoctorLogin, DoctorAgenda, DoctorDpa,
  SecretaryAgenda, SecretaryCrm,
  AdminAudit, AdminUsers, AdminRerank,
} = window;

// Mini phone wrapper to embed inside artboards (skips heavy IOSDevice frame)
function PhoneFrame({ children, label }) {
  return (
    <div style={{
      width: 320, height: 680, borderRadius: 38,
      background: '#0A0D14',
      border: '8px solid #1a1f2e',
      boxShadow: '0 30px 80px rgba(0,0,0,0.4), inset 0 0 0 1px rgba(255,255,255,0.05)',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* status bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 44, zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 22px',
        fontFamily: 'var(--f-body)', fontSize: 12, fontWeight: 600, color: '#fff',
        pointerEvents: 'none',
      }}>
        <span>9:41</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <svg width="14" height="9" viewBox="0 0 14 9" fill="none"><path d="M1 7h2v1H1zM4 5h2v3H4zM7 3h2v5H7zM10 1h2v7h-2z" fill="#fff"/></svg>
          <svg width="20" height="10" viewBox="0 0 20 10" fill="none"><rect x="1" y="1" width="16" height="8" rx="2" stroke="#fff" opacity="0.6"/><rect x="3" y="3" width="11" height="4" rx="1" fill="#fff"/><rect x="18" y="4" width="1.5" height="2" fill="#fff" opacity="0.6"/></svg>
        </span>
      </div>
      {/* dynamic island */}
      <div style={{
        position: 'absolute', top: 11, left: '50%', transform: 'translateX(-50%)',
        width: 100, height: 28, borderRadius: 99, background: '#000', zIndex: 101,
      }}/>
      {/* content */}
      <div style={{ position: 'absolute', inset: 0 }}>{children}</div>
      {/* home indicator */}
      <div style={{
        position: 'absolute', bottom: 8, left: '50%', transform: 'translateX(-50%)',
        width: 120, height: 4, borderRadius: 99, background: 'rgba(255,255,255,0.45)', zIndex: 100,
      }}/>
    </div>
  );
}

// Browser chrome wrapper for desktop dashboards
function BrowserFrame({ url, role, children, w = 1280, h = 800 }) {
  return (
    <div style={{
      width: w, height: h, borderRadius: 12,
      background: '#0a0d14',
      boxShadow: '0 30px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)',
      overflow: 'hidden', display: 'flex', flexDirection: 'column',
    }}>
      <div style={{
        height: 36, background: '#1a1f2e', display: 'flex', alignItems: 'center',
        padding: '0 14px', gap: 8, borderBottom: '1px solid rgba(255,255,255,0.05)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {['#FF5F56','#FFBD2E','#27C93F'].map(c => (
            <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }}/>
          ))}
        </div>
        <div style={{
          flex: 1, height: 22, marginLeft: 12, marginRight: 12,
          background: '#0a0d14', borderRadius: 6,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--f-mono)', fontSize: 10, color: '#94A3B8',
          letterSpacing: '0.04em',
          border: '1px solid rgba(255,255,255,0.05)', padding: '0 12px',
        }}>
          <span style={{ color: '#22C55E', marginRight: 6 }}>●</span>
          medisense.ma{url}
        </div>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 9, color: '#64748B',
          letterSpacing: '0.12em', textTransform: 'uppercase',
        }}>{role}</div>
      </div>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>{children}</div>
    </div>
  );
}

function App() {
  const TWEAK_DEFAULS = /*EDITMODE-BEGIN*/{
    "patient_screen": "chat",
    "patient_urgent": true,
    "patient_paired": true
  }/*EDITMODE-END*/;
  const [t, setTweak] = useTweaks(TWEAK_DEFAULS);

  // Patient mobile main app screen (which tab is shown in App artboard)
  const renderPatientScreen = (s) => {
    if (s === 'splash') return <SplashScreen onDone={() => {}}/>;
    if (s === 'onboarding') return <OnboardingScreen onDone={() => {}}/>;
    if (s === 'login') return <LoginScreen onLogin={() => {}}/>;
    if (s === 'consent') return <ConsentScreen onDone={() => {}}/>;
    if (s === 'chat') return <ChatScreen initialUrgent={t.patient_urgent}/>;
    if (s === 'chat_empty') return <ChatScreen initialUrgent={false} initialEmpty/>;
    if (s === 'vitals') return t.patient_paired ? <VitalsScreen/> : <NoDeviceScreen/>;
    if (s === 'agenda') return <AppointmentsScreen/>;
    if (s === 'profile') return <ProfileScreen/>;
    if (s === 'history') return <HistoryScreen/>;
    if (s === 'reminders') return <RemindersScreen/>;
    return null;
  };

  return (
    <>
      <DesignCanvas>
        {/* ─────────── PATIENT MOBILE ─────────── */}
        <DCSection id="patient-flow" title="Patient · Onboarding & Auth"
          subtitle="Flutter mobile · iOS/Android · FR/AR/Darija">
          <DCArtboard id="p-splash" label="01 · Splash" width={320} height={680}>
            <PhoneFrame><SplashScreen onDone={() => {}}/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-onboard" label="02 · Onboarding" width={320} height={680}>
            <PhoneFrame><OnboardingScreen onDone={() => {}}/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-login" label="03 · Login" width={320} height={680}>
            <PhoneFrame><LoginScreen onLogin={() => {}}/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-consent" label="04 · Consentement RGPD" width={320} height={680}>
            <PhoneFrame><ConsentScreen onDone={() => {}}/></PhoneFrame>
          </DCArtboard>
          <DCPostIt x={1320} y={40}>
            Conformité <strong>Loi 09-08</strong> exigée — l'écran consentement est un step bloquant après le login. Toggles distincts par usage (data / IoT / ML / urgence SAMU).
          </DCPostIt>
        </DCSection>

        <DCSection id="patient-app" title="Patient · App principale"
          subtitle="Bottom-tab navigation · streaming RAG · IoT vitals">
          <DCArtboard id="p-chat-empty" label="Chat · empty state" width={320} height={680}>
            <PhoneFrame><ChatScreen initialUrgent={false} initialEmpty/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-chat-urgent" label="Chat · urgence détectée ★" width={320} height={680}>
            <PhoneFrame><ChatScreen initialUrgent/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-vitals" label="Vitaux IoT" width={320} height={680}>
            <PhoneFrame><VitalsScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-vitals-empty" label="Vitaux · pas d'appareil" width={320} height={680}>
            <PhoneFrame><NoDeviceScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-agenda" label="Agenda patient" width={320} height={680}>
            <PhoneFrame><AppointmentsScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-history" label="Historique convos" width={320} height={680}>
            <PhoneFrame><HistoryScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-reminders" label="Rappels traitement" width={320} height={680}>
            <PhoneFrame><RemindersScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-profile" label="Profil patient" width={320} height={680}>
            <PhoneFrame><ProfileScreen/></PhoneFrame>
          </DCArtboard>
          <DCPostIt x={2680} y={40}>
            <strong>★ centerpiece soutenance.</strong> Le chat urgence montre : streaming RAG + scoring confiance + bandeau SAMU 141 + voix. Démo idéale en live.
          </DCPostIt>
        </DCSection>

        {/* ─────────── DOCTOR ─────────── */}
        <DCSection id="doctor" title="Médecin · Web dashboard"
          subtitle="Next.js · console clinique · accès dossier patient assisté IA">
          <DCArtboard id="d-login" label="Login médecin" width={1280} height={800}>
            <BrowserFrame url="/login" role="doctor"><DoctorLogin/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="d-agenda" label="Agenda · risk-coded" width={1280} height={800}>
            <BrowserFrame url="/agenda" role="doctor"><DoctorAgenda/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="d-dpa" label="Résumé DPA · 3-col ★" width={1280} height={800}>
            <BrowserFrame url="/patients/a1b2c3d4" role="doctor"><DoctorDpa/></BrowserFrame>
          </DCArtboard>
          <DCPostIt x={4080} y={40}>
            Le DPA en 3 colonnes (timeline · résumé IA · sources) permet au médecin de valider en 30s. Le Dr. doit pouvoir contredire l'IA — bouton "rejeter" bien visible.
          </DCPostIt>
        </DCSection>

        {/* ─────────── SECRETARY ─────────── */}
        <DCSection id="secretary" title="Secrétaire · Web dashboard"
          subtitle="CRM tâches · feedback ML pour entraînement no-show">
          <DCArtboard id="s-agenda" label="Agenda + feedback" width={1280} height={800}>
            <BrowserFrame url="/agenda" role="secretary"><SecretaryAgenda/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="s-crm" label="CRM tâches IA" width={1280} height={800}>
            <BrowserFrame url="/crm" role="secretary"><SecretaryCrm/></BrowserFrame>
          </DCArtboard>
          <DCPostIt x={2720} y={40}>
            Le feedback "présenté/absent" ferme la boucle d'entraînement XGBoost no-show. C'est l'unique source de label terrain — UX pensée pour 1 clic.
          </DCPostIt>
        </DCSection>

        {/* ─────────── ADMIN ─────────── */}
        <DCSection id="admin" title="Admin · Web dashboard"
          subtitle="RGPD compliance · gestion utilisateurs · evaluation modèles">
          <DCArtboard id="a-audit" label="Logs RGPD ★" width={1280} height={800}>
            <BrowserFrame url="/admin/audit" role="admin"><AdminAudit/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="a-users" label="Utilisateurs" width={1280} height={800}>
            <BrowserFrame url="/admin/users" role="admin"><AdminUsers/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="a-rerank" label="Évaluation Rerank (BM25 vs Reranker)" width={1280} height={800}>
            <BrowserFrame url="/admin/rerank" role="admin"><AdminRerank/></BrowserFrame>
          </DCArtboard>
          <DCPostIt x={4080} y={40}>
            <strong>★ pièce maîtresse Loi 09-08.</strong> Logs immuables, exportables, chiffrés. Toute action sur donnée nominative = ligne. CNDP-ready.
          </DCPostIt>
        </DCSection>
      </DesignCanvas>

      <TweaksPanel title="Tweaks">
        <TweakSection label="États du Chat patient">
          <TweakToggle label="Urgence détectée (chat)" value={t.patient_urgent} onChange={(v) => setTweak('patient_urgent', v)}/>
          <TweakToggle label="Bracelet IoT appairé" value={t.patient_paired} onChange={(v) => setTweak('patient_paired', v)}/>
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);

}
