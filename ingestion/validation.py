"""Cross-source corpus validation after ingestion stages."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ingestion.schemas import RawRecord
from ingestion.stages.dedupe import content_fingerprint


@dataclass
class CorpusValidationReport:
    total_records: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    cross_source_duplicates: int = 0
    duplicate_examples: list[dict[str, str]] = field(default_factory=list)
    records_without_signals: int = 0
    avg_text_length_by_source: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_records": self.total_records,
            "by_source": self.by_source,
            "cross_source_duplicates": self.cross_source_duplicates,
            "duplicate_examples": self.duplicate_examples,
            "records_without_signals": self.records_without_signals,
            "avg_text_length_by_source": self.avg_text_length_by_source,
        }


def validate_corpus(records: list[RawRecord]) -> CorpusValidationReport:
    """Analyze dedupe risk and quality distribution across source types."""
    report = CorpusValidationReport(total_records=len(records))
    lengths: dict[str, list[int]] = defaultdict(list)
    fingerprint_sources: dict[str, set[str]] = defaultdict(set)

    for record in records:
        source = record.source.value
        report.by_source[source] = report.by_source.get(source, 0) + 1
        lengths[source].append(len(record.text))
        if not record.matched_signals:
            report.records_without_signals += 1
        fingerprint_sources[content_fingerprint(record.text)].add(source)

    for fp, sources in fingerprint_sources.items():
        if len(sources) > 1:
            report.cross_source_duplicates += 1
            if len(report.duplicate_examples) < 5:
                report.duplicate_examples.append(
                    {"fingerprint": fp[:12], "sources": ",".join(sorted(sources))}
                )

    report.avg_text_length_by_source = {
        source: round(sum(values) / len(values), 1)
        for source, values in lengths.items()
        if values
    }
    return report


def summarize_source_coverage(by_source: Counter[str]) -> dict[str, bool]:
    """Return whether each expected source type contributed records."""
    expected = {
        "research",
        "play_store",
        "reddit",
        "youtube",
        "product_review",
        "social",
    }
    return {source: by_source.get(source, 0) > 0 for source in sorted(expected)}
