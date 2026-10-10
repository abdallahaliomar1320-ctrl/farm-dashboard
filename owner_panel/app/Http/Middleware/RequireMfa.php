<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * بوابة التحقق بخطوتين: مستخدم فعّل TOTP لا يصل أي صفحة قبل إدخال الرمز.
 */
class RequireMfa
{
    public function handle(Request $request, Closure $next): Response
    {
        $user = $request->user();

        if ($user && $user->totp_enabled && ! $request->session()->get('mfa.passed')) {
            return redirect()->route('mfa.verify');
        }

        return $next($request);
    }
}
