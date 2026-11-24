// Shapes the backend sends and accepts. Field names match the backend (snake_case).

export type Role = "tech" | "reviewer";

export interface Me {
  id: number;
  name: string;
  role: Role;
  email: string | null;
}
