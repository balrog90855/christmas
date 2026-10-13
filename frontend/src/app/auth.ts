import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

const KEY = 'raffle_admin_token';

export const getToken = () => sessionStorage.getItem(KEY);
export const setToken = (t: string) => sessionStorage.setItem(KEY, t);
export const clearToken = () => sessionStorage.removeItem(KEY);

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = getToken();
  if (token && req.url.startsWith('/api/admin') && !req.url.endsWith('/login')) {
    req = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  }
  return next(req);
};

export const adminGuard: CanActivateFn = () => {
  const router = inject(Router);
  return getToken() ? true : router.createUrlTree(['/admin/login']);
};
