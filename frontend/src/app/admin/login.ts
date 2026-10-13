import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api, errorText } from '../api';
import { setToken } from '../auth';

@Component({
  selector: 'app-admin-login',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="wrap">
      <form class="modal" (ngSubmit)="submit()">
        <div class="big">🎅</div>
        <h2>Admin login</h2>
        <label>Username <input name="u" [(ngModel)]="username" autocomplete="username" required /></label>
        <label>Password <input name="p" type="password" [(ngModel)]="password" autocomplete="current-password" required /></label>
        @if (error()) { <p class="banner error">{{ error() }}</p> }
        <button class="btn primary" type="submit" [disabled]="busy()">{{ busy() ? 'Signing in…' : 'Sign in' }}</button>
        <a routerLink="/" class="muted small">← Back to the raffle</a>
      </form>
    </div>
  `,
  styles: `
    .wrap { min-height: 100vh; display: grid; place-items: center; padding: 1rem; }
    .modal { align-items: stretch; text-align: center; }
    a { text-decoration: none; }
  `,
})
export class AdminLogin {
  private api = inject(Api);
  private router = inject(Router);
  username = '';
  password = '';
  busy = signal(false);
  error = signal('');

  submit() {
    this.busy.set(true);
    this.error.set('');
    this.api.login(this.username, this.password).subscribe({
      next: (r) => {
        setToken(r.access_token);
        this.router.navigateByUrl('/admin');
      },
      error: (e) => {
        this.busy.set(false);
        this.error.set(errorText(e, 'Could not sign in'));
      },
    });
  }
}
