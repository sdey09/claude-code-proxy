const STATUSES = ["200", "400", "401", "429", "500", "502"];

export default function FilterBar({ models, model, status, onChange }) {
  return (
    <form className="filters" onSubmit={(e) => e.preventDefault()}>
      <select value={model} onChange={(e) => onChange({ model: e.target.value, status })}>
        <option value="">All models</option>
        {models.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <select value={status} onChange={(e) => onChange({ model, status: e.target.value })}>
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
