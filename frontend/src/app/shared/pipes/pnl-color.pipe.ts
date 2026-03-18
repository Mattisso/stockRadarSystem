import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'pnlColor',
  standalone: true,
})
export class PnlColorPipe implements PipeTransform {
  transform(value: number | null): string {
    if (value === null || value === undefined) return 'pnl-neutral';
    if (value > 0) return 'pnl-positive';
    if (value < 0) return 'pnl-negative';
    return 'pnl-neutral';
  }
}
