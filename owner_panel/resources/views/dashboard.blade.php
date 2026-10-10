@extends('layouts.app')

@section('content')
<div class="page-header">
    <h1>النظرة العامة</h1>
</div>

<div class="grid-3">
    <div class="card">
        <div class="card-header">
            <span class="card-title">إجمالي المزارع</span>
        </div>
        <div style="font-size: 2rem; font-weight: 700; color: var(--primary);">
            {{ $data['farms_total'] }}
        </div>
        <div style="color: var(--text-muted); font-size: 0.875rem;">
            نشط: {{ $data['farms_active'] }} | معلق: {{ $data['farms_suspended'] }}
        </div>
    </div>

    <div class="card">
        <div class="card-header">
            <span class="card-title">الاشتراكات النشطة</span>
        </div>
        <div style="font-size: 2rem; font-weight: 700; color: var(--secondary);">
            {{ $data['subscriptions_active'] }}
        </div>
    </div>

    <div class="card">
        <div class="card-header">
            <span class="card-title">العمليات (هذا الشهر)</span>
        </div>
        <div style="font-size: 2rem; font-weight: 700; color: var(--text-main);">
            {{ $data['month_operations'] }}
        </div>
        <div style="color: var(--text-muted); font-size: 0.875rem;">
            من إجمالي {{ $data['total_operations'] }} عملية
        </div>
    </div>
</div>

@if(count($data['subscriptions_expiring_soon']) > 0)
<div class="card" style="border-color: var(--warning-border);">
    <div class="card-header" style="background: var(--warning-bg); margin: -1.5rem -1.5rem 1.5rem; padding: 1.5rem; border-radius: var(--radius-md) var(--radius-md) 0 0;">
        <span class="card-title" style="color: var(--warning-text);">اشتراكات تقارب على الانتهاء</span>
    </div>
    <div class="table-responsive">
        <table>
            <thead>
                <tr>
                    <th>المزرعة</th>
                    <th>تاريخ الانتهاء</th>
                    <th>الأيام المتبقية</th>
                    <th>فترة السماح</th>
                </tr>
            </thead>
            <tbody>
                @foreach($data['subscriptions_expiring_soon'] as $sub)
                <tr>
                    <td><a href="{{ route('farms.show', $sub['farm_id']) }}">{{ $sub['farm_name'] }}</a></td>
                    <td dir="ltr">{{ $sub['end_date'] }}</td>
                    <td>
                        <span class="badge badge-warning">{{ $sub['days_left'] }} يوم</span>
                    </td>
                    <td>{{ $sub['in_grace'] ? 'نعم' : 'لا' }}</td>
                </tr>
                @endforeach
            </tbody>
        </table>
    </div>
</div>
@endif

@endsection
