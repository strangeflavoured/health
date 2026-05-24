// Temporary until design-system.jsx is converted to .tsx
declare module "./design-system" {
  export function GlobalStyles(): React.ReactElement;
}

import React, { useState, useEffect } from "react";

/* ============================================================
   DOMAIN TYPES
   ============================================================ */

export type HealthStatus = "normal" | "elevated" | "critical" | "low";
export type DeltaDir     = "up" | "down" | "flat";

export interface StatusConfig {
  kind:  HealthStatus;
  label: string;
}

/* Column descriptor for VitalsTable. T is the row shape. */
export interface Column<T> {
  key:     string;
  label:   string;
  align?:  "left" | "right" | "center";
  render?: (row: T) => React.ReactNode;
}

/* ============================================================
   THEME TOGGLE
   Sets data-theme on <html>; honours OS preference on first load.
   ============================================================ */

interface ThemeToggleProps {
  style?: React.CSSProperties;
}

export function ThemeToggle({ style }: ThemeToggleProps): React.ReactElement {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
    setTheme(prefersDark ? "dark" : "light");
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggle = (): void => setTheme((t) => (t === "dark" ? "light" : "dark"));

  const sunIcon = (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );

  const moonIcon = (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" />
    </svg>
  );

  return (
    <button
      onClick={toggle}
      aria-label="Toggle colour theme"
      title="Toggle theme"
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 38, height: 38, borderRadius: "var(--r)",
        background: "var(--surface)", border: "1px solid var(--border)",
        color: "var(--text)", cursor: "pointer", transition: "all 0.15s ease",
        ...style,
      }}
    >
      {theme === "dark" ? moonIcon : sunIcon}
    </button>
  );
}

/* ============================================================
   APP SHELL — sidebar + topbar + content grid
   ============================================================ */

interface AppShellProps {
  sidebar:  React.ReactNode;
  topbar:   React.ReactNode;
  children: React.ReactNode;
}

export function AppShell({ sidebar, topbar, children }: AppShellProps): React.ReactElement {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "260px 1fr",
      gridTemplateRows: "auto 1fr",
      gridTemplateAreas: `"sidebar topbar" "sidebar main"`,
      minHeight: "100vh",
    }}>
      <aside style={{ gridArea: "sidebar" }}>{sidebar}</aside>
      <div   style={{ gridArea: "topbar"  }}>{topbar}</div>
      <main  style={{ gridArea: "main", padding: 32, maxWidth: 1180 }}>{children}</main>
    </div>
  );
}

/* ============================================================
   SIDEBAR
   ============================================================ */

interface SidebarProps {
  brand:     React.ReactNode;
  children:  React.ReactNode;
  footer?:   React.ReactNode;
}

export function Sidebar({ brand, children, footer }: SidebarProps): React.ReactElement {
  return (
    <div style={{
      position: "sticky", top: 0, height: "100vh", overflowY: "auto",
      display: "flex", flexDirection: "column", gap: 4,
      padding: "24px 20px", background: "var(--surface)",
      borderRight: "1px solid var(--border)",
    }}>
      {brand}
      <nav>{children}</nav>
      {footer && <div style={{ marginTop: "auto", paddingTop: 16 }}>{footer}</div>}
    </div>
  );
}

/* ============================================================
   NAV GROUP
   ============================================================ */

interface NavGroupProps {
  label:    string;
  children: React.ReactNode;
}

export function NavGroup({ label, children }: NavGroupProps): React.ReactElement {
  return (
    <>
      <div style={{
        fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.16em",
        textTransform: "uppercase", color: "var(--muted)", padding: "20px 8px 8px",
      }}>{label}</div>
      {children}
    </>
  );
}

/* ============================================================
   NAV ITEM
   ============================================================ */

interface NavItemProps {
  icon?:     React.ReactNode;
  children:  React.ReactNode;
  active?:   boolean;
  badge?:    number | string;
  onClick?:  React.MouseEventHandler;
  href?:     string;
}

export function NavItem({
  icon, children, active = false, badge, onClick, href,
}: NavItemProps): React.ReactElement {
  const sharedStyle: React.CSSProperties = {
    display: "flex", alignItems: "center", gap: 12,
    padding: "8px 12px", borderRadius: "var(--r)",
    color: active ? "var(--accent-dk)" : "var(--muted)",
    background: active ? "var(--accent-bg)" : "transparent",
    border: `1px solid ${active ? "rgba(47,111,230,0.22)" : "transparent"}`,
    fontWeight: 500, fontSize: 14, letterSpacing: "-0.01em",
    textDecoration: "none", cursor: "pointer", transition: "all 0.15s ease",
  };

  const inner = (
    <>
      {icon && <span style={{ display: "inline-flex", opacity: active ? 1 : 0.8 }}>{icon}</span>}
      <span style={{ flex: 1 }}>{children}</span>
      {badge != null && (
        <span style={{
          fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 500,
          padding: "1px 7px", borderRadius: 100,
          color: "var(--crit-fg)", background: "var(--crit-bg)",
        }}>{badge}</span>
      )}
    </>
  );

  if (href) {
    return <a href={href} style={sharedStyle}>{inner}</a>;
  }
  return <div role="button" onClick={onClick} style={sharedStyle}>{inner}</div>;
}

/* ============================================================
   TOPBAR
   ============================================================ */

interface TopbarProps {
  eyebrow?:     string;
  title:        string;
  titleItalic?: string;
  meta?:        React.ReactNode;
  actions?:     React.ReactNode;
}

export function Topbar({
  eyebrow, title, titleItalic, meta, actions,
}: TopbarProps): React.ReactElement {
  return (
    <header style={{
      position: "sticky", top: 0, zIndex: 50,
      display: "flex", alignItems: "center", gap: 16,
      padding: "20px 32px",
      background: "color-mix(in srgb, var(--bg) 88%, transparent)",
      backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
      borderBottom: "1px solid var(--border)",
    }}>
      <div>
        {eyebrow && (
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.18em",
            textTransform: "uppercase", color: "var(--accent-dk)", marginBottom: 6,
          }}>
            <span style={{ width: 20, height: 1.5, background: "var(--accent)", borderRadius: 2 }} />
            {eyebrow}
          </div>
        )}
        <h1 style={{
          fontFamily: "var(--font-display)", fontWeight: 400, fontSize: 26,
          letterSpacing: "-0.02em", lineHeight: 1.1, margin: 0,
        }}>
          {title}
          {titleItalic && (
            <> <em style={{ fontStyle: "italic", color: "var(--accent-dk)" }}>{titleItalic}</em></>
          )}
        </h1>
        {meta && (
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
            {meta}
          </div>
        )}
      </div>
      <div style={{ flex: 1 }} />
      {actions}
    </header>
  );
}

/* ============================================================
   METRIC TILE — DM Serif Display value, mono label/unit
   ============================================================ */

interface MetricTileProps {
  icon?:   React.ReactNode;
  label:   string;
  value:   string | number;
  unit?:   string;
  status?: StatusConfig;
  delta?:  React.ReactNode;
  hover?:  boolean;
}

export function MetricTile({
  icon, label, value, unit, status, delta, hover = true,
}: MetricTileProps): React.ReactElement {
  const handleEnter = (e: React.MouseEvent<HTMLElement>): void => {
    e.currentTarget.style.borderColor = "var(--accent)";
  };
  const handleLeave = (e: React.MouseEvent<HTMLElement>): void => {
    e.currentTarget.style.borderColor = "var(--border)";
  };

  return (
    <article
      style={{
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: "calc(var(--r) + 2px)", padding: 24,
        transition: "border-color 0.2s ease",
      }}
      onMouseEnter={hover ? handleEnter : undefined}
      onMouseLeave={hover ? handleLeave : undefined}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        {icon && (
          <span style={{
            width: 34, height: 34, display: "grid", placeItems: "center",
            borderRadius: "var(--r)", background: "var(--accent-bg)",
            color: "var(--accent-dk)", border: "1px solid var(--border)",
          }}>{icon}</span>
        )}
        <span style={{
          fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.15em",
          textTransform: "uppercase", color: "var(--muted)",
        }}>{label}</span>
      </div>

      <div style={{
        fontFamily: "var(--font-display)", fontWeight: 400, fontSize: "2.6rem", lineHeight: 1,
        letterSpacing: "-0.02em", color: "var(--text)", fontFeatureSettings: '"tnum" 1, "lnum" 1',
        display: "flex", alignItems: "baseline", gap: 6,
      }}>
        {value}
        {unit && (
          <span style={{ fontFamily: "var(--font-body)", fontSize: "1rem", fontWeight: 500, color: "var(--muted)" }}>
            {unit}
          </span>
        )}
      </div>

      {(status ?? delta) && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
          {status && <StatusPill status={status.kind}>{status.label}</StatusPill>}
          {delta}
        </div>
      )}
    </article>
  );
}

/* ============================================================
   DELTA CHIP — mono, up / down / flat
   ============================================================ */

interface DeltaProps {
  dir?:     DeltaDir;
  children: React.ReactNode;
  since?:   string;
}

const DELTA_MAP: Record<DeltaDir, { color: string; background: string; arrow: string }> = {
  up:   { color: "var(--ok-fg)",    background: "var(--ok-bg)",    arrow: "▲" },
  down: { color: "var(--crit-fg)", background: "var(--crit-bg)", arrow: "▼" },
  flat: { color: "var(--muted)",   background: "var(--surface2)", arrow: "→" },
};

export function Delta({ dir = "flat", children, since }: DeltaProps): React.ReactElement {
  const s = DELTA_MAP[dir];
  return (
    <>
      <span style={{
        display: "inline-flex", alignItems: "center", gap: 4,
        fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 500,
        padding: "2px 8px", borderRadius: 100, color: s.color, background: s.background,
      }}>
        {s.arrow} {children}
      </span>
      {since && (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted)" }}>
          {since}
        </span>
      )}
    </>
  );
}

/* ============================================================
   STATUS PILL — health ranges (template .tag idiom)
   ============================================================ */

interface StatusPillProps {
  status?:  HealthStatus;
  children: React.ReactNode;
}

const STATUS_MAP: Record<HealthStatus, { fg: string; bg: string; bd: string }> = {
  normal:   { fg: "var(--ok-fg)",   bg: "var(--ok-bg)",   bd: "var(--ok-bd)"   },
  elevated: { fg: "var(--warn-fg)", bg: "var(--warn-bg)", bd: "var(--warn-bd)" },
  critical: { fg: "var(--crit-fg)", bg: "var(--crit-bg)", bd: "var(--crit-bd)" },
  low:      { fg: "var(--info-fg)", bg: "var(--info-bg)", bd: "var(--info-bd)" },
};

export function StatusPill({ status = "normal", children }: StatusPillProps): React.ReactElement {
  const s = STATUS_MAP[status] ?? STATUS_MAP.normal;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 500, lineHeight: 1,
      padding: "4px 10px", borderRadius: 100, letterSpacing: "0.04em", textTransform: "uppercase",
      color: s.fg, background: s.bg, border: `1px solid ${s.bd}`,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: "50%", background: "currentColor",
        animation: status === "critical" ? "ds-fadeIn 1.6s ease infinite alternate" : undefined,
      }} />
      {children}
    </span>
  );
}

/* ============================================================
   RING STAT — conic-gradient ring with serif centre value
   ============================================================ */

interface RingStatProps {
  value?: number;
  label?: string;
  color?: string;
}

export function RingStat({ value = 72, label, color = "var(--accent)" }: RingStatProps): React.ReactElement {
  return (
    <div style={{
      width: 128, height: 128, borderRadius: "50%", flex: "none",
      display: "grid", placeItems: "center", position: "relative",
      background: `conic-gradient(${color} ${value}%, var(--surface2) 0)`,
    }}>
      <div style={{ position: "absolute", inset: 11, borderRadius: "50%", background: "var(--surface)" }} />
      <div style={{ position: "relative", textAlign: "center" }}>
        <b style={{
          fontFamily: "var(--font-display)", fontWeight: 400, fontSize: "1.75rem",
          color: "var(--text)", fontFeatureSettings: '"tnum" 1',
        }}>{value}%</b>
        {label && (
          <span style={{
            display: "block", fontFamily: "var(--font-mono)", fontSize: 10,
            letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginTop: 2,
          }}>{label}</span>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   PROGRESS STAT — labelled horizontal bar
   ============================================================ */

interface ProgressStatProps {
  label:    string;
  value:    number;           // 0–100
  display?: string;           // overrides the "N%" label if provided
  color?:   string;
}

export function ProgressStat({
  label, value, display, color = "var(--accent)",
}: ProgressStatProps): React.ReactElement {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
        <span>{label}</span>
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>
          {display ?? `${value}%`}
        </span>
      </div>
      <div style={{ height: 6, borderRadius: 100, background: "var(--surface2)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${value}%`, borderRadius: 100, background: color }} />
      </div>
    </div>
  );
}

/* ============================================================
   AVATAR
   ============================================================ */

interface AvatarProps {
  initials: string;
  color?:   string;
}

export function Avatar({ initials, color = "var(--accent)" }: AvatarProps): React.ReactElement {
  return (
    <span style={{
      width: 30, height: 30, borderRadius: "50%", flex: "none",
      display: "grid", placeItems: "center", color: "#fff", background: color,
      fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 500,
    }}>{initials}</span>
  );
}

/* ============================================================
   VITALS TABLE
   Generic over the row shape T so column.render gets the full row type.
   ============================================================ */

interface VitalsTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[];
  rows:    T[];
}

export function VitalsTable<T extends Record<string, unknown>>({
  columns, rows,
}: VitalsTableProps<T>): React.ReactElement {
  return (
    <div style={{ overflow: "auto", border: "1px solid var(--border)", borderRadius: "calc(var(--r) + 2px)" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14, background: "var(--surface)" }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{
                position: "sticky", top: 0, background: "var(--surface2)",
                textAlign: c.align ?? "left",
                fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 500,
                textTransform: "uppercase", letterSpacing: "0.12em", color: "var(--muted)",
                padding: "12px 16px", borderBottom: "1px solid var(--border)",
              }}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              style={{ transition: "background 0.15s ease" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--surface2)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              {columns.map((c) => {
                const isNum = c.align === "right";
                return (
                  <td key={c.key} style={{
                    padding: "14px 16px",
                    borderBottom: i === rows.length - 1 ? "0" : "1px solid var(--border)",
                    textAlign: c.align ?? "left",
                    color: "var(--text)",
                    fontFamily: isNum ? "var(--font-mono)" : "inherit",
                    fontFeatureSettings: isNum ? '"tnum" 1, "lnum" 1' : undefined,
                  }}>
                    {c.render ? c.render(row) : String(row[c.key] ?? "")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ============================================================
   DEMO — remove in production
   ============================================================ */

import { GlobalStyles } from "./design-system";

interface VitalRow extends Record<string, unknown> {
  initials:    string;
  name:        string;
  vital:       string;
  reading:     string;
  status:      HealthStatus;
  statusLabel: string;
  seen:        string;
  color:       string;
}

const ico = (d: string): React.ReactElement => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const DEMO_ROWS: VitalRow[] = [
  { initials: "AM", name: "Anna Müller",    vital: "Heart rate",     reading: "112 bpm",    status: "elevated", statusLabel: "Elevated", seen: "2m",      color: "var(--accent)" },
  { initials: "JR", name: "Jonas Richter",  vital: "SpO₂",           reading: "88 %",       status: "critical", statusLabel: "Critical", seen: "now",     color: "#14a3b0"        },
  { initials: "SB", name: "Sofia Bauer",    vital: "Glucose",        reading: "5.4 mmol/L", status: "normal",   statusLabel: "Normal",   seen: "14m",     color: "#2c9466"        },
  { initials: "LW", name: "Liam Wagner",    vital: "Blood pressure", reading: "96/61",      status: "low",      statusLabel: "Low",      seen: "31m",     color: "#8a6fd0"        },
];

const DEMO_COLUMNS: Column<VitalRow>[] = [
  {
    key: "name", label: "Patient",
    render: (r) => (
      <span style={{ display: "flex", alignItems: "center", gap: 12, fontWeight: 600 }}>
        <Avatar initials={r.initials} color={r.color} /> {r.name}
      </span>
    ),
  },
  { key: "vital",   label: "Vital"     },
  { key: "reading", label: "Reading",   align: "right" },
  { key: "status",  label: "Status",    render: (r) => <StatusPill status={r.status}>{r.statusLabel}</StatusPill> },
  { key: "seen",    label: "Last seen", align: "right" },
];

export default function HealthDashboardDemo(): React.ReactElement {
  return (
    <>
      <GlobalStyles />
      <div style={{ background: "var(--bg)", minHeight: "100vh", color: "var(--text)", fontFamily: "var(--font-body)" }}>
        <AppShell
          sidebar={
            <Sidebar
              brand={
                <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 8px 24px" }}>
                  <span style={{ width: 34, height: 34, display: "grid", placeItems: "center", borderRadius: "var(--r)", background: "var(--accent)", color: "#fff" }}>
                    {ico("M3 12h3l2-5 4 13 2.5-8H21")}
                  </span>
                  <div>
                    <div style={{ fontFamily: "var(--font-display)", fontSize: 20, lineHeight: 1 }}>Vitalis</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--muted)", marginTop: 3 }}>Health Cloud</div>
                  </div>
                </div>
              }
              footer={<ThemeToggle style={{ width: "100%" }} />}
            >
              <NavGroup label="Overview">
                <NavItem icon={ico("M3 12h4l2-6 4 12 2-6h6")} active>Dashboard</NavItem>
                <NavItem icon={ico("M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2")}>Patients</NavItem>
              </NavGroup>
              <NavGroup label="Monitoring">
                <NavItem icon={ico("M3 17l6-6 4 4 7-8")}>Trends</NavItem>
                <NavItem icon={ico("M10.3 3.5a2 2 0 0 1 3.4 0l8 13.5a2 2 0 0 1-1.7 3H4a2 2 0 0 1-1.7-3z")} badge={3}>Alerts</NavItem>
              </NavGroup>
            </Sidebar>
          }
          topbar={
            <Topbar
              eyebrow="Live · 12s ago"
              title="Patient" titleItalic="Overview"
              actions={
                <>
                  <ThemeToggle />
                  <button style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "var(--font-body)", fontWeight: 500, fontSize: 14, padding: "9px 18px", borderRadius: "var(--r)", background: "var(--accent)", color: "#fff", border: "none", cursor: "pointer" }}>
                    {ico("M12 5v14M5 12h14")} New reading
                  </button>
                </>
              }
            />
          }
        >
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(212px, 1fr))", gap: 16, marginBottom: 32 }}>
            <MetricTile
              icon={ico("M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8z")}
              label="Heart rate" value="72" unit="bpm"
              status={{ kind: "normal", label: "Normal" }}
              delta={<Delta dir="down" since="vs last hr">4</Delta>}
            />
            <MetricTile
              icon={ico("M12 22a8 8 0 0 0 8-8c0-3.5-3-7-8-12C7 7 4 10.5 4 14a8 8 0 0 0 8 8z")}
              label="Blood pressure" value="118" unit="/76"
              status={{ kind: "normal", label: "Optimal" }}
            />
            <MetricTile
              icon={ico("M12 7v5l3 2")}
              label="SpO₂" value="98" unit="%"
              status={{ kind: "normal", label: "Normal" }}
              delta={<Delta dir="up" since="vs am">1</Delta>}
            />
            <MetricTile
              icon={ico("M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z")}
              label="Sleep" value="6" unit="h 02m"
              status={{ kind: "elevated", label: "Below target" }}
              delta={<Delta dir="down">58m</Delta>}
            />
          </div>

          <VitalsTable<VitalRow> columns={DEMO_COLUMNS} rows={DEMO_ROWS} />
        </AppShell>
      </div>
    </>
  );
}
