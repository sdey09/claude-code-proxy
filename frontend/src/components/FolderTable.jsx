export default function FolderTable({ byFolder }) {
  return (
    <div className="table-wrap">
      <table className="req-table">
        <thead>
          <tr>
            <th>Folder</th>
            <th>Requests</th>
            <th>Input tok</th>
            <th>Output tok</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
          {byFolder.length === 0 && (
            <tr>
              <td colSpan={5} className="empty">
                No file-editing tool calls captured yet.
              </td>
            </tr>
          )}
          {byFolder.map((f) => (
            <tr key={f.full_path}>
              <td title={f.full_path}>{f.folder}</td>
              <td>{f.request_count}</td>
              <td>{f.input_tokens.toLocaleString()}</td>
              <td>{f.output_tokens.toLocaleString()}</td>
              <td>${f.cost.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
