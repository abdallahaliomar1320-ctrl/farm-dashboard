@extends('layouts.app')

@section('content')
<div class="page-header">
    <h1>إعدادات النظام العامة</h1>
</div>

<div class="card" style="max-width: 800px;">
    <form action="{{ route('settings.update') }}" method="POST">
        @csrf
        @method('PUT')
        
        <h3 style="margin-bottom: 1rem; color: var(--primary);">إعدادات العمليات (Quotas)</h3>
        <div class="grid-3" style="margin-bottom: 2rem;">
            <div>
                <label class="text-muted" style="font-weight: 600;">الحد المجاني الشهري</label>
                <input type="number" name="free_ops_limit" class="form-control" value="{{ $settings['free_ops_limit'] }}" required min="1">
            </div>
            <div>
                <label class="text-muted" style="font-weight: 600;">التنبيه الأول (عملية)</label>
                <input type="number" name="alert_threshold_1" class="form-control" value="{{ $settings['alert_threshold_1'] }}" required min="1">
            </div>
            <div>
                <label class="text-muted" style="font-weight: 600;">التنبيه الثاني (عملية)</label>
                <input type="number" name="alert_threshold_2" class="form-control" value="{{ $settings['alert_threshold_2'] }}" required min="1">
            </div>
        </div>

        <h3 style="margin-bottom: 1rem; color: var(--primary);">إعدادات الاشتراكات (Subscriptions)</h3>
        <div class="grid-3" style="margin-bottom: 2rem;">
            <div>
                <label class="text-muted" style="font-weight: 600;">السعر الافتراضي</label>
                <input type="number" name="subscription_price" class="form-control" value="{{ $settings['subscription_price'] }}">
            </div>
            <div>
                <label class="text-muted" style="font-weight: 600;">العملة</label>
                <input type="text" name="subscription_currency" class="form-control" value="{{ $settings['subscription_currency'] }}" required>
            </div>
            <div>
                <label class="text-muted" style="font-weight: 600;">مدة الاشتراك باليوم</label>
                <input type="number" name="subscription_duration_days" class="form-control" value="{{ $settings['subscription_duration_days'] }}" required min="1">
            </div>
            <div>
                <label class="text-muted" style="font-weight: 600;">فترة السماح (أيام)</label>
                <input type="number" name="grace_period_days" class="form-control" value="{{ $settings['grace_period_days'] }}" required min="0">
            </div>
        </div>

        <h3 style="margin-bottom: 1rem; color: var(--primary);">إعدادات النظام</h3>
        <div style="margin-bottom: 2rem; max-width: 300px;">
            <label class="text-muted" style="font-weight: 600;">المنطقة الزمنية</label>
            <input type="text" name="timezone" class="form-control" value="{{ $settings['timezone'] }}" required dir="ltr" style="text-align: left;">
        </div>

        <button type="submit" class="btn btn-primary" style="width: 100%;">حفظ التعديلات</button>
    </form>
</div>
@endsection
