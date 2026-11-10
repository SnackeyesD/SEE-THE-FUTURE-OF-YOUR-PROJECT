export type LogLevel = "info" | "success" | "error";

export interface LogEntry {
  id: number;
  at: string;
  level: LogLevel;
  message: string;
}
