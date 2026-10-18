import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  subtitle: string
  tag?: string
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, tag = 'WORKSPACE', actions }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-col gap-4 border-b border-slate-200/80 pb-6 md:flex-row md:items-end md:justify-between">
      <div>
        <p className="text-[11px] font-bold tracking-[0.2em] uppercase text-indigo-600 font-mono">
          {tag}
        </p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 md:text-3xl font-display">
          {title}
        </h2>
        <p className="mt-1.5 text-sm text-slate-500 max-w-2xl leading-relaxed">
          {subtitle}
        </p>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </div>
  )
}
