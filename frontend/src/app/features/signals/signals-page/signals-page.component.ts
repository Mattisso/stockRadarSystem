import { Component, ChangeDetectionStrategy, computed, inject, OnDestroy, OnInit, signal } from '@angular/core';
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
import { SymbolStage } from '../../../shared/models';

type StageFilter = 'all' | 'unstaged' | SymbolStage;

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
  readonly stageFilter = signal<StageFilter>('all');
  readonly stageOptions: Array<{ value: StageFilter; label: string }> = [
    { value: 'all', label: 'All stages' },
    { value: 'unstaged', label: 'Unstaged' },
    { value: 'normal', label: 'Normal' },
    { value: 'watching', label: 'Watching' },
    { value: 'candidate', label: 'Candidate' },
    { value: 'l2_confirm', label: 'L2 Confirm' },
    { value: 'ready_to_buy', label: 'Ready to Buy' },
  ];
  readonly filteredSignals = computed(() => {
    const selectedStage = this.stageFilter();
    const signals = this.signals();

    if (selectedStage === 'all') {
      return signals;
    }

    if (selectedStage === 'unstaged') {
      return signals.filter((signal) => signal.stage === null);
    }

    return signals.filter((signal) => signal.stage === selectedStage);
  });

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

  onStageFilterChanged(value: string): void {
    this.stageFilter.set(value as StageFilter);
  }
}
