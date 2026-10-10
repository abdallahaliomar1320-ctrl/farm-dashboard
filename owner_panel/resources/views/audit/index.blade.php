@extends('layouts.app')

@section('content')
<div class="page-header">
    <h1>سجل التدقيق (Audit Log)</h1>
</div>

<div class="card">
    <div class="card-header">
        <form action="{{ route('audit') }}" method="GET" style="display: flex; gap: 1rem; width: 100%;">
            <input type="text" name="action" class="form-control" placeholder="ابحث بنوع الإجراء..." value="{{ request('action') }}" style="margin-bottom: 0;">
            <input type="text" name="entity" class="form-control" placeholder="الكيان (farm, settings...)" value="{{ request('entity') }}" style="margin-bottom: 0;" dir="ltr">
            <button type="submit" class="btn btn-secondary">تصفية</button>
        </form>
    </div>

    <div class="table-responsive">
        <table>
            <thead>
                <tr>
                    <th>م</th>
                    <th>المنفذ</th>
                    <th>الإجراء</th>
                    <th>الكيان</th>
                    <th>معرف الكيان</th>
                    <th>السبب</th>
                    <th>التفاصيل</th>
                    <th>التاريخ والوقت</th>
                </tr>
            </thead>
            <tbody>
                @foreach($data['items'] as $log)
                <tr>
                    <td>{{ $log['id'] }}</td>
                    <td>{{ $log['actor'] }}</td>
                    <td><span class="badge badge-suspended" dir="ltr">{{ $log['action'] }}</span></td>
                    <td dir="ltr">{{ $log['entity'] }}</td>
                    <td>{{ $log['entity_id'] }}</td>
                    <td>{{ $log['reason'] ?? '-' }}</td>
                    <td><pre style="font-size: 0.75rem; color: var(--text-muted); background: var(--surface-variant); padding: 0.5rem; border-radius: var(--radius-sm); max-width: 200px; overflow-x: auto;" dir="ltr">{{ $log['details'] }}</pre></td>
                    <td dir="ltr">{{ \Carbon\Carbon::parse($log['created_at'])->format('Y-m-d H:i:s') }}</td>
                </tr>
                @endforeach
            </tbody>
        </table>
    </div>
</div>
@endsection
