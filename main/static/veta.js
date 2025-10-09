// 全局变量
let currentMode = 'vet';
let currentTaskId = null;
let tasks = [];
let currentUserId = localStorage.getItem('currentUserId') || null;
let userStorage = null; // 用户存储管理器
let isAutoLoginInProgress = false; // 防止重复显示登录弹窗
let ragEnabled = false; // RAG知识库开关状态

// DOM 元素
const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const newTaskBtn = document.getElementById('new-task-btn');
const modeOptions = document.querySelectorAll('.mode-option');
const modeIcon = document.getElementById('mode-icon');
const modeName = document.getElementById('mode-name');
const modal = document.getElementById('mode-modal');
const modalCancel = document.getElementById('modal-cancel');
const modalConfirm = document.getElementById('modal-confirm');
const modeCards = document.querySelectorAll('.mode-card');
const userIdModal = document.getElementById('user-id-modal');
const userIdInput = document.getElementById('user-id-input');
const userIdConfirm = document.getElementById('user-id-confirm');
const clearAllTasksBtn = document.getElementById('clear-all-tasks-btn');
const userMenuBtn = document.getElementById('user-menu-btn');
const userDropdown = document.getElementById('user-dropdown');
const logoutBtn = document.getElementById('logout-btn');
const currentUserDisplay = document.getElementById('current-user-display');
const dropdownUserName = document.getElementById('dropdown-user-name');
const menuToggle = document.getElementById('menu-toggle');
const sidebar = document.querySelector('.sidebar');
const sidebarOverlay = document.querySelector('.sidebar-overlay');

// 新增的控制元素
const knowledgeToggle = document.getElementById('knowledge-checkbox');
const voiceBtn = document.getElementById('voice-btn');
const attachmentBtn = document.getElementById('attachment-btn');
const toolsBtn = document.getElementById('tools-btn');
const toolsMenu = document.getElementById('tools-menu');

// 任务管理
class TaskManager {
    constructor(userStorage) {
        this.userStorage = userStorage;
        this.tasks = this.userStorage ? this.userStorage.getItem('vetTasks', []) : [];
        this.currentTaskId = this.userStorage ? this.userStorage.getItem('currentTaskId') : null;
        this.render();
    }

    createTask(mode, title = null) {
        const task = {
            id: Date.now().toString(),
            mode: mode,
            title: title || this.getDefaultTitle(mode),
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        
        this.tasks.unshift(task);
        this.saveToStorage();
        return task;
    }

    getDefaultTitle(mode) {
        const titles = {
            animal: '模拟问诊',
            vet: '兽医问答'
        };
        return titles[mode] || '新对话';
    }

    updateTaskTitle(taskId, title) {
        const task = this.tasks.find(t => t.id === taskId);
        if (task) {
            task.title = title;
            task.updatedAt = new Date().toISOString();
            this.saveToStorage();
            this.render();
        }
    }

    addMessage(taskId, role, content) {
        const task = this.tasks.find(t => t.id === taskId);
        if (task) {
            task.messages.push({ role, content, timestamp: new Date().toISOString() });
            task.updatedAt = new Date().toISOString();
            
            // 自动更新任务标题（使用第一条用户消息）
            if (role === 'user' && task.messages.filter(m => m.role === 'user').length === 1) {
                task.title = content.slice(0, 30) + (content.length > 30 ? '...' : '');
            }
            
            this.saveToStorage();
            this.render();
        }
    }

    // 读取当前任务最后一条AI消息文本
    getLastAiMessageText(taskId) {
        const task = this.tasks.find(t => t.id === taskId);
        if (!task || !task.messages || task.messages.length === 0) return null;
        for (let i = task.messages.length - 1; i >= 0; i--) {
            const msg = task.messages[i];
            if (msg && msg.role === 'ai' && typeof msg.content === 'string' && msg.content.length > 0) {
                return msg.content;
            }
        }
        return null;
    }

    getTask(taskId) {
        return this.tasks.find(t => t.id === taskId);
    }

    deleteTask(taskId) {
        const wasCurrent = currentTaskId === taskId;
        this.tasks = this.tasks.filter(t => t.id !== taskId);
        this.saveToStorage();
        this.render();

        if (wasCurrent) {
            if (this.tasks.length > 0) {
                // 切到最新的一个任务
                const nextTask = this.tasks[0];
                this.switchToTask(nextTask.id);
            } else {
                // 如果没有任务了，创建一个与当前模式一致的新任务
                createNewTask(currentMode);
            }
        }
    }

    clearAllTasks() {
        this.tasks = [];
        currentTaskId = null;
        this.saveToStorage();
        this.render();
        // 清空聊天窗口
        chatWindow.innerHTML = '';
        // 创建新任务
        createNewTask(currentMode);
    }

    saveToStorage() {
        if (this.userStorage) {
            this.userStorage.setItem('vetTasks', this.tasks);
            if (currentTaskId) {
                this.userStorage.setItem('currentTaskId', currentTaskId);
            }
        }
    }

    render() {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

        const todayTasks = [];
        const yesterdayTasks = [];
        const weekTasks = [];

        this.tasks.forEach(task => {
            const taskDate = new Date(task.updatedAt);
            const taskDay = new Date(taskDate.getFullYear(), taskDate.getMonth(), taskDate.getDate());
            
            if (taskDay.getTime() === today.getTime()) {
                todayTasks.push(task);
            } else if (taskDay.getTime() === yesterday.getTime()) {
                yesterdayTasks.push(task);
            } else if (taskDate >= weekAgo) {
                weekTasks.push(task);
            }
        });

        this.renderTaskSection('today-tasks', todayTasks);
        this.renderTaskSection('yesterday-tasks', yesterdayTasks);
        this.renderTaskSection('week-tasks', weekTasks);
    }

    renderTaskSection(containerId, tasks) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = '';
        
        tasks.forEach(task => {
            const taskElement = document.createElement('div');
            taskElement.className = `task-item ${task.id === currentTaskId ? 'active' : ''}`;
            taskElement.innerHTML = `
                <i class="fas ${task.mode === 'animal' ? 'fa-hospital' : 'fa-user-md'}"></i>
                <span class="task-title">${task.title}</span>
                <button type="button" class="task-delete-btn" title="删除任务" aria-label="删除任务">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            
            taskElement.addEventListener('click', () => {
                this.switchToTask(task.id);
            });
            
            const deleteBtn = taskElement.querySelector('.task-delete-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const ok = window.confirm('确认删除该任务？此操作不可恢复');
                if (!ok) return;
                this.deleteTask(task.id);
            });
            
            container.appendChild(taskElement);
        });
    }

    switchToTask(taskId) {
        const task = this.getTask(taskId);
        if (!task) return;

        currentTaskId = taskId;
        currentMode = task.mode;
        
        // 更新UI
        this.updateModeUI();
        this.render();
        this.loadTaskMessages(task);
        
        // 保存当前状态
        if (this.userStorage) {
            this.userStorage.setItem('currentTaskId', currentTaskId);
        }
    }

    updateModeUI() {
        // 更新模式显示
        const modeConfig = {
            animal: { icon: 'fas fa-hospital', name: '模拟问诊' },
            vet: { icon: 'fas fa-user-md', name: '兽医问答' }
        };
        
        const config = modeConfig[currentMode];
        modeIcon.className = config.icon;
        modeName.textContent = config.name;
        
        // 更新侧边栏模式选择
        modeOptions.forEach(option => {
            option.classList.toggle('active', option.dataset.mode === currentMode);
        });
    }

    loadTaskMessages(task) {
        chatWindow.innerHTML = '';
        
        if (task.messages.length === 0) {
            this.showWelcomeMessage();
        } else {
            task.messages.forEach(msg => {
                this.appendMessage(msg.role, msg.content);
            });
        }
    }

    showWelcomeMessage() {
        const welcomeMessages = {
            animal: '您好，欢迎来到智能体动物医院！这里是模拟问诊模式，我将以医生的身份与您进行对话，帮助记录和分析您的宠物症状，模拟真实的就诊流程。',
            vet: '您好，我是您的宠物问答AI助手。在这里，您可以向我咨询关于宠物健康、日常护理、饮食建议等方面的问题，我会为您提供专业的参考意见。'
        };
        
        
        this.appendMessage('ai', welcomeMessages[currentMode]);
    }

    appendMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        if (role === 'ai') {
            messageContent.innerHTML = this.renderMarkdown(content);
        } else {
            messageContent.textContent = content;
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    renderMarkdown(mdText) {
        if (!mdText) return '';
        // 使用 markdown-it 渲染并用 DOMPurify 消毒
        try {
            const md = window.markdownit({
                html: false,
                linkify: true,
                typographer: true,
                breaks: true  // 支持软换行（GFM风格）
            });
            const dirty = md.render(mdText);
            const clean = window.DOMPurify ? window.DOMPurify.sanitize(dirty, {USE_PROFILES: {html: true}}) : dirty;
            return `<div class="md">${clean}</div>`;
        } catch (e) {
            console.error('Markdown 渲染失败，退回纯文本:', e);
            return `<div class="md"><pre>${mdText}</pre></div>`;
        }
    }
}

// 初始化任务管理器（稍后在用户登录后初始化）
let taskManager = null;

// 用户ID管理
function showUserIdModal() {
    // 如果正在自动登录过程中，不显示登录弹窗
    if (isAutoLoginInProgress) {
        console.log('🚫 自动登录进行中，跳过显示登录弹窗');
        return;
    }
    
    console.log('🔑 显示登录弹窗');
    // 清空界面，显示空白背景
    clearUIForLogin();
    userIdModal.classList.remove('hidden');
    userIdInput.focus();
}

// 清空UI为登录状态
function clearUIForLogin() {
    // 清空聊天窗口
    chatWindow.innerHTML = '';
    
    // 清空用户显示
    currentUserDisplay.textContent = '';
    dropdownUserName.textContent = '';
    
    // 清空任务列表
    document.getElementById('today-tasks').innerHTML = '';
    document.getElementById('yesterday-tasks').innerHTML = '';
    document.getElementById('week-tasks').innerHTML = '';
    
    // 重置为默认模式显示
    currentMode = 'vet';
    modeIcon.className = 'fas fa-user-md';
    modeName.textContent = '兽医模式';
    
    // 更新侧边栏模式选择
    modeOptions.forEach(option => {
        option.classList.toggle('active', option.dataset.mode === 'vet');
    });
}

function hideUserIdModal() {
    userIdModal.classList.add('hidden');
}

function setUserId(userId) {
    console.log('🔧 设置用户ID:', userId);
    
    currentUserId = userId;
    localStorage.setItem('currentUserId', userId);
    
    // 验证保存是否成功
    const savedUserId = localStorage.getItem('currentUserId');
    console.log('💾 保存验证 - 期望:', userId, '实际:', savedUserId, '成功:', savedUserId === userId);
    
    // 初始化用户存储管理器
    userStorage = new UserStorage(userId);
    
    // 初始化任务管理器
    taskManager = new TaskManager(userStorage);
    
    console.log('✅ 用户ID已设置:', userId);
    console.log('📊 用户存储空间大小:', (userStorage.getDataSize() / 1024).toFixed(2) + ' KB');
    console.log('🔒 用户ID已保存到浏览器缓存，下次访问将自动登录');
    
    // 更新用户显示
    updateUserDisplay();
}

// 更新用户显示
function updateUserDisplay() {
    if (currentUserId) {
        currentUserDisplay.textContent = currentUserId.length > 8 ? currentUserId.substring(0, 8) + '...' : currentUserId;
        dropdownUserName.textContent = currentUserId;
    }
}

// 显示自动登录消息
function showAutoLoginMessage(userId) {
    // 创建临时提示消息
    const message = document.createElement('div');
    message.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #4CAF50, #45a049);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        font-size: 14px;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    message.textContent = `欢迎回来，${userId}！`;
    
    document.body.appendChild(message);
    
    // 显示动画
    setTimeout(() => message.style.opacity = '1', 100);
    
    // 3秒后自动消失
    setTimeout(() => {
        message.style.opacity = '0';
        setTimeout(() => document.body.removeChild(message), 300);
    }, 3000);
}

// 退出登录
function logout() {
    // 清除本地存储
    localStorage.removeItem('currentUserId');
    currentUserId = null;
    userStorage = null;
    taskManager = null;
    
    // 显示登录弹窗（会自动清空UI）
    showUserIdModal();
}

// 事件监听器
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 页面加载完成，检查用户登录状态...');
    
    // 重新从localStorage获取用户ID，确保最新值
    const storedUserId = localStorage.getItem('currentUserId');
    console.log('🔍 localStorage中的用户ID:', storedUserId);
    console.log('🔍 全局变量currentUserId:', currentUserId);
    
    // 使用localStorage中的值作为最终判断
    if (!storedUserId || storedUserId.trim() === '') {
        console.log('❌ 未找到有效的缓存用户ID，显示登录弹窗');
        showUserIdModal();
        return;
    }
    
    console.log('✅ 找到缓存的用户ID:', storedUserId);
    // 设置自动登录标志
    isAutoLoginInProgress = true;
    
    // 更新全局变量
    currentUserId = storedUserId;
    
    // 自动登录：初始化用户数据
    console.log('🔄 开始自动登录流程...');
    setUserId(currentUserId);
    updateUserDisplay();
    
    // 直接初始化应用，不再调用initializeApp()避免重复检查
    console.log('🚀 直接初始化应用组件...');
    initializeAppComponents();
    
    // 显示自动登录提示
    showAutoLoginMessage(currentUserId);
    
    // 确保登录弹窗被隐藏
    hideUserIdModal();
    
    // 清除自动登录标志
    isAutoLoginInProgress = false;
    console.log('✅ 自动登录完成');
});

// 初始化应用组件（不做用户检查）
function initializeAppComponents() {
    console.log('🎯 初始化应用组件...');
    
    // 获取用户的当前任务ID
    currentTaskId = userStorage.getItem('currentTaskId');
    console.log('📋 当前任务ID:', currentTaskId);
    
    // 如果有当前任务，切换到该任务
    if (currentTaskId) {
        const task = taskManager.getTask(currentTaskId);
        if (task) {
            console.log('🔄 切换到现有任务:', currentTaskId);
            taskManager.switchToTask(currentTaskId);
        } else {
            console.log('📝 创建新任务（旧任务不存在）');
            createNewTask();
        }
    } else {
        console.log('📝 创建新任务（无当前任务）');
        createNewTask();
    }
    
    // 初始化控制元素
    initializeControls();
}

function initializeApp() {
    console.log('🔧 初始化应用...');
    console.log('🔍 检查状态:', {
        currentUserId: currentUserId,
        userStorage: !!userStorage,
        taskManager: !!taskManager
    });
    
    // 确保已经设置了用户ID和存储管理器
    if (!userStorage || !taskManager) {
        if (currentUserId) {
            console.log('🔧 重新初始化用户存储和任务管理器');
            setUserId(currentUserId);
        } else {
            console.log('❌ 没有用户ID，显示登录弹窗');
            showUserIdModal();
            return;
        }
    }
    
    // 调用应用组件初始化
    initializeAppComponents();
}

// 新任务按钮
newTaskBtn.addEventListener('click', () => {
    modal.classList.remove('hidden');
});

// 模式选择
modeOptions.forEach(option => {
    option.addEventListener('click', () => {
        const mode = option.dataset.mode;
        if (mode !== currentMode) {
            // 切换模式需要创建新任务
            modal.classList.remove('hidden');
            // 预选择对应模式
            modeCards.forEach(card => {
                card.classList.toggle('selected', card.dataset.mode === mode);
            });
        }
    });
});

// 模式卡片选择
modeCards.forEach(card => {
    card.addEventListener('click', () => {
        modeCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
    });
});

// 模态框按钮
modalCancel.addEventListener('click', () => {
    modal.classList.add('hidden');
    // 重置选择
    modeCards.forEach(card => {
        card.classList.toggle('selected', card.dataset.mode === currentMode);
    });
});

modalConfirm.addEventListener('click', () => {
    const selectedCard = document.querySelector('.mode-card.selected');
    if (selectedCard) {
        const newMode = selectedCard.dataset.mode;
        createNewTask(newMode);
    }
    modal.classList.add('hidden');
});

// 用户ID弹窗事件监听
userIdConfirm.addEventListener('click', () => {
    const userId = userIdInput.value.trim();
    if (!userId) {
        alert('请输入用户ID');
        return;
    }
    
    console.log('用户登录:', userId);
    setUserId(userId);
    hideUserIdModal();
    initializeApp();
    
    // 显示登录成功提示
    console.log('用户登录成功，已保存到浏览器缓存');
});

// 用户ID输入框回车事件
userIdInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        userIdConfirm.click();
    }
});

// 聊天表单提交
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;

    // 确保有当前任务和taskManager
    if (!currentTaskId || !taskManager) {
        createNewTask();
    }

    // 添加用户消息
    if (taskManager) {
        taskManager.addMessage(currentTaskId, 'user', text);
        taskManager.appendMessage('user', text);
    }
    userInput.value = '';

    //用户的输入从这里通过HTTP请求发送到后端（流式版本）
    try {
        const response = await fetch('/send_message_stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: text, 
                mode: currentMode,
                task_id: currentTaskId,
                user_id: currentUserId,
                rag_enabled: ragEnabled
            })
        });
        
        // 创建AI消息容器用于流式显示
        const aiMessageDiv = document.createElement('div');
        aiMessageDiv.className = 'message ai';
        aiMessageDiv.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content">
                <div class="streaming-content"></div>
                <span class="cursor"></span>
            </div>
        `;
        chatWindow.appendChild(aiMessageDiv);
        const streamingContent = aiMessageDiv.querySelector('.streaming-content');
        const cursor = aiMessageDiv.querySelector('.cursor');
        
        let fullResponse = '';
        
        // 读取流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'clear') {
                            // 后端指示开始同一节点的新一轮输出，清空上一轮内容
                            console.log('🧹 收到 clear 信号，清空内容');
                            fullResponse = '';
                            streamingContent.innerHTML = '';
                            chatWindow.scrollTop = chatWindow.scrollHeight;
                        } else if (data.type === 'token') {
                            // 流式添加 token 并实时渲染 markdown
                            fullResponse += data.content;
                            
                            // 使用 renderMarkdown 实时渲染
                            if (taskManager) {
                                streamingContent.innerHTML = taskManager.renderMarkdown(fullResponse);
                            } else {
                                streamingContent.textContent = fullResponse;
                            }
                            chatWindow.scrollTop = chatWindow.scrollHeight;
                        } else if (data.type === 'done') {
                            // 完成，移除光标
                            cursor.remove();
                            
                            // 如果流式累积的内容为空，才使用服务器返回的内容
                            if (!fullResponse && data.response) {
                                fullResponse = data.response;
                                // 最终渲染
                                if (taskManager) {
                                    streamingContent.innerHTML = taskManager.renderMarkdown(fullResponse);
                                } else {
                                    streamingContent.textContent = fullResponse;
                                }
                            }
                            
                            // 保存到任务管理器
                            if (taskManager) {
                                taskManager.addMessage(currentTaskId, 'ai', fullResponse);
                            }
                        } else if (data.type === 'error') {
                            // 错误处理
                            cursor.remove();
                            streamingContent.textContent = '抱歉，发生了错误：' + data.message;
                        }
                    } catch (e) {
                        console.error('解析SSE数据错误:', e, line);
                    }
                }
            }
        }
        
    } catch (error) {
        console.error('Error:', error);
        
        // 显示错误消息
        if (taskManager) {
            taskManager.appendMessage('ai', '抱歉，发生了错误，请稍后重试。');
        }
    }
});

// 创建新任务
function createNewTask(mode = 'vet') {
    // 确保taskManager已初始化
    if (!taskManager) {
        if (currentUserId) {
            setUserId(currentUserId);
        } else {
            console.error('无法创建任务：用户未登录');
            return;
        }
    }
    
    const task = taskManager.createTask(mode);
    currentTaskId = task.id;
    currentMode = mode;
    
    taskManager.switchToTask(currentTaskId);
}

// 清理所有任务按钮事件
clearAllTasksBtn.addEventListener('click', () => {
    const confirmed = confirm('确定要清理所有任务吗？此操作不可恢复。');
    if (confirmed && taskManager) {
        taskManager.clearAllTasks();
    }
});

// 用户菜单事件
userMenuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    userDropdown.classList.toggle('hidden');
});

// 点击其他地方关闭用户菜单
document.addEventListener('click', (e) => {
    if (!userDropdown.contains(e.target) && !userMenuBtn.contains(e.target)) {
        userDropdown.classList.add('hidden');
    }
});

// 退出登录按钮事件
logoutBtn.addEventListener('click', () => {
    const confirmed = confirm('确定要退出登录吗？');
    if (confirmed) {
        logout();
        userDropdown.classList.add('hidden');
    }
});

// 键盘快捷键
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + N 新任务
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        modal.classList.remove('hidden');
    }
    
    // ESC 关闭模态框
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
        modal.classList.add('hidden');
    }
});

// 点击模态框背景关闭
modal.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.classList.add('hidden');
    }
});

// 移动端侧边栏控制
function toggleSidebar() {
    sidebar.classList.toggle('open');
    sidebarOverlay.classList.toggle('active');
    
    // 切换汉堡菜单图标
    const icon = menuToggle.querySelector('i');
    if (sidebar.classList.contains('open')) {
        icon.className = 'fas fa-times';
    } else {
        icon.className = 'fas fa-bars';
    }
}

function closeSidebar() {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('active');
    const icon = menuToggle.querySelector('i');
    icon.className = 'fas fa-bars';
}

// 汉堡菜单按钮点击
if (menuToggle) {
    menuToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSidebar();
    });
}

// 遮罩层点击关闭侧边栏
if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeSidebar);
}

// 移动端点击任务后自动关闭侧边栏
const originalSwitchToTask = TaskManager.prototype.switchToTask;
TaskManager.prototype.switchToTask = function(taskId) {
    originalSwitchToTask.call(this, taskId);
    
    // 如果是移动端，关闭侧边栏
    if (window.innerWidth <= 768) {
        closeSidebar();
    }
};

// 窗口大小改变时的处理
let resizeTimer;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
        // 如果从移动端切换到桌面端，确保侧边栏正常显示
        if (window.innerWidth > 768) {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
            const icon = menuToggle.querySelector('i');
            if (icon) icon.className = 'fas fa-bars';
        }
    }, 250);
});

// 阻止移动端侧边栏打开时背景滚动
document.addEventListener('touchmove', (e) => {
    if (sidebar.classList.contains('open') && !sidebar.contains(e.target)) {
        e.preventDefault();
    }
}, { passive: false });

// 初始化控制元素
function initializeControls() {
    console.log('🎛️ 初始化控制元素...');
    
    // 从localStorage恢复RAG状态
    ragEnabled = localStorage.getItem('ragEnabled') === 'true';
    if (knowledgeToggle) {
        knowledgeToggle.checked = ragEnabled;
    }
    
    // 工具按钮下拉菜单
    if (toolsBtn && toolsMenu) {
        toolsBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            toolsMenu.classList.toggle('hidden');
        });
        
        // 点击其他地方关闭菜单
        document.addEventListener('click', function() {
            if (toolsMenu && !toolsMenu.classList.contains('hidden')) {
                toolsMenu.classList.add('hidden');
            }
        });
        
        // 阻止菜单内部点击事件冒泡
        toolsMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    // RAG开关事件监听
    if (knowledgeToggle) {
        knowledgeToggle.addEventListener('change', function() {
            ragEnabled = this.checked;
            localStorage.setItem('ragEnabled', ragEnabled.toString());
            console.log('🔄 RAG状态切换:', ragEnabled ? '开启' : '关闭');
            
            // 显示提示
            showToast(ragEnabled ? '知识库已开启' : '知识库已关闭', ragEnabled ? 'success' : 'info');
        });
    }
    
    // 语音按钮事件监听（占位功能）
    if (voiceBtn) {
        voiceBtn.addEventListener('click', function() {
            console.log('🎤 语音输入功能（待实现）');
            showToast('语音输入功能正在开发中...', 'info');
        });
    }
    
    // 附件按钮事件监听（占位功能）
    if (attachmentBtn) {
        attachmentBtn.addEventListener('click', function() {
            console.log('📎 附件功能（待实现）');
            showToast('附件功能正在开发中...', 'info');
        });
    }
}

// 简单的Toast提示功能
function showToast(message, type = 'info') {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // 添加样式
    Object.assign(toast.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        background: type === 'success' ? '#4CAF50' : '#2196F3',
        color: 'white',
        padding: '12px 20px',
        borderRadius: '6px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        zIndex: '10000',
        fontSize: '14px',
        fontWeight: '500',
        opacity: '0',
        transform: 'translateY(-10px)',
        transition: 'all 0.3s ease'
    });
    
    document.body.appendChild(toast);
    
    // 显示动画
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    }, 10);
    
    // 自动消失
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}