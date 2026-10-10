<?php

namespace App\Services;

use App\Exceptions\FarmApiException;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;

/**
 * عميل خادم-إلى-خادم لواجهات الإدارة في خلفية Python.
 *
 * القاعدة: كل منطق الأعمال (الاحتساب، الاشتراكات، الحدود) يبقى في Python.
 * هذه الخدمة تنقل البيانات وتعرضها فقط، ولا تكرر أي حساب.
 *
 * كل الطلبات تحمل ترويسة X-Service-Token من إعدادات البيئة السرية،
 * ولا يجوز استدعاء واجهات Python من متصفح المستخدم مباشرة.
 */
class FarmApiService
{
    protected string $baseUrl;
    protected string $token;
    protected int $timeout;

    public function __construct()
    {
        $this->baseUrl = rtrim((string) config('farmapi.base_url'), '/');
        $this->token = (string) config('farmapi.service_token');
        $this->timeout = (int) config('farmapi.timeout', 10);
    }

    /** نظرة عامة على النظام (لوحة البداية) */
    public function overview(): array
    {
        return $this->get('/api/admin/overview');
    }

    /** قائمة المزارع مع بحث وفلاتر وترقيم صفحات */
    public function farms(array $query = []): array
    {
        return $this->get('/api/admin/farms', $query);
    }

    /** تفاصيل مزرعة (لا تتضمن api_key أبداً) */
    public function farm(int $id): array
    {
        return $this->get("/api/admin/farms/{$id}");
    }

    /** إنشاء مزرعة — يُعاد api_key مرة واحدة فقط */
    public function createFarm(array $data): array
    {
        return $this->post('/api/admin/farms', $data);
    }

    /** تعليق أو تنشيط مزرعة */
    public function setStatus(int $id, array $data): array
    {
        return $this->post("/api/admin/farms/{$id}/status", $data);
    }

    /** إضافة/تمديد اشتراك */
    public function addSubscription(int $id, array $data): array
    {
        return $this->post("/api/admin/farms/{$id}/subscription", $data);
    }

    /** إلغاء الاشتراك النشط */
    public function cancelSubscription(int $id, array $data): array
    {
        return $this->post("/api/admin/farms/{$id}/subscription/cancel", $data);
    }

    /** تحديث حالة الدفع إدارياً (تتبع فقط، لا تحصيل) */
    public function setPaymentStatus(int $id, array $data): array
    {
        return $this->post("/api/admin/farms/{$id}/payment-status", $data);
    }

    /** توليد مفتاح API جديد — يُعاد مرة واحدة فقط */
    public function regenerateKey(int $id, array $data): array
    {
        return $this->post("/api/admin/farms/{$id}/regenerate-key", $data);
    }

    /** إعدادات النظام الحالية */
    public function settings(): array
    {
        return $this->get('/api/admin/settings');
    }

    /** تحديث إعدادات النظام */
    public function updateSettings(array $data): array
    {
        return $this->put('/api/admin/settings', $data);
    }

    /** احتساب الاستخدام الشهري لكل مزرعة */
    public function usage(): array
    {
        return $this->get('/api/admin/usage');
    }

    /** تنبيهات الحدود والاشتراكات */
    public function alerts(): array
    {
        return $this->get('/api/admin/alerts');
    }

    /** سجل التدقيق (قراءة فقط) */
    public function audit(array $query = []): array
    {
        return $this->get('/api/admin/audit', $query);
    }

    // ------------------------------------------------------------------

    protected function get(string $path, array $query = []): array
    {
        return $this->request('get', $path, $query, []);
    }

    protected function post(string $path, array $data = []): array
    {
        return $this->request('post', $path, [], $data);
    }

    protected function put(string $path, array $data = []): array
    {
        return $this->request('put', $path, [], $data);
    }

    /**
     * تنفيذ الطلب وإرجاع نتيجة موحّدة:
     * ['ok' => bool, 'status' => int, 'data' => array|null, 'error' => string|null]
     * أخطاء الاتصال والخادم ترمي FarmApiException لتُعرض صفحة خدمة غير متاحة.
     */
    protected function request(string $method, string $path, array $query, array $data): array
    {
        if ($this->baseUrl === '') {
            throw new FarmApiException('لم يتم ضبط عنوان خدمة API (FARM_API_URL).');
        }
        if ($this->token === '') {
            throw new FarmApiException('لم يتم ضبط مفتاح خدمة API (FARM_API_SERVICE_TOKEN).');
        }

        try {
            $response = Http::withHeaders([
                    'X-Service-Token' => $this->token,
                    'Accept' => 'application/json',
                ])
                ->timeout($this->timeout)
                ->connectTimeout(5)
                ->withQueryParameters($query)
                ->{$method}($this->baseUrl.$path, $data);
        } catch (ConnectionException) {
            throw new FarmApiException('تعذر الاتصال بخدمة إدارة المزارع. تأكد من تشغيل خلفية Python ومن صحة العنوان في FARM_API_URL.');
        }

        if ($response->serverError()) {
            throw new FarmApiException('خدمة إدارة المزارع أرجأت خطأ داخلي ('.$response->status().'). حاول لاحقاً أو راجع سجلات الخلفية.');
        }

        $body = $response->json();

        if ($response->successful()) {
            return ['ok' => true, 'status' => $response->status(), 'data' => $body, 'error' => null];
        }

        $detail = is_array($body) && isset($body['detail']) ? (string) $body['detail'] : null;
        if ($detail === '' || $detail === null) {
            $detail = 'رفضت خدمة إدارة المزارع الطلب (رمز '.$response->status().').';
        }

        return ['ok' => false, 'status' => $response->status(), 'data' => $body, 'error' => $detail];
    }
}
