@extends('layouts.app')

@section('content')
<div class="page-header">
    <h1>تنبيهات الاستهلاك ({{ $data['month'] }})</h1>
    <a href="{{ route('usage') }}" class="btn btn-secondary">العودة للتقرير</a>
</div>

<div class="card">
    <div class="table-responsive">
        <table>
            <thead>
                <tr>
                    <th>المزرعة</th>
                    <th>المستوى</th>
                    <th>الاستهلاك</th>
                    <th>الرسالة</th>
                </tr>
            </thead>
            <tbody>
                @foreach($data['alerts'] as $alert)
                <tr>
                    <td><a href="{{ route('farms.show', $alert['farm_id']) }}">{{ $alert['farm_name'] }}</a></td>
                    <td>
                        @if($alert['level'] == 'over_limit')
                            <span class="badge badge-danger">تجاوز الحد</span>
                        @elseif($alert['level'] == 'threshold_2')
                            <span class="badge badge-warning">اقتراب حرج</span>
                        @else
                            <span class="badge badge-warning">تنبيه أولي</span>
                        @endif
                    </td>
                    <td>{{ $alert['used'] }} / {{ $alert['limit'] }}</td>
                    <td>{{ $alert['message'] }}</td>
                </tr>
                @endforeach
                @if(count($data['alerts']) == 0)
                <tr>
                    <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2rem;">لا توجد تنبيهات هذا الشهر.</td>
                </tr>
                @endif
            </tbody>
        </table>
    </div>
</div>
@endsection
