import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ThemeService } from '../../core/theme.service';
import { NavigationService } from '../../core/navigation.service';
import { NavBarComponent } from '../nav-bar/nav-bar.component';
import { SideNavComponent } from '../side-nav/side-nav.component';
import { APP_MENU } from '../../app.menu';

@Component({
  selector: 'app-layout-shell',
  standalone: true,
  imports: [RouterOutlet, NavBarComponent, SideNavComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './layout-shell.component.html',
  styleUrl: './layout-shell.component.scss',
})
export class LayoutShellComponent {
  private readonly themeService = inject(ThemeService);
  private readonly navService = inject(NavigationService);

  readonly menuItems = APP_MENU;
  readonly isDark = this.themeService.isDark;
  readonly collapsed = this.navService.collapsed;

  onMenuToggle(): void {
    this.navService.toggleCollapsed();
  }

  onThemeToggle(): void {
    this.themeService.toggle();
  }
}
