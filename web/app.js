const routes = {
  1: "M80 430 H180 V150 H760 L870 105",
  2: "M80 430 H180 V150",
  3: "M80 430 H180 H760 V300",
  4: "M80 430 H420",
};

const form = document.querySelector("#searchForm");
const plateInput = document.querySelector("#plateInput");
const plateValue = document.querySelector("#plateValue");
const cameraValue = document.querySelector("#cameraValue");
const timeValue = document.querySelector("#timeValue");
const resultState = document.querySelector("#resultState");
const routeLabel = document.querySelector("#routeLabel");
const routePath = document.querySelector("#routePath");
const plateCrop = document.querySelector("#plateCrop");
const cameraGrid = document.querySelector("#cameraGrid");
const eventList = document.querySelector("#eventList");
const channelCount = document.querySelector("#channelCount");
const recordCount = document.querySelector("#recordCount");
const clock = document.querySelector("#clock");

function updateClock() {
  const now = new Date();
  clock.textContent = now.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function setActiveCamera(cameraId) {
  document.querySelectorAll(".camera-point").forEach((point) => {
    point.classList.toggle("active", point.dataset.camera === String(cameraId));
  });
}

function clearRoute() {
  routePath.classList.add("hidden");
  routePath.setAttribute("d", "");
  setActiveCamera(null);
  routeLabel.textContent = "等待查询结果";
}

function showRoute(cameraId, plateNumber) {
  const d = routes[cameraId];
  if (!d) {
    clearRoute();
    return;
  }
  routePath.setAttribute("d", d);
  routePath.classList.remove("hidden");
  setActiveCamera(cameraId);
  routeLabel.textContent = `${plateNumber} 入口 -> C${cameraId} 号摄像头`;
}

function setCrop(src) {
  plateCrop.innerHTML = "";
  if (!src) {
    const span = document.createElement("span");
    span.textContent = "暂无截图";
    plateCrop.appendChild(span);
    return;
  }

  const img = document.createElement("img");
  img.alt = "车牌截图";
  img.src = src;
  plateCrop.appendChild(img);
}

async function searchPlate(plate) {
  const query = plate.trim().toUpperCase();
  if (!query) {
    plateValue.textContent = "请输入车牌号";
    cameraValue.textContent = "暂无结果";
    timeValue.textContent = "--";
    resultState.textContent = "等待查询";
    setCrop(null);
    clearRoute();
    return;
  }

  resultState.textContent = "查询中";
  const response = await fetch(`/api/search?plate=${encodeURIComponent(query)}`);
  const data = await response.json();

  if (data.ok && data.result) {
    const result = data.result;
    plateValue.textContent = result.plateNumber;
    cameraValue.textContent = `C${result.cameraId} 号摄像头`;
    timeValue.textContent = result.timestamp;
    resultState.textContent = "已定位";
    setCrop(result.cropImage);
    showRoute(result.cameraId, result.plateNumber);
    return;
  }

  plateValue.textContent = query;
  cameraValue.textContent = "未找到";
  timeValue.textContent = "--";
  resultState.textContent = data.suggestions?.length ? "找到相近记录" : "无记录";
  setCrop(null);
  clearRoute();

  if (data.suggestions?.length) {
    cameraValue.textContent = data.suggestions
      .slice(0, 3)
      .map((item) => item.plateNumber)
      .join(" / ");
  }
}

function renderCameras(images) {
  cameraGrid.innerHTML = "";
  const safeImages = images.length ? images : [];

  for (let index = 0; index < 4; index += 1) {
    const tile = document.createElement("article");
    tile.className = "camera-tile";

    if (safeImages[index % safeImages.length]) {
      const img = document.createElement("img");
      img.alt = `C${index + 1} 监控画面`;
      img.src = safeImages[index % safeImages.length];
      tile.appendChild(img);
    }

    const label = document.createElement("span");
    label.textContent = `C${index + 1}`;
    tile.appendChild(label);
    cameraGrid.appendChild(tile);
  }
}

function renderEvents(events) {
  eventList.innerHTML = "";
  if (!events.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "暂无通行日志";
    eventList.appendChild(empty);
    return;
  }

  events.forEach((event) => {
    const item = document.createElement("li");
    const time = document.createElement("time");
    const text = document.createElement("span");
    time.textContent = event.timestamp.split(" ").pop() || "--:--:--";
    text.textContent = `C${event.cameraId} 识别到 ${event.plateNumber}`;
    item.appendChild(time);
    item.appendChild(text);
    eventList.appendChild(item);
  });
}

async function loadEvents() {
  const response = await fetch("/api/events");
  const data = await response.json();
  renderCameras(data.cameraImages || []);
  renderEvents(data.events || []);
  channelCount.textContent = data.stats?.channels ?? 4;
  recordCount.textContent = data.stats?.records ?? 0;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  searchPlate(plateInput.value).catch(() => {
    resultState.textContent = "查询失败";
  });
});

updateClock();
setInterval(updateClock, 30_000);
loadEvents();
setInterval(loadEvents, 8_000);
