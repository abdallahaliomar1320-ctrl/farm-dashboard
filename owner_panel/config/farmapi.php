<?php

// إعدادات الاتصال بخلفية Python — خادم إلى خادم فقط.
// المفتاح يُقرأ من بيئة الإعداد ولا يُمرَّر إلى المتصفح أبداً.

return [

    'base_url' => env('FARM_API_URL', 'http://127.0.0.1:8000'),

    'service_token' => env('FARM_API_SERVICE_TOKEN', ''),

    'timeout' => (int) env('FARM_API_TIMEOUT', 10),

];
