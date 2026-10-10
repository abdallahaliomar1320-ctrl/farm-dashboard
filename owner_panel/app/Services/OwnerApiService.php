<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class OwnerApiService
{
    protected $baseUrl;
    protected $token;

    public function __construct()
    {
        // Default to localhost:8000 for Python backend, use env config
        $this->baseUrl = env('PYTHON_API_URL', 'http://127.0.0.1:8000');
        $this->token = env('OWNER_SERVICE_TOKEN');
    }

    protected function client()
    {
        return Http::withHeaders([
            'X-Service-Token' => $this->token,
            'Accept' => 'application/json',
        ])->baseUrl($this->baseUrl);
    }

    public function getOverview()
    {
        return $this->client()->get('/api/admin/overview')->json();
    }

    public function getFarms($params = [])
    {
        return $this->client()->get('/api/admin/farms', $params)->json();
    }

    public function getFarmDetails($farmId)
    {
        return $this->client()->get("/api/admin/farms/{$farmId}")->json();
    }

    public function createFarm($data)
    {
        return $this->client()->post('/api/admin/farms', $data)->json();
    }

    public function updateFarmStatus($farmId, $status, $reason, $actor)
    {
        return $this->client()->post("/api/admin/farms/{$farmId}/status", [
            'status' => $status,
            'reason' => $reason,
            'actor' => $actor,
        ])->json();
    }

    public function addSubscription($farmId, $data)
    {
        return $this->client()->post("/api/admin/farms/{$farmId}/subscription", $data)->json();
    }

    public function cancelSubscription($farmId, $reason, $actor)
    {
        return $this->client()->post("/api/admin/farms/{$farmId}/subscription/cancel", [
            'reason' => $reason,
            'actor' => $actor,
        ])->json();
    }

    public function updatePaymentStatus($farmId, $status, $actor)
    {
        return $this->client()->post("/api/admin/farms/{$farmId}/payment-status", [
            'payment_status' => $status,
            'actor' => $actor,
        ])->json();
    }

    public function regenerateFarmKey($farmId, $actor)
    {
        return $this->client()->post("/api/admin/farms/{$farmId}/regenerate-key", [
            'actor' => $actor,
        ])->json();
    }

    public function getUsage($month = null)
    {
        $params = $month ? ['month' => $month] : [];
        return $this->client()->get('/api/admin/usage', $params)->json();
    }

    public function getAlerts($month = null)
    {
        $params = $month ? ['month' => $month] : [];
        return $this->client()->get('/api/admin/alerts', $params)->json();
    }

    public function getSettings()
    {
        return $this->client()->get('/api/admin/settings')->json();
    }

    public function updateSettings($data)
    {
        return $this->client()->put('/api/admin/settings', $data)->json();
    }

    public function getAudit($params = [])
    {
        return $this->client()->get('/api/admin/audit', $params)->json();
    }
}
