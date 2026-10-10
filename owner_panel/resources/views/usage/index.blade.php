@extends('layouts.app')

@section('content')
<div class="page-header">
    <h1>استخدام العمليات ({{ $data['month'] }})</h1>
    <a href="{{ route('alerts') }}" class="btn btn-secondary">عرض التنبيهات</a>
</div>

<div class="card">
    <div class="card-header">
        <span class="card-title">تقرير الاستهلاك</span>
    </div>
    
    <div class="grid-3" style="margin-bottom: 2rem;">
        <div style="background: var(--surface-variant); padding: 1rem; border-radius: var(--radius-sm);">
            <strong>تجاوز الحد:</strong> <span style="color: var(--danger); font-size: 1.5rem; font-weight: 700;">{{ count($data['over_limit']) }}</span> مزرعة
        </div>
        <div style="background: var(--surface-variant); padding: 1rem; border-radius: var(--radius-sm);">
            <strong>قريب من الحد:</strong> <span style="color: var(--warning); font-size: 1.5rem; font-weight: 700;">{{ count($data['near_limit']) }}</span> مزرعة
        </div>
        <div style="background: var(--surface-variant); padding: 1rem; border-radius: var(--radius-sm);">
            <strong>على الحد تماماً:</strong> <span style="color: var(--warning); font-size: 1.5rem; font-weight: 700;">{{ count($data['at_limit']) }}</span> مزرعة
        </div>
    </div>

    <div class="table-responsive">
        <table>
            <thead>
                <tr>
                    <th>المزرعة</th>
                    <th>الاستخدام</th>
                    <th>الحد المجاني</th>
                    <th>الحالة التشغيلية</th>
                    <th>شريط التقدم</th>
                </tr>
            </thead>
            <tbody>
                @foreach($data['items'] as $item)
                <tr>
                    <td><a href="{{ route('farms.show', $item['farm_id']) }}">{{ $item['farm_name'] }}</a></td>
                    <td style="font-weight: 600;">{{ $item['usage']['used'] }}</td>
                    <td>{{ $item['usage']['limit'] }}</td>
                    <td>
                        @if($item['usage']['over_limit'])
                            <span class="badge badge-danger">تجاوز الحد</span>
                        @elseif($item['usage']['threshold_1_reached'])
                            <span class="badge badge-warning">تنبيه استهلاك</span>
                        @else
                            <span class="badge badge-active">ضمن الحد المجاني</span>
                        @endif
                    </td>
                    <td style="width: 200px;">
                        <div class="progress-container">
                            @php
                                $pct = min(100, ($item['usage']['used'] / max(1, $item['usage']['limit'])) * 100);
                                $color = 'var(--success)';
                                if($item['usage']['over_limit']) $color = 'var(--danger)';
                                elseif($item['usage']['threshold_1_reached']) $color = 'var(--warning)';
                            @endphp
                            <div class="progress-bar" style="width: {{ $pct }}%; background-color: {{ $color }};"></div>
                        </div>
                    </td>
                </tr>
                @endforeach
            </tbody>
        </table>
    </div>
</div>
@endsection
