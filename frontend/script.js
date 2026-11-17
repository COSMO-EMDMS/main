// === 1. ГЛОБАЛЬНОЕ СОСТОЯНИЕ ДАННЫХ И СИНХРОНИЗАЦИЯ ===
let appState = {
  ra: "83.6331",
  dec: "+22.0145",
  regionName: "Target Region (RA: 83.6331)",
  epochs: [
    { date: "14 Oct 2026 · 03:42 UTC", short: "14 Oct", img: "https://images-assets.nasa.gov/image/PIA16874/PIA16874~medium.jpg" },
    { date: "16 Oct 2026 · 03:42 UTC", short: "16 Oct", img: "https://images-assets.nasa.gov/image/PIA04216/PIA04216~medium.jpg" },
    { date: "18 Oct 2026 · 03:42 UTC", short: "18 Oct", img: "https://images-assets.nasa.gov/image/PIA16874/PIA16874~medium.jpg" },
    { date: "20 Oct 2026 · 03:42 UTC", short: "20 Oct", img: "https://images-assets.nasa.gov/image/PIA15403/PIA15403~medium.jpg" }
  ],
  userMarkers: [] // Массив меток: { id, x, y, frameIndex, name }
};

const initialLoadingOverlay = document.getElementById("explorer-loading");
if (initialLoadingOverlay?.hidden) {
  initialLoadingOverlay.style.display = "none";
}

function applyObservationResult(result) {
  const epochsList = result?.epochs || result;
  if (!Array.isArray(epochsList) || epochsList.length === 0) {
    throw new Error("Backend returned no observation images");
  }

  const uniqueEpochs = [];
  const seenImages = new Set();
  for (const epoch of epochsList) {
    const imgUrl = typeof epoch === "string" ? epoch : (epoch.img || epoch.url);
    if (seenImages.has(imgUrl)) continue;
    seenImages.add(imgUrl);
    uniqueEpochs.push(epoch);
    if (uniqueEpochs.length === 12) break;
  }

  appState.epochs = uniqueEpochs.map((epoch, index) => {
    const imgUrl = typeof epoch === "string" ? epoch : (epoch.img || epoch.url);
    const name = typeof epoch === "object" && epoch.name
      ? epoch.name
      : `Epoch ${index + 1}`;
    return {
      date: name,
      short: name,
      img: imgUrl
    };
  });

  const firstImage = appState.epochs[0].img;
  const lastImage = appState.epochs[appState.epochs.length - 1].img;
  const cacheBust = `?t=${Date.now()}`;
  document.getElementById("explorer-img").src = firstImage + cacheBust;
  document.getElementById("explorer-epoch-date").innerText = appState.epochs[0].date;
  document.getElementById("lab-img-a").src = firstImage + cacheBust;
  document.getElementById("lab-img-b").src = lastImage + cacheBust;
  document.getElementById("tm-img").src = firstImage + cacheBust;
  const loadingOverlay = document.getElementById("explorer-loading");
  loadingOverlay.hidden = true;
  loadingOverlay.style.display = "none";

  const observationsTable = document.querySelector("#display-coord")
    ?.closest(".panel")
    ?.querySelector(".meta-table");
  if (observationsTable) {
    const observationRow = observationsTable.rows[2];
    if (observationRow) {
      observationRow.cells[1].innerText =
        `${appState.epochs.length} ${appState.epochs.length === 1 ? "epoch" : "epochs"} loaded`;
    }
  }

  const dots = document.getElementById("timeline-dots");
  if (dots) {
    dots.innerHTML = appState.epochs.map((epoch, index) =>
      `<div class="step-dot${index === 0 ? " active" : ""}" onclick="selectEpoch(${index})"><div class="dot"></div><span id="label-dot-${index}">${epoch.short}</span></div>`
    ).join("");
  }

  const timelineCount = document.querySelector(".timeline-box span");
  if (timelineCount) {
    timelineCount.innerText =
      `${appState.epochs.length} epochs · Backend synced`;
  }

  if (typeof selectEpoch === "function") selectEpoch(0);
}

// === 2. НАВИГАЦИЯ МЕЖДУ ЭКРАНАМИ ===
function switchPage(pageId) {
  document.querySelectorAll('.page-section').forEach(sec => sec.classList.remove('active-section'));
  document.getElementById(pageId).classList.add('active-section');

  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.remove('active');
    if (link.dataset.target === pageId) link.classList.add('active');
  });

  stopTimeMachinePlay();
  stopBlinking();
  if (pageId === 'details') {
    updateDetailsMetrics();
  }
}

document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    switchPage(link.dataset.target);
  });
});

document.addEventListener('click', (event) => {
  const target = event.target.closest('[data-target]');
  if (!target || target.classList.contains('nav-link')) return;
  if (target.dataset.target && document.getElementById(target.dataset.target)) {
    switchPage(target.dataset.target);
  }
});

function initializeImagePanning() {
  setupImagePanning(
    document.getElementById('explorer-img'),
    'explorer',
    () => currentZoom
  );
  setupImagePanning(
    document.getElementById('tm-img'),
    'tm',
    () => 1.15
  );
  setupImagePanning(
    document.getElementById('lab-img-a'),
    'lab-a',
    () => zoomLabA
  );
  setupImagePanning(
    document.getElementById('lab-img-b'),
    'lab-b',
    () => zoomLabB
  );
  setupImagePanning(
    document.getElementById('details-preview-img'),
    'details',
    () => 1.15
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeImagePanning);
} else {
  initializeImagePanning();
}

// === 3. SKY EXPLORER (ПОИСК ПО КООРДИНАТАМ И ЗУМ) ===
let currentZoom = 1;
let gridVisible = true;
const panOffsets = new Map();

function applyImageTransform(image, zoom, panKey) {
  if (!image) return;
  const pan = panOffsets.get(panKey) || { x: 0, y: 0 };
  image.style.transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`;
  image.style.transformOrigin = 'center';
}

function clampPan(panKey, zoom, viewport) {
  const pan = panOffsets.get(panKey) || { x: 0, y: 0 };
  if (!viewport || zoom <= 1) {
    panOffsets.set(panKey, { x: 0, y: 0 });
    return;
  }
  const rect = viewport.getBoundingClientRect();
  const maxX = rect.width * (zoom - 1) / 2;
  const maxY = rect.height * (zoom - 1) / 2;
  panOffsets.set(panKey, {
    x: Math.max(-maxX, Math.min(maxX, pan.x)),
    y: Math.max(-maxY, Math.min(maxY, pan.y))
  });
}

function setupImagePanning(image, panKey, getZoom) {
  if (!image || image.dataset.panEnabled === 'true') return;
  image.dataset.panEnabled = 'true';
  image.draggable = false;

  let dragging = false;
  let moved = false;
  let startX = 0;
  let startY = 0;
  let startPan = { x: 0, y: 0 };

  image.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    dragging = true;
    moved = false;
    startX = event.clientX;
    startY = event.clientY;
    startPan = panOffsets.get(panKey) || { x: 0, y: 0 };
    if (typeof image.setPointerCapture === 'function') {
      try {
        image.setPointerCapture(event.pointerId);
      } catch (_) {
        // Synthetic or canceled pointers may not support capture.
      }
    }
    image.classList.add('image-panning');
  });

  image.addEventListener('pointermove', (event) => {
    if (!dragging) return;
    const dx = event.clientX - startX;
    const dy = event.clientY - startY;
    if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
    if (moved) {
      const viewport = image.closest('.sky-viewport, .frame-card');
      panOffsets.set(panKey, { x: startPan.x + dx, y: startPan.y + dy });
      clampPan(panKey, getZoom(), viewport);
      applyImageTransform(image, getZoom(), panKey);
    }
  });

  function finishDrag(event) {
    if (!dragging) return;
    dragging = false;
    image.classList.remove('image-panning');
    if (image.releasePointerCapture && image.hasPointerCapture(event.pointerId)) {
      image.releasePointerCapture(event.pointerId);
    }
    if (moved) {
      const viewport = image.closest('.frame-card');
      if (viewport) viewport.dataset.dragMoved = 'true';
    }
  }

  image.addEventListener('pointerup', finishDrag);
  image.addEventListener('pointercancel', finishDrag);
  image.addEventListener('lostpointercapture', () => {
    dragging = false;
    image.classList.remove('image-panning');
  });
}

async function updateCoordinates() {
  const raVal = parseFloat(document.getElementById('input-ra').value.trim()) || 83.6331;
  const decVal = parseFloat(document.getElementById('input-dec').value.trim()) || 22.0145;
  
  appState.ra = raVal;
  appState.dec = decVal;
  appState.regionName = `Field RA: ${raVal} / Dec: ${decVal}`;

  // Обновляем текст в интерфейсе
  document.getElementById('display-coord').innerText = `${raVal}° / ${decVal}°`;
  document.getElementById('display-region-name').innerText = appState.regionName;
  document.getElementById('field-banner').innerText = `FIELD ${raVal} ${decVal}`;
  
  document.getElementById('tm-region-title').innerText = appState.regionName;
  document.getElementById('tm-coords-subtitle').innerText = `RA ${raVal}° / Dec ${decVal}°`;
  document.getElementById('lab-region-label').innerText = appState.regionName;
  document.getElementById('info-field-name').innerText = appState.regionName;

  const statusBox = document.getElementById('job-status');
  const statusTitle = document.getElementById('job-status-title');
  const statusMessage = document.getElementById('job-status-message');
  const statusPercent = document.getElementById('job-status-percent');
  const statusEta = document.getElementById('job-status-eta');
  const progress = document.getElementById('job-progress');
  const loadingPlaceholder = document.getElementById('explorer-loading');
  const queryButton = document.querySelector('button[onclick="updateCoordinates()"]');
  let resultApplied = false;

  function applyAndFinalize(statusData) {
    if (statusData?.status === 'complete' && statusData.result) {
      applyObservationResult(statusData.result);
      statusTitle.innerText = 'Observation ready';
      statusMessage.innerText = 'Ready';
      statusPercent.innerText = '100%';
      progress.style.width = '100%';
      resultApplied = true;
      return true;
    }
    return false;
  }

  function formatDuration(seconds) {
    if (seconds == null) return '';
    if (seconds < 60) return `${Math.ceil(seconds)} sec left`;
    return `${Math.ceil(seconds / 60)} min left`;
  }

  function renderJobStatus(data) {
    const labels = {
      queued: 'Queued',
      querying: 'Checking archive',
      downloading: 'Downloading observations',
      processing: 'Generating previews',
      complete: 'Observation ready',
      failed: 'Observation failed'
    };
    statusTitle.innerText = labels[data.status] || 'Working';
    statusMessage.innerText = data.status === 'complete'
      ? 'Ready'
      : (data.message || 'Working...');
    statusPercent.innerText = data.progress_percent == null
      ? `${Math.round(data.elapsed_seconds || 0)}s elapsed`
      : `${Math.round(data.progress_percent)}%`;
    progress.style.width = data.progress_percent == null
      ? '25%'
      : `${Math.max(0, Math.min(100, data.progress_percent))}%`;
    statusEta.innerText = formatDuration(data.estimated_seconds_remaining)
      || (data.status === 'querying' ? 'IRSA response pending' : '');
    statusBox.hidden = false;
    loadingPlaceholder.hidden = data.status === 'complete' || data.status === 'failed';
    if (loadingPlaceholder.hidden) {
      loadingPlaceholder.style.display = 'none';
    } else {
      loadingPlaceholder.style.display = 'flex';
    }
  }

  try {
    statusBox.hidden = false;
    loadingPlaceholder.hidden = false;
    statusTitle.innerText = 'Starting observation';
    statusMessage.innerText = 'Connecting to the SPHEREx archive...';
    progress.style.width = '8%';
    if (queryButton) queryButton.disabled = true;
    console.log("Отправляем запрос на бэкенд:", { ra: raVal, dec: decVal });
    
    // 1. Отправляем POST-запрос на создание задачи
    const response = await fetch('/api/cutouts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ra: raVal,
        dec: decVal,
        cutout_size: "200px"
      })
    });
    
    // Если сервер занят (503), обрабатываем Retry-After
    if (response.status === 503) {
      const retryAfter = response.headers.get("Retry-After") || 30;
      console.log(`Сервер занят, пробуем через ${retryAfter} секунд...`);
      alert(`Сервер перегружен. Повторите попытку через ${retryAfter} сек.`);
      return;
    }

    if (!response.ok) {
      throw new Error(`Ошибка HTTP: ${response.status}`);
    }
    
    let job = await response.json();
    console.log("Получили задачу:", job);

    let statusUrl = job.poll_url;
    let jobStatus = job.status;
    renderJobStatus(job);

    if (jobStatus === 'complete') {
      const cachedStatus = await fetch(statusUrl, {
        headers: { 'Cache-Control': 'no-store' }
      });
      if (cachedStatus.ok) {
        const statusData = await cachedStatus.json();
        if (!statusData.result) {
          throw new Error("Cache entry is missing observation results");
        }
        applyAndFinalize(statusData);
        if (!resultApplied) {
          throw new Error("Could not apply cached observation result");
        }
      } else {
        throw new Error(`Could not read observation result: HTTP ${cachedStatus.status}`);
      }
    }

    // 2. Делаем Polling (опрос статуса каждые 1.5 секунды, как говорил друг)
    while (jobStatus !== 'complete' && jobStatus !== 'failed') {
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      const pollResponse = await fetch(statusUrl, {
        headers: {
          'Cache-Control': 'no-store'
        }
      });
      
      if (!pollResponse.ok) continue;
      
      const statusData = await pollResponse.json();
      jobStatus = statusData.status;
      renderJobStatus(statusData);
      console.log("Текущий статус задачи:", jobStatus);

      if (jobStatus === 'complete' && statusData.result) {
        console.log("Картинки успешно получены!", statusData.result);
        applyAndFinalize(statusData);
        break;
      }
      
      if (jobStatus === 'failed') {
        throw new Error(statusData.error || statusData.message || "Backend job failed");
      }
    }

  } catch (error) {
    console.error("Ошибка при запросе к бэкенду:", error);
    statusTitle.innerText = 'Could not load observation';
    statusMessage.innerText = error.message;
    loadingPlaceholder.hidden = true;
  } finally {
    if (queryButton) queryButton.disabled = false;
  }
}

function zoomExplorer(delta) {
  currentZoom = Math.min(Math.max(currentZoom + delta, 1), 2.5);
  const image = document.getElementById('explorer-img');
  clampPan('explorer', currentZoom, image.closest('.sky-viewport'));
  applyImageTransform(image, currentZoom, 'explorer');
}

function resetZoom() {
  currentZoom = 1;
  panOffsets.set('explorer', { x: 0, y: 0 });
  applyImageTransform(document.getElementById('explorer-img'), currentZoom, 'explorer');
}

function toggleGrid() {
  gridVisible = !gridVisible;
  document.getElementById('coord-grid').style.display = gridVisible ? 'block' : 'none';
  document.getElementById('btn-toggle-grid').innerText = `Grid: ${gridVisible ? 'On' : 'Off'}`;
}

// === 4. TIME MACHINE (ТАЙМЛАЙН И ДАТЫ) ===
let currentEpoch = 0;
let tmTimer = null;

function selectEpoch(index) {
  if (!appState.epochs[index]) return;
  currentEpoch = index;
  document.getElementById('tm-epoch-tag').innerText =
    `OBSERVATION ${String(index + 1).padStart(2, '0')} / ${String(appState.epochs.length).padStart(2, '0')}`;
  document.getElementById('tm-date-input').value = appState.epochs[index].date;
  document.getElementById('tm-img').src = appState.epochs[index].img;
  applyImageTransform(document.getElementById('tm-img'), 1.15, 'tm');

  document.querySelectorAll('#timeline-dots .step-dot').forEach((dot, i) => {
    dot.classList.toggle('active', i === index);
  });

  document.querySelectorAll('#obs-sidebar-list .obs-item').forEach((item, i) => {
    item.classList.toggle('active', i === index);
  });
}

function updateCustomDate(index, val) {
  appState.epochs[index].date = val;
  appState.epochs[index].short = val.split('·')[0].trim();
  
  const dotLabel = document.getElementById(`label-dot-${index}`);
  if (dotLabel) dotLabel.innerText = appState.epochs[index].short;

  const sideLabel = document.getElementById(`sidebar-label-${index}`);
  if (sideLabel) {
    sideLabel.innerHTML = `0${index + 1} &nbsp; ${val}`;
  }

  const dDate = document.getElementById(`d-date-${index}`);
  if (dDate) dDate.innerText = appState.epochs[index].short;

  if (index === 0) document.getElementById('lab-date-a').value = appState.epochs[0].short;
  if (index === 3) document.getElementById('lab-date-b').value = appState.epochs[3].short;
}

function stepEpoch(dir) {
  let next = currentEpoch + dir;
  if (next >= appState.epochs.length) next = 0;
  if (next < 0) next = appState.epochs.length - 1;
  selectEpoch(next);
}

function toggleTimeMachinePlay() {
  const btn = document.getElementById('tm-play-btn');
  if (tmTimer) {
    stopTimeMachinePlay();
  } else {
    const speed = parseInt(document.getElementById('tm-speed').value);
    btn.innerHTML = '&#10074;&#10074; Pause';
    tmTimer = setInterval(() => {
      const loop = document.getElementById('tm-loop').checked;
      if (!loop && currentEpoch === appState.epochs.length - 1) {
        stopTimeMachinePlay();
        return;
      }
      stepEpoch(1);
    }, speed);
  }
}

function stopTimeMachinePlay() {
  if (tmTimer) {
    clearInterval(tmTimer);
    tmTimer = null;
    document.getElementById('tm-play-btn').innerHTML = '&#9654; Play';
  }
}

// === 5. DETECTION LAB, МАРКЕРЫ И РАЗДЕЛЬНЫЙ ЗУМ КАДРОВ ===
let zoomLabA = 1;
let zoomLabB = 1;
let blinkTimer = null;
let showFrameA = true;
let markersVisible = true;

// Раздельный зум для фото А и Б в Detection Lab
function zoomLab(frame, delta) {
  if (frame === 'a') {
    zoomLabA = Math.min(Math.max(zoomLabA + delta, 1), 2.5);
    const image = document.getElementById('lab-img-a');
    clampPan('lab-a', zoomLabA, image.closest('.frame-card'));
    applyImageTransform(image, zoomLabA, 'lab-a');
  } else {
    zoomLabB = Math.min(Math.max(zoomLabB + delta, 1), 2.5);
    const image = document.getElementById('lab-img-b');
    clampPan('lab-b', zoomLabB, image.closest('.frame-card'));
    applyImageTransform(image, zoomLabB, 'lab-b');
  }
}

function resetLabZoom(frame) {
  if (frame === 'a') {
    zoomLabA = 1;
    panOffsets.set('lab-a', { x: 0, y: 0 });
    applyImageTransform(document.getElementById('lab-img-a'), zoomLabA, 'lab-a');
  } else {
    zoomLabB = 1;
    panOffsets.set('lab-b', { x: 0, y: 0 });
    applyImageTransform(document.getElementById('lab-img-b'), zoomLabB, 'lab-b');
  }
}

// Клик по картинкам в лаборатории для расстановки меток
function handleImageClick(event, frameIndex) {
  if (event.currentTarget.dataset.dragMoved === 'true') {
    event.currentTarget.dataset.dragMoved = 'false';
    return;
  }
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  
  const xPercent = (x / rect.width) * 100;
  const yPercent = (y / rect.height) * 100;

  const isPrimary = appState.userMarkers.length === 0;
  const markerNum = appState.userMarkers.length + 1;
  const defaultName = isPrimary ? `Primary Target ${markerNum}` : `Secondary Candidate ${markerNum}`;
  
  const newMarker = {
    id: `OBJ-${markerNum}`,
    name: defaultName,
    x: xPercent,
    y: yPercent,
    frame: frameIndex,
    isPrimary: isPrimary
  };

  appState.userMarkers.push(newMarker);
  renderUserMarkers();
  updateCandidatesSidebar();
}

// Функция переименования отметки по запросу
function renameMarker(index) {
  const currentName = appState.userMarkers[index].name;
  const newName = prompt("Введите новое название для этой отметки:", currentName);
  if (newName !== null && newName.trim() !== "") {
    appState.userMarkers[index].name = newName.trim();
    renderUserMarkers();
    updateCandidatesSidebar();
  }
}

function renderUserMarkers() {
  const containerA = document.getElementById('markers-container-a');
  const containerB = document.getElementById('markers-container-b');
  containerA.innerHTML = '';
  containerB.innerHTML = '';

  if (!markersVisible) return;

  appState.userMarkers.forEach((m, idx) => {
    const div = document.createElement('div');
    div.className = m.isPrimary ? 'user-marker' : 'user-marker secondary';
    div.style.left = `${m.x}%`;
    div.style.top = `${m.y}%`;
    div.innerHTML = `<span>${m.name}</span>`;

    if (m.frame === 0) {
      containerA.appendChild(div);
    } else {
      containerB.appendChild(div);
    }
  });
}

function toggleUserMarkersVisibility() {
  markersVisible = document.getElementById('toggle-markers').checked;
  document.getElementById('markers-container-a').style.display = markersVisible ? 'block' : 'none';
  document.getElementById('markers-container-b').style.display = markersVisible ? 'block' : 'none';
}

function clearAllMarkers() {
  appState.userMarkers = [];
  renderUserMarkers();
  updateCandidatesSidebar();
}

function updateCandidatesSidebar() {
  const listContainer = document.getElementById('candidates-sidebar-list');
  const countSubtitle = document.getElementById('candidates-count-subtitle');
  const summaryText = document.getElementById('measurement-summary-text');

  countSubtitle.innerText = `${appState.userMarkers.length} objects / markers placed`;

  if (appState.userMarkers.length === 0) {
    listContainer.innerHTML = `<div style="font-size: 12px; color: #64748b; text-align: center; padding: 20px 0;">Click on images to place tracking markers.</div>`;
    summaryText.innerText = `Place a primary marker to start tracking shifts.`;
    return;
  }

  let html = '';
  let primary = appState.userMarkers.find(m => m.isPrimary) || appState.userMarkers[0];
  let latest = appState.userMarkers[appState.userMarkers.length - 1];

  let dx = (latest.x - primary.x) * 25;
  let dy = (latest.y - primary.y) * 25;
  let pixelShift = Math.sqrt(dx*dx + dy*dy).toFixed(1);

  appState.userMarkers.forEach((m, idx) => {
    html += `
      <div class="candidate-box" style="margin-bottom:8px;">
        <div style="display: flex; justify-content: space-between; align-items:center;">
          <strong style="color: ${m.isPrimary ? '#56b4f9' : '#eab308'}; font-size: 13px;">${m.name}</strong>
          <div style="display: flex; gap: 6px;">
            <button onclick="renameMarker(${idx})" style="background:none; border:none; color:#38bdf8; cursor:pointer; font-size:11px;">Rename</button>
            <button onclick="removeMarker(${idx})" style="background:none; border:none; color:#ef4444; cursor:pointer; font-size:11px;">Remove</button>
          </div>
        </div>
        <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">X: ${m.x.toFixed(1)}%, Y: ${m.y.toFixed(1)}%</div>
      </div>
    `;
  });

  listContainer.innerHTML = html;
  summaryText.innerHTML = `Displacement vector from Primary to latest marker: <b>${pixelShift}" arcsec</b> across frames.`;
}

function removeMarker(index) {
  appState.userMarkers.splice(index, 1);
  renderUserMarkers();
  updateCandidatesSidebar();
}

function setLabView(mode) {
  stopBlinking();
  const grid = document.getElementById('lab-compare-grid');
  const frameA = document.getElementById('frame-a');
  const frameB = document.getElementById('frame-b');
  const btnSide = document.getElementById('btn-side-mode');
  const btnBlink = document.getElementById('btn-blink-mode');

  if (mode === 'side') {
    grid.classList.remove('blink-single');
    frameA.style.display = 'block';
    frameB.style.display = 'block';
    btnSide.className = 'btn-accent';
    btnBlink.className = 'btn-outline';
  } else {
    grid.classList.add('blink-single');
    frameA.style.display = 'block';
    frameB.style.display = 'none';
    btnBlink.className = 'btn-accent';
    btnSide.className = 'btn-outline';
  }
}

function toggleBlinking() {
  const btn = document.getElementById('btn-start-blink');
  if (blinkTimer) {
    stopBlinking();
  } else {
    setLabView('blink');
    btn.innerHTML = '&#10074;&#10074; Stop blinking';
    const interval = parseInt(document.getElementById('blink-interval').value);
    const frameA = document.getElementById('frame-a');
    const frameB = document.getElementById('frame-b');

    blinkTimer = setInterval(() => {
      showFrameA = !showFrameA;
      frameA.style.display = showFrameA ? 'block' : 'none';
      frameB.style.display = showFrameA ? 'none' : 'block';
    }, interval);
  }
}

function stopBlinking() {
  if (blinkTimer) {
    clearInterval(blinkTimer);
    blinkTimer = null;
    document.getElementById('btn-start-blink').innerHTML = '&#9654; Start blinking';
  }
}

function syncLabDates() {
  const dateA = document.getElementById('lab-date-a').value;
  const dateB = document.getElementById('lab-date-b').value;
  if (appState.epochs[0]) appState.epochs[0].short = dateA;
  if (appState.epochs[3]) appState.epochs[3].short = dateB;
}

// === 6. SYNCHRONIZATION FOR OBJECT DETAILS (ЭКРАН 5) ===
function updateDetailsMetrics() {
  document.getElementById('info-markers-count').innerText = appState.userMarkers.length;
  
  if (appState.userMarkers.length > 0) {
    let primary = appState.userMarkers[0];
    let latest = appState.userMarkers[appState.userMarkers.length - 1];
    let dx = (latest.x - primary.x) * 25;
    let dy = (latest.y - primary.y) * 25;
    let totalDisp = Math.sqrt(dx*dx + dy*dy).toFixed(2);

    document.getElementById('metric-displacement').innerText = `${totalDisp}"`;
    document.getElementById('metric-motion').innerText = `${(totalDisp / 6).toFixed(2)}" / day`;
    
    document.getElementById('d-offset-0').innerText = `0.0"`;
    document.getElementById('d-offset-3').innerText = `${totalDisp}"`;
    document.getElementById('h-off-3').innerText = `${totalDisp}"`;
  } else {
    document.getElementById('metric-displacement').innerText = `0.0"`;
    document.getElementById('metric-motion').innerText = `0.00" / day`;
  }
}