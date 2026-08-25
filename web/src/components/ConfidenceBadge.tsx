import { confidenceColor, formatLabel } from "../types";

interface Props {
  confidence: number | null;
  label?: string;
}

export default function ConfidenceBadge({ confidence, label = "Confidence" }: Props) {
  return (
    <span className="badge">
      <span className="badge-dot" style={{ background: confidenceColor(confidence) }} />
      {label}: {confidence === null ? "n/a" : `${Math.round(confidence * 100)}%`}
    </span>
  );
}

export function formatReason(value: string): string {
  return formatLabel(value);
}
