import { DatePipe } from '@angular/common';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api, errorText } from '../api';
import { Board, Charity, ConfirmResponse, Prize, PublicEntry, PublicWinner } from '../models';

@Component({
  selector: 'app-home',
  imports: [FormsModule, DatePipe, RouterLink],
  templateUrl: './home.html',
  styleUrl: './home.css',
})
export class Home implements OnInit, OnDestroy {
  private api = inject(Api);
  private timer?: ReturnType<typeof setInterval>;

  board = signal<Board | null>(null);
  prizes = signal<Prize[]>([]);
  charities = signal<Charity[]>([]);
  winners = signal<PublicWinner[]>([]);
  loadError = signal('');
  selected = signal<Set<number>>(new Set());
  hovered = signal<number | null>(null);
  now = signal(Date.now());

  // modals
  showHow = signal(false);
  hideGrid = signal(false);
  showConfirm = signal(false);
  result = signal<ConfirmResponse | null>(null);
  lockTarget = signal<PublicEntry | null>(null);
  lockDone = signal(false);
  voteDone = signal(false);
  voteMode = signal(false);
  selectedCharityId = signal<number | null>(null);
  busy = signal(false);
  formError = signal('');
  name = '';
  employeeNumber = '';
  email = '';
  code = '';

  settings = computed(() => this.board()?.settings ?? null);
  tileNumbers = computed(() => {
    const s = this.settings();
    return s ? Array.from({ length: s.cols * s.rows }, (_, i) => i + 1) : [];
  });
  owners = computed(() => {
    const map = new Map<number, PublicEntry>();
    for (const e of this.board()?.entries ?? []) for (const t of e.tiles) map.set(t, e);
    return map;
  });
  winnersMap = computed(() => {
    const map = new Map<number, PublicWinner>();
    for (const w of this.winners()) map.set(w.tile_number, w);
    return map;
  });
  selectedCount = computed(() => this.selected().size);
  total = computed(() => this.selectedCount() * (this.settings()?.price_pounds ?? 0));
  raised = computed(() => {
    const b = this.board();
    if (!b) return 0;
    return Math.floor((b.tiles_sold * b.settings.price_pounds * b.settings.charity_percent) / 100);
  });
  progress = computed(() => {
    const b = this.board();
    return b && b.tiles_total ? Math.round(((b.tiles_total - b.tiles_available) / b.tiles_total) * 100) : 0;
  });
  highlighted = computed(() => {
    const id = this.hovered();
    return new Set(this.board()?.entries.find((e) => e.id === id)?.tiles ?? []);
  });

  ngOnInit() {
    this.refresh();
    this.api.prizes().subscribe((p) => this.prizes.set(p));
    this.refreshCharities();
    this.refreshWinners();
    this.timer = setInterval(() => {
      this.now.set(Date.now());
      if (!this.showConfirm() && !this.lockTarget()) {
        this.refresh();
        this.refreshWinners();
      }
    }, 30000);
  }

  refreshCharities() {
    this.api.charities().subscribe({ next: (items) => this.charities.set(items) });
  }

  refreshWinners() {
    this.api.winners().subscribe({ next: (items) => this.winners.set(items) });
  }

  ngOnDestroy() {
    clearInterval(this.timer);
  }

  refresh() {
    this.api.board().subscribe({
      next: (b) => {
        this.board.set(b);
        this.loadError.set('');
        // drop selections that someone else has since taken
        const taken = new Set(b.entries.flatMap((e) => e.tiles));
        const keep = [...this.selected()].filter((t) => !taken.has(t));
        if (keep.length !== this.selected().size) this.selected.set(new Set(keep));
      },
      error: () => this.loadError.set('Could not load the raffle board. Retrying shortly…'),
    });
  }

  tileClass(n: number) {
    const isWinner = this.winnersMap().has(n);
    const owner = this.owners().get(n);
    const base = owner ? (owner.status === 'locked' ? 'locked' : 'held') : this.selected().has(n) ? 'selected' : 'free';
    return isWinner ? `${base} winner` : base;
  }

  toggle(n: number) {
    if (this.owners().has(n)) {
      const e = this.owners().get(n)!;
      if (e.status === 'provisional') this.openLock(e);
      return;
    }
    const next = new Set(this.selected());
    next.has(n) ? next.delete(n) : next.add(n);
    this.selected.set(next);
  }

  clear() {
    this.selected.set(new Set());
  }

  tileTitle(n: number) {
    const win = this.winnersMap().get(n);
    if (win) {
      const prize = win.prize_title ? ` (${win.prize_title})` : '';
      return `Square ${n} · 🏆 WINNER: ${win.display_name}${prize}`;
    }
    const o = this.owners().get(n);
    if (!o) return `Square ${n}`;
    return `Square ${n} · ${o.status === 'locked' ? 'Locked in by' : 'Held by'} ${o.display_name}`;
  }

  timeLeft(e: PublicEntry) {
    const ms = new Date(e.expires_at).getTime() - this.now();
    if (ms <= 0) return 'expiring';
    const d = Math.floor(ms / 86400000);
    const h = Math.floor((ms % 86400000) / 3600000);
    return d > 0 ? `${d}d ${h}h left` : `${h}h left`;
  }

  openConfirm() {
    this.formError.set('');
    this.showConfirm.set(true);
  }

  submit() {
    if (this.busy()) return;
    if (this.name.trim().length < 2 || !this.employeeNumber.trim()) {
      this.formError.set('Please enter your name and employee number.');
      return;
    }
    this.busy.set(true);
    this.api
      .confirm({
        tiles: [...this.selected()].sort((a, b) => a - b),
        name: this.name,
        employee_number: this.employeeNumber,
        email: this.email || null,
      })
      .subscribe({
        next: (r) => {
          this.busy.set(false);
          this.showConfirm.set(false);
          this.result.set(r);
          this.clear();
          this.name = this.employeeNumber = this.email = '';
          this.refresh();
        },
        error: (e) => {
          this.busy.set(false);
          this.formError.set(errorText(e));
          if (e.status === 409) this.refresh();
        },
      });
  }

  openLock(e: PublicEntry) {
    this.code = '';
    this.formError.set('');
    this.lockDone.set(false);
    this.voteDone.set(false);
    this.voteMode.set(false);
    this.selectedCharityId.set(null);
    this.lockTarget.set(e);
  }

  openVote(e: PublicEntry) {
    this.openLock(e);
    this.voteMode.set(true);
  }

  startVote() {
    this.voteMode.set(true);
    this.lockDone.set(false);
    this.formError.set('');
    this.selectedCharityId.set(null);
  }

  submitLock() {
    const t = this.lockTarget();
    if (!t || this.busy() || !this.code.trim()) return;
    this.busy.set(true);
    this.api.lockIn(t.id, this.code).subscribe({
      next: () => {
        this.busy.set(false);
        this.lockDone.set(true);
        this.refresh();
      },
      error: (e) => {
        this.busy.set(false);
        this.formError.set(errorText(e));
        if (e.status === 404) this.refresh();
      },
    });
  }

  submitVote() {
    const target = this.lockTarget();
    const charityId = this.selectedCharityId();
    if (!target || this.busy() || !this.code.trim() || charityId === null) return;
    this.busy.set(true);
    this.api.vote(target.id, this.code, charityId).subscribe({
      next: () => {
        this.busy.set(false);
        this.voteDone.set(true);
        this.refreshCharities();
        this.refresh();
      },
      error: (e) => {
        this.busy.set(false);
        this.formError.set(errorText(e));
        if (e.status === 404) this.refresh();
      },
    });
  }

  selectCharity(id: number) {
    this.selectedCharityId.set(id);
  }

  closeModals() {
    this.showHow.set(false);
    this.showConfirm.set(false);
    this.result.set(null);
    this.lockTarget.set(null);
  }
}
