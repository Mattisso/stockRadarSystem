import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login-page',
  standalone: true,
  imports: [FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="login-container">
      <mat-card class="login-card">
        <mat-card-header>
          <mat-icon mat-card-avatar>radar</mat-icon>
          <mat-card-title>Stock Radar</mat-card-title>
          <mat-card-subtitle>Enter your API key to continue</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>API Key</mat-label>
            <input matInput type="password" [(ngModel)]="apiKey" (keyup.enter)="login()" />
          </mat-form-field>
          @if (error()) {
            <p class="error-text">{{ error() }}</p>
          }
        </mat-card-content>
        <mat-card-actions align="end">
          <button mat-flat-button color="primary" (click)="login()" [disabled]="loading()">
            {{ loading() ? 'Authenticating...' : 'Login' }}
          </button>
        </mat-card-actions>
      </mat-card>
    </div>
  `,
  styles: `
    .login-container {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
    }
    .login-card {
      width: 380px;
      max-width: 90vw;
    }
    .full-width {
      width: 100%;
    }
    .error-text {
      color: var(--mat-sys-error);
      font-size: 0.85rem;
      margin: 0;
    }
  `,
})
export class LoginPageComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  apiKey = '';
  error = signal('');
  loading = signal(false);

  login(): void {
    if (!this.apiKey.trim()) return;

    this.loading.set(true);
    this.error.set('');

    this.auth.login(this.apiKey).subscribe({
      next: () => {
        this.loading.set(false);
        this.router.navigate(['/dashboard']);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Invalid API key');
      },
    });
  }
}
