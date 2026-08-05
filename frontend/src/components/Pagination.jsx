export default function Pagination({ page, totalPages, onChange }) {
  return (
    <div className="pagination">
      {page > 1 && (
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            onChange(page - 1);
          }}
        >
          ← Prev
        </a>
      )}
      <span>
        Page {page} / {totalPages}
      </span>
      {page < totalPages && (
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            onChange(page + 1);
          }}
        >
          Next →
        </a>
      )}
    </div>
  );
}
