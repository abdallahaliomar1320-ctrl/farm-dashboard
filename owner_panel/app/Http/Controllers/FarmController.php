<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Services\OwnerApiService;

class FarmController extends Controller
{
    protected $api;

    public function __construct(OwnerApiService $api)
    {
        $this->api = $api;
    }

    public function index(Request $request)
    {
        $params = $request->only(['search', 'status', 'subscription', 'page', 'per_page']);
        $data = $this->api->getFarms($params);
        return view('farms.index', ['data' => $data]);
    }

    public function create()
    {
        return view('farms.create');
    }

    public function store(Request $request)
    {
        $validated = $request->validate([
            'name' => 'required|string|min:1',
            'contact_name' => 'nullable|string',
            'contact_phone' => 'nullable|string',
            'notes' => 'nullable|string',
        ]);
        $validated['actor'] = auth()->user()->email ?? 'owner-panel';
        
        $response = $this->api->createFarm($validated);
        return redirect()->route('farms.show', $response['id'])->with('success', 'تم إنشاء المزرعة بنجاح. مفتاح API: ' . $response['api_key']);
    }

    public function show($farmId)
    {
        $data = $this->api->getFarmDetails($farmId);
        return view('farms.show', ['farm' => $data]);
    }

    public function setStatus(Request $request, $farmId)
    {
        $validated = $request->validate([
            'status' => 'required|in:active,suspended',
            'reason' => 'required_if:status,suspended|string'
        ]);
        $actor = auth()->user()->email ?? 'owner-panel';
        $this->api->updateFarmStatus($farmId, $validated['status'], $validated['reason'] ?? 'تفعيل', $actor);
        return back()->with('success', 'تم تحديث حالة المزرعة');
    }

    public function addSubscription(Request $request, $farmId)
    {
        $validated = $request->validate([
            'months' => 'required|integer|min:0',
            'days' => 'required|integer|min:0',
            'price' => 'nullable|numeric|min:0',
            'payment_status' => 'required|in:paid,pending',
            'notes' => 'nullable|string',
        ]);
        $validated['actor'] = auth()->user()->email ?? 'owner-panel';
        $this->api->addSubscription($farmId, $validated);
        return back()->with('success', 'تم إضافة الاشتراك بنجاح');
    }

    public function cancelSubscription(Request $request, $farmId)
    {
        $validated = $request->validate([
            'reason' => 'required|string|min:1',
        ]);
        $actor = auth()->user()->email ?? 'owner-panel';
        $this->api->cancelSubscription($farmId, $validated['reason'], $actor);
        return back()->with('success', 'تم إلغاء الاشتراك');
    }

    public function setPaymentStatus(Request $request, $farmId)
    {
        $validated = $request->validate([
            'payment_status' => 'required|in:paid,pending',
        ]);
        $actor = auth()->user()->email ?? 'owner-panel';
        $this->api->updatePaymentStatus($farmId, $validated['payment_status'], $actor);
        return back()->with('success', 'تم تحديث حالة الدفع');
    }

    public function regenerateKey(Request $request, $farmId)
    {
        $actor = auth()->user()->email ?? 'owner-panel';
        $response = $this->api->regenerateFarmKey($farmId, $actor);
        return back()->with('success', 'تم تجديد المفتاح: ' . $response['api_key']);
    }
}
