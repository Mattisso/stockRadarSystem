import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { DebugOverlayComponent } from './shared/components/debug-overlay/debug-overlay.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, DebugOverlayComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
