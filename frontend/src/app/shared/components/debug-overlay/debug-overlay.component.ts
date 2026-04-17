import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DebugStorageService } from '../../../core/debug-storage.service';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

@Component({
  selector: 'app-debug-overlay',
  standalone: true,
  imports: [CommonModule, MatIconModule, MatButtonModule, MatSnackBarModule],
  templateUrl: './debug-overlay.component.html',
  styleUrl: './debug-overlay.component.scss'
})
export class DebugOverlayComponent {
  readonly debugStorage = inject(DebugStorageService);
  private readonly clipboard = inject(Clipboard);
  private readonly snackBar = inject(MatSnackBar);

  expanded = signal(false);

  toggle() {
    this.expanded.update(v => !v);
  }

  copyCurl() {
    const request = this.debugStorage.lastRequest();
    if (request?.curl) {
      this.clipboard.copy(request.curl);
      this.snackBar.open('cURL copied to clipboard', 'Dismiss', { duration: 2000 });
    }
  }
}
