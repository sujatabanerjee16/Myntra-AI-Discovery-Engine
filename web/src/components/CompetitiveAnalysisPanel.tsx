import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CompetitiveAnalysisResponse } from "../types";
import { formatReason } from "./ConfidenceBadge";

const PLATFORM_COLORS: Record<string, string> = {
  myntra: "#FF3F6C",
  nykaa: "#FC2779",
  ajio: "#2C4152",
  other: "#64748b",
};

interface Props {
  data: CompetitiveAnalysisResponse | null;
  loading?: boolean;
  /** Platforms selected in the shared sidebar filter; scopes this panel. */
  selectedPlatforms?: string[];
}

function platformLabel(platform: string): string {
  return platform.charAt(0).toUpperCase() + platform.slice(1);
}

/** Split a "lead — detail" barrier line into a bold lead + supporting detail,
 *  and pick a platform accent color when the line is platform-specific. */
function parseWhyItem(raw: string): { lead: string; detail: string; accent?: string } {
  const text = raw.trim();
  const sep = text.match(/\s[–—-]\s/);
  let lead = text;
  let detail = "";
  if (sep && sep.index !== undefined) {
    lead = text.slice(0, sep.index).trim();
    detail = text.slice(sep.index + sep[0].length).trim();
  }
  const lower = lead.toLowerCase();
  const platform = Object.keys(PLATFORM_COLORS).find((p) => lower.startsWith(p));
  return { lead, detail, accent: platform ? PLATFORM_COLORS[platform] : undefined };
}

export default function CompetitiveAnalysisPanel({ data, loading, selectedPlatforms }: Props) {
  const platforms = useMemo(() => {
    if (!data) return [];
    if (!selectedPlatforms || selectedPlatforms.length === 0) return data.platforms;
    const selected = new Set(selectedPlatforms.map((p) => p.toLowerCase()));
    const filtered = data.platforms.filter((p) => selected.has(p.toLowerCase()));
    // Fall back to all platforms if the selection excludes everything we have data for.
    return filtered.length > 0 ? filtered : data.platforms;
  }, [data, selectedPlatforms]);
  const motiveChart = useMemo(() => {
    if (!data) return [];
    const labels = Array.from(new Set(data.motives.map((m) => m.label)));
    return labels.map((label) => {
      const row: Record<string, string | number> = { label: formatReason(label) };
      for (const platform of data.platforms) {
        const hit = data.motives.find((m) => m.label === label && m.platform === platform);
        row[platform] = hit?.count ?? 0;
      }
      return row;
    });
  }, [data]);

  const barrierChart = useMemo(() => {
    if (!data) return [];
    const labels = Array.from(new Set(data.barriers.map((b) => b.label)));
    return labels
      .map((label) => {
        const row: Record<string, string | number> = { label: formatReason(label) };
        let total = 0;
        for (const platform of data.platforms) {
          const hit = data.barriers.find((b) => b.label === label && b.platform === platform);
          const count = hit?.count ?? 0;
          row[platform] = count;
          total += count;
        }
        row._total = total;
        return row;
      })
      .sort((a, b) => Number(b._total) - Number(a._total))
      .slice(0, 8)
      .map(({ _total, ...rest }) => rest);
  }, [data]);

  if (loading && !data) {
    return (
      <section className="wi-dash-card wi-competitive">
        <h2>Competitive Wishlist Analysis</h2>
        <p className="muted">Loading competitive comparison…</p>
      </section>
    );
  }

  if (!data || data.platforms.length === 0) {
    return (
      <section className="wi-dash-card wi-competitive">
        <h2>Competitive Wishlist Analysis</h2>
        <p className="muted">
          No platform-tagged competitive evidence yet. Refresh analytics after merging
          competitive seeds (Myntra / Nykaa / Ajio) to populate this view.
        </p>
      </section>
    );
  }

  return (
    <section className="wi-dash-card wi-competitive">
      <div className="wi-competitive-head">
        <div>
          <h2>Competitive Wishlist Analysis</h2>
          <p className="wi-competitive-sub">
            Why users wishlist on <strong>Myntra vs Nykaa vs Ajio</strong> — and which barriers
            keep wishlisted items from converting within 30 days.
          </p>
        </div>
        <div className="wi-competitive-platforms">
          {platforms.map((platform) => (
            <span
              key={platform}
              className="wi-platform-chip"
              style={{ borderColor: PLATFORM_COLORS[platform] || "#94a3b8" }}
            >
              {platformLabel(platform)}
            </span>
          ))}
        </div>
      </div>

      <div className="wi-competitive-why">
        <h3>Why wishlist items are not purchased</h3>
        <div className="wi-why-grid">
          {data.why_not_purchase.map((item) => {
            const { lead, detail, accent } = parseWhyItem(item);
            return (
              <div
                key={item}
                className="wi-why-card"
                style={accent ? { borderLeftColor: accent } : undefined}
              >
                <p className="wi-why-lead">{lead}</p>
                {detail && <p className="wi-why-detail">{detail}</p>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="wi-competitive-grid">
        <div className="wi-competitive-chart">
          <h3>Wishlist motives by platform</h3>
          <div className="wi-competitive-chart-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={motiveChart} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={70} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                {platforms.map((platform) => (
                  <Bar
                    key={platform}
                    dataKey={platform}
                    name={platformLabel(platform)}
                    fill={PLATFORM_COLORS[platform] || "#94a3b8"}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="wi-competitive-chart">
          <h3>Non-purchase barriers by platform</h3>
          <div className="wi-competitive-chart-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={barrierChart} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={70} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                {platforms.map((platform) => (
                  <Bar
                    key={platform}
                    dataKey={platform}
                    name={platformLabel(platform)}
                    fill={PLATFORM_COLORS[platform] || "#94a3b8"}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="wi-competitive-tops">
        {platforms.map((platform) => {
          const motive = data.top_motive_by_platform[platform];
          const barrier = data.top_barrier_by_platform[platform];
          const unique = data.unique_motives_by_platform[platform] || [];
          return (
            <article key={platform} className="wi-competitive-top-card">
              <h4 style={{ color: PLATFORM_COLORS[platform] || "#0f172a" }}>
                {platformLabel(platform)}
              </h4>
              <p>
                <span className="muted">Top wishlist motive</span>
                <strong>{motive ? formatReason(motive.label) : "—"}</strong>
              </p>
              <p>
                <span className="muted">Top barrier to purchase</span>
                <strong>{barrier ? formatReason(barrier.label) : "—"}</strong>
              </p>
              {unique.length > 0 && (
                <p>
                  <span className="muted">More unique motives</span>
                  <strong>{unique.map(formatReason).join(", ")}</strong>
                </p>
              )}
            </article>
          );
        })}
      </div>

      {data.shared_motives.length > 0 && (
        <div className="wi-competitive-shared">
          <h3>Shared across platforms</h3>
          <div className="wi-competitive-shared-chips">
            {data.shared_motives.map((motive) => (
              <span key={motive} className="wi-filter-chip">
                {formatReason(motive)}
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="wi-competitive-limitations">{data.limitations}</p>
    </section>
  );
}
