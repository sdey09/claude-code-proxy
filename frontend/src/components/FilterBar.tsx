const STATUSES = ["200", "400", "401", "429", "500", "502"];

const selectCls = "mr-2 rounded-md border border-border bg-panel px-2.5 py-1.5 text-text";

interface FilterBarProps {
  models: string[];
  model: string;
  status: string;
  onChange: (next: { model: string; status: string }) => void;
}

export default function FilterBar({ models, model, status, onChange }: FilterBarProps) {
  return (
    <form className="flex" onSubmit={(e) => e.preventDefault()}>
      <select className={selectCls} value={model} onChange={(e) => onChange({ model: e.target.value, status })}>
        <option value="">All models</option>
        {models.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <select className={selectCls} value={status} onChange={(e) => onChange({ model, status: e.target.value })}>
        <option value="">All statuses</option>
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </form>
  );
}
