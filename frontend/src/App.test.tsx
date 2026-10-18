import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { apiClient } from './services/api'
import App from './App'

describe('App shell', () => {
  it('renders the dashboard navigation for a verified session', async () => {
    vi.spyOn(apiClient, 'hasSession').mockReturnValue(true)
    vi.spyOn(apiClient, 'getCurrentUser').mockResolvedValue({
      id: 'test-user',
      email: 'researcher@example.com',
      role: 'analyst',
      created_at: '2026-01-01T00:00:00Z',
    })

    render(<App />)

    expect(await screen.findAllByText('Overview')).toHaveLength(2)
    expect(screen.getAllByText('AI Assistant')).toHaveLength(1)
    expect(screen.getAllByText('Documents')).toHaveLength(2)
    expect(screen.getByText(/researcher@example.com/)).toBeInTheDocument()
  })

  it('renders all required navigation links in the sidebar', async () => {
    vi.spyOn(apiClient, 'hasSession').mockReturnValue(true)
    vi.spyOn(apiClient, 'getCurrentUser').mockResolvedValue({
      id: 'test-user',
      email: 'researcher@example.com',
      role: 'analyst',
      created_at: '2026-01-01T00:00:00Z',
    })

    render(<App />)

    const nav = await screen.findByRole('navigation')
    expect(within(nav).getByRole('link', { name: /Overview/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /AI Assistant/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Documents/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Data Analytics/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /System Status/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /About This Project/i })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Settings/i })).toBeInTheDocument()
  })

  it('navigates to About This Project page when link is clicked', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'hasSession').mockReturnValue(true)
    vi.spyOn(apiClient, 'getCurrentUser').mockResolvedValue({
      id: 'test-user',
      email: 'researcher@example.com',
      role: 'analyst',
      created_at: '2026-01-01T00:00:00Z',
    })

    render(<App />)

    const nav = await screen.findByRole('navigation')
    const aboutLink = within(nav).getByRole('link', { name: /About This Project/i })
    await user.click(aboutLink)

    expect(await screen.findByRole('heading', { name: 'About This Project' })).toBeInTheDocument()
    expect(screen.getByText(/How to Use the Enterprise AI Research Agent/i)).toBeInTheDocument()
    expect(screen.getByText(/End-to-End Information Flow/i)).toBeInTheDocument()
  })

  it('shows a sign-in screen without a stored session', () => {
    vi.spyOn(apiClient, 'hasSession').mockReturnValue(false)

    render(<App />)

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByText('AI Assistant')).not.toBeInTheDocument()
  })
})
