<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Services\OwnerApiService;

class AuditController extends Controller
{
    protected $api;

    public function __construct(OwnerApiService $api)
    {
        $this->api = $api;
    }

    public function index(Request $request)
    {
        $params = $request->only(['action', 'entity', 'page', 'per_page']);
        $data = $this->api->getAudit($params);
        return view('audit.index', ['data' => $data]);
    }
}
