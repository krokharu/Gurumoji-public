/* 発話の表示用計算を共有し、原本の配列や発話は変更しない。 */
(() => {
  'use strict';
  function select({rows, query}) {
    const {keyword, speaker, emotion, agreement, sort} = query;
    const matches = rows.filter(row => (!keyword || row.text.toLocaleLowerCase().includes(keyword))
      && (!speaker || row.speaker === speaker)
      && (!emotion || (emotion === 'none' ? !row.emotion : row.emotion === emotion))
      && (!agreement || row.agreement === agreement));
    const occurrences = text => keyword ? text.toLocaleLowerCase().split(keyword).length - 1 : 0;
    // キーワード一致数は比較のたびに本文を走査せず、一度だけ計算する。
    const counts = sort === 'keyword' ? new Map(matches.map(row => [row.index, occurrences(row.text)])) : null;
    matches.sort((left, right) => {
      if (sort === 'time_desc') return right.start - left.start;
      if (sort === 'speaker') return left.sortSpeaker.localeCompare(right.sortSpeaker, 'ja') || left.start - right.start;
      if (sort === 'emotion') return left.emotion.localeCompare(right.emotion, 'ja') || left.start - right.start;
      if (sort === 'keyword') return counts.get(right.index) - counts.get(left.index) || left.start - right.start;
      return left.start - right.start;
    });
    return matches.map(row => row.index);
  }
  globalThis.GurumojiTranscriptMath = Object.freeze({select});
})();
