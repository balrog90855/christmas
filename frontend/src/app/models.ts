export interface PublicSettings {
  title: string;
  subtitle: string;
  cols: number;
  rows: number;
  price_pounds: number;
  charity_percent: number;
  charity_name: string;
  hold_days: number;
  image_url: string | null;
}

export interface PublicEntry {
  id: number;
  display_name: string;
  status: 'provisional' | 'locked';
  tiles: number[];
  expires_at: string;
  has_voted: boolean;
}

export interface Board {
  settings: PublicSettings;
  entries: PublicEntry[];
  tiles_total: number;
  tiles_available: number;
  tiles_sold: number;
}

export interface Prize {
  id: number;
  position: number;
  title: string;
  description: string;
}

export interface Charity {
  id: number;
  position: number;
  name: string;
  description: string;
  votes: number;
}

export interface ConfirmRequest {
  tiles: number[];
  name: string;
  employee_number: string;
  email?: string | null;
}

export interface ConfirmResponse {
  entry: PublicEntry;
  total_pounds: number;
  message: string;
}

export interface AdminEntry {
  id: number;
  name: string;
  employee_number: string;
  email: string | null;
  lockin_code: string;
  status: 'provisional' | 'locked';
  tiles: number[];
  total_pounds: number;
  created_at: string;
  expires_at: string;
  locked_at: string | null;
  failed_attempts: number;
  charity_vote: string | null;
}

export interface PublicWinner {
  id: number;
  tile_number: number;
  display_name: string;
  prize_title: string | null;
  drawn_at: string;
}

export interface AdminWinner {
  id: number;
  tile_number: number;
  entry_id: number;
  name: string;
  employee_number: string;
  email: string | null;
  prize_id: number | null;
  prize_title: string | null;
  drawn_at: string;
}

export interface DrawRequest {
  prize_id?: number | null;
  prize_title?: string | null;
  pool?: 'locked' | 'all_claimed';
  allow_repeat_person?: boolean;
}

