<?php

use App\Exceptions\FarmApiException;
use App\Http\Middleware\EnsureRole;
use App\Http\Middleware\RequireMfa;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->alias([
            'role' => EnsureRole::class,
            'mfa' => RequireMfa::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );

        // انقطاع خدمة الخلفية: صفحة واضحة بدل خطأ تقني
        $exceptions->render(function (FarmApiException $e, Request $request) {
            if ($request->expectsJson() || $request->is('api/*')) {
                return response()->json(['message' => $e->getMessage()], 503);
            }

            return response()->view('errors.farmapi', ['message' => $e->getMessage()], 503);
        });
    })->create();
