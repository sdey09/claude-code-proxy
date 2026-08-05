export default function ModelTable({ byModel }) {
  return (
    <div className="table-wrap">
      <table className="req-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Requests</th>
            <th>Input tok</th>
            <th>Output tok</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
          {byModel.length === 0 && (
            <tr>
              <td colSpan={5} className="empty">
                No requests captured yet.
              </td>
            </tr>
          )}
          {byModel.map((m) => (
            <tr key={m.model || "unknown"}>
              <td>{m.model || "unknown"}</td>
              <td>{m.request_count}</td>
              <td>{m.total_input_tokens.toLocaleString()}</td>
              <td>{m.total_output_tokens.toLocaleString()}</td>
              <td>${(m.total_cost || 0).toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
