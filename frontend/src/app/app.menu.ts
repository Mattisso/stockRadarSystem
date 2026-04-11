import { MenuItem } from './core/navigation.service';

export const APP_MENU: MenuItem[] = [
  { label: 'Dashboard', icon: 'dashboard', route: '/dashboard' },
  { label: 'Universe', icon: 'public', route: '/universe', section: 'Market' },
  { label: 'Polygon Day', icon: 'calendar_today', route: '/polygon-data/day', section: 'Polygon' },
  { label: 'Polygon Minute', icon: 'schedule', route: '/polygon-data/minute' },
  { label: 'Polygon Second', icon: 'timer', route: '/polygon-data/second' },
  { label: 'Polygon Ticks', icon: 'multiline_chart', route: '/polygon-data/ticks' },
  { label: 'Aggregate Live State', icon: 'monitoring', route: '/aggregate-data/live-state', section: 'Aggregate' },
  { label: 'Aggregate Candidates', icon: 'filter_alt', route: '/aggregate-data/candidate-events' },
  { label: 'Signals', icon: 'bolt', route: '/signals' },
  { label: 'State Monitor', icon: 'device_hub', route: '/state-monitor' },
  { label: 'Secret Sauce', icon: 'science', route: '/secret-sauce' },
  { label: 'Trades', icon: 'swap_horiz', route: '/trades', section: 'Trading' },
  { label: 'Analytics', icon: 'analytics', route: '/analytics' },
  { label: 'Settings', icon: 'settings', route: '/settings', section: 'System' },
];
