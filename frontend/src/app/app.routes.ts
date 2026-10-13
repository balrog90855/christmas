import { Routes } from '@angular/router';
import { adminGuard } from './auth';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./home/home').then((m) => m.Home) },
  { path: 'admin/login', loadComponent: () => import('./admin/login').then((m) => m.AdminLogin) },
  {
    path: 'admin',
    canActivate: [adminGuard],
    loadComponent: () => import('./admin/dashboard').then((m) => m.AdminDashboard),
  },
  { path: '**', redirectTo: '' },
];
