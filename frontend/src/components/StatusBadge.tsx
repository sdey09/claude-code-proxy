const BASE = "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold leading-tight";
const TONES = {
  ok: "bg-ok/15 text-ok",
  warn: "bg-warn/15 text-warn",
  error: "bg-err/15 text-err",
  neutral: "bg-muted/15 text-muted",
} as const;

interface StatusBadgeProps {
  status: number | null | undefined;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  if (!status) return <span className={`${BASE} ${TONES.neutral}`}>—</span>;
  const tone = status >= 500 ? "error" : status >= 400 ? "warn" : status >= 200 ? "ok" : "neutral";
  return <span className={`${BASE} ${TONES[tone]}`}>{status}</span>;
}
