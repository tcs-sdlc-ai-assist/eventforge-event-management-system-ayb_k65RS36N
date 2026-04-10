document.addEventListener('DOMContentLoaded', function () {

    // ============================================================
    // Ticket Type Form Rows (Add / Remove)
    // ============================================================

    const ticketTypeContainer = document.getElementById('ticket-types-container');
    const addTicketTypeBtn = document.getElementById('add-ticket-type-btn');

    let ticketTypeIndex = ticketTypeContainer
        ? ticketTypeContainer.querySelectorAll('.ticket-type-row').length
        : 0;

    function createTicketTypeRow(index) {
        const row = document.createElement('div');
        row.classList.add('ticket-type-row', 'flex', 'flex-wrap', 'items-end', 'gap-4', 'p-4', 'border', 'border-gray-200', 'rounded-lg', 'bg-gray-50');
        row.dataset.index = index;

        row.innerHTML = `
            <div class="flex-1 min-w-[180px]">
                <label class="block text-sm font-medium text-gray-700 mb-1">Ticket Name</label>
                <input type="text" name="ticket_type_name_${index}" required
                       class="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                       placeholder="e.g. General Admission">
            </div>
            <div class="w-32">
                <label class="block text-sm font-medium text-gray-700 mb-1">Price</label>
                <input type="number" name="ticket_type_price_${index}" min="0" step="0.01" required
                       class="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                       placeholder="0.00">
            </div>
            <div class="w-32">
                <label class="block text-sm font-medium text-gray-700 mb-1">Quantity</label>
                <input type="number" name="ticket_type_quantity_${index}" min="1" step="1" required
                       class="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                       placeholder="100">
            </div>
            <div>
                <button type="button" class="remove-ticket-type-btn inline-flex items-center px-3 py-2 text-sm font-medium text-red-700 bg-red-100 rounded-md hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500"
                        title="Remove ticket type">
                    <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                    Remove
                </button>
            </div>
        `;

        return row;
    }

    function updateRemoveButtons() {
        if (!ticketTypeContainer) return;
        const rows = ticketTypeContainer.querySelectorAll('.ticket-type-row');
        rows.forEach(function (row) {
            const btn = row.querySelector('.remove-ticket-type-btn');
            if (btn) {
                btn.disabled = rows.length <= 1;
                if (rows.length <= 1) {
                    btn.classList.add('opacity-50', 'cursor-not-allowed');
                } else {
                    btn.classList.remove('opacity-50', 'cursor-not-allowed');
                }
            }
        });
    }

    if (addTicketTypeBtn && ticketTypeContainer) {
        addTicketTypeBtn.addEventListener('click', function () {
            const row = createTicketTypeRow(ticketTypeIndex);
            ticketTypeContainer.appendChild(row);
            ticketTypeIndex++;
            updateRemoveButtons();
        });

        ticketTypeContainer.addEventListener('click', function (e) {
            const btn = e.target.closest('.remove-ticket-type-btn');
            if (!btn) return;
            const row = btn.closest('.ticket-type-row');
            if (row && ticketTypeContainer.querySelectorAll('.ticket-type-row').length > 1) {
                row.remove();
                updateRemoveButtons();
            }
        });

        updateRemoveButtons();
    }

    // ============================================================
    // AJAX Polling for Check-In Status Updates
    // ============================================================

    const checkInStatusEl = document.getElementById('check-in-status');
    let pollingInterval = null;
    let pollingUrl = null;

    function startCheckInPolling(url, intervalMs) {
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }
        pollingUrl = url;
        pollingInterval = setInterval(fetchCheckInStatus, intervalMs || 5000);
        fetchCheckInStatus();
    }

    function stopCheckInPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    async function fetchCheckInStatus() {
        if (!pollingUrl) return;
        try {
            const response = await fetch(pollingUrl, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });
            if (!response.ok) {
                console.error('Check-in status poll failed:', response.status);
                return;
            }
            const data = await response.json();
            updateCheckInStatusUI(data);
        } catch (err) {
            console.error('Check-in status poll error:', err);
        }
    }

    function updateCheckInStatusUI(data) {
        if (!checkInStatusEl) return;

        if (data.total_tickets !== undefined && data.checked_in !== undefined) {
            const total = data.total_tickets;
            const checkedIn = data.checked_in;
            const pct = total > 0 ? Math.round((checkedIn / total) * 100) : 0;

            const countEl = checkInStatusEl.querySelector('[data-check-in-count]');
            if (countEl) {
                countEl.textContent = `${checkedIn} / ${total}`;
            }

            const pctEl = checkInStatusEl.querySelector('[data-check-in-pct]');
            if (pctEl) {
                pctEl.textContent = `${pct}%`;
            }

            const barEl = checkInStatusEl.querySelector('[data-check-in-bar]');
            if (barEl) {
                barEl.style.width = `${pct}%`;
            }
        }

        if (data.recent_check_ins && Array.isArray(data.recent_check_ins)) {
            const listEl = checkInStatusEl.querySelector('[data-check-in-list]');
            if (listEl) {
                listEl.innerHTML = '';
                data.recent_check_ins.forEach(function (entry) {
                    const li = document.createElement('li');
                    li.classList.add('text-sm', 'text-gray-600', 'py-1');
                    const name = escapeHtml(entry.attendee_name || 'Unknown');
                    const time = entry.checked_in_at ? formatDatetime(entry.checked_in_at) : '';
                    li.innerHTML = `<span class="font-medium">${name}</span> <span class="text-gray-400">${time}</span>`;
                    listEl.appendChild(li);
                });
            }
        }
    }

    if (checkInStatusEl) {
        const url = checkInStatusEl.dataset.pollUrl;
        const interval = parseInt(checkInStatusEl.dataset.pollInterval, 10) || 5000;
        if (url) {
            startCheckInPolling(url, interval);
        }
    }

    // Expose polling controls globally
    window.EventForge = window.EventForge || {};
    window.EventForge.startCheckInPolling = startCheckInPolling;
    window.EventForge.stopCheckInPolling = stopCheckInPolling;

    // ============================================================
    // Form Validation Helpers
    // ============================================================

    function validateRequired(form) {
        let valid = true;
        const requiredFields = form.querySelectorAll('[required]');
        requiredFields.forEach(function (field) {
            clearFieldError(field);
            if (!field.value || !field.value.trim()) {
                showFieldError(field, 'This field is required.');
                valid = false;
            }
        });
        return valid;
    }

    function validateEmail(input) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (input.value && !emailRegex.test(input.value.trim())) {
            showFieldError(input, 'Please enter a valid email address.');
            return false;
        }
        return true;
    }

    function validateMinLength(input, minLen) {
        if (input.value && input.value.trim().length < minLen) {
            showFieldError(input, `Must be at least ${minLen} characters.`);
            return false;
        }
        return true;
    }

    function validatePositiveNumber(input) {
        const val = parseFloat(input.value);
        if (isNaN(val) || val < 0) {
            showFieldError(input, 'Please enter a valid positive number.');
            return false;
        }
        return true;
    }

    function validateDateRange(startInput, endInput) {
        if (startInput.value && endInput.value) {
            const start = new Date(startInput.value);
            const end = new Date(endInput.value);
            if (end <= start) {
                showFieldError(endInput, 'End date must be after start date.');
                return false;
            }
        }
        return true;
    }

    function showFieldError(field, message) {
        clearFieldError(field);
        field.classList.add('border-red-500', 'focus:border-red-500', 'focus:ring-red-500');
        field.classList.remove('border-gray-300', 'focus:border-indigo-500', 'focus:ring-indigo-500');
        const errorEl = document.createElement('p');
        errorEl.classList.add('field-error', 'mt-1', 'text-sm', 'text-red-600');
        errorEl.textContent = message;
        field.parentNode.appendChild(errorEl);
    }

    function clearFieldError(field) {
        field.classList.remove('border-red-500', 'focus:border-red-500', 'focus:ring-red-500');
        field.classList.add('border-gray-300', 'focus:border-indigo-500', 'focus:ring-indigo-500');
        const existing = field.parentNode.querySelector('.field-error');
        if (existing) {
            existing.remove();
        }
    }

    function clearAllErrors(form) {
        form.querySelectorAll('.field-error').forEach(function (el) { el.remove(); });
        form.querySelectorAll('.border-red-500').forEach(function (el) {
            el.classList.remove('border-red-500', 'focus:border-red-500', 'focus:ring-red-500');
            el.classList.add('border-gray-300', 'focus:border-indigo-500', 'focus:ring-indigo-500');
        });
    }

    // Attach client-side validation to forms with data-validate attribute
    document.querySelectorAll('form[data-validate]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            clearAllErrors(form);
            let valid = validateRequired(form);

            form.querySelectorAll('input[type="email"]').forEach(function (input) {
                if (!validateEmail(input)) valid = false;
            });

            form.querySelectorAll('input[data-min-length]').forEach(function (input) {
                const minLen = parseInt(input.dataset.minLength, 10);
                if (minLen && !validateMinLength(input, minLen)) valid = false;
            });

            form.querySelectorAll('input[type="number"][min="0"]').forEach(function (input) {
                if (!validatePositiveNumber(input)) valid = false;
            });

            const startDate = form.querySelector('input[name="start_date"], input[name="starts_at"]');
            const endDate = form.querySelector('input[name="end_date"], input[name="ends_at"]');
            if (startDate && endDate) {
                if (!validateDateRange(startDate, endDate)) valid = false;
            }

            if (!valid) {
                e.preventDefault();
                const firstError = form.querySelector('.border-red-500');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstError.focus();
                }
            }
        });
    });

    // Expose validation helpers globally
    window.EventForge.validateRequired = validateRequired;
    window.EventForge.validateEmail = validateEmail;
    window.EventForge.validateMinLength = validateMinLength;
    window.EventForge.validatePositiveNumber = validatePositiveNumber;
    window.EventForge.validateDateRange = validateDateRange;
    window.EventForge.showFieldError = showFieldError;
    window.EventForge.clearFieldError = clearFieldError;
    window.EventForge.clearAllErrors = clearAllErrors;

    // ============================================================
    // Datetime Formatting Utilities
    // ============================================================

    function formatDatetime(isoString, options) {
        try {
            const date = new Date(isoString);
            if (isNaN(date.getTime())) return isoString;
            const defaults = {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            };
            const opts = Object.assign({}, defaults, options || {});
            return date.toLocaleDateString(undefined, opts);
        } catch (err) {
            return isoString;
        }
    }

    function formatDate(isoString) {
        return formatDatetime(isoString, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: undefined,
            minute: undefined
        });
    }

    function formatTime(isoString) {
        try {
            const date = new Date(isoString);
            if (isNaN(date.getTime())) return isoString;
            return date.toLocaleTimeString(undefined, {
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (err) {
            return isoString;
        }
    }

    function timeAgo(isoString) {
        try {
            const date = new Date(isoString);
            if (isNaN(date.getTime())) return isoString;
            const now = new Date();
            const diffMs = now - date;
            const diffSec = Math.floor(diffMs / 1000);
            const diffMin = Math.floor(diffSec / 60);
            const diffHr = Math.floor(diffMin / 60);
            const diffDay = Math.floor(diffHr / 24);

            if (diffSec < 60) return 'just now';
            if (diffMin < 60) return `${diffMin}m ago`;
            if (diffHr < 24) return `${diffHr}h ago`;
            if (diffDay < 7) return `${diffDay}d ago`;
            return formatDate(isoString);
        } catch (err) {
            return isoString;
        }
    }

    function formatDatetimeLocal(isoString) {
        try {
            const date = new Date(isoString);
            if (isNaN(date.getTime())) return '';
            const pad = function (n) { return n.toString().padStart(2, '0'); };
            return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
        } catch (err) {
            return '';
        }
    }

    // Auto-format elements with data-datetime attribute
    document.querySelectorAll('[data-datetime]').forEach(function (el) {
        const raw = el.dataset.datetime;
        const format = el.dataset.datetimeFormat || 'datetime';
        if (!raw) return;
        switch (format) {
            case 'date':
                el.textContent = formatDate(raw);
                break;
            case 'time':
                el.textContent = formatTime(raw);
                break;
            case 'ago':
                el.textContent = timeAgo(raw);
                break;
            default:
                el.textContent = formatDatetime(raw);
        }
        el.title = raw;
    });

    window.EventForge.formatDatetime = formatDatetime;
    window.EventForge.formatDate = formatDate;
    window.EventForge.formatTime = formatTime;
    window.EventForge.timeAgo = timeAgo;
    window.EventForge.formatDatetimeLocal = formatDatetimeLocal;

    // ============================================================
    // HTML Escape Utility
    // ============================================================

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    window.EventForge.escapeHtml = escapeHtml;

    // ============================================================
    // Alpine.js Initialization Helpers
    // ============================================================

    function initAlpineData() {
        if (typeof Alpine === 'undefined') return;

        Alpine.data('dropdown', function () {
            return {
                open: false,
                toggle: function () { this.open = !this.open; },
                close: function () { this.open = false; }
            };
        });

        Alpine.data('modal', function () {
            return {
                show: false,
                openModal: function () { this.show = true; },
                closeModal: function () { this.show = false; }
            };
        });

        Alpine.data('tabs', function (defaultTab) {
            return {
                activeTab: defaultTab || '',
                setTab: function (tab) { this.activeTab = tab; },
                isActive: function (tab) { return this.activeTab === tab; }
            };
        });

        Alpine.data('confirmDelete', function () {
            return {
                confirming: false,
                startConfirm: function () { this.confirming = true; },
                cancel: function () { this.confirming = false; },
                confirmed: function () {
                    this.confirming = false;
                    return true;
                }
            };
        });

        Alpine.data('toast', function () {
            return {
                visible: false,
                message: '',
                type: 'info',
                showToast: function (msg, type) {
                    var self = this;
                    self.message = msg;
                    self.type = type || 'info';
                    self.visible = true;
                    setTimeout(function () {
                        self.visible = false;
                    }, 4000);
                }
            };
        });

        Alpine.data('checkInScanner', function () {
            return {
                ticketCode: '',
                status: '',
                statusType: '',
                loading: false,
                submitCheckIn: function () {
                    var self = this;
                    if (!self.ticketCode.trim()) {
                        self.status = 'Please enter a ticket code.';
                        self.statusType = 'error';
                        return;
                    }
                    self.loading = true;
                    self.status = '';
                    var form = self.$el.closest('form');
                    var url = form ? form.action : '/check-in';
                    fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify({ ticket_code: self.ticketCode.trim() })
                    })
                    .then(function (resp) {
                        return resp.json().then(function (data) {
                            return { ok: resp.ok, data: data };
                        });
                    })
                    .then(function (result) {
                        self.loading = false;
                        if (result.ok) {
                            self.status = result.data.message || 'Check-in successful!';
                            self.statusType = 'success';
                            self.ticketCode = '';
                        } else {
                            self.status = result.data.detail || result.data.message || 'Check-in failed.';
                            self.statusType = 'error';
                        }
                    })
                    .catch(function (err) {
                        self.loading = false;
                        self.status = 'Network error. Please try again.';
                        self.statusType = 'error';
                        console.error('Check-in error:', err);
                    });
                }
            };
        });
    }

    // Initialize Alpine.js data components if Alpine is available
    if (typeof Alpine !== 'undefined') {
        document.addEventListener('alpine:init', initAlpineData);
    } else {
        // If Alpine loads later, try again
        window.addEventListener('alpine:init', initAlpineData);
    }

    window.EventForge.initAlpineData = initAlpineData;

    // ============================================================
    // Flash Message Auto-Dismiss
    // ============================================================

    document.querySelectorAll('[data-auto-dismiss]').forEach(function (el) {
        var delay = parseInt(el.dataset.autoDismiss, 10) || 5000;
        setTimeout(function () {
            el.style.transition = 'opacity 0.3s ease';
            el.style.opacity = '0';
            setTimeout(function () { el.remove(); }, 300);
        }, delay);
    });

    // ============================================================
    // Dismiss buttons for alerts
    // ============================================================

    document.querySelectorAll('[data-dismiss]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var target = btn.closest(btn.dataset.dismiss || '.alert');
            if (target) {
                target.style.transition = 'opacity 0.2s ease';
                target.style.opacity = '0';
                setTimeout(function () { target.remove(); }, 200);
            }
        });
    });

});