// Toast notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const bgColors = {
        success: 'bg-emerald-600 text-white',
        error: 'bg-red-600 text-white',
        info: 'bg-slate-900 text-white',
        warning: 'bg-amber-600 text-white'
    };

    toast.className = `${bgColors[type] || bgColors.info} px-4 py-3 rounded-xl shadow-lg text-sm flex items-center gap-2 transform transition-all duration-300 translate-y-2 opacity-0`;
    toast.innerHTML = `<span>${message}</span>`;
    
    container.appendChild(toast);

    // Animate in
    setTimeout(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    // Auto remove after 3.5s
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Global files array for public request form
let selectedFiles = [];

function updateFilesUI() {
    const fileInput = document.getElementById('file-input');
    const countBadge = document.getElementById('files-count-badge');
    const listContainer = document.getElementById('files-list-container');
    const listEl = document.getElementById('files-list');

    if (!selectedFiles.length) {
        if (countBadge) countBadge.classList.add('hidden');
        if (listContainer) listContainer.classList.add('hidden');
        if (fileInput) fileInput.required = true;
        return;
    }

    if (fileInput) fileInput.required = false;

    const totalBytes = selectedFiles.reduce((acc, f) => acc + f.size, 0);
    if (countBadge) {
        countBadge.classList.remove('hidden');
        countBadge.textContent = `${selectedFiles.length} файл(ов) • ${formatFileSize(totalBytes)}`;
    }

    if (listContainer) listContainer.classList.remove('hidden');

    if (listEl) {
        listEl.innerHTML = '';
        selectedFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'flex items-center justify-between bg-white border border-slate-200 rounded-xl p-2.5 shadow-sm text-xs hover:border-slate-300 transition-colors';
            item.innerHTML = `
                <div class="flex items-center gap-2.5 overflow-hidden">
                    <div class="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                        <i data-lucide="file-text" class="w-4 h-4"></i>
                    </div>
                    <div class="text-left overflow-hidden">
                        <p class="font-medium text-slate-800 truncate max-w-xs sm:max-w-md">${file.name}</p>
                        <p class="text-[11px] text-slate-400">${formatFileSize(file.size)}</p>
                    </div>
                </div>
                <button type="button" onclick="removeSingleFile(${index})" title="Удалить файл"
                    class="text-slate-400 hover:text-red-600 p-1 rounded-lg hover:bg-red-50 transition-colors">
                    <i data-lucide="x" class="w-4 h-4"></i>
                </button>
            `;
            listEl.appendChild(item);
        });
    }

    if (window.lucide) lucide.createIcons();
}

function addFiles(newFiles) {
    if (!newFiles || !newFiles.length) return;
    for (let i = 0; i < newFiles.length; i++) {
        const file = newFiles[i];
        // Skip exact duplicate filename and size
        const exists = selectedFiles.some(f => f.name === file.name && f.size === file.size);
        if (!exists) {
            selectedFiles.push(file);
        }
    }
    syncToFileInput();
}

function removeSingleFile(index) {
    if (index >= 0 && index < selectedFiles.length) {
        selectedFiles.splice(index, 1);
        syncToFileInput();
    }
}

function clearAllFiles() {
    selectedFiles = [];
    syncToFileInput();
}

function syncToFileInput() {
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        try {
            const dt = new DataTransfer();
            selectedFiles.forEach(f => dt.items.add(f));
            fileInput.files = dt.files;
        } catch (e) {
            // Fallback for older browsers
        }
    }
    updateFilesUI();
}

// Client public form handling
document.addEventListener('DOMContentLoaded', () => {
    const requestForm = document.getElementById('content-request-form');
    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('drop-zone');
    const clearAllBtn = document.getElementById('clear-all-files-btn');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.getElementById('btn-text');
    const btnIcon = document.getElementById('btn-icon');
    const btnSpinner = document.getElementById('btn-spinner');
    const successModal = document.getElementById('success-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');

    // Drag and drop handling
    if (dropZone && fileInput) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropZone.classList.add('border-blue-500', 'bg-blue-50/60');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropZone.classList.remove('border-blue-500', 'bg-blue-50/60');
            });
        });

        dropZone.addEventListener('drop', (e) => {
            if (e.dataTransfer && e.dataTransfer.files) {
                addFiles(e.dataTransfer.files);
            }
        });

        fileInput.addEventListener('change', () => {
            addFiles(fileInput.files);
        });

        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => {
                clearAllFiles();
            });
        }
    }

    // Form submit via AJAX
    if (requestForm) {
        requestForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (!selectedFiles.length) {
                showToast('Пожалуйста, прикрепите хотя бы один документ с правками', 'warning');
                return;
            }

            // UI loading state
            submitBtn.disabled = true;
            const fileCount = selectedFiles.length;
            btnText.textContent = `Загрузка в Google Диск (${fileCount} ${fileCount === 1 ? 'файл' : 'файла(-ов)'})...`;
            btnIcon?.classList.add('hidden');
            btnSpinner?.classList.remove('hidden');

            const formData = new FormData(requestForm);
            // Ensure all selectedFiles are in FormData
            formData.delete('files');
            formData.delete('file');
            selectedFiles.forEach(f => {
                formData.append('files', f);
            });

            try {
                const response = await fetch('/submit', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    // Populate success modal
                    document.getElementById('modal-task-id').textContent = `#${data.task_id}`;
                    
                    const modalList = document.getElementById('modal-files-list');
                    if (modalList && data.files && data.files.length) {
                        modalList.innerHTML = '';
                        data.files.forEach(f => {
                            const fItem = document.createElement('div');
                            fItem.className = 'flex items-center justify-between bg-white border border-slate-200 rounded-lg p-2 hover:border-blue-200 transition-colors';
                            fItem.innerHTML = `
                                <div class="flex items-center gap-2 overflow-hidden pr-2">
                                    <i data-lucide="file-text" class="w-3.5 h-3.5 text-blue-600 shrink-0"></i>
                                    <span class="truncate font-medium text-slate-800">${f.name}</span>
                                </div>
                                <a href="${f.url}" target="_blank" 
                                   class="text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1 shrink-0">
                                    <span>Открыть ↗</span>
                                </a>
                            `;
                            modalList.appendChild(fItem);
                        });
                    }

                    successModal.classList.remove('hidden');
                    requestForm.reset();
                    clearAllFiles();
                    if (window.lucide) lucide.createIcons();
                } else {
                    showToast(data.message || 'Ошибка при отправке заявки', 'error');
                }
            } catch (err) {
                showToast('Сетевая ошибка при отправке запроса', 'error');
            } finally {
                submitBtn.disabled = false;
                btnText.textContent = 'Отправить заявку';
                btnIcon?.classList.remove('hidden');
                btnSpinner?.classList.add('hidden');
            }
        });
    }

    if (modalCloseBtn && successModal) {
        modalCloseBtn.addEventListener('click', () => {
            successModal.classList.add('hidden');
        });
    }
});

// Admin Panel Functions
async function toggleTaskDone(taskId, isChecked) {
    const newStatus = isChecked ? 'completed' : 'new';
    await updateTaskStatus(taskId, newStatus);
}

async function updateTaskStatus(taskId, newStatus) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            const card = document.getElementById(`task-card-${taskId}`);
            const badge = document.getElementById(`status-badge-${taskId}`);
            
            if (newStatus === 'completed') {
                showToast(`Задача #${taskId} отмечена как выполненная! 🎉`, 'success');
                if (card) {
                    card.classList.add('border-emerald-200', 'bg-emerald-50/20');
                    card.classList.remove('border-slate-200');
                }
                if (badge) {
                    badge.className = 'text-[11px] font-semibold px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 bg-emerald-100 text-emerald-800';
                    badge.innerHTML = `<i data-lucide="check-check" class="w-3 h-3"></i> Сделано`;
                }
            } else if (newStatus === 'in_progress') {
                showToast(`Задача #${taskId} переведена в статус "В работе"`, 'info');
                if (card) {
                    card.classList.remove('border-emerald-200', 'bg-emerald-50/20');
                    card.classList.add('border-slate-200');
                }
                if (badge) {
                    badge.className = 'text-[11px] font-semibold px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 bg-amber-100 text-amber-800';
                    badge.innerHTML = `<i data-lucide="play" class="w-3 h-3"></i> В работе`;
                }
            } else {
                showToast(`Задача #${taskId} возвращена в очередь`, 'info');
                if (card) {
                    card.classList.remove('border-emerald-200', 'bg-emerald-50/20');
                    card.classList.add('border-slate-200');
                }
                if (badge) {
                    badge.className = 'text-[11px] font-semibold px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 bg-blue-100 text-blue-800';
                    badge.innerHTML = `<i data-lucide="circle-dot" class="w-3 h-3"></i> В очереди`;
                }
            }

            // Update stats counters if present
            if (data.stats) {
                updateStatsUI(data.stats);
            }

            if (window.lucide) lucide.createIcons();
        } else {
            showToast('Не удалось обновить статус задачи', 'error');
        }
    } catch (err) {
        showToast('Ошибка сети при обновлении статуса', 'error');
    }
}

function updateStatsUI(stats) {
    const elTotal = document.getElementById('stat-total');
    const elPending = document.getElementById('stat-pending');
    const elInProgress = document.getElementById('stat-in-progress');
    const elCompleted = document.getElementById('stat-completed');
    if (elTotal) elTotal.textContent = stats.total;
    if (elPending) elPending.textContent = stats.pending;
    if (elInProgress) elInProgress.textContent = stats.in_progress;
    if (elCompleted) elCompleted.textContent = stats.completed;
}

async function saveTaskNote(taskId) {
    const noteInput = document.getElementById(`note-input-${taskId}`);
    if (!noteInput) return;

    try {
        const response = await fetch(`/api/tasks/${taskId}/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes: noteInput.value })
        });
        const data = await response.json();
        if (response.ok && data.success) {
            showToast('Заметка сохранена', 'success');
        } else {
            showToast('Ошибка сохранения заметки', 'error');
        }
    } catch (err) {
        showToast('Сетевая ошибка', 'error');
    }
}

async function deleteTask(taskId) {
    if (!confirm(`Вы действительно хотите удалить задачу #${taskId}?`)) return;

    try {
        const response = await fetch(`/api/tasks/${taskId}/delete`, {
            method: 'POST'
        });
        const data = await response.json();
        if (response.ok && data.success) {
            const card = document.getElementById(`task-card-${taskId}`);
            if (card) {
                card.style.opacity = '0';
                card.style.transform = 'scale(0.95)';
                setTimeout(() => card.remove(), 250);
            }
            if (data.stats) updateStatsUI(data.stats);
            showToast(`Задача #${taskId} удалена`, 'info');
        } else {
            showToast('Ошибка при удалении задачи', 'error');
        }
    } catch (err) {
        showToast('Сетевая ошибка', 'error');
    }
}

async function testDriveConnection() {
    showToast('Проверка подключения к Google Диску...', 'info');
    try {
        const res = await fetch('/api/test-drive');
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
        } else {
            showToast(data.message, 'warning');
        }
    } catch (e) {
        showToast('Ошибка при проверке связи', 'error');
    }
}

function openDriveSetupModal() {
    document.getElementById('drive-setup-modal')?.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}

function closeDriveSetupModal() {
    document.getElementById('drive-setup-modal')?.classList.add('hidden');
}
