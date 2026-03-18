import { Component, ChangeDetectionStrategy, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { StatusBadgeComponent } from '../../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-settings-page',
  standalone: true,
  imports: [DatePipe, MatCardModule, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './settings-page.component.html',
  styleUrl: './settings-page.component.scss',
})
export class SettingsPageComponent implements OnInit {
  private readonly http = inject(HttpClient);

  healthy = signal(false);
  checkedAt = signal<string | null>(null);

  ngOnInit(): void {
    this.http.get<{ status: string }>('/api/health').subscribe({
      next: res => {
        this.healthy.set(res.status === 'ok');
        this.checkedAt.set(new Date().toISOString());
      },
      error: () => {
        this.healthy.set(false);
        this.checkedAt.set(new Date().toISOString());
      },
    });
  }
}
