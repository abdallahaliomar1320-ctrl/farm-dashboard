<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Services\OwnerApiService;

class UsageController extends Controller
{
    protected $api;

    public function __construct(OwnerApiService $api)
    {
        $this->api = $api;
    }

    public function index(Request $request)
    {
        $month = $request->query('month');
        $data = $this->api->getUsage($month);
        return view('usage.index', ['data' => $data]);
    }

    public function alerts(Request $request)
    {
        $month = $request->query('month');
        $data = $this->api->getAlerts($month);
        return view('usage.alerts', ['data' => $data]);
    }
}
