import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'signalType',
  standalone: true,
})
export class SignalTypePipe implements PipeTransform {
  transform(value: string): string {
    switch (value) {
      case 'breakout': return 'Breakout';
      case 'false_breakout': return 'False Breakout';
      default: return value;
    }
  }
}
