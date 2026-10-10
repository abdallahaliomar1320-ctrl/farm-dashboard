@extends('layouts.app')

@section('content')
<div class="page-header">
    <h1>تفاصيل المزرعة: {{ $farm['name'] }}</h1>
    <a href="{{ route('farms.index') }}" class="btn btn-secondary">العودة للقائمة</a>
</div>

<div class="grid-3" style="margin-bottom: 1.5rem;">
    <!-- Farm Info -->
    <div class="card" style="margin-bottom: 0;">
        <div class="card-header">
            <span class="card-title">المعلومات الأساسية</span>
        </div>
        <div style="margin-bottom: 1rem;">
            <strong>المسؤول:</strong> {{ $farm['contact_name'] ?? 'غير محدد' }}<br>
            <strong>الهاتف:</strong> <span dir="ltr">{{ $farm['contact_phone'] ?? 'غير محدد' }}</span><br>
            <strong>ملاحظات:</strong> {{ $farm['notes'] ?? 'لا يوجد' }}
        </div>
        
        <form action="{{ route('farms.status', $farm['id']) }}" method="POST" style="margin-top: 1.5rem; border-top: 1px solid var(--border); padding-top: 1rem;">
            @csrf
            <h4>تغيير حالة المزرعة</h4>
            <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                <select name="status" class="form-control" style="margin-bottom: 0;">
                    <option value="active" {{ $farm['status'] == 'active' ? 'selected' : '' }}>نشط</option>
                    <option value="suspended" {{ $farm['status'] == 'suspended' ? 'selected' : '' }}>معلق</option>
                </select>
                <input type="text" name="reason" class="form-control" placeholder="السبب (مطلوب للتعليق)" style="margin-bottom: 0;">
                <button type="submit" class="btn btn-primary">حفظ</button>
            </div>
        </form>

        <form action="{{ route('farms.regenerate-key', $farm['id']) }}" method="POST" style="margin-top: 1.5rem; border-top: 1px solid var(--border); padding-top: 1rem;">
            @csrf
            <h4>مفتاح الربط (API Key)</h4>
            @if(isset($farm['api_key']))
                <div class="alert alert-success" style="word-break: break-all;">
                    {{ $farm['api_key'] }}
                </div>
            @endif
            <button type="submit" class="btn btn-danger" onclick="return confirm('تجديد المفتاح سيوقف التطبيقات الحالية المتصلة بهذه المزرعة. هل أنت متأكد؟')">تجديد المفتاح</button>
        </form>
    </div>

    <!-- Usage & Subscription Info -->
    <div class="card" style="margin-bottom: 0; grid-column: span 2;">
        <div class="card-header">
            <span class="card-title">الاستهلاك والاشتراك الحالي</span>
            @if($farm['subscription']['active'])
                <span class="badge badge-active">اشتراك مدفوع نشط</span>
            @else
                @if($farm['usage']['over_limit'])
                    <span class="badge badge-danger">تجاوز الحد (متوقف)</span>
                @else
                    <span class="badge badge-warning">باقة مجانية</span>
                @endif
            @endif
        </div>

        <div style="margin-bottom: 1.5rem;">
            <h4>استهلاك هذا الشهر: {{ $farm['usage']['used'] }} / {{ $farm['usage']['limit'] }} عملية</h4>
            <div class="progress-container">
                @php
                    $pct = min(100, ($farm['usage']['used'] / max(1, $farm['usage']['limit'])) * 100);
                    $color = 'var(--success)';
                    if($farm['usage']['over_limit']) $color = 'var(--danger)';
                    elseif($farm['usage']['threshold_1_reached']) $color = 'var(--warning)';
                @endphp
                <div class="progress-bar" style="width: {{ $pct }}%; background-color: {{ $color }};"></div>
            </div>
        </div>

        <hr style="border: 0; border-top: 1px solid var(--border); margin: 1.5rem 0;">

        <h4>تجديد / إضافة اشتراك مدفوع</h4>
        <form action="{{ route('farms.subscription', $farm['id']) }}" method="POST" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
            @csrf
            <div>
                <label class="text-muted text-sm">المدة بالأشهر</label>
                <input type="number" name="months" class="form-control" value="1" min="0">
            </div>
            <div>
                <label class="text-muted text-sm">أيام إضافية</label>
                <input type="number" name="days" class="form-control" value="0" min="0">
            </div>
            <div>
                <label class="text-muted text-sm">السعر (اختياري، يتبع الإعدادات الافتراضية)</label>
                <input type="number" name="price" class="form-control" placeholder="مثال: 5000">
            </div>
            <div>
                <label class="text-muted text-sm">حالة الدفع</label>
                <select name="payment_status" class="form-control">
                    <option value="paid">تم الدفع</option>
                    <option value="pending">معلق (آجل)</option>
                </select>
            </div>
            <div style="grid-column: span 2;">
                <button type="submit" class="btn btn-primary" style="width: 100%;">إضافة الاشتراك المفتوح</button>
            </div>
        </form>
    </div>
</div>

<div class="card">
    <div class="card-header">
        <span class="card-title">سجل الاشتراكات</span>
    </div>
    <div class="table-responsive">
        <table>
            <thead>
                <tr>
                    <th>المعرف</th>
                    <th>من تاريخ</th>
                    <th>إلى تاريخ</th>
                    <th>الحالة</th>
                    <th>السعر</th>
                    <th>حالة الدفع</th>
                </tr>
            </thead>
            <tbody>
                @foreach($farm['subscriptions_history'] as $sub)
                <tr>
                    <td>#{{ $sub['id'] }}</td>
                    <td dir="ltr">{{ $sub['start_date'] }}</td>
                    <td dir="ltr">{{ $sub['end_date'] }}</td>
                    <td>
                        @if($sub['status'] == 'active') <span class="badge badge-active">نشط</span>
                        @elseif($sub['status'] == 'cancelled') <span class="badge badge-danger">ملغي</span>
                        @else <span class="badge badge-suspended">منتهي</span> @endif
                    </td>
                    <td>{{ $sub['price'] }} {{ $sub['currency'] }}</td>
                    <td>
                        @if($sub['payment_status'] == 'paid') <span style="color: var(--success);">مدفوع</span>
                        @else <span style="color: var(--warning);">آجل (معلق)</span> @endif
                    </td>
                </tr>
                @endforeach
            </tbody>
        </table>
    </div>
</div>
@endsection
