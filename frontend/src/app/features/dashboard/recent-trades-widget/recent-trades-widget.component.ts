import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { CurrencyPipe, DatePipe, UpperCasePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { ITrade } from '../../../shared/models';
import { PnlColorPipe } from '../../../shared/pipes/pnl-color.pipe';

@Component({
  selector: 'app-recent-trades-widget',
  standalone: true,
  imports: [CurrencyPipe, DatePipe, UpperCasePipe, MatCardModule, MatListModule, MatIconModule, PnlColorPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './recent-trades-widget.component.html',
  styleUrl: './recent-trades-widget.component.scss',
})
export class RecentTradesWidgetComponent {
  trades = input<ITrade[]>([]);
}
