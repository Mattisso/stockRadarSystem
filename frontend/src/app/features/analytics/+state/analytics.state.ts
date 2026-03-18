import { IKpi, IMlStatus, ISignalAccuracyBucket } from '../../../shared/models';

export interface AnalyticsState {
  kpis: IKpi | null;
  mlStatus: IMlStatus | null;
  signalAccuracy: ISignalAccuracyBucket[];
  loading: boolean;
  retraining: boolean;
  error: string | null;
}

export const initialAnalyticsState: AnalyticsState = {
  kpis: null,
  mlStatus: null,
  signalAccuracy: [],
  loading: false,
  retraining: false,
  error: null,
};
