import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { IPortfolio } from '../../../shared/models';
import { PnlColorPipe } from '../../../shared/pipes/pnl-color.pipe';

@Component({
  selector: 'app-portfolio-summary-widget',
  standalone: true,
  imports: [CurrencyPipe, MatCardModule, PnlColorPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './portfolio-summary-widget.component.html',
  styleUrl: './portfolio-summary-widget.component.scss',
})
export class PortfolioSummaryWidgetComponent {
  portfolio = input<IPortfolio | null>(null);
}
