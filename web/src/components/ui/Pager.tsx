interface PagerProps {
  total: number;
  offset: number;
  limit: number;
  onMove: (direction: "prev" | "next") => void;
}

export function Pager({ total, offset, limit, onMove }: PagerProps) {
  if (total <= limit) {
    return (
      <div className="pager">
        <span className="pager-copy">Showing {total} item(s).</span>
      </div>
    );
  }

  const start = offset + 1;
  const end = Math.min(offset + limit, total);

  return (
    <div className="pager">
      <span className="pager-copy">
        Showing {start}-{end} of {total}
      </span>
      <div className="pager-actions">
        <button
          type="button"
          className="button button-secondary"
          disabled={offset <= 0}
          onClick={() => onMove("prev")}
        >
          Previous
        </button>
        <button
          type="button"
          className="button"
          disabled={offset + limit >= total}
          onClick={() => onMove("next")}
        >
          Next
        </button>
      </div>
    </div>
  );
}
