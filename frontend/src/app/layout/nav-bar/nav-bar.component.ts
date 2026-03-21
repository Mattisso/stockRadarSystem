import { Component, ChangeDetectionStrategy, inject, input, output } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-nav-bar',
  standalone: true,
  imports: [MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './nav-bar.component.html',
  styleUrl: './nav-bar.component.scss',
})
export class NavBarComponent {
  private readonly auth = inject(AuthService);

  isDark = input(false);
  menuToggled = output<void>();
  themeToggled = output<void>();

  logout(): void {
    this.auth.logout();
  }
}
