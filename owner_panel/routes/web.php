<?php

use App\Http\Controllers\AuthController;
use App\Http\Controllers\AuditController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\FarmController;
use App\Http\Controllers\ProfileController;
use App\Http\Controllers\SettingsController;
use App\Http\Controllers\UsageController;
use Illuminate\Support\Facades\Route;

// ---------------------------------------------------------------- دخول

Route::middleware('guest')->group(function () {
    Route::get('/login', [AuthController::class, 'showLogin'])->name('login');
    Route::post('/login', [AuthController::class, 'login'])
        ->middleware('throttle:login')->name('login.attempt');
});

Route::middleware('auth')->group(function () {
    Route::post('/logout', [AuthController::class, 'logout'])->name('logout');

    Route::get('/mfa/verify', [AuthController::class, 'showMfa'])->name('mfa.verify');
    Route::post('/mfa/verify', [AuthController::class, 'verifyMfa'])
        ->middleware('throttle:mfa')->name('mfa.attempt');

    Route::get('/profile', [ProfileController::class, 'show'])->name('profile');
    Route::post('/profile/mfa/start', [ProfileController::class, 'mfaStart'])->name('profile.mfa.start');
    Route::post('/profile/mfa/confirm', [ProfileController::class, 'mfaConfirm'])->name('profile.mfa.confirm');
    Route::post('/profile/mfa/disable', [ProfileController::class, 'mfaDisable'])->name('profile.mfa.disable');
});

// ------------------------------------------------------- صفحات اللوحة

Route::middleware(['auth', 'mfa'])->group(function () {
    Route::get('/', [DashboardController::class, 'index'])->name('dashboard');

    Route::get('/farms', [FarmController::class, 'index'])->name('farms.index');
    Route::get('/farms/create', [FarmController::class, 'create'])
        ->middleware('role:owner')->name('farms.create');
    Route::post('/farms', [FarmController::class, 'store'])
        ->middleware('role:owner')->name('farms.store');

    Route::get('/farms/{farm}', [FarmController::class, 'show'])->name('farms.show');
    Route::post('/farms/{farm}/status', [FarmController::class, 'setStatus'])
        ->middleware('role:owner')->name('farms.status');
    Route::post('/farms/{farm}/subscription', [FarmController::class, 'addSubscription'])
        ->middleware('role:owner')->name('farms.subscription');
    Route::post('/farms/{farm}/subscription/cancel', [FarmController::class, 'cancelSubscription'])
        ->middleware('role:owner')->name('farms.subscription.cancel');
    Route::post('/farms/{farm}/payment-status', [FarmController::class, 'setPaymentStatus'])
        ->middleware('role:owner')->name('farms.payment-status');
    Route::post('/farms/{farm}/regenerate-key', [FarmController::class, 'regenerateKey'])
        ->middleware('role:owner')->name('farms.regenerate-key');

    Route::get('/usage', [UsageController::class, 'index'])->name('usage');
    Route::get('/alerts', [UsageController::class, 'alerts'])->name('alerts');
    Route::get('/audit', [AuditController::class, 'index'])->name('audit');

    Route::get('/settings', [SettingsController::class, 'edit'])
        ->middleware('role:owner')->name('settings.edit');
    Route::put('/settings', [SettingsController::class, 'update'])
        ->middleware('role:owner')->name('settings.update');
});
