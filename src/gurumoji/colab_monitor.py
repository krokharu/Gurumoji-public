"""任意のColab資源モニター。計測値だけを表示し、ファイルへ保存しない。"""

from __future__ import annotations

from collections import deque
import csv
import html
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading

from .colab_support import ColabSetupError


def _number(value, *, maximum=None):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0 or maximum is not None and value > maximum:
        return None
    return value


def collect_runtime_snapshot(*, runner=subprocess.run, environ=None, statistics=None):
    """GPUモデルや利用者データを読まず、ランタイム全体の使用状況だけを計測する。"""
    environment = os.environ if environ is None else environ
    result = {"cpu_percent": None, "ram_percent": None, "ram_used_gib": None,
              "ram_total_gib": None, "gpus": [], "gpu_status": "unavailable"}
    try:
        if statistics is None:
            import psutil as statistics
        # 最初の呼出しが0%になる非ブロッキング計測を避ける。
        result["cpu_percent"] = _number(statistics.cpu_percent(interval=0.1), maximum=100)
        memory = statistics.virtual_memory()
        total = _number(memory.total)
        available = _number(memory.available)
        if total is not None and total > 0 and available is not None and available <= total:
            result.update(ram_percent=round(100 * (total - available) / total, 1),
                          ram_used_gib=round((total - available) / 1024**3, 2),
                          ram_total_gib=round(total / 1024**3, 2))
    except (ImportError, AttributeError, OSError, ValueError):
        pass
    visible = environment.get("CUDA_VISIBLE_DEVICES")
    if visible is not None and visible.strip() in {"", "-1"}:
        result["gpu_status"] = "disabled"
        return result
    try:
        completed = runner([
            "nvidia-smi", "--query-gpu=index,uuid,name,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ], capture_output=True, text=True, check=True, timeout=2)
        allowed = {value.strip() for value in visible.split(",")} if visible is not None else None
        result["gpu_status"] = "none"
        for row in csv.reader(io.StringIO(completed.stdout)):
            if len(row) != 6:
                continue
            index, uuid, name, utilization, used, total = (value.strip() for value in row)
            if allowed is not None and index not in allowed and uuid not in allowed:
                continue
            used_mib, total_mib = _number(used), _number(total)
            memory_ok = used_mib is not None and total_mib is not None and total_mib > 0 and used_mib <= total_mib
            result["gpus"].append({
                "id": uuid or index, "name": name, "utilization_percent": _number(utilization, maximum=100),
                "memory_percent": round(100 * used_mib / total_mib, 1) if memory_ok else None,
                "memory_used_gib": round(used_mib / 1024, 2) if memory_ok else None,
                "memory_total_gib": round(total_mib / 1024, 2) if memory_ok else None,
            })
        if result["gpus"]:
            result["gpu_status"] = "detected"
    except (OSError, subprocess.SubprocessError):
        pass
    return result


def _progress(value, label):
    value = _number(value, maximum=100)
    if value is None:
        return '<div class="gm-empty-bar" aria-label="未取得"></div>'
    return f'<progress max="100" value="{value:.1f}" aria-label="{html.escape(label)}"></progress>'


def _history_chart(values, label):
    segments, current = [], []
    count = max(2, len(values))
    for index, value in enumerate(values):
        value = _number(value, maximum=100)
        if value is None:
            if current:
                segments.append(current)
                current = []
        else:
            current.append((300 * index / (count - 1), 54 - value / 2))
    if current:
        segments.append(current)
    marks = []
    for points in segments:
        if len(points) == 1:
            x, y = points[0]
            marks.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="currentColor"/>')
        else:
            encoded = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
            marks.append(f'<polyline points="{encoded}" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke"/>')
    return f'<svg viewBox="0 0 300 58" preserveAspectRatio="none" role="img" aria-label="{html.escape(label)}の推移（0〜100%）">{"".join(marks)}</svg>'


def render_monitor_html(history, *, interval=2, running=True):
    """計測不能は未取得と表示し、欠測した履歴は線でつながない。"""
    rows = list(history)
    latest = rows[-1] if rows else {}
    state = "計測中" if running and rows else "計測を開始しています" if running else "停止済み"

    def percent(value):
        value = _number(value, maximum=100)
        return f"{value:.1f}%" if value is not None else "未取得"

    def capacity(used, total):
        used, total = _number(used), _number(total)
        return f"{used:.2f} / {total:.2f} GiB" if used is not None and total is not None else "容量未取得"

    def card(title, value, detail, values, *, extra=""):
        return f'<section class="gm-monitor-card"><h4>{html.escape(title)}</h4><strong>{html.escape(percent(value))}</strong><p>{html.escape(detail)}</p>{_progress(value, title)}{extra}{_history_chart(values, title)}</section>'

    cards = [card("CPU", latest.get("cpu_percent"), "ランタイム全体の使用率", [row.get("cpu_percent") for row in rows])]
    for gpu in latest.get("gpus", []):
        values = [next((entry.get("utilization_percent") for entry in row.get("gpus", []) if entry.get("id") == gpu.get("id")), None) for row in rows]
        memory = capacity(gpu.get("memory_used_gib"), gpu.get("memory_total_gib"))
        extra = f'<p class="gm-vram">GPUメモリー {html.escape(memory)}</p>{_progress(gpu.get("memory_percent"), "GPUメモリー")}'
        cards.append(card("GPU", gpu.get("utilization_percent"), str(gpu.get("name") or "NVIDIA GPU"), values, extra=extra))
    if not latest.get("gpus"):
        cards.append(card("GPU", None, "GPUは未検出・未割当、または取得できません", []))
    cards.append(card("RAM", latest.get("ram_percent"), capacity(latest.get("ram_used_gib"), latest.get("ram_total_gib")), [row.get("ram_percent") for row in rows]))
    notice = '<p class="gm-monitor-notice">計測を取得できませんでした。次の更新で再確認します。</p>' if latest.get("sample_failed") else ""
    return f'''<div class="gm-runtime-monitor" role="region" aria-label="ランタイムの使用状況">
<style>
.gm-runtime-monitor {{font-family:system-ui,sans-serif;line-height:1.5;color:var(--gm-text);--gm-text:#172c23;--gm-accent:#23816a;--gm-line:#d7dedb;--gm-surface:#f5f8f6}}
.gm-runtime-monitor h3 {{margin:0;font-size:17px}} .gm-runtime-monitor p {{margin:4px 0;font-size:12px;overflow-wrap:anywhere}}
.gm-monitor-grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr));gap:12px;margin:10px 0}}
.gm-monitor-card {{display:flex;flex-direction:column;min-width:0;padding:12px;border:1px solid var(--gm-line);border-radius:10px;background:var(--gm-surface)}}
.gm-monitor-card h4 {{margin:0;font-size:14px}} .gm-monitor-card strong {{font-size:24px;font-variant-numeric:tabular-nums}}
.gm-monitor-card progress {{display:block;width:100%;height:9px;accent-color:var(--gm-accent)}}
.gm-empty-bar {{height:7px;margin:2px 0;background:var(--gm-line);border-radius:6px}}
.gm-monitor-card svg {{display:block;width:100%;height:58px;color:var(--gm-accent);margin-top:auto;padding-top:5px;overflow:visible}}
.gm-runtime-monitor .gm-vram {{margin-top:9px}} .gm-monitor-notice {{font-weight:600}}
@media(prefers-color-scheme:dark) {{.gm-runtime-monitor {{--gm-text:#e5f2e9;--gm-accent:#77cdb0;--gm-line:#48554f;--gm-surface:#25312c}}}}
</style><h3>ランタイムの使用状況</h3><p>{state} · {interval}秒間隔 · このランタイム全体の値</p>
{notice}<div class="gm-monitor-grid">{"".join(cards)}</div><p>直近{len(rows)}回の使用率（0〜100%・最大60回）。未取得は0%として表示しません。</p></div>'''


class RuntimeMonitor:
    def __init__(self, python, repo_dir, publish, *, interval=2, runner=subprocess.run):
        if type(interval) is not int or not 1 <= interval <= 30:
            raise ColabSetupError("MONITOR_INTERVAL", "更新間隔は1〜30秒で指定してください。")
        self.python, self.repo_dir, self.publish = str(python), Path(repo_dir), publish
        self.interval, self.runner = interval, runner
        self.history = deque(maxlen=60)
        self._stop = threading.Event()
        self._thread = None

    def _sample(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(self.repo_dir / "src")
        try:
            completed = self.runner([self.python, "-m", "gurumoji.colab_monitor", "--snapshot"],
                                    cwd=self.repo_dir, env=environment, capture_output=True,
                                    text=True, check=True, timeout=5)
            result = json.loads(completed.stdout)
            if not isinstance(result, dict):
                raise ValueError
            return result
        except (OSError, ValueError, subprocess.SubprocessError):
            return {"sample_failed": True, "gpus": []}

    def _run(self):
        try:
            while not self._stop.is_set():
                sample = self._sample()
                if self._stop.is_set():
                    break
                self.history.append(sample)
                self.publish(render_monitor_html(self.history, interval=self.interval))
                if self._stop.wait(self.interval):
                    break
        except Exception:
            # 表示先を失った場合も計測だけが走り続けないよう停止する。
            self._stop.set()

    def start(self):
        if self._thread is not None:
            return self
        self.publish(render_monitor_html([], interval=self.interval))
        self._thread = threading.Thread(target=self._run, name="gurumoji-runtime-monitor", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=6)
            if self._thread.is_alive():
                raise ColabSetupError("MONITOR_STOP", "計測の終了を待っています。少し待ってモニターのセルを再実行してください。")
        try:
            self.publish(render_monitor_html(self.history, interval=self.interval, running=False))
        except Exception:
            pass


def start_runtime_monitor(python, repo_dir, *, interval=2):
    from IPython.display import HTML, display

    handle = display(HTML("<p>ランタイムモニターを準備しています。</p>"), display_id=True)
    if handle is None:
        raise ColabSetupError("MONITOR_DISPLAY", "Colabの画面に接続してモニターのセルを実行してください。")
    monitor = RuntimeMonitor(python, repo_dir, lambda content: handle.update(HTML(content)), interval=interval)
    try:
        from ipywidgets import Button
        button = Button(description="モニターを停止", icon="stop")

        def stop_clicked(_):
            monitor.stop()
            button.disabled = True
            button.description = "停止済み"

        button.on_click(stop_clicked)
        display(button)
    except ImportError:
        pass
    return monitor.start()


if __name__ == "__main__" and sys.argv[1:] == ["--snapshot"]:
    print(json.dumps(collect_runtime_snapshot(), ensure_ascii=True, allow_nan=False))
