/**
 * Planche de contrôle des tokens « Ink & Signal » (refont phase 02).
 * Visible uniquement en dev : http://localhost:5173/?tokens
 * Utilise exclusivement les tokens — zéro hex (règle 1 de la charte).
 */
import { SERIES, signals, ink, line, text } from "@see/ui";
import "@see/ui";

const swatchStyle = (color: string): React.CSSProperties => ({
  width: "100%",
  height: 44,
  borderRadius: "var(--r-2)",
  border: "1px solid var(--border)",
  background: color,
});

const sectionStyle: React.CSSProperties = {
  padding: "var(--sp-5)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-4)",
  background: "var(--bg-surface)",
  display: "grid",
  gap: "var(--sp-3)",
};

const h2Style: React.CSSProperties = {
  margin: 0,
  fontSize: "var(--fs-13)",
  color: "var(--muted)",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const labelStyle: React.CSSProperties = {
  fontFamily: "var(--font-data)",
  fontSize: "var(--fs-11)",
  color: "var(--faint)",
  fontVariantNumeric: "tabular-nums",
};

function Swatches({ tokens }: { tokens: Record<string, string> }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: "var(--sp-3)" }}>
      {Object.entries(tokens).map(([name, value]) => (
        <div key={name} style={{ display: "grid", gap: 4 }}>
          <div style={swatchStyle(value)} />
          <span style={labelStyle}>{name}</span>
          <span style={{ ...labelStyle, color: "var(--faint)" }}>{value}</span>
        </div>
      ))}
    </div>
  );
}

export function TokenBoard() {
  const seriesTokens = Object.fromEntries(
    SERIES.map((s) => [s.name, s.color]),
  );
  const seriesFills = Object.fromEntries(
    SERIES.map((s) => [s.name, s.fill ?? "transparent"]),
  );

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--bg-root)",
        backgroundImage: "var(--trame)",
        backgroundSize: "var(--trame-background-size)",
        color: "var(--text)",
        fontFamily: "var(--font-ui)",
        padding: "var(--sp-6)",
        display: "grid",
        gap: "var(--sp-5)",
        maxWidth: 1180,
        margin: "0 auto",
      }}
    >
      <header>
        <p style={{ margin: 0, color: "var(--accent)", fontSize: "var(--fs-12)", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase" }}>
          Refont · phase 02
        </p>
        <h1 style={{ margin: "4px 0 0", fontSize: "var(--fs-30)", letterSpacing: "-0.02em" }}>
          Tokens « Ink & Signal »
        </h1>
        <p style={{ margin: "8px 0 0", color: "var(--muted)", fontSize: "var(--fs-14)" }}>
          Source de vérité : <code style={labelStyle}>packages/ui/src/tokens.css</code> — miroir TS généré{" "}
          <code style={labelStyle}>tokens.ts</code>. Fond : encre + trame 28px.
        </p>
      </header>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Encre & lignes (primitives)</h2>
        <Swatches tokens={{ ...ink, ...line, ...text }} />
        <p style={{ margin: 0, ...labelStyle }}>
          Valeurs affichées depuis le miroir généré <code>tokens.ts</code> — aucune hex littérale dans ce composant.
        </p>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Signaux</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "var(--sp-3)" }}>
          {Object.entries({ accent: signals.accent, ok: signals.ok, warn: signals.warn, danger: signals.danger }).map(([name, value]) => (
            <div key={name} style={{ display: "grid", gap: 4 }}>
              <div style={swatchStyle(value)} />
              <span style={labelStyle}>--{name} · {value}</span>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-3)" }}>
          {["--accent-a6", "--accent-a10", "--accent-a14", "--accent-a35", "--accent-a50", "--ok-a7", "--warn-a7", "--warn-a35", "--danger-a7", "--danger-a12", "--danger-a35", "--danger-a45"].map((t) => (
            <div key={t} style={{ display: "grid", gap: 4, width: 96 }}>
              <div style={{ ...swatchStyle(`var(${t})`), height: 24 }} />
              <span style={labelStyle}>{t}</span>
            </div>
          ))}
        </div>
        <p style={{ margin: 0, ...labelStyle }}>
          Règle : accent = interactif uniquement (focus, liens, CTA, onglet actif). JAMAIS couleur de série.
        </p>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Dataviz — 10 séries (validées daltonisme)</h2>
        <Swatches tokens={seriesTokens} />
        <h2 style={{ ...h2Style, marginTop: "var(--sp-2)" }}>Remplissages de distribution</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: "var(--sp-3)" }}>
          {Object.entries(seriesFills).map(([name, value]) => (
            <div key={name} style={{ display: "grid", gap: 4 }}>
              <div style={{ ...swatchStyle(value), height: 28 }} />
              <span style={labelStyle}>{name}-fill</span>
            </div>
          ))}
        </div>
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--r-3)", overflow: "hidden" }}>
          <svg viewBox="0 0 600 120" style={{ display: "block", width: "100%", background: "var(--bg-inset)" }} role="img" aria-label="Aperçu des 10 séries">
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
              <circle key={i} cx={30 + i * 60} cy={40} r={7} fill={SERIES[i].color} />
            ))}
            <line x1={20} y1={80} x2={580} y2={80} stroke="var(--chart-axis)" />
            <line x1={20} y1={100} x2={580} y2={100} stroke="var(--chart-zero)" strokeDasharray="5 4" />
            <text x={20} y={115} fill="var(--chart-label)" fontFamily="var(--font-data)" fontSize={10}>ticks mono tabulaire · --chart-axis / --chart-zero</text>
          </svg>
        </div>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Typographie</h2>
        <div style={{ display: "grid", gap: "var(--sp-2)" }}>
          <div style={{ fontSize: "var(--fs-30)", letterSpacing: "-0.02em" }}>Inter — UI · Aa 123 (fs-30)</div>
          <div style={{ fontSize: "var(--fs-16)" }}>Inter fs-16 — corps de texte lisible.</div>
          <div style={{ fontFamily: "var(--font-data)", fontSize: "var(--fs-16)", fontVariantNumeric: "tabular-nums" }}>
            JetBrains Mono — 1 234 567 FCFA · P50 12 450 000 · 42,7 %
          </div>
          <div style={{ fontFamily: "var(--font-data)", fontSize: "var(--fs-13)", color: "var(--muted)" }}>
            tabular-nums : 1111111 + 8888888 = 9999999 (largeur constante)
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(70px, 1fr))", gap: "var(--sp-2)" }}>
          {["fs-10", "fs-11", "fs-12", "fs-13", "fs-14", "fs-16", "fs-18", "fs-20", "fs-24", "fs-30"].map((t) => (
            <div key={t} style={{ display: "grid", gap: 2 }}>
              <span style={{ fontSize: `var(--${t})` }}>Aa</span>
              <span style={labelStyle}>{t}</span>
            </div>
          ))}
        </div>
      </section>

      <section style={sectionStyle}>
        <h2 style={h2Style}>Espace · rayons · ombres · code</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-2)", alignItems: "flex-end" }}>
          {["sp-1", "sp-2", "sp-3", "sp-4", "sp-5", "sp-6"].map((t) => (
            <div key={t} style={{ display: "grid", gap: 2, justifyItems: "center" }}>
              <div style={{ width: `var(--${t})`, height: 20, background: "var(--accent-a35)", borderRadius: 2 }} />
              <span style={labelStyle}>{t}</span>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-3)" }}>
          {["r-1", "r-2", "r-3", "r-4", "r-5"].map((t) => (
            <div key={t} style={{ display: "grid", gap: 2, justifyItems: "center" }}>
              <div style={{ width: 56, height: 36, background: "var(--bg-raised)", border: "1px solid var(--border)", borderRadius: `var(--${t})` }} />
              <span style={labelStyle}>{t}</span>
            </div>
          ))}
        </div>
        <div style={{ background: "var(--code-bg)", border: "1px solid var(--border)", borderRadius: "var(--r-3)", padding: "var(--sp-3)", fontFamily: "var(--font-data)", fontSize: "var(--fs-13)", lineHeight: "var(--lh-body)" }}>
          <div><span style={{ color: "var(--code-comment)" }}># coloration sandbox</span></div>
          <div><span style={{ color: "var(--code-keyword)" }}>import</span> numpy <span style={{ color: "var(--code-keyword)" }}>as</span> np</div>
          <div>p50 = np.<span style={{ color: "var(--code-builtin)" }}>percentile</span>(profit, <span style={{ color: "var(--code-number)" }}>50</span>)</div>
          <div>label = <span style={{ color: "var(--code-string)" }}>"P50"</span></div>
        </div>
        <p style={{ margin: 0, ...labelStyle }}>
          Trame visible en fond de page (--trame, 28px). Durées : --dur-fast 120ms / --dur-base 180ms / --dur-slow 240ms.
        </p>
      </section>
    </div>
  );
}
