# ruff: noqa: E501

"""Small, same-origin rolo-vis web console.

The first rolo-vis surface intentionally has no build toolchain or third-party
frontend dependency.  It is a thin projection over the existing HTTP control
plane: users choose one exact pending Stage Agent request, then the browser
submits that request's artifact reference back to the stage endpoint.  The
server remains the authority for digest, identity, expiry and single-use checks.
"""

from __future__ import annotations

import uvicorn
from fastapi.responses import HTMLResponse

from rolo.api import app as control_plane_app
from rolo.core.config import get_settings

_VIS_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>rolo-vis</title>
  <style>
    :root { color-scheme: light dark; font: 15px/1.5 system-ui,sans-serif; }
    body { margin: 0 auto; max-width: 1100px; padding: 24px; }
    header { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
    h1 { margin:0 16px 0 0; }
    input,select,button { font:inherit; padding:7px 9px; }
    button { cursor:pointer; }
    .muted { opacity:.75; }
    .card { border:1px solid #8886; border-radius:8px; padding:14px; margin:12px 0; }
    .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
    code { overflow-wrap:anywhere; }
    pre { max-height:360px; overflow:auto; white-space:pre-wrap; }
    .danger { color:#d66; }
  </style>
</head>
<body>
  <header>
    <h1>rolo-vis</h1>
    <label>API token <input id="token" type="password" autocomplete="off" placeholder="optional"></label>
    <button id="refresh">刷新</button>
  </header>
  <p class="muted">只读查看证据和待授权请求；批准按钮只恢复当前选中的、digest 绑定的 Stage Agent run。</p>
  <section class="card">
    <div class="row"><label>Robot <select id="robot"></select></label><label>Stage <select id="stage"><option value="">全部</option><option value="diagnose">diagnose</option><option value="verify">verify</option></select></label></div>
    <div id="requests" class="muted">加载中…</div>
  </section>
  <section class="card"><h2>最近 run</h2><div id="runs" class="muted">选择一个授权请求后会显示 run。</div></section>
  <script>
    const $ = (id) => document.getElementById(id);
    const token = () => { const value = $('token').value.trim(); return value ? {'Authorization': `Bearer ${value}`} : {}; };
    const jsonHeaders = () => ({...token(), 'Content-Type': 'application/json'});
    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    let requests = [];
    async function api(path, options = {}) {
      const response = await fetch(path, {...options, headers: {...token(), ...(options.headers || {})}});
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail ? JSON.stringify(body.detail) : `${response.status}`);
      return body;
    }
    async function loadRobots() {
      const robots = await api('/v1/robots');
      $('robot').innerHTML = robots.map(item => `<option value="${esc(item.robot_id)}">${esc(item.robot_id)}</option>`).join('');
      if (!robots.length) $('requests').textContent = '没有已登记 robot';
    }
    async function loadSession() {
      await api('/v1/session');
    }
    async function loadRequests() {
      const robot = $('robot').value;
      if (!robot) return;
      const stage = $('stage').value;
      const suffix = stage ? `?stage=${encodeURIComponent(stage)}` : '';
      const body = await api(`/v1/robots/${encodeURIComponent(robot)}/stage-auth-requests${suffix}`);
      requests = body.requests || [];
      $('requests').innerHTML = requests.length ? requests.map((item, index) => `
        <article class="card"><div><b>${esc(item.stage)}</b> · ${esc(item.executor)} / ${esc(item.provider)}</div>
        <div>run <code>${esc(item.run_id)}</code></div><div>plan <code>${esc(item.plan_sha256)}</code></div>
        <div>expires <code>${esc(item.expires_at)}</code></div>
        <button data-index="${index}" class="approve">确认并恢复此 run</button>
      </article>`).join('') : '当前没有待授权请求';
      document.querySelectorAll('.approve').forEach(button => button.addEventListener('click', () => approve(Number(button.dataset.index))));
    }
    async function approve(index) {
      const item = requests[index];
      if (!item) return;
      if (!window.confirm(`确认执行 ${item.stage} / ${item.robot_id}？\nplan: ${item.plan_sha256}`)) return;
      try {
        const body = await api(`/v1/robots/${encodeURIComponent(item.robot_id)}/${item.stage}/run`, {method:'POST', headers: jsonHeaders(), body: JSON.stringify({confirmed:true, authorization_ref:item.request_ref})});
        $('runs').innerHTML = `<pre>${esc(JSON.stringify(body, null, 2))}</pre>`;
        await loadRequests();
        await loadRun(item.stage, item.robot_id, body.run_id);
      } catch (error) { $('runs').innerHTML = `<p class="danger">${esc(error.message)}</p>`; }
    }
    async function loadRun(stage, robot, runId) {
      if (!runId) return;
      try {
        const [detail, events] = await Promise.all([
          api(`/v1/robots/${encodeURIComponent(robot)}/${stage}/runs/${encodeURIComponent(runId)}`),
          api(`/v1/robots/${encodeURIComponent(robot)}/${stage}/runs/${encodeURIComponent(runId)}/events?limit=100`)
        ]);
        $('runs').innerHTML = `<pre>${esc(JSON.stringify({detail, events}, null, 2))}</pre>`;
      } catch (error) { $('runs').innerHTML += `<p class="danger">${esc(error.message)}</p>`; }
    }
    $('refresh').addEventListener('click', async () => { try { await loadSession(); await loadRobots(); await loadRequests(); } catch (error) { $('requests').textContent = error.message; } });
    $('robot').addEventListener('change', loadRequests); $('stage').addEventListener('change', loadRequests);
    loadSession().then(loadRobots).then(loadRequests).catch(error => $('requests').textContent = error.message);
  </script>
</body>
</html>"""


def create_vis_app():
    """Return the control-plane app with the rolo-vis dashboard at ``/``."""

    marker = "_rolo_vis_route_installed"
    if not getattr(control_plane_app.state, marker, False):
        control_plane_app.add_api_route(
            "/",
            lambda: HTMLResponse(_VIS_HTML),
            methods=["GET"],
            include_in_schema=False,
        )
        setattr(control_plane_app.state, marker, True)
    return control_plane_app


app = create_vis_app()


def main() -> None:
    """Serve rolo-vis and the same-origin Rolo HTTP control plane."""

    settings = get_settings()
    uvicorn.run(app, host=settings.rolo_host, port=settings.rolo_port)


__all__ = ["app", "create_vis_app", "main"]
