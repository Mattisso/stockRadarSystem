import { Component, ChangeDetectionStrategy, inject, OnInit, OnDestroy } from '@angular/core';
import { Store } from '@ngrx/store';
import { SignalsActions } from '../+state/signals.actions';
import {
  selectAllSignals,
  selectSignalsLoading,
  selectSignalsError,
  selectSelectedSignal,
} from '../+state/signals.reducer';
import { SignalsTableComponent } from '../signals-table/signals-table.component';
import { SignalDetailComponent } from '../signal-detail/signal-detail.component';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';

@Component({
  selector: 'app-signals-page',
  standalone: true,
  imports: [SignalsTableComponent, SignalDetailComponent, LoadingComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './signals-page.component.html',
  styleUrl: './signals-page.component.scss',
})
export class SignalsPageComponent implements OnInit, OnDestroy {
  private readonly store = inject(Store);

  signals = this.store.selectSignal(selectAllSignals);
  loading = this.store.selectSignal(selectSignalsLoading);
  error = this.store.selectSignal(selectSignalsError);
  selectedSignal = this.store.selectSignal(selectSelectedSignal);

  ngOnInit(): void {
    this.store.dispatch(SignalsActions.loadSignals());
    this.store.dispatch(SignalsActions.startPolling());
  }

  ngOnDestroy(): void {
    this.store.dispatch(SignalsActions.stopPolling());
  }

  onSignalSelected(id: number): void {
    this.store.dispatch(SignalsActions.selectSignal({ id }));
  }
}
