import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'stageBadge',
  standalone: true,
})
export class StageBadgePipe implements PipeTransform {
  transform(value: string | null): string {
    switch (value) {
      case 'normal': return 'Normal';
      case 'watching': return 'Watching';
      case 'candidate': return 'Candidate';
      case 'l2_confirm': return 'L2 Confirm';
      case 'ready_to_buy': return 'Ready to Buy';
      default: return value ?? '-';
    }
  }
}
