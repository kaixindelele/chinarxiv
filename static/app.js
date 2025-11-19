// ============= 全局状态 =============
let currentTaskId = null;
let eventSource = null;
let selectedFile = null;

// ============= DOM元素 =============
const elements = {
    // Tab切换
    tabButtons: document.querySelectorAll('.tab-button'),
    tabContents: document.querySelectorAll('.tab-content'),
    
    // 输入元素
    arxivInput: document.getElementById('arxiv-input'),
    fileUpload: document.getElementById('file-upload'),
    uploadArea: document.getElementById('upload-area'),
    fileInfo: document.getElementById('file-info'),
    userRequirements: document.getElementById('user-requirements'),
    userTerms: document.getElementById('user-terms'),
    outputBilingual: document.getElementById('output-bilingual'),
    forceRetranslate: document.getElementById('force-retranslate'),
    
    // 高级参数
    advancedToggle: document.getElementById('advanced-toggle'),
    advancedContent: document.getElementById('advanced-content'),
    
    // 简介区域
    introToggle: document.getElementById('intro-toggle'),
    introContent: document.getElementById('intro-content'),
    
    // 按钮
    translateButton: document.getElementById('translate-button'),
    clearLogButton: document.getElementById('clear-log-button'),
    refreshCacheButton: document.getElementById('refresh-cache-button'),
    clearCacheButton: document.getElementById('clear-cache-button'),
    
    // 结果显示
    progressContainer: document.getElementById('progress-container'),
    progressFill: document.getElementById('progress-fill'),
    progressText: document.getElementById('progress-text'),
    logContent: document.getElementById('log-content'),
    downloadSection: document.getElementById('download-section'),
    downloadList: document.getElementById('download-list'),
    
    // 缓存信息
    cacheCount: document.getElementById('cache-count'),
    cacheSize: document.getElementById('cache-size'),
};

// ============= 初始化 =============
document.addEventListener('DOMContentLoaded', () => {
    initTabSwitching();
    initFileUpload();
    initIntroToggle();
    initAdvancedToggle();
    initTranslateButton();
    initCacheManagement();
    loadCacheStats();
});

// ============= Tab切换 =============
function initTabSwitching() {
    elements.tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.dataset.tab;
            
            // 更新按钮状态
            elements.tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // 更新内容显示
            elements.tabContents.forEach(content => {
                if (content.id === `${tabName}-tab`) {
                    content.classList.add('active');
                } else {
                    content.classList.remove('active');
                }
            });
        });
    });
}

// ============= 文件上传 =============
function initFileUpload() {
    // 点击上传区域
    elements.uploadArea.addEventListener('click', () => {
        elements.fileUpload.click();
    });
    
    // 文件选择
    elements.fileUpload.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileSelect(file);
        }
    });
    
    // 拖拽上传
    elements.uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.uploadArea.classList.add('drag-over');
    });
    
    elements.uploadArea.addEventListener('dragleave', () => {
        elements.uploadArea.classList.remove('drag-over');
    });
    
    elements.uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.uploadArea.classList.remove('drag-over');
        
        const file = e.dataTransfer.files[0];
        if (file && file.type === 'application/pdf') {
            handleFileSelect(file);
        } else {
            showError('请选择PDF文件');
        }
    });
}

function handleFileSelect(file) {
    selectedFile = file;
    
    // 显示文件信息
    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
    elements.fileInfo.innerHTML = `
        <strong>已选择：</strong> ${file.name} (${sizeInMB} MB)
    `;
    elements.fileInfo.style.display = 'block';
}

// ============= 简介区域折叠 =============
function initIntroToggle() {
    elements.introToggle.addEventListener('click', () => {
        const isVisible = elements.introContent.style.display !== 'none';
        
        if (isVisible) {
            elements.introContent.style.display = 'none';
            elements.introToggle.classList.remove('active');
        } else {
            elements.introContent.style.display = 'grid';
            elements.introToggle.classList.add('active');
        }
    });
}

// ============= 高级参数切换 =============
function initAdvancedToggle() {
    elements.advancedToggle.addEventListener('click', () => {
        const isVisible = elements.advancedContent.style.display !== 'none';
        
        if (isVisible) {
            elements.advancedContent.style.display = 'none';
            elements.advancedToggle.classList.remove('active');
        } else {
            elements.advancedContent.style.display = 'block';
            elements.advancedToggle.classList.add('active');
        }
    });
}

// ============= 翻译按钮 =============
function initTranslateButton() {
    elements.translateButton.addEventListener('click', handleTranslate);
}

async function handleTranslate() {
    // 获取当前激活的tab
    const activeTab = document.querySelector('.tab-button.active').dataset.tab;
    
    // 重置状态
    resetTranslationUI();
    
    if (activeTab === 'arxiv') {
        await translateArxiv();
    } else {
        await translateUpload();
    }
}

async function translateArxiv() {
    const arxivInput = elements.arxivInput.value.trim();
    
    if (!arxivInput) {
        showError('请输入arxiv链接或ID');
        return;
    }
    
    const formData = new FormData();
    formData.append('arxiv_input', arxivInput);
    formData.append('user_requirements', elements.userRequirements.value);
    formData.append('user_terms', elements.userTerms.value);
    formData.append('output_bilingual', elements.outputBilingual.checked);
    formData.append('force_retranslate', elements.forceRetranslate.checked);
    
    setTranslateButtonLoading(true);
    
    try {
        const response = await fetch('/api/translate/arxiv', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentTaskId = result.task_id;
            addLog(`任务已创建: ${result.task_id}`);
            startLogStreaming(result.task_id);
        } else {
            showError(result.error || '翻译启动失败');
            setTranslateButtonLoading(false);
        }
    } catch (error) {
        showError(`请求失败: ${error.message}`);
        setTranslateButtonLoading(false);
    }
}

async function translateUpload() {
    if (!selectedFile) {
        showError('请选择PDF文件');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('user_requirements', elements.userRequirements.value);
    formData.append('output_bilingual', elements.outputBilingual.checked);
    formData.append('force_retranslate', elements.forceRetranslate.checked);
    
    setTranslateButtonLoading(true);
    
    try {
        const response = await fetch('/api/translate/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentTaskId = result.task_id;
            addLog(`文件上传成功，任务ID: ${result.task_id}`);
            startLogStreaming(result.task_id);
        } else {
            showError(result.error || '上传失败');
            setTranslateButtonLoading(false);
        }
    } catch (error) {
        showError(`请求失败: ${error.message}`);
        setTranslateButtonLoading(false);
    }
}

// ============= 日志流 =============
function startLogStreaming(taskId) {
    // 关闭之前的连接
    if (eventSource) {
        eventSource.close();
    }
    
    // 显示进度条
    elements.progressContainer.style.display = 'block';
    
    // 创建SSE连接
    eventSource = new EventSource(`/api/translate/logs/${taskId}`);
    
    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleLogEvent(data);
        } catch (error) {
            console.error('解析日志失败:', error);
        }
    };
    
    eventSource.onerror = (error) => {
        console.error('SSE连接错误:', error);
        eventSource.close();
        setTranslateButtonLoading(false);
    };
}

function handleLogEvent(data) {
    switch (data.type) {
        case 'log':
            addLog(data.message);
            break;
            
        case 'progress':
            updateProgress(data.progress);
            if (data.status === 'completed' || data.status === 'error') {
                setTranslateButtonLoading(false);
            }
            break;
            
        case 'success':
            addLog('✅ 翻译完成！', 'success');
            showDownloadSection(data.files);
            setTranslateButtonLoading(false);
            loadCacheStats(); // 刷新缓存信息
            break;
            
        case 'error':
            addLog(`❌ ${data.message}`, 'error');
            setTranslateButtonLoading(false);
            break;
            
        case 'done':
            if (eventSource) {
                eventSource.close();
            }
            break;
    }
}

// ============= UI更新函数 =============
function resetTranslationUI() {
    // 清空日志
    elements.logContent.innerHTML = '';
    
    // 隐藏进度条和下载区域
    elements.progressContainer.style.display = 'none';
    elements.downloadSection.style.display = 'none';
    
    // 重置进度
    updateProgress(0);
}

function addLog(message, type = 'normal') {
    // 移除空日志提示
    const emptyLog = elements.logContent.querySelector('.log-empty');
    if (emptyLog) {
        emptyLog.remove();
    }
    
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    logEntry.textContent = message;
    
    elements.logContent.appendChild(logEntry);
    
    // 自动滚动到底部
    elements.logContent.scrollTop = elements.logContent.scrollHeight;
}

function updateProgress(progress) {
    elements.progressFill.style.width = `${progress}%`;
    elements.progressText.textContent = `${Math.round(progress)}%`;
}

function showDownloadSection(files) {
    elements.downloadSection.style.display = 'block';
    elements.downloadList.innerHTML = '';
    
    files.forEach(filePath => {
        const filename = filePath.split('/').pop();
        
        const downloadItem = document.createElement('div');
        downloadItem.className = 'download-item';
        downloadItem.innerHTML = `
            <span class="download-filename">📄 ${filename}</span>
            <a href="/api/download/${currentTaskId}/${filename}" 
               class="download-button" 
               download="${filename}">
                下载
            </a>
        `;
        
        elements.downloadList.appendChild(downloadItem);
    });
}

function setTranslateButtonLoading(loading) {
    const buttonText = elements.translateButton.querySelector('.button-text');
    const buttonLoading = elements.translateButton.querySelector('.button-loading');
    
    if (loading) {
        buttonText.style.display = 'none';
        buttonLoading.style.display = 'flex';
        elements.translateButton.disabled = true;
    } else {
        buttonText.style.display = 'block';
        buttonLoading.style.display = 'none';
        elements.translateButton.disabled = false;
    }
}

function showError(message) {
    addLog(`❌ ${message}`, 'error');
}

// ============= 缓存管理 =============
function initCacheManagement() {
    elements.clearLogButton.addEventListener('click', () => {
        elements.logContent.innerHTML = '<div class="log-empty">日志已清空</div>';
    });
    
    elements.refreshCacheButton.addEventListener('click', loadCacheStats);
    
    elements.clearCacheButton.addEventListener('click', async () => {
        if (!confirm('确定要清空所有缓存吗？')) {
            return;
        }
        
        try {
            const response = await fetch('/api/cache/clear', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                alert(result.message);
                loadCacheStats();
            } else {
                alert('清空缓存失败');
            }
        } catch (error) {
            alert(`请求失败: ${error.message}`);
        }
    });
}

async function loadCacheStats() {
    try {
        const response = await fetch('/api/cache/stats');
        const result = await response.json();
        
        if (result.success) {
            const stats = result.stats;
            elements.cacheCount.textContent = stats.count;
            elements.cacheSize.textContent = `${stats.size_mb.toFixed(2)} MB`;
        }
    } catch (error) {
        console.error('加载缓存信息失败:', error);
    }
}

// ============= 工具函数 =============
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

function formatTime(seconds) {
    if (seconds < 60) {
        return `${seconds}秒`;
    }
    
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    return `${minutes}分${remainingSeconds}秒`;
}

// ============= 错误处理 =============
window.addEventListener('error', (event) => {
    console.error('全局错误:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('未处理的Promise拒绝:', event.reason);
});

