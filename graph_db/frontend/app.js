const queryInput = document.getElementById('queryInput');
const searchBtn = document.getElementById('searchBtn');
const answerEl = document.getElementById('answer');
const contextEl = document.getElementById('context');
const sourcesEl = document.getElementById('sources');
const statusEl = document.getElementById('status');
const sourceCountEl = document.getElementById('sourceCount');
const graphMetaEl = document.getElementById('graphMeta');
const graphContainer = document.getElementById('graph');

const groupColors = {
  Document: '#38bdf8',
  Complaint: '#f472b6',
  Person: '#a78bfa',
  Department: '#34d399'
};

let network;
let nodesDataset;
let edgesDataset;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? '#fca5a5' : '#7dd3fc';
}

function renderSources(sources) {
  if (!sources || sources.length === 0) {
    sourcesEl.textContent = '검색 후 참조 노드가 표시됩니다.';
    sourceCountEl.textContent = '-';
    return;
  }

  sourceCountEl.textContent = `${sources.length}개`;
  sourcesEl.innerHTML = '';
  sources.forEach((src) => {
    const div = document.createElement('div');
    div.className = 'source-card';
    const typeClass = src.type.toLowerCase();
    div.innerHTML = `
      <span class="type ${typeClass}">${src.type}</span>
      <h4>${src.title || '-'} </h4>
      <p>ID: ${src.id || src.nodeKey}</p>
    `;
    sourcesEl.appendChild(div);
  });
}

function buildNodeOptions() {
  return {
    shape: 'dot',
    size: 18,
    font: { color: '#e5e7eb', size: 13 },
    borderWidth: 2,
    shadow: true
  };
}

function buildEdgesOptions() {
  return {
    color: {
      color: '#475569',
      highlight: '#facc15'
    },
    width: 1.4,
    arrows: 'to',
    smooth: { type: 'dynamic', roundness: 0.3 },
    font: { align: 'top', color: '#cbd5e1', size: 10 }
  };
}

function hydrateGraph(nodes, edges) {
  nodesDataset = new vis.DataSet(
    nodes.map((n) => ({
      id: n.id,
      label: n.title,
      group: n.label,
      title: `${n.label} | ${n.title}`,
      color: {
        background: `${groupColors[n.label] || '#94a3b8'}30`,
        border: groupColors[n.label] || '#94a3b8'
      }
    }))
  );

  edgesDataset = new vis.DataSet(
    edges.map((e) => ({
      from: e.from,
      to: e.to,
      label: e.type,
      ...buildEdgesOptions()
    }))
  );

  const options = {
    interaction: { hover: true },
    physics: {
      enabled: true,
      stabilization: { iterations: 200 },
      barnesHut: { gravitationalConstant: -4500 }
    },
    nodes: buildNodeOptions(),
    edges: buildEdgesOptions(),
    groups: {
      Document: { color: { background: '#38bdf830', border: '#38bdf8' } },
      Complaint: { color: { background: '#f472b630', border: '#f472b6' } },
      Person: { color: { background: '#a78bfa30', border: '#a78bfa' } },
      Department: { color: { background: '#34d39930', border: '#34d399' } }
    }
  };

  network = new vis.Network(graphContainer, { nodes: nodesDataset, edges: edgesDataset }, options);
}

function highlightNodes(nodeKeys = []) {
  if (!nodesDataset) return;
  const highlights = new Set(nodeKeys);
  const defaultColors = (label) => ({
    background: `${groupColors[label] || '#94a3b8'}30`,
    border: groupColors[label] || '#94a3b8'
  });

  nodesDataset.getIds().forEach((id) => {
    const node = nodesDataset.get(id);
    const isHighlighted = highlights.has(id);
    nodesDataset.update({
      id,
      color: isHighlighted
        ? { background: '#facc1530', border: '#facc15' }
        : defaultColors(node.group)
    });
  });

  if (highlights.size > 0 && network) {
    network.fit({ nodes: Array.from(highlights), animation: { duration: 600 } });
  }
}

async function fetchGraph() {
  try {
    setStatus('그래프 로딩 중...');
    const res = await fetch('/api/graph');
    if (!res.ok) throw new Error('그래프 데이터를 불러오지 못했습니다.');
    const data = await res.json();
    graphMetaEl.textContent = `${data.nodes.length} nodes / ${data.edges.length} edges`;
    hydrateGraph(data.nodes, data.edges);
    setStatus('그래프 로딩 완료');
  } catch (err) {
    console.error(err);
    setStatus(err.message, true);
  }
}

async function runSearch() {
  const query = queryInput.value.trim();
  if (!query) {
    setStatus('질문을 입력해 주세요.', true);
    return;
  }

  setStatus('검색 실행 중...');
  searchBtn.disabled = true;
  try {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    if (!res.ok) {
      throw new Error('검색 요청에 실패했습니다. API 서버 상태를 확인해 주세요.');
    }

    const data = await res.json();
    answerEl.textContent = data.answer || '결과가 없습니다.';
    contextEl.textContent = data.context || '';
    renderSources(data.sources || []);
    highlightNodes((data.sources || []).map((s) => s.nodeKey).filter(Boolean));
    setStatus('검색 완료');
  } catch (err) {
    console.error(err);
    setStatus(err.message, true);
  } finally {
    searchBtn.disabled = false;
  }
}

searchBtn.addEventListener('click', runSearch);
queryInput.addEventListener('keydown', (e) => {
  if (e.metaKey && e.key === 'Enter') {
    runSearch();
  }
});

fetchGraph();
