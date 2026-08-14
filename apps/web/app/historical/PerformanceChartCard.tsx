"use client";

import { useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceArea, ReferenceLine,
} from "recharts";

export interface ChartSeriesPoint {
  date: string;   // "YYYY-MM-DD"
  value: number;  // real index close
}

const RANGES = ["1M", "3M", "6M", "1Y"] as const;
type Range = (typeof RANGES)[number];
const RANGE_AFTER_DAYS: Record<Range, number> = { "1M": 30, "3M": 90, "6M": 180, "1Y": 365 };
const BEFORE_DAYS = 30;
const DAY_MS = 86400000;

function fmtDate(d: string): string {
  const dt = new Date(d);
  return dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-surface-border/15 bg-surface-card px-3 py-2 text-[11px] shadow-lg">
      <p className="font-semibold text-text-primary">{label ? fmtDate(label) : ""}</p>
      <p className="mt-0.5 font-bold text-sky-600 dark:text-sky-300">{payload[0].value.toLocaleString("en-IN")}</p>
    </div>
  );
}

/**
 * Real NIFTY 50 daily-close line chart around a historical event, with a
 * client-side-only 1M/3M/6M/1Y range toggle — the backend already fetches a
 * single wide real series (-95d/+380d) per event, so switching ranges here
 * just re-slices data already in memory instead of firing another request.
 */
export function PerformanceChartCard({
  fullSeries, eventDate, indexName = "NIFTY 50", isLoading,
}: {
  fullSeries: ChartSeriesPoint[];
  eventDate: string;
  indexName?: string;
  isLoading?: boolean;
}) {
  const [range, setRange] = useState<Range>("3M");

  const { data, eventX, duringEndX, zones } = useMemo(() => {
    if (!fullSeries.length) return { data: [] as ChartSeriesPoint[], eventX: null as string | null, duringEndX: null as string | null, zones: null };
    const evtTime = new Date(eventDate).getTime();
    const startTime = evtTime - BEFORE_DAYS * DAY_MS;
    const endTime = evtTime + RANGE_AFTER_DAYS[range] * DAY_MS;
    const sliced = fullSeries.filter(p => {
      const t = new Date(p.date).getTime();
      return t >= startTime && t <= endTime;
    });
    if (sliced.length === 0) return { data: [], eventX: null, duringEndX: null, zones: null };

    let eIdx = sliced.findIndex(p => p.date === eventDate);
    if (eIdx === -1) {
      eIdx = sliced.reduce((best, p, i) =>
        Math.abs(new Date(p.date).getTime() - evtTime) < Math.abs(new Date(sliced[best].date).getTime() - evtTime) ? i : best, 0);
    }
    const dIdx = Math.min(sliced.length - 1, eIdx + 3);
    const totalSpan = sliced.length - 1 || 1;
    const zoneInfo = {
      beforeFrac: eIdx / totalSpan,
      duringFrac: (dIdx - eIdx) / totalSpan,
      afterFrac: (sliced.length - 1 - dIdx) / totalSpan,
    };
    return { data: sliced, eventX: sliced[eIdx].date, duringEndX: sliced[dIdx].date, zones: zoneInfo };
  }, [fullSeries, eventDate, range]);

  const MIN_LABEL_FRAC = 0.08;

  return (
    <div className="rounded-[20px] border border-surface-border/8 bg-surface-card p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-sky-500" />
          <div>
            <p className="text-[13px] font-bold text-text-primary">{indexName} Performance</p>
            <p className="text-[10.5px] text-text-muted">Real daily closes, {indexName}</p>
          </div>
        </div>
        <div className="flex rounded-full border border-surface-border/10 bg-text-primary/[0.03] p-1">
          {RANGES.map(r => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                range === r ? "bg-sky-500 text-white" : "text-text-muted hover:bg-text-primary/[0.05] hover:text-text-secondary"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-[300px] items-center justify-center">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
        </div>
      ) : data.length === 0 ? (
        <p className="flex h-[300px] items-center justify-center text-center text-[12px] text-text-muted">
          No real daily price data available for this range.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 24, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgb(var(--text-primary) / 0.06)" />
            <XAxis
              dataKey="date"
              tickFormatter={fmtDate}
              tick={{ fontSize: 10.5, fill: "rgb(var(--text-muted))" }}
              axisLine={{ stroke: "rgb(var(--text-primary) / 0.08)" }}
              tickLine={false}
              interval={Math.max(0, Math.ceil(data.length / 7) - 1)}
              minTickGap={24}
            />
            <YAxis
              tickFormatter={(v: number) => v.toLocaleString("en-IN")}
              tick={{ fontSize: 10.5, fill: "rgb(var(--text-muted))" }}
              axisLine={false}
              tickLine={false}
              width={56}
              domain={["dataMin - 100", "dataMax + 100"]}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: "rgb(var(--text-primary) / 0.2)", strokeDasharray: "3 3" }} />

            {zones && eventX && zones.beforeFrac >= MIN_LABEL_FRAC && (
              <ReferenceArea x1={data[0].date} x2={eventX} fill="rgb(var(--text-primary))" fillOpacity={0.03}
                label={{ value: "Before Event", position: "insideTop", fontSize: 10, fontWeight: 700, fill: "rgb(var(--text-muted))" }} />
            )}
            {zones && eventX && duringEndX && zones.duringFrac >= MIN_LABEL_FRAC && (
              <ReferenceArea x1={eventX} x2={duringEndX} fill="#f59e0b" fillOpacity={0.07}
                label={{ value: "During Event", position: "insideTop", fontSize: 10, fontWeight: 700, fill: "#d97706" }} />
            )}
            {zones && duringEndX && zones.afterFrac >= MIN_LABEL_FRAC && (
              <ReferenceArea x1={duringEndX} x2={data[data.length - 1].date} fill="#10b981" fillOpacity={0.06}
                label={{ value: "After Event", position: "insideTop", fontSize: 10, fontWeight: 700, fill: "#059669" }} />
            )}
            {eventX && (
              <ReferenceLine x={eventX} stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4 4" />
            )}

            <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}

      <div className="mt-2 flex items-center justify-between text-[10px] text-text-muted">
        <span>{data[0] ? fmtDate(data[0].date) : ""}</span>
        <span className="font-semibold text-amber-600 dark:text-amber-400">Event: {fmtDate(eventDate)}</span>
        <span>{data[data.length - 1] ? fmtDate(data[data.length - 1].date) : ""}</span>
      </div>
    </div>
  );
}
