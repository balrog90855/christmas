import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import {
  AdminEntry,
  AdminWinner,
  Board,
  Charity,
  ConfirmRequest,
  ConfirmResponse,
  DrawRequest,
  Prize,
  PublicEntry,
  PublicSettings,
  PublicWinner,
} from './models';

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);

  board = () => this.http.get<Board>('/api/board');
  prizes = () => this.http.get<Prize[]>('/api/prizes');
  charities = () => this.http.get<Charity[]>('/api/charities');
  winners = () => this.http.get<PublicWinner[]>('/api/winners');
  confirm = (body: ConfirmRequest) => this.http.post<ConfirmResponse>('/api/entries', body);
  lockIn = (id: number, code: string) =>
    this.http.post<PublicEntry>(`/api/entries/${id}/lockin`, { code });
  vote = (entry_id: number, code: string, charity_id: number) =>
    this.http.post<{ charity_name: string; message: string }>('/api/votes', {
      entry_id,
      code,
      charity_id,
    });

  login = (username: string, password: string) =>
    this.http.post<{ access_token: string }>('/api/admin/login', { username, password });
  adminEntries = () => this.http.get<AdminEntry[]>('/api/admin/entries');
  regenerate = (id: number) =>
    this.http.post<AdminEntry>(`/api/admin/entries/${id}/regenerate`, {});
  adminLock = (id: number) => this.http.post<AdminEntry>(`/api/admin/entries/${id}/lock`, {});
  resetAll = () => this.http.delete<void>('/api/admin/entries');
  release = (id: number) => this.http.delete<void>(`/api/admin/entries/${id}`);
  saveSettings = (body: Partial<PublicSettings>) =>
    this.http.put<PublicSettings>('/api/admin/settings', body);
  saveGrid = (cols: number, rows: number) =>
    this.http.put<PublicSettings>('/api/admin/grid', { cols, rows });
  uploadImage = (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return this.http.post<PublicSettings>('/api/admin/image', fd);
  };
  deleteImage = () => this.http.delete<PublicSettings>('/api/admin/image');
  addPrize = (title: string, description: string) =>
    this.http.post<Prize>('/api/admin/prizes', { title, description });
  updatePrize = (p: Prize) =>
    this.http.put<Prize>(`/api/admin/prizes/${p.id}`, {
      title: p.title,
      description: p.description,
    });
  deletePrize = (id: number) => this.http.delete<void>(`/api/admin/prizes/${id}`);
  addCharity = (name: string, description: string) =>
    this.http.post<Charity>('/api/admin/charities', { name, description });
  updateCharity = (charity: Charity) =>
    this.http.put<Charity>(`/api/admin/charities/${charity.id}`, {
      name: charity.name,
      description: charity.description,
    });
  deleteCharity = (id: number) => this.http.delete<void>(`/api/admin/charities/${id}`);
  adminWinners = () => this.http.get<AdminWinner[]>('/api/admin/winners');
  draw = (body: DrawRequest) => this.http.post<AdminWinner>('/api/admin/draw', body);
  deleteWinner = (id: number) => this.http.delete<void>(`/api/admin/winners/${id}`);
  resetWinners = () => this.http.delete<void>('/api/admin/winners');
}

export const errorText = (e: any, fallback = 'Something went wrong'): string => {
  const d = e?.error?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg;
  return fallback;
};
