<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Services\OwnerApiService;

class SettingsController extends Controller
{
    protected $api;

    public function __construct(OwnerApiService $api)
    {
        $this->api = $api;
    }

    public function edit()
    {
        $settings = $this->api->getSettings();
        return view('settings.edit', ['settings' => $settings]);
    }

    public function update(Request $request)
    {
        $validated = $request->validate([
            'free_ops_limit' => 'required|integer|min:1',
            'alert_threshold_1' => 'required|integer|min:1',
            'alert_threshold_2' => 'required|integer|min:1',
            'subscription_price' => 'nullable|numeric|min:0',
            'subscription_currency' => 'required|string|min:1',
            'subscription_duration_days' => 'required|integer|min:1',
            'grace_period_days' => 'required|integer|min:0',
            'timezone' => 'required|string|min:1',
        ]);
        $validated['actor'] = auth()->user()->email ?? 'owner-panel';
        
        $this->api->updateSettings($validated);
        return back()->with('success', 'تم حفظ الإعدادات بنجاح');
    }
}
