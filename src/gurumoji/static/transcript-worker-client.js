/* 最新の表示要求だけを採用し、Worker未対応・起動失敗時は同じ計算へ戻す。 */
(() => {
  'use strict';
  let worker = null, unavailable = false, nextId = 0;
  const pending = new Map();
  function fallback(payload) { return GurumojiTranscriptMath.select(payload); }
  function stop() {
    unavailable = true;
    worker?.terminate(); worker = null;
    for (const [id, task] of pending) {
      clearTimeout(task.timer); pending.delete(id);
      try { task.resolve(fallback(task.payload)); } catch (error) { task.reject(error); }
    }
  }
  function getWorker() {
    if (worker || unavailable) return worker;
    const url = document.querySelector('meta[name="gurumoji-transcript-worker"]')?.content;
    if (typeof Worker !== 'function' || !url) { unavailable = true; return null; }
    try {
      worker = new Worker(url, {name: 'gurumoji-transcript'});
      worker.onmessage = ({data}) => {
        const task = pending.get(data?.id);
        if (!task) return;
        pending.delete(data.id); clearTimeout(task.timer);
        if (data.error || !Array.isArray(data.result)) {
          try { task.resolve(fallback(task.payload)); } catch (error) { task.reject(error); }
        } else task.resolve(data.result);
      };
      worker.onerror = event => { event.preventDefault(); stop(); };
      worker.onmessageerror = stop;
      return worker;
    } catch (_) { unavailable = true; return null; }
  }
  function select(payload) {
    // 入力が更新されたら、古い結果を待っている画面を即座に解放する。
    for (const [id, task] of pending) { clearTimeout(task.timer); task.resolve(null); pending.delete(id); }
    const target = getWorker();
    if (!target) return Promise.resolve().then(() => fallback(payload));
    return new Promise((resolve, reject) => {
      const id = ++nextId;
      const timer = setTimeout(stop, 10000);
      pending.set(id, {payload, resolve, reject, timer});
      try { target.postMessage({id, type: 'select', payload}); } catch (_) { stop(); }
    });
  }
  window.addEventListener('pagehide', stop);
  globalThis.GurumojiTranscriptTasks = Object.freeze({select});
})();
