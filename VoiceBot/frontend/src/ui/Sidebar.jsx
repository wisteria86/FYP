import { Icon } from '../ui/core'

export function Sidebar({ view, setView, health, user, onLogout }) {
  const nav = [
    ['home', 'Home', 'dashboard'],
    ['path', 'Learning Path', 'sparkles'],
    ['training', 'Training', 'mic'],
    ['progress', 'Progress', 'chart'],
    ['plan', 'Training Plan', 'calendar'],
    ['resources', 'Resources', 'book'],
    ['settings', 'Settings', 'settings'],
  ]
  return <aside className="sidebar">
    <div className="brand"><span className="brand-mark" aria-hidden="true">光</span><div><strong>Hikari</strong></div></div>
    <nav>{nav.map(([id, label, icon]) => <button key={id} className={view === id ? 'active' : ''} aria-current={view === id ? 'page' : undefined} onClick={() => setView(id)}><Icon name={icon}/>{label}</button>)}</nav>
    <div className="profile"><span>{(user?.name||'User').slice(0,1)}</span><div><strong>{user?.name||'User'}</strong><small>{health.status==='ready'?'Voice ready':health.status==='loading'?'Connecting…':'Text practice only'}</small></div><button onClick={onLogout} title="Sign out" aria-label="Sign out"><Icon name="logout"/></button></div>
  </aside>
}
