import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Activity,
  BarChart3,
  BookOpen,
  Bot,
  ChevronLeft,
  ChevronRight,
  FileText,
  LayoutDashboard,
  LogOut,
  Settings,
  ShieldCheck,
  X,
} from 'lucide-react'
import type { AuthUser } from '../services/api'

export const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/assistant', label: 'AI Assistant', icon: Bot },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/analytics', label: 'Data Analytics', icon: BarChart3 },
  { to: '/status', label: 'System Status', icon: Activity },
  { to: '/about', label: 'About This Project', icon: BookOpen },
  { to: '/settings', label: 'Settings', icon: Settings },
]

interface SidebarProps {
  user: AuthUser
  onSignOut: () => void
  mobileOpen: boolean
  onCloseMobile: () => void
}

export function Sidebar({ user, onSignOut, mobileOpen, onCloseMobile }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  const roleColor = {
    admin: 'bg-purple-50 text-purple-700 border-purple-200',
    analyst: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    viewer: 'bg-slate-100 text-slate-700 border-slate-200',
  }[user.role] ?? 'bg-slate-100 text-slate-700 border-slate-200'

  const userInitial = (user.email.charAt(0) || 'U').toUpperCase()

  const navContent = (
    <div className="flex h-full flex-col justify-between">
      {/* Top brand header */}
      <div>
        <div className={`flex items-center border-b border-slate-200/80 p-4 transition-all ${collapsed ? 'justify-center' : 'justify-between px-5'}`}>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm ring-4 ring-indigo-50">
              <ShieldCheck className="h-5 w-5" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <span className="block text-[10px] font-bold tracking-[0.2em] uppercase text-indigo-600 font-mono">
                  Enterprise
                </span>
                <span className="block text-base font-bold text-slate-900 font-display truncate">
                  AI Research
                </span>
              </div>
            )}
          </div>

          {/* Desktop collapse toggle */}
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="hidden lg:flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-800 transition shadow-xs"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
          </button>

          {/* Mobile close button */}
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 text-slate-500 hover:text-slate-900"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation list */}
        <nav className="mt-4 space-y-1.5 px-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onCloseMobile}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-sm font-semibold'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                } ${collapsed ? 'justify-center px-2' : ''}`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={`h-4 w-4 shrink-0 transition-transform duration-200 group-hover:scale-110 ${
                      isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-700'
                    }`}
                  />
                  {!collapsed && <span className="truncate">{label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* User profile & logout bottom area */}
      <div className="border-t border-slate-200/80 p-3 bg-slate-50/50">
        <div className={`flex items-center gap-3 rounded-xl p-2 transition ${collapsed ? 'justify-center' : 'justify-between'}`}>
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs ring-2 ring-indigo-200/60 shadow-xs">
              {userInitial}
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-slate-800" title={user.email}>
                  {user.email}
                </p>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span className={`inline-block rounded-md border px-1.5 py-0.2 text-[10px] font-semibold uppercase tracking-wider ${roleColor}`}>
                    {user.role}
                  </span>
                </div>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onSignOut}
            title="Sign out"
            aria-label="Sign out"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-200/80 bg-white text-slate-500 hover:bg-rose-50 hover:text-rose-600 hover:border-rose-200 transition shadow-2xs"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside
        className={`hidden lg:flex lg:flex-col border-r border-slate-200 bg-white sticky top-0 h-screen transition-all duration-300 z-30 shrink-0 ${
          collapsed ? 'w-[72px]' : 'w-64'
        }`}
      >
        {navContent}
      </aside>

      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-xs transition-opacity lg:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Mobile Drawer Slider */}
      {mobileOpen && (
        <aside
          className="fixed inset-y-0 left-0 z-50 w-72 bg-white shadow-xl lg:hidden"
        >
          {navContent}
        </aside>
      )}
    </>
  )
}
