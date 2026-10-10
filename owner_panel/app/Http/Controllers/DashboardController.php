<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use App\Services\OwnerApiService;

class DashboardController extends Controller
{
    protected $api;

    public function __construct(OwnerApiService $api)
    {
        $this->api = $api;
    }

    public function index()
    {
        $data = $this->api->getOverview();
        
        // Pass data to view (view implementation paused due to lack of Stitch MCP access)
        return view('dashboard', ['data' => $data]);
    }
}
