import { Component, ChangeDetectionStrategy, inject, OnInit } from '@angular/core';
import { Store } from '@ngrx/store';
import { TradesActions } from '../+state/trades.actions';
import { selectAllTrades, selectTradesLoading, selectTradesError } from '../+state/trades.reducer';
import { TradesTableComponent } from '../trades-table/trades-table.component';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';

@Component({
  selector: 'app-trades-page',
  standalone: true,
  imports: [TradesTableComponent, LoadingComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './trades-page.component.html',
  styleUrl: './trades-page.component.scss',
})
export class TradesPageComponent implements OnInit {
  private readonly store = inject(Store);

  trades = this.store.selectSignal(selectAllTrades);
  loading = this.store.selectSignal(selectTradesLoading);
  error = this.store.selectSignal(selectTradesError);

  ngOnInit(): void {
    this.store.dispatch(TradesActions.loadTrades());
  }
}
