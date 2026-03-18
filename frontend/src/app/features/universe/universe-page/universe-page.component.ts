import { Component, ChangeDetectionStrategy, inject, OnInit } from '@angular/core';
import { Store } from '@ngrx/store';
import { UniverseActions } from '../+state/universe.actions';
import { selectAllSymbols, selectUniverseLoading, selectUniverseError } from '../+state/universe.reducer';
import { UniverseTableComponent } from '../universe-table/universe-table.component';
import { LoadingComponent } from '../../../shared/components/loading/loading.component';

@Component({
  selector: 'app-universe-page',
  standalone: true,
  imports: [UniverseTableComponent, LoadingComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './universe-page.component.html',
  styleUrl: './universe-page.component.scss',
})
export class UniversePageComponent implements OnInit {
  private readonly store = inject(Store);

  symbols = this.store.selectSignal(selectAllSymbols);
  loading = this.store.selectSignal(selectUniverseLoading);
  error = this.store.selectSignal(selectUniverseError);

  ngOnInit(): void {
    this.store.dispatch(UniverseActions.loadSymbols());
  }
}
