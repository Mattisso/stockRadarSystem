import { Injectable, signal } from '@angular/core';

export interface MenuItem {
  label: string;
  icon: string;
  route: string;
  section?: string;
}

@Injectable({ providedIn: 'root' })
export class NavigationService {
  collapsed = signal(false);

  toggleCollapsed(): void {
    this.collapsed.update(v => !v);
  }
}
