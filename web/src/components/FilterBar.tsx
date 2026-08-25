import type { DashboardFilters, FilterState } from "../types";

interface Props {
  filters: FilterState;
  options: DashboardFilters | null;
  onChange: (next: FilterState) => void;
  onClear: () => void;
}

export default function FilterBar({ filters, options, onChange, onClear }: Props) {
  const update = (key: keyof FilterState, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <section className="filters">
      <label>
        Segment
        <select value={filters.segment} onChange={(e) => update("segment", e.target.value)}>
          <option value="">All segments</option>
          {options?.segments.map((value) => (
            <option key={value} value={value}>{value.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>
      <label>
        Category
        <select value={filters.category} onChange={(e) => update("category", e.target.value)}>
          <option value="">All categories</option>
          {options?.categories.map((value) => (
            <option key={value} value={value}>{value.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>
      <label>
        Occasion
        <select value={filters.occasion} onChange={(e) => update("occasion", e.target.value)}>
          <option value="">All occasions</option>
          {options?.occasions.map((value) => (
            <option key={value} value={value}>{value.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>
      <label>
        Price band
        <select value={filters.price_band} onChange={(e) => update("price_band", e.target.value)}>
          <option value="">All price bands</option>
          {options?.price_bands.map((value) => (
            <option key={value} value={value}>{value.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>
      <label>
        Reason
        <select
          value={filters.reason_category}
          onChange={(e) => update("reason_category", e.target.value)}
        >
          <option value="">All reasons</option>
          {options?.reason_categories.map((value) => (
            <option key={value} value={value}>{value.replace(/_/g, " ")}</option>
          ))}
        </select>
      </label>
      <button type="button" className="btn-secondary" onClick={onClear}>
        Clear filters
      </button>
    </section>
  );
}
