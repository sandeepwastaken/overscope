import type { CSSProperties } from "react";

import { SCOPE, scopeDistribution } from "./lib";
import type { OverscopeReport } from "./types";

export function Icon({
  name,
  size = 16,
  className = "",
  style,
}: {
  name: string;
  size?: number;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={{ fontSize: size, ...style }}
      aria-hidden
    >
      {name}
    </span>
  );
}

export function ScopeBar({ report, className = "" }: { report: OverscopeReport; className?: string }) {
  const dist = scopeDistribution(report);
  const total = report.files.length || 1;
  return (
    <div className={`flex h-2 w-full overflow-hidden rounded-sm bg-surface-container-lowest ${className}`}>
      {dist.map(({ status, count }) =>
        count > 0 ? (
          <div
            key={status}
            className={`${SCOPE[status].bar} h-full`}
            style={{ width: `${(count / total) * 100}%` }}
            title={`${SCOPE[status].label}: ${count}`}
          />
        ) : null,
      )}
    </div>
  );
}

export function ScopeLegend({ report }: { report: OverscopeReport }) {
  const dist = scopeDistribution(report);
  return (
    <div className="flex flex-wrap items-center gap-space-md font-label-mono text-label-mono">
      {dist.map(({ status, count, pct }) => (
        <span key={status} className="flex items-center gap-space-xs text-on-surface-variant">
          <span className={`h-2 w-2 rounded-sm ${SCOPE[status].dot}`} />
          <span className={count ? SCOPE[status].text : "text-outline"}>
            {SCOPE[status].label} ({pct}%)
          </span>
        </span>
      ))}
    </div>
  );
}

export function Dot({ className = "" }: { className?: string }) {
  return <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${className}`} />;
}
