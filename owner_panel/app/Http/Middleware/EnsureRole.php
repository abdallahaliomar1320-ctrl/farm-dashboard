<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * حصر الأدوار من طرف الخادم في كل طلب حساس — لا اعتماد على واجهة المتصفح.
 * 'role:owner' أو 'role:owner,manager'
 */
class EnsureRole
{
    public function handle(Request $request, Closure $next, string ...$roles): Response
    {
        $user = $request->user();

        if (! $user || ! $user->hasAnyRole($roles)) {
            abort(403, 'لا تملك صلاحية تنفيذ هذا الإجراء.');
        }

        return $next($request);
    }
}
