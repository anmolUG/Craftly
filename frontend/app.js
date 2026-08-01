/* ============================================
   Coder Buddy — Frontend Logic
   ============================================ */

   const wsUrl = `ws://${window.location.host}/ws`;
   let ws = null;
   let isProcessing = false;
   let activeTab = null;
   let files = {}; // path -> content
   
   // DOM Elements
   const statusBadge = document.getElementById('statusBadge');
   const statusDot = document.getElementById('statusDot');
   const statusText = document.getElementById('statusText');
   const promptInput = document.getElementById('promptInput');
   const sendBtn = document.getElementById('sendBtn');
   const activityFeed = document.getElementById('activityFeed');
   const welcomeScreen = document.getElementById('welcomeScreen');
   const tabBar = document.getElementById('tabBar');
   const previewTab = document.getElementById('previewTab');
   const codeViewer = document.getElementById('codeViewer');
   const emptyState = document.getElementById('emptyState');
   const previewFrame = document.getElementById('previewFrame');
   
   // --- WebSocket Connection ---
   function connect() {
       ws = new WebSocket(wsUrl);
   
       ws.onopen = () => {
           console.log("Connected to server");
           if (!isProcessing) setStatus("Ready", false);
       };
   
       ws.onclose = () => {
           console.log("Disconnected. Reconnecting in 3s...");
           setStatus("Disconnected", false);
           setTimeout(connect, 3000);
       };
   
       ws.onmessage = (event) => {
           const msg = JSON.parse(event.data);
           handleEvent(msg.type, msg.data);
       };
   }
   
   // --- Event Handling ---
   let currentCardId = null;
   
   function handleEvent(type, data) {
       switch (type) {
           case "planner_start":
               isProcessing = true;
               setStatus("Planning...", true);
               emptyState.style.display = "none";
               previewFrame.classList.remove('active');
               currentCardId = addActivityCard("Planner", "Analyzing request and creating project plan");
               break;
   
           case "planner_done":
               updateActivityCard(currentCardId, "Planner", `Plan created: ${data.plan.name}`, true);
               appendCardDetail(currentCardId, `Techstack: ${data.plan.techstack}`);
               appendCardDetail(currentCardId, `Features: ${data.plan.features.length}`);
               appendCardDetail(currentCardId, `Files: ${data.plan.files.length}`);
               break;
   
           case "architect_start":
               setStatus("Architecting...", true);
               currentCardId = addActivityCard("Architect", "Breaking down plan into engineering tasks");
               break;
   
           case "architect_done":
            updateActivityCard(currentCardId, "Architect", `Created ${data.tasks.length} tasks`, true);
            if (data.tasks) {
                data.tasks.forEach(t => {
                    const desc = t.task_description || '';
                    const shortDesc = desc.length > 50 ? desc.substring(0, 50) + '...' : desc;
                    appendCardDetail(currentCardId, `${t.filepath}: ${shortDesc}`);
                });
            }
            break;
   
           case "coder_start":
               setStatus(`Coding (${data.step}/${data.total})...`, true);
               currentCardId = addActivityCard("Coder", `Writing ${data.filepath}`);
               appendCardProgress(currentCardId);
               break;
   
           case "file_written":
               handleFileWritten(data.filepath, data.content);
               break;
   
           case "coder_step_done":
               updateActivityCard(currentCardId, "Coder", `Completed step ${data.step}/${data.total}`, true);
               updateCardProgress(currentCardId, 100);
               break;
   
           case "done":
            isProcessing = false;
            setStatus("Done", false);
            statusDot.classList.add('done');
            addActivityCard("Done", "Project generation complete!", true);
            previewTab.style.display = "flex";
            switchToPreview();
            
            // Change placeholder to encourage iteration
            promptInput.placeholder = "Describe the changes you want to make...";
            break;
   
           case "error":
               isProcessing = false;
               setStatus("Error", false);
               addActivityCard("Error", data.message, true);
               break;
       }
   }
   
   // --- UI Updates ---
   function setStatus(text, active) {
       statusText.textContent = text;
       if (active) {
           statusDot.classList.add('active');
           statusDot.classList.remove('done');
           sendBtn.disabled = true;
           promptInput.disabled = true;
       } else {
           statusDot.classList.remove('active');
           sendBtn.disabled = false;
           promptInput.disabled = false;
           promptInput.focus();
       }
   }
   
   // --- Activity Feed ---
   function addActivityCard(title, subtitle, isDone = false) {
       if (welcomeScreen) welcomeScreen.style.display = 'none';
   
       const id = 'card-' + Date.now();
       const card = document.createElement('div');
       card.className = 'activity-card';
       card.id = id;
   
       card.innerHTML = `
        <div class="activity-card-header" onclick="toggleDetails('${id}')" style="cursor: pointer;">
            <button class="accordion-toggle" title="View details">›</button>
            <div class="activity-icon">${title.charAt(0)}</div>
            <div class="activity-label">${title}</div>
            <div class="activity-status" id="${id}-status">
                ${isDone ? '<span class="check-icon">✓</span>' : '<div class="spinner"></div>'}
            </div>
        </div>
        <div class="activity-body" id="${id}-body">
            ${subtitle}
            <div class="activity-details-container" id="${id}-details-container">
                <ul id="${id}-details"></ul>
            </div>
        </div>
    `;
   
       activityFeed.appendChild(card);
       activityFeed.scrollTop = activityFeed.scrollHeight;
       return id;
   }
   
   function updateActivityCard(id, title, subtitle, isDone) {
       const card = document.getElementById(id);
       if (!card) return;
       
       const body = document.getElementById(`${id}-body`);
       const status = document.getElementById(`${id}-status`);
       
       // Update first text node
       body.childNodes[0].nodeValue = subtitle;
       
       if (isDone) {
           status.innerHTML = '<span class="check-icon">✓</span>';
       }
   }
   
   function appendCardDetail(id, detail) {
    const ul = document.getElementById(`${id}-details`);
    if (!ul) return;
    const li = document.createElement('li');
    li.textContent = detail;
    ul.appendChild(li);
}

function toggleDetails(id) {
    const btn = document.querySelector(`#${id} .accordion-toggle`);
    const container = document.getElementById(`${id}-details-container`);
    if (container) {
        if (btn) btn.classList.toggle('open');
        container.classList.toggle('open');
    }
}
   
   function appendCardProgress(id) {
       const body = document.getElementById(`${id}-body`);
       if (!body) return;
       const prog = document.createElement('div');
       prog.className = 'progress-container';
       prog.innerHTML = '<div class="progress-bar"><div class="progress-fill" id="'+id+'-progress"></div></div>';
       body.appendChild(prog);
       
       // Simulate progress
       setTimeout(() => {
           const bar = document.getElementById(`${id}-progress`);
           if(bar) bar.style.width = '70%';
       }, 500);
   }
   
   function updateCardProgress(id, pct) {
       const bar = document.getElementById(`${id}-progress`);
       if(bar) bar.style.width = pct + '%';
   }
   
   // --- Prompt Input ---
   function sendPrompt(text = null) {
       if (isProcessing) return;
       
       const prompt = text || promptInput.value.trim();
       if (!prompt) return;
   
       const is_update = Object.keys(files).length > 0;

    if (!is_update) {
        // Reset UI state for new project
        activityFeed.innerHTML = '';
        files = {};
        tabBar.innerHTML = `<button class="tab tab-preview" id="previewTab" onclick="switchToPreview()" style="display:none;">
                                <span>◉</span><span>Preview</span>
                            </button>`;
        document.querySelectorAll('.code-content').forEach(el => el.remove());
        emptyState.style.display = 'flex';
        previewFrame.classList.remove('active');
    } else {
        // For updates, just switch to preview so they see changes happen
        switchToPreview();
    }
    
    // Add user message
    const msg = document.createElement('div');
    msg.className = 'user-message';
    msg.textContent = prompt;
    activityFeed.appendChild(msg);

    ws.send(JSON.stringify({ prompt: prompt, is_update: is_update }));
    promptInput.value = '';
    promptInput.style.height = 'auto';
}
   
   function useSuggestion(btn) {
       sendPrompt(btn.textContent);
   }
   
   // Auto-resize textarea
   promptInput.addEventListener('input', function() {
       this.style.height = 'auto';
       this.style.height = (this.scrollHeight) + 'px';
   });
   
   promptInput.addEventListener('keydown', function(e) {
       if (e.key === 'Enter' && !e.shiftKey) {
           e.preventDefault();
           sendPrompt();
       }
   });
   
   // --- File Handling & Code Viewer ---
   function handleFileWritten(filepath, content) {
       files[filepath] = content;
       
       // Create tab if it doesn't exist
       let tabId = 'tab-' + filepath.replace(/[^a-zA-Z0-9]/g, '-');
       let tab = document.getElementById(tabId);
       
       if (!tab) {
           tab = document.createElement('button');
           tab.className = 'tab';
           tab.id = tabId;
           tab.onclick = () => switchToFile(filepath);
           
           const icon = document.createElement('span');
           icon.className = 'tab-icon';
           icon.textContent = getFileIcon(filepath);
           
           const name = document.createElement('span');
           name.textContent = filepath.split('/').pop();
           
           tab.appendChild(icon);
           tab.appendChild(name);
           
           // Insert before preview tab
           const previewBtn = document.getElementById('previewTab');
           tabBar.insertBefore(tab, previewBtn);
       }
       
       // Create content container
       let contentId = 'content-' + filepath.replace(/[^a-zA-Z0-9]/g, '-');
       let contentDiv = document.getElementById(contentId);
       
       if (!contentDiv) {
           contentDiv = document.createElement('div');
           contentDiv.className = 'code-content';
           contentDiv.id = contentId;
           codeViewer.appendChild(contentDiv);
       }
       
       contentDiv.innerHTML = renderCode(content, filepath);
       
       // Auto-switch to newly written file
       switchToFile(filepath);
   }
   
   function switchToFile(filepath) {
       activeTab = filepath;
       
       // Update tabs
       document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
       const tabId = 'tab-' + filepath.replace(/[^a-zA-Z0-9]/g, '-');
       const tab = document.getElementById(tabId);
       if (tab) tab.classList.add('active');
       
       // Update content
       document.querySelectorAll('.code-content').forEach(c => c.classList.remove('active'));
       previewFrame.classList.remove('active');
       
       const contentId = 'content-' + filepath.replace(/[^a-zA-Z0-9]/g, '-');
       const contentDiv = document.getElementById(contentId);
       if (contentDiv) contentDiv.classList.add('active');
   }
   
   function switchToPreview() {
       activeTab = 'preview';
       document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
       const pTab = document.getElementById('previewTab');
       if(pTab) pTab.classList.add('active');
       
       document.querySelectorAll('.code-content').forEach(c => c.classList.remove('active'));
       previewFrame.classList.add('active');
       
       // Check if index.html exists
       if (files['index.html']) {
           previewFrame.src = '/preview/index.html?t=' + Date.now();
       } else {
           // Find first html file
           const firstHtml = Object.keys(files).find(f => f.endsWith('.html'));
           if (firstHtml) {
               previewFrame.src = '/preview/' + firstHtml + '?t=' + Date.now();
           } else {
               // Fallback: show first file
               const firstFile = Object.keys(files)[0];
               if (firstFile) switchToFile(firstFile);
           }
       }
   }
   
   // --- Simple Syntax Highlighting ---
   function escapeHtml(str) {
       return str
           .replace(/&/g, "&amp;")
           .replace(/</g, "&lt;")
           .replace(/>/g, "&gt;")
           .replace(/"/g, "&quot;")
           .replace(/'/g, "&#039;");
   }
   
   function highlightHtml(code) {
       let esc = escapeHtml(code);
       esc = esc.replace(/(&lt;!--.*?--&gt;)/g, '<span class="cm">$1</span>');
       esc = esc.replace(/(&lt;\/?)([a-zA-Z0-9\-]+)/g, '$1<span class="tag">$2</span>');
       esc = esc.replace(/([a-zA-Z0-9\-]+)=(&quot;.*?&quot;)/g, '<span class="attr">$1</span>=<span class="str">$2</span>');
       return esc;
   }
   
   function highlightCss(code) {
       let esc = escapeHtml(code);
       esc = esc.replace(/(\/\*.*?\*\/)/gs, '<span class="cm">$1</span>');
       esc = esc.replace(/([a-zA-Z\-]+)\s*:/g, '<span class="attr">$1</span>:');
       return esc;
   }
   
   function highlightJs(code) {
       let esc = escapeHtml(code);
       // simple regex, order matters
       esc = esc.replace(/(\/\/.*$)/gm, '<span class="cm">$1</span>');
       esc = esc.replace(/(&quot;.*?&quot;|&#039;.*?&#039;|`.*?`)/gs, '<span class="str">$1</span>');
       esc = esc.replace(/\b(function|const|let|var|if|else|return|for|while|class|import|export|from|await|async|new|this)\b/g, '<span class="kw">$1</span>');
       esc = esc.replace(/\b([0-9]+)\b/g, '<span class="num">$1</span>');
       return esc;
   }
   
   function renderCode(code, filepath) {
       const ext = filepath.split('.').pop().toLowerCase();
       let hl = escapeHtml(code);
       
       if (ext === 'html' || ext === 'htm') hl = highlightHtml(code);
       else if (ext === 'css') hl = highlightCss(code);
       else if (ext === 'js' || ext === 'ts') hl = highlightJs(code);
       else if (ext === 'py') hl = highlightJs(code); // basic overlap
       
       const lines = hl.split('\n');
       const numbered = lines.map((l, i) => `<span class="line-numbers">${i+1}</span>${l}`).join('\n');
       
       return `<pre>${numbered}</pre>`;
   }
   
   function getFileIcon(filepath) {
       const ext = filepath.split('.').pop().toLowerCase();
       if (['html', 'htm'].includes(ext)) return '</>';
       if (['css'].includes(ext)) return '#';
       if (['js', 'ts', 'jsx', 'tsx'].includes(ext)) return '{}';
       if (['py'].includes(ext)) return '🐍';
       if (['json'].includes(ext)) return '[]';
       return '📄';
   }
   
   // Init
   connect();
