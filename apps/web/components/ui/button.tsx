type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost'
}

export function Button({ variant = 'primary', className = '', ...props }: Props) {
  const base = 'rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50'
  const styles =
    variant === 'primary'
      ? 'bg-[var(--color-accent)] text-white'
      : 'border border-[var(--color-line)] hover:bg-[var(--color-canvas)]'
  return <button className={`${base} ${styles} ${className}`} {...props} />
}
