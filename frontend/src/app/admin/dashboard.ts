import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api, errorText } from '../api';
import { clearToken } from '../auth';
import { AdminEntry, AdminWinner, Charity, DrawRequest, Prize, PublicSettings } from '../models';

type Tab = 'entries' | 'prizes' | 'charities' | 'draw' | 'settings';

@Component({
  selector: 'app-admin-dashboard',
  imports: [FormsModule, DatePipe, RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class AdminDashboard implements OnInit {
  private api = inject(Api);
  private router = inject(Router);

  tab = signal<Tab>('entries');
  entries = signal<AdminEntry[]>([]);
  prizes = signal<Prize[]>([]);
  charities = signal<Charity[]>([]);
  winners = signal<AdminWinner[]>([]);
  settings = signal<PublicSettings | null>(null);
  filter = signal('');
  message = signal('');
  error = signal('');
  copied = signal<number | null>(null);

  // Raffle draw state
  drawPool = signal<'locked' | 'all_claimed'>('locked');
  allowRepeatPerson = signal(false);
  selectedPrizeId = signal<number | null>(null);
  customPrizeTitle = signal('');
  drawing = signal(false);
  animatedNumber = signal<number | null>(null);
  latestWinner = signal<AdminWinner | null>(null);
  copiedSummary = signal(false);

  form = { title: '', subtitle: '', price_pounds: 5, charity_percent: 50, charity_name: '', hold_days: 5 };
  grid = { cols: 10, rows: 6 };
  newPrize = { title: '', description: '' };
  newCharity = { name: '', description: '' };

  visible = computed(() => {
    const q = this.filter().trim().toLowerCase();
    if (!q) return this.entries();
    return this.entries().filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.employee_number.toLowerCase().includes(q) ||
        e.lockin_code.toLowerCase().includes(q) ||
        e.tiles.join(',').split(',').includes(q),
    );
  });
  totals = computed(() => {
    const all = this.entries();
    const sum = (list: AdminEntry[]) => list.reduce((a, e) => a + e.total_pounds, 0);
    const locked = all.filter((e) => e.status === 'locked');
    return {
      held: all.filter((e) => e.status === 'provisional').length,
      locked: locked.length,
      lockedPounds: sum(locked),
      pendingPounds: sum(all.filter((e) => e.status === 'provisional')),
    };
  });

  eligibleTiles = computed(() => {
    const pool = this.drawPool();
    const allowRepeat = this.allowRepeatPerson();
    const currentWinners = this.winners();
    const wonTiles = new Set(currentWinners.map((w) => w.tile_number));
    const wonEmployees = new Set(
      currentWinners.map((w) => w.employee_number.trim().toLowerCase()),
    );

    const allEntries = this.entries();
    const targetEntries =
      pool === 'locked'
        ? allEntries.filter((e) => e.status === 'locked')
        : allEntries.filter((e) => e.status === 'locked' || e.status === 'provisional');

    const eligible: { tile: number; entry: AdminEntry }[] = [];
    for (const entry of targetEntries) {
      if (!allowRepeat && wonEmployees.has(entry.employee_number.trim().toLowerCase())) {
        continue;
      }
      for (const t of entry.tiles) {
        if (!wonTiles.has(t)) {
          eligible.push({ tile: t, entry });
        }
      }
    }
    return eligible;
  });

  ngOnInit() {
    this.loadAll();
  }

  loadAll() {
    this.api.adminEntries().subscribe({ next: (e) => this.entries.set(e), error: (e) => this.fail(e) });
    this.api.prizes().subscribe((p) => this.prizes.set(p));
    this.api.charities().subscribe((c) => this.charities.set(c));
    this.api.adminWinners().subscribe((w) => this.winners.set(w));
    this.api.board().subscribe((b) => this.applySettings(b.settings));
  }

  private applySettings(s: PublicSettings) {
    this.settings.set(s);
    this.form = {
      title: s.title,
      subtitle: s.subtitle,
      price_pounds: s.price_pounds,
      charity_percent: s.charity_percent,
      charity_name: s.charity_name,
      hold_days: s.hold_days,
    };
    this.grid = { cols: s.cols, rows: s.rows };
  }

  private fail(e: any) {
    if (e.status === 401) {
      this.logout();
      return;
    }
    this.message.set('');
    this.error.set(errorText(e));
  }

  private ok(msg: string) {
    this.error.set('');
    this.message.set(msg);
  }

  logout() {
    clearToken();
    this.router.navigateByUrl('/admin/login');
  }

  replace(updated: AdminEntry) {
    this.entries.update((list) => list.map((e) => (e.id === updated.id ? updated : e)));
  }

  async copy(e: AdminEntry) {
    await navigator.clipboard?.writeText(e.lockin_code);
    this.copied.set(e.id);
    setTimeout(() => this.copied.set(null), 1500);
  }

  regenerate(e: AdminEntry) {
    if (!confirm(`Generate a new lock-in code for ${e.name}? The old code stops working and their hold is extended.`)) return;
    this.api.regenerate(e.id).subscribe({
      next: (u) => { this.replace(u); this.ok(`New code for ${u.name}: ${u.lockin_code}`); },
      error: (er) => this.fail(er),
    });
  }

  lock(e: AdminEntry) {
    this.api.adminLock(e.id).subscribe({
      next: (u) => { this.replace(u); this.ok(`${u.name}'s squares are locked in.`); },
      error: (er) => this.fail(er),
    });
  }

  release(e: AdminEntry) {
    if (e.charity_vote) return;
    if (!confirm(`Release ${e.tiles.length} square(s) held by ${e.name}? They become available to everyone.`)) return;
    this.api.release(e.id).subscribe({
      next: () => { this.entries.update((l) => l.filter((x) => x.id !== e.id)); this.ok('Squares released.'); },
      error: (er) => this.fail(er),
    });
  }

  saveSettings() {
    this.api.saveSettings(this.form).subscribe({
      next: (s) => { this.applySettings(s); this.ok('Settings saved.'); },
      error: (e) => this.fail(e),
    });
  }

  saveGrid() {
    this.api.saveGrid(this.grid.cols, this.grid.rows).subscribe({
      next: (s) => { this.applySettings(s); this.ok(`Grid is now ${s.cols} × ${s.rows}.`); },
      error: (e) => this.fail(e),
    });
  }

  upload(ev: Event) {
    const input = ev.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.api.uploadImage(file).subscribe({
      next: (s) => { this.applySettings(s); this.ok('Image uploaded and fitted to the grid.'); input.value = ''; },
      error: (e) => { this.fail(e); input.value = ''; },
    });
  }

  removeImage() {
    this.api.deleteImage().subscribe({
      next: (s) => { this.applySettings(s); this.ok('Image removed.'); },
      error: (e) => this.fail(e),
    });
  }

  addPrize() {
    if (!this.newPrize.title.trim()) return;
    this.api.addPrize(this.newPrize.title, this.newPrize.description).subscribe({
      next: (p) => { this.prizes.update((l) => [...l, p]); this.newPrize = { title: '', description: '' }; this.ok('Prize added.'); },
      error: (e) => this.fail(e),
    });
  }

  savePrize(p: Prize) {
    this.api.updatePrize(p).subscribe({
      next: () => this.ok(`Saved "${p.title}".`),
      error: (e) => this.fail(e),
    });
  }

  deletePrize(p: Prize) {
    if (!confirm(`Delete prize "${p.title}"?`)) return;
    this.api.deletePrize(p.id).subscribe({
      next: () => { this.prizes.update((l) => l.filter((x) => x.id !== p.id)); this.ok('Prize deleted.'); },
      error: (e) => this.fail(e),
    });
  }

  addCharity() {
    if (!this.newCharity.name.trim()) return;
    this.api.addCharity(this.newCharity.name, this.newCharity.description).subscribe({
      next: (charity) => {
        this.charities.update((items) => [...items, charity]);
        this.newCharity = { name: '', description: '' };
        this.ok('Charity option added.');
      },
      error: (e) => this.fail(e),
    });
  }

  saveCharity(charity: Charity) {
    this.api.updateCharity(charity).subscribe({
      next: (updated) => {
        this.charities.update((items) => items.map((item) => item.id === updated.id ? updated : item));
        this.ok(`Saved "${updated.name}".`);
      },
      error: (e) => this.fail(e),
    });
  }

  deleteCharity(charity: Charity) {
    if (charity.votes || !confirm(`Delete charity option "${charity.name}"?`)) return;
    this.api.deleteCharity(charity.id).subscribe({
      next: () => {
        this.charities.update((items) => items.filter((item) => item.id !== charity.id));
        this.ok('Charity option deleted.');
      },
      error: (e) => this.fail(e),
    });
  }

  performDraw() {
    if (this.drawing() || this.eligibleTiles().length === 0) return;
    this.drawing.set(true);
    this.error.set('');
    this.message.set('');
    this.latestWinner.set(null);

    const poolSquares = this.eligibleTiles().map((x) => x.tile);
    let counter = 0;
    const rollInterval = setInterval(() => {
      const rand =
        poolSquares[Math.floor(Math.random() * poolSquares.length)] ??
        Math.floor(Math.random() * 100) + 1;
      this.animatedNumber.set(rand);
      counter++;
    }, 70);

    const payload: DrawRequest = {
      pool: this.drawPool(),
      allow_repeat_person: this.allowRepeatPerson(),
      prize_id: this.selectedPrizeId() || undefined,
      prize_title: this.customPrizeTitle().trim() || undefined,
    };

    this.api.draw(payload).subscribe({
      next: (winner) => {
        const elapsed = counter * 70;
        const remaining = Math.max(0, 1600 - elapsed);
        setTimeout(() => {
          clearInterval(rollInterval);
          this.animatedNumber.set(winner.tile_number);
          this.latestWinner.set(winner);
          this.winners.update((w) => [...w, winner]);
          this.drawing.set(false);
          this.ok(`🎉 Winning square #${winner.tile_number} drawn for ${winner.name}!`);
        }, remaining);
      },
      error: (e) => {
        clearInterval(rollInterval);
        this.drawing.set(false);
        this.animatedNumber.set(null);
        this.fail(e);
      },
    });
  }

  deleteWinner(w: AdminWinner) {
    if (
      !confirm(
        `Remove winning square #${w.tile_number} (${w.name})? This square will return to the eligible draw pool.`,
      )
    )
      return;
    this.api.deleteWinner(w.id).subscribe({
      next: () => {
        this.winners.update((list) => list.filter((x) => x.id !== w.id));
        if (this.latestWinner()?.id === w.id) {
          this.latestWinner.set(null);
          this.animatedNumber.set(null);
        }
        this.ok(`Removed square #${w.tile_number} from winners.`);
      },
      error: (e) => this.fail(e),
    });
  }

  resetAll() {
    if (this.entries().length === 0) return;
    const typed = prompt(
      'This deletes ALL entries, charity votes and drawn winners, and frees every square. This cannot be undone.\n\nType RESET to confirm:',
    );
    if (typed?.trim().toUpperCase() !== 'RESET') return;
    this.api.resetAll().subscribe({
      next: () => {
        this.entries.set([]);
        this.winners.set([]);
        this.latestWinner.set(null);
        this.animatedNumber.set(null);
        this.loadAll();
        this.ok('Everything has been reset. All squares are available again.');
      },
      error: (e) => this.fail(e),
    });
  }

  resetWinners() {
    if (this.winners().length === 0) return;
    if (!confirm('Are you sure you want to reset ALL drawn winners? This cannot be undone.')) return;
    this.api.resetWinners().subscribe({
      next: () => {
        this.winners.set([]);
        this.latestWinner.set(null);
        this.animatedNumber.set(null);
        this.ok('All raffle draws have been reset.');
      },
      error: (e) => this.fail(e),
    });
  }

  async copySummary() {
    const items = this.winners();
    if (!items.length) return;
    const lines = [
      `🎄 ${this.settings()?.title ?? 'Christmas Raffle'} — Winners 🎄`,
      '',
      ...items.map((w, idx) => {
        const prize = w.prize_title ? ` [${w.prize_title}]` : '';
        return `${idx + 1}. Square #${w.tile_number}${prize}: ${w.name} (${w.employee_number})${
          w.email ? ' · ' + w.email : ''
        }`;
      }),
      '',
      `Generated by Christmas Raffle Webapp`,
    ];
    await navigator.clipboard?.writeText(lines.join('\n'));
    this.copiedSummary.set(true);
    setTimeout(() => this.copiedSummary.set(false), 2000);
  }
}

