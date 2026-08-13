export function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">{children}</table>
    </div>
  )
}

export function Th({ children, align = 'left' }: { children: React.ReactNode; align?: 'left' | 'right' }) {
  return (
    <th
      className={`border-b border-[var(--color-line)] pb-2 font-medium text-[var(--color-muted)] ${align === 'right' ? 'text-right' : 'text-left'}`}
    >
      {children}
    </th>
  )
}

export function Td({ children, align = 'left' }: { children: React.ReactNode; align?: 'left' | 'right' }) {
  return (
    <td
      className={`tabular border-b border-[var(--color-line)] py-2 ${align === 'right' ? 'text-right' : 'text-left'}`}
    >
      {children}
    </td>
  )
}
