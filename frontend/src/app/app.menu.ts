import { MenuItem } from './core/navigation.service';

export const APP_MENU: MenuItem[] = [
  { label: 'Dashboard', icon: 'dashboard', route: '/dashboard' },
  { label: 'Universe', icon: 'public', route: '/universe', section: 'Market' },
  { label: 'Signals', icon: 'bolt', route: '/signals' },
  { label: 'Trades', icon: 'swap_horiz', route: '/trades', section: 'Trading' },
  { label: 'Analytics', icon: 'analytics', route: '/analytics' },
  { label: 'Settings', icon: 'settings', route: '/settings', section: 'System' },
];
