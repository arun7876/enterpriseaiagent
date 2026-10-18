export type StatusType = 'healthy' | 'operational' | 'ready' | 'unavailable' | 'degraded' | 'offline' | 'not_loaded' | 'unknown'

interface StatusBadgeProps {
  value: StatusType | string
  label?: string
  size?: 'sm' | 'md'
}

export function StatusBadge({ value, label, size = 'md' }: StatusBadgeProps) {
  const normalized = value.toLowerCase()

  const isGreen = ['healthy', 'operational', 'ready', 'online', 'indexed', 'already_indexed', 'success', 'available', 'writable', 'model_available', 'loaded'].includes(normalized)
  const isAmber = ['unavailable', 'degraded', 'not_loaded', 'offline', 'empty', 'pending'].includes(normalized)
  const isRed = ['failed', 'error', 'model_missing', 'unreachable'].includes(normalized)

  let badgeClasses = 'bg-slate-100 text-slate-600 border-slate-200'
  let dotClasses = 'bg-slate-400'

  if (isGreen) {
    badgeClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
    dotClasses = 'bg-emerald-500'
  } else if (isAmber) {
    badgeClasses = 'bg-amber-50 text-amber-700 border-amber-200/80'
    dotClasses = 'bg-amber-500'
  } else if (isRed) {
    badgeClasses = 'bg-rose-50 text-rose-700 border-rose-200/80'
    dotClasses = 'bg-rose-500'
  }

  const displayLabel = label ?? (
    isGreen ? (value === 'loaded' ? 'Loaded' : 'Healthy') :
    isAmber ? (value === 'not_loaded' ? 'Not loaded' : 'Unavailable') :
    isRed ? 'Error' :
    value
  )

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${sizeClasses} ${badgeClasses}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dotClasses} ${isGreen ? 'animate-pulse-subtle' : ''}`} />
      <span>{displayLabel}</span>
    </span>
  )
}
