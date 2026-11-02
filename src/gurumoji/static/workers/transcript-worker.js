/* 文字起こしの検索と並べ替えだけを担当する専用スレッド。 */
'use strict';
importScripts('../transcript-math.js');
self.onmessage = ({data}) => {
  if (!data || !Number.isSafeInteger(data.id)) return;
  try {
    if (data.type !== 'select') throw new Error('未対応の表示用計算です。');
    self.postMessage({id: data.id, result: GurumojiTranscriptMath.select(data.payload)});
  } catch (error) {
    self.postMessage({id: data.id, error: error instanceof Error ? error.message : '表示用計算に失敗しました。'});
  }
};
