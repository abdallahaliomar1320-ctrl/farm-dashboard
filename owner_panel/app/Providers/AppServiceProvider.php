<?php

namespace App\Providers;

use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        // حماية من تخمين كلمة المرور: 5 محاولات فاشلة لكل بريد+IP في الدقيقة
        RateLimiter::for('login', function (Request $request) {
            $email = mb_strtolower((string) $request->input('email'));

            return [
                Limit::perMinute(5)->by("login|{$email}|{$request->ip()}"),
                Limit::perMinute(20)->by("login-ip|{$request->ip()}"),
            ];
        });

        // رمز التحقق بخطوتين: 5 محاولات للمستخدم الواحد في الدقيقة
        RateLimiter::for('mfa', function (Request $request) {
            return Limit::perMinute(5)->by('mfa|'.$request->session()->getId());
        });
    }
}
