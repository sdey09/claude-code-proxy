interface PaginationProps {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}

export default function Pagination({ page, totalPages, onChange }: PaginationProps) {
  return (
    <div className="mt-4 flex items-center gap-4 text-sm text-muted">
      {page > 1 && (
        <a
          href="#"
          className="text-accent no-underline hover:underline"
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
          className="text-accent no-underline hover:underline"
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
