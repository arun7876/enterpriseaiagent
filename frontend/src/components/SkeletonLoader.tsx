export function StatCardSkeleton() {
  return (
    <div className="animate-pulse rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
      <div className="flex items-center justify-between mb-3">
        <div className="h-3 w-24 rounded bg-slate-200" />
        <div className="h-8 w-8 rounded-lg bg-slate-100" />
      </div>
      <div className="h-7 w-16 rounded bg-slate-200 my-2" />
      <div className="h-3 w-32 rounded bg-slate-100" />
    </div>
  )
}

export function TableRowSkeleton({ cols = 5 }: { cols?: number }) {
  return (
    <tr className="animate-pulse border-b border-slate-100">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-5 py-4">
          <div className="h-4 rounded bg-slate-200" style={{ width: `${Math.floor(40 + (i * 15) % 50)}%` }} />
        </td>
      ))}
    </tr>
  )
}
