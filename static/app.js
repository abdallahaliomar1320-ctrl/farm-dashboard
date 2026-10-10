let workers = [];
let currentFilter = 'all';
let isEditing = false;
let activeWorkerId = null;

const API_BASE = '/api';

document.getElementById('startDate').valueAsDate = new Date();

async function fetchWorkers() {
    try {
        const res = await fetch(`${API_BASE}/workers/`);
        workers = await res.json();
        renderWorkers();
    } catch (err) {
        console.error('Error fetching workers:', err);
    }
}

// Initial fetch
fetchWorkers();

async function handleFormSubmit(e) {
    e.preventDefault();
    const workerData = {
        name: document.getElementById('name').value,
        phone: document.getElementById('phone').value,
        start_date: document.getElementById('startDate').value,
        end_date: document.getElementById('endDate').value || null,
        job: document.getElementById('job').value,
        pay_type: document.getElementById('payType').value,
        pay_amount: parseFloat(document.getElementById('payAmount').value) || 0
    };

    if (isEditing) {
        const id = parseInt(document.getElementById('workerId').value);
        await fetch(`${API_BASE}/workers/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(workerData)
        });
        alert('تم تحديث البيانات بنجاح!');
    } else {
        await fetch(`${API_BASE}/workers/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(workerData)
        });
        alert('تم حفظ العامل بنجاح!');
    }

    resetForm();
    showSection('list');
    fetchWorkers();
}

function prepareAddNewWorker() {
    resetForm();
    isEditing = false;
    document.getElementById('formTitle').innerHTML = '<i class="fa-solid fa-user-plus text-emerald-600"></i> إضافة عامل جديد';
    document.getElementById('submitBtn').textContent = 'حفظ البيانات';
    document.getElementById('cancelBtn').classList.add('hidden');
    showSection('add');
}

function editWorker(id) {
    const worker = workers.find(w => w.id === id);
    if (!worker) return;

    isEditing = true;
    document.getElementById('formTitle').innerHTML = '<i class="fa-solid fa-user-pen text-amber-600"></i> تعديل بيانات العامل';
    document.getElementById('submitBtn').textContent = 'تحديث البيانات';
    document.getElementById('submitBtn').className = 'flex-grow bg-amber-600 text-white font-bold py-3 rounded-lg shadow-sm';
    document.getElementById('cancelBtn').classList.remove('hidden');

    document.getElementById('workerId').value = worker.id;
    document.getElementById('name').value = worker.name;
    document.getElementById('phone').value = worker.phone;
    document.getElementById('startDate').value = worker.start_date;
    document.getElementById('endDate').value = worker.end_date || '';
    document.getElementById('job').value = worker.job;
    document.getElementById('payType').value = worker.pay_type;
    document.getElementById('payAmount').value = worker.pay_amount;

    showSection('add');
}

function resetForm() {
    document.getElementById('workerForm').reset();
    document.getElementById('workerId').value = '';
    document.getElementById('startDate').valueAsDate = new Date();
    document.getElementById('submitBtn').className = 'flex-grow bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-lg shadow-sm transition';
}

async function deleteWorker(id) {
    if (confirm('هل أنت تأكد من حذف هذا العامل وحساباته؟')) {
        await fetch(`${API_BASE}/workers/${id}`, { method: 'DELETE' });
        fetchWorkers();
    }
}

function isWorkerActive(endDateStr) {
    if (!endDateStr) return true; 
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return new Date(endDateStr) >= today;
}

// --- إدارة المالية والسلف ---
function openFinanceModal(id) {
    activeWorkerId = id;
    const worker = workers.find(w => w.id === id);
    if (!worker) return;

    if (!worker.advances) worker.advances = [];

    document.getElementById('modalWorkerName').textContent = worker.name;
    updateFinanceUI(worker);
    document.getElementById('financeModal').classList.remove('hidden');
}

function closeFinanceModal() {
    document.getElementById('financeModal').classList.add('hidden');
    activeWorkerId = null;
    fetchWorkers(); // Refresh in case we added/deleted advances
}

async function addAdvance(e) {
    e.preventDefault();
    const worker = workers.find(w => w.id === activeWorkerId);
    if (!worker) return;

    const amount = parseFloat(document.getElementById('advAmount').value);
    const notes = document.getElementById('advNotes').value || 'سلفة نقداً';
    const date = new Date().toISOString().split('T')[0];

    if (amount > 0) {
        const newAdvance = { amount, notes, date };
        
        await fetch(`${API_BASE}/workers/${activeWorkerId}/advances/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newAdvance)
        });

        document.getElementById('advAmount').value = '';
        document.getElementById('advNotes').value = '';
        
        // Re-fetch workers to update state
        const res = await fetch(`${API_BASE}/workers/`);
        workers = await res.json();
        const updatedWorker = workers.find(w => w.id === activeWorkerId);
        updateFinanceUI(updatedWorker);
    }
}

async function deleteAdvance(advId) {
    if(confirm('هل أنت متأكد من حذف هذه السلفة؟')) {
        await fetch(`${API_BASE}/advances/${advId}`, { method: 'DELETE' });
        
        // Re-fetch to update state
        const res = await fetch(`${API_BASE}/workers/`);
        workers = await res.json();
        const updatedWorker = workers.find(w => w.id === activeWorkerId);
        updateFinanceUI(updatedWorker);
    }
}

function updateFinanceUI(worker) {
    const totalAdvances = (worker.advances || []).reduce((sum, a) => sum + a.amount, 0);
    const totalPay = worker.pay_amount || 0;
    const remaining = totalPay - totalAdvances;

    document.getElementById('statTotalPay').textContent = `${totalPay} ريال`;
    document.getElementById('statAdvances').textContent = `${totalAdvances} ريال`;
    document.getElementById('statRemaining').textContent = `${remaining} ريال`;

    const list = document.getElementById('advancesList');
    list.innerHTML = '';

    if (!worker.advances || worker.advances.length === 0) {
        list.innerHTML = `<p class="text-xs text-slate-400 text-center py-2">لا توجد سُلف مسجلة</p>`;
        return;
    }

    worker.advances.forEach(a => {
        list.innerHTML += `
            <div class="flex justify-between items-center bg-slate-100 p-2 rounded-lg text-xs">
                <div>
                    <span class="font-bold text-rose-600">${a.amount} ريال</span> - 
                    <span class="text-slate-600">${a.notes}</span>
                    <span class="text-slate-400 text-[10px] block">${a.date}</span>
                </div>
                <button onclick="deleteAdvance(${a.id})" class="text-rose-500 hover:text-rose-700 p-1"><i class="fa-solid fa-trash"></i></button>
            </div>
        `;
    });
}

// --- عرض البطاقات ---
function renderWorkers() {
    const grid = document.getElementById('workersGrid');
    const search = document.getElementById('searchInput').value.toLowerCase();
    grid.innerHTML = '';

    const filtered = workers.filter(w => {
        const matchesSearch = w.name.toLowerCase().includes(search) || w.phone.includes(search);
        const active = isWorkerActive(w.end_date);
        if (currentFilter === 'active') return matchesSearch && active;
        if (currentFilter === 'expired') return matchesSearch && !active;
        return matchesSearch;
    });

    document.getElementById('workerCount').textContent = `${workers.length} عمال`;

    if (filtered.length === 0) {
        grid.innerHTML = `<div class="col-span-full text-center py-8 text-slate-400">لا يوجد عمال لعرضهم</div>`;
        return;
    }

    filtered.forEach(w => {
        const active = isWorkerActive(w.end_date);
        const statusBadge = active 
            ? `<span class="bg-emerald-100 text-emerald-700 text-xs font-bold px-2.5 py-1 rounded-full">🟢 نشط</span>`
            : `<span class="bg-rose-100 text-rose-700 text-xs font-bold px-2.5 py-1 rounded-full">🔴 منتهي</span>`;

        const endDateDisplay = w.end_date ? w.end_date : 'مستمر';
        const totalAdv = (w.advances || []).reduce((sum, a) => sum + a.amount, 0);
        const remainingPay = (w.pay_amount || 0) - totalAdv;

        grid.innerHTML += `
                    <div class="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between space-y-4">
                        <div class="flex justify-between items-start">
                            <div class="flex items-center gap-3">
                                <div class="bg-blue-50 text-blue-600 p-3 rounded-full flex items-center justify-center">
                                    <i class="fa-solid fa-users text-xl"></i>
                                </div>
                                <div>
                                    <h3 class="font-bold text-slate-800 text-xl">${w.name}</h3>
                                    <div class="flex items-center gap-1 text-sm text-slate-500 mt-1">
                                        <i class="fa-solid fa-briefcase"></i>
                                        <span>طبيعة العمل: ${w.job}</span>
                                    </div>
                                </div>
                            </div>
                            ${statusBadge}
                        </div>
                        
                        <div class="text-base space-y-2 text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-200">
                            <div class="flex items-center gap-2">
                                <i class="fa-solid fa-phone text-slate-400 w-5"></i>
                                <span>رقم الهاتف: </span>
                                <a href="tel:${w.phone}" class="text-emerald-700 font-bold underline" dir="ltr">${w.phone}</a>
                            </div>
                            <div class="flex items-center gap-2">
                                <i class="fa-regular fa-calendar-days text-slate-400 w-5"></i>
                                <span>تاريخ البداية: ${w.start_date}</span>
                            </div>
                            <div class="flex items-center gap-2">
                                <i class="fa-regular fa-hourglass-half text-slate-400 w-5"></i>
                                <span>تاريخ النهاية: ${endDateDisplay}</span>
                            </div>
                            
                            <div class="grid grid-cols-2 gap-2 pt-3 mt-2 border-t border-slate-200">
                                <div class="flex items-center gap-2 bg-emerald-50 text-emerald-800 p-2 rounded-lg">
                                    <i class="fa-solid fa-money-bill-wave text-emerald-600"></i>
                                    <span class="font-bold text-sm">الراتب: ${w.pay_amount}</span>
                                </div>
                                <div class="flex items-center gap-2 bg-blue-50 text-blue-800 p-2 rounded-lg">
                                    <i class="fa-solid fa-wallet text-blue-600"></i>
                                    <span class="font-bold text-sm">الباقي: ${remainingPay}</span>
                                </div>
                            </div>
                        </div>

                        <div class="flex justify-between items-center pt-3 border-t border-slate-200">
                            <button onclick="openFinanceModal(${w.id})" class="bg-slate-100 text-slate-700 hover:bg-slate-200 px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition">
                                <i class="fa-solid fa-coins text-amber-500 text-lg"></i> السُّلف والحساب
                            </button>
                            <div class="flex gap-2">
                                <button onclick="editWorker(${w.id})" class="text-amber-600 hover:bg-amber-50 px-3 py-2 rounded-xl text-sm font-bold flex items-center gap-1 transition">
                                    <i class="fa-solid fa-pen"></i> تعديل
                                </button>
                                <button onclick="deleteWorker(${w.id})" class="text-rose-600 hover:bg-rose-50 px-3 py-2 rounded-xl text-sm font-bold flex items-center gap-1 transition">
                                    <i class="fa-solid fa-trash"></i> حذف
                                </button>
                            </div>
                        </div>
                    </div>
        `;
    });
}

// --- تصدير البيانات إلى ملف Excel ---
function exportToExcel() {
    if (workers.length === 0) {
        alert('لا توجد بيانات عمال لتصديرها!');
        return;
    }

    const data = workers.map((w, index) => {
        const totalAdv = (w.advances || []).reduce((sum, a) => sum + a.amount, 0);
        return {
            "م": index + 1,
            "اسم العامل": w.name,
            "رقم الهاتف": w.phone,
            "طبيعة العمل": w.job,
            "تاريخ البداية": w.start_date,
            "تاريخ النهاية": w.end_date || 'مستمر',
            "نظام الأجر": w.pay_type,
            "إجمالي الأجر": w.pay_amount,
            "إجمالي السُّلف": totalAdv,
            "المبلغ المتبقي": w.pay_amount - totalAdv
        };
    });

    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "العمال والرواتب");

    XLSX.writeFile(workbook, `كشف_عمال_المزرعة_${new Date().toISOString().split('T')[0]}.xlsx`);
}

function setFilter(filter) {
    currentFilter = filter;
    ['all', 'active', 'expired'].forEach(f => {
        const btn = document.getElementById(`filter-${f}`);
        btn.className = f === filter 
            ? 'px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-medium whitespace-nowrap'
            : 'px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 font-medium whitespace-nowrap';
    });
    renderWorkers();
}

function showSection(section) {
    if (section === 'add') {
        document.getElementById('addSection').classList.remove('hidden');
        document.getElementById('listSection').classList.add('hidden');
    } else {
        document.getElementById('addSection').classList.add('hidden');
        document.getElementById('listSection').classList.remove('hidden');
        renderWorkers();
    }
}
