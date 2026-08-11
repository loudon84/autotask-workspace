export interface RpaComponent {
  id: string;
  name: string;
  type: string;
  category: string;
  description: string;
  inputParams: string[];
  outputResult: string;
  enabled: boolean;
}
