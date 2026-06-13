const routeNodes = {
  northGate: { x: 600, y: 38, name: "北入口" },
  northRamp: { x: 600, y: 120, name: "北侧坡道" },
  westGate: { x: 52, y: 360, name: "西入口" },
  westRamp: { x: 130, y: 360, name: "收费岛" },
  southGate: { x: 600, y: 682, name: "南入口" },
  southRamp: { x: 600, y: 610, name: "商业入口" },
  eastGate: { x: 1148, y: 345, name: "东入口" },
  eastRamp: { x: 1060, y: 345, name: "快停入口" },
  top1: { x: 230, y: 150 },
  top2: { x: 430, y: 150 },
  top3: { x: 600, y: 150, name: "北侧支路" },
  top4: { x: 780, y: 150 },
  top5: { x: 980, y: 150 },
  mid1: { x: 230, y: 300 },
  mid2: { x: 430, y: 300 },
  mid3: { x: 600, y: 300, name: "核心设备区" },
  mid4: { x: 780, y: 300 },
  mid5: { x: 980, y: 300 },
  core1: { x: 230, y: 360 },
  core2: { x: 430, y: 360 },
  core3: { x: 600, y: 360, name: "中央主通道" },
  core4: { x: 780, y: 360 },
  core5: { x: 980, y: 360 },
  low1: { x: 230, y: 470 },
  low2: { x: 430, y: 470 },
  low3: { x: 600, y: 470, name: "南侧支路" },
  low4: { x: 780, y: 470 },
  low5: { x: 980, y: 470 },
  bot1: { x: 230, y: 610 },
  bot2: { x: 430, y: 610 },
  bot3: { x: 600, y: 610, name: "商业区环道" },
  bot4: { x: 780, y: 610 },
  bot5: { x: 980, y: 610 },
  cam1: { x: 1010, y: 110, name: "C1" },
  cam2: { x: 185, y: 150, name: "C2" },
  cam3: { x: 815, y: 470, name: "C3" },
  cam4: { x: 400, y: 610, name: "C4" },
  cam5: { x: 600, y: 300, name: "C5" },
  cam6: { x: 1035, y: 470, name: "C6" },
  cam7: { x: 745, y: 610, name: "C7" },
  cam8: { x: 130, y: 360, name: "C8" },
};

const entrances = {
  north: { label: "北入口", node: "northGate" },
  west: { label: "西入口", node: "westGate" },
  south: { label: "南入口", node: "southGate" },
  east: { label: "东入口", node: "eastGate" },
};

const cameras = {
  1: { label: "C1", node: "cam1", area: "B 区东翼出口" },
  2: { label: "C2", node: "cam2", area: "A 区北侧支路" },
  3: { label: "C3", node: "cam3", area: "D 区中段环道" },
  4: { label: "C4", node: "cam4", area: "C 区南侧车位" },
  5: { label: "C5", node: "cam5", area: "核心设备区" },
  6: { label: "C6", node: "cam6", area: "D 区东侧车位" },
  7: { label: "C7", node: "cam7", area: "D 区商业入口" },
  8: { label: "C8", node: "cam8", area: "西侧收费岛" },
};

const edgePairs = [];

function connectSeries(nodeIds) {
  for (let index = 0; index < nodeIds.length - 1; index += 1) {
    edgePairs.push([nodeIds[index], nodeIds[index + 1]]);
  }
}

[
  ["top1", "top2", "top3", "top4", "top5"],
  ["mid1", "mid2", "mid3", "mid4", "mid5"],
  ["core1", "core2", "core3", "core4", "core5"],
  ["low1", "low2", "low3", "low4", "low5"],
  ["bot1", "bot2", "bot3", "bot4", "bot5"],
  ["top1", "mid1", "core1", "low1", "bot1"],
  ["top2", "mid2", "core2", "low2", "bot2"],
  ["northRamp", "top3", "mid3", "core3", "low3", "bot3", "southRamp"],
  ["top4", "mid4", "core4", "low4", "bot4"],
  ["top5", "mid5", "core5", "low5", "bot5"],
].forEach(connectSeries);

edgePairs.push(
  ["northGate", "northRamp"],
  ["westGate", "westRamp"],
  ["westRamp", "core1"],
  ["southRamp", "southGate"],
  ["eastGate", "eastRamp"],
  ["eastRamp", "core5"],
  ["top5", "cam1"],
  ["top1", "cam2"],
  ["low4", "cam3"],
  ["bot2", "cam4"],
  ["mid3", "cam5"],
  ["low5", "cam6"],
  ["bot4", "cam7"],
  ["westRamp", "cam8"]
);

const form = document.querySelector("#searchForm");
const plateInput = document.querySelector("#plateInput");
const plateValue = document.querySelector("#plateValue");
const cameraValue = document.querySelector("#cameraValue");
const timeValue = document.querySelector("#timeValue");
const resultState = document.querySelector("#resultState");
const routeLabel = document.querySelector("#routeLabel");
const routeMeta = document.querySelector("#routeMeta");
const routePath = document.querySelector("#routePath");
const routeHalo = document.querySelector("#routeHalo");
const plateCrop = document.querySelector("#plateCrop");
const cameraGrid = document.querySelector("#cameraGrid");
const eventList = document.querySelector("#eventList");
const channelCount = document.querySelector("#channelCount");
const recordCount = document.querySelector("#recordCount");
const clock = document.querySelector("#clock");
const entryOptions = Array.from(document.querySelectorAll(".entry-option"));
const entryPoints = Array.from(document.querySelectorAll(".entry-point"));

const routeGraph = createGraph();
let selectedEntry = "north";
let activeCameraId = null;
let activePlateNumber = "";

function createGraph() {
  const graph = {};
  Object.keys(routeNodes).forEach((nodeId) => {
    graph[nodeId] = [];
  });

  edgePairs.forEach(([from, to]) => {
    const start = routeNodes[from];
    const end = routeNodes[to];
    if (!start || !end) {
      return;
    }

    const weight = Math.hypot(start.x - end.x, start.y - end.y);
    graph[from].push({ id: to, weight });
    graph[to].push({ id: from, weight });
  });

  return graph;
}

function shortestPath(startId, endId) {
  const distances = {};
  const previous = {};
  const unvisited = new Set(Object.keys(routeNodes));

  Object.keys(routeNodes).forEach((nodeId) => {
    distances[nodeId] = Infinity;
  });
  distances[startId] = 0;

  while (unvisited.size) {
    let current = null;
    unvisited.forEach((nodeId) => {
      if (current === null || distances[nodeId] < distances[current]) {
        current = nodeId;
      }
    });

    if (current === null || distances[current] === Infinity) {
      break;
    }

    if (current === endId) {
      break;
    }

    unvisited.delete(current);

    routeGraph[current].forEach((edge) => {
      if (!unvisited.has(edge.id)) {
        return;
      }

      const nextDistance = distances[current] + edge.weight;
      if (nextDistance < distances[edge.id]) {
        distances[edge.id] = nextDistance;
        previous[edge.id] = current;
      }
    });
  }

  if (!Number.isFinite(distances[endId])) {
    return [];
  }

  const path = [];
  let current = endId;
  while (current) {
    path.unshift(current);
    current = previous[current];
  }
  return path;
}

function pathToSvg(path) {
  return path
    .map((nodeId, index) => {
      const node = routeNodes[nodeId];
      const command = index === 0 ? "M" : "L";
      return `${command}${node.x} ${node.y}`;
    })
    .join(" ");
}

function routeLength(path) {
  return path.slice(1).reduce((total, nodeId, index) => {
    const previousNode = routeNodes[path[index]];
    const currentNode = routeNodes[nodeId];
    return total + Math.hypot(previousNode.x - currentNode.x, previousNode.y - currentNode.y);
  }, 0);
}

function routeVia(path) {
  const candidates = [
    ["core3", "中央主通道"],
    ["top3", "北侧支路"],
    ["low3", "南侧支路"],
    ["bot3", "商业区环道"],
    ["westRamp", "西侧收费岛"],
    ["eastRamp", "东侧快停入口"],
  ];
  const match = candidates.find(([nodeId]) => path.includes(nodeId));
  return match ? match[1] : "地库环线";
}

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

function setActiveEntry(entryId) {
  entryOptions.forEach((button) => {
    const isActive = button.dataset.entry === entryId;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });

  entryPoints.forEach((point) => {
    const isActive = point.dataset.entry === entryId;
    point.classList.toggle("active", isActive);
    point.setAttribute("aria-pressed", String(isActive));
  });
}

function hideRoute() {
  routePath.classList.add("hidden");
  routeHalo.classList.add("hidden");
  routePath.setAttribute("d", "");
  routeHalo.setAttribute("d", "");
}

function clearRoute() {
  activeCameraId = null;
  activePlateNumber = "";
  hideRoute();
  setActiveCamera(null);
  routeLabel.textContent = "等待查询结果";
  routeMeta.textContent = `${entrances[selectedEntry].label} 已选，查询车辆后生成推荐路线`;
}

function renderActiveRoute() {
  const entry = entrances[selectedEntry];
  const camera = cameras[activeCameraId];
  if (!entry || !camera) {
    hideRoute();
    return;
  }

  const path = shortestPath(entry.node, camera.node);
  if (!path.length) {
    hideRoute();
    routeLabel.textContent = "无法生成路线";
    routeMeta.textContent = "当前入口与目标点位之间缺少可通行拓扑";
    return;
  }

  const d = pathToSvg(path);
  const distance = Math.max(20, Math.round(routeLength(path) / 8));
  routeHalo.setAttribute("d", d);
  routePath.setAttribute("d", d);
  routeHalo.classList.remove("hidden");
  routePath.classList.remove("hidden");
  setActiveCamera(activeCameraId);
  routeLabel.textContent = `${activePlateNumber} ${entry.label} -> ${camera.label}`;
  routeMeta.textContent = `推荐路线：${entry.label} -> ${routeVia(path)} -> ${camera.label}，约 ${distance} 米，目标位于 ${camera.area}`;
}

function showRoute(cameraId, plateNumber) {
  activeCameraId = Number(cameraId);
  activePlateNumber = plateNumber;
  renderActiveRoute();
}

function chooseEntry(entryId) {
  if (!entrances[entryId]) {
    return;
  }

  selectedEntry = entryId;
  setActiveEntry(entryId);
  if (activeCameraId) {
    renderActiveRoute();
    return;
  }

  routeMeta.textContent = `${entrances[selectedEntry].label} 已选，查询车辆后生成推荐路线`;
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
    const camera = cameras[result.cameraId];
    plateValue.textContent = result.plateNumber;
    cameraValue.textContent = camera ? `${camera.label} ${camera.area}` : `C${result.cameraId} 号摄像头`;
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

    if (safeImages.length && safeImages[index % safeImages.length]) {
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

entryOptions.forEach((button) => {
  button.addEventListener("click", () => chooseEntry(button.dataset.entry));
});

entryPoints.forEach((point) => {
  point.addEventListener("click", () => chooseEntry(point.dataset.entry));
  point.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      chooseEntry(point.dataset.entry);
    }
  });
});

setActiveEntry(selectedEntry);
updateClock();
setInterval(updateClock, 30_000);
loadEvents();
setInterval(loadEvents, 8_000);
