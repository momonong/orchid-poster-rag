'use strict';
(function(root) {
  const locales = {
    en: {
      pageTitle:'Orchid patterns | One orchid, three clues', description:'Explore orchid pigmentation through three clues, source-linked questions and a local voice guide.',
      skip:'Ask a question', brand:'Orchid patterns', institution:'NCKU · Research Day guide', researchNav:'Research sources', posterOpen:'View poster ↗', paperOpen:'Read paper ↗',
      eyebrow:'How does a flower grow its pattern?', title:'One orchid, three clues', subtitle:'From spots to purple patches: the mathematics behind flower patterns.', researchTag:'Simulation study',
      flowerAlt:'Eight Phalaenopsis patterns from the research poster: separate purple spots through extensive purple patches', flowerCaption:'Different patterns may reflect different regulatory balances.', flowerCredit:'Original research poster · Introduction',
      guideHeading:'Meet the study in one minute', introExpand:'Open guide ＋', introCollapse:'Close guide −', introFallback:'This study explores Phalaenopsis patterns with a reaction–diffusion model. Predictions still need experimental validation.',
      clueTabs:'Three research clues', tabs:['01 Spots','02 Fusion','03 Edges'], clueFigure:'Poster Figure', modelSimulation:'model simulation', clueAlt:'Poster simulation', askClue:'Ask about this clue →', previous:'← Previous clue', next:'Next clue →',
      evidenceNote:'Simulations propose mechanisms and predictions; experimental validation is still needed.',
      chatEyebrow:'Follow your curiosity', chatHeading:'Ask about the study', clear:'Clear conversation', checking:'Checking research data and question service…', ready:'Research data and local questions are ready.', indexNotReady:'The research index is not ready. You can read the guide and sources.', modelNotReady:'The local model is not ready. You can read the guide and sources.', healthUnknown:'Question service status could not be confirmed. You can read the guide and sources.',
      messagesLabel:'Questions and answers', welcomeTitle:'Start with the patterns you see.', welcomeBody:'Ask about the study, its parameters, or the difference between simulation and experiment. Replies include sources you can open.', cleared:'Conversation cleared. You can start with a new question.',
      suggestionsLabel:'Suggested questions', suggestions:[['What does this study investigate?','Introduce this study in simple terms.'],['What does miR858 do?','What role does miR858 play in the model?'],['Simulation or experiment?','Have these patterns been validated in biological experiments?']],
      questionLabel:'Your question', placeholder:'For example: why do spots fuse?', inputHelp:'Shift + Enter: new line · up to 600 characters', send:'Send question ↗', sending:'Finding sources and answering…', privacy:'Conversation stays on this page and is lost when cleared or refreshed. Questions are not sent on your behalf. Only your language preference is saved.',
      footerSource:'Research: Lu et al. (2024), BMC Plant Biology 24, 681.', correction:'Figure correction', license:'Paper: CC BY 4.0', contact:'Contact the researchers', credit:'Images cropped from the supplied poster; original biological and simulation context retained. Reviewed summaries are not verbatim quotations.',
      sourceTitle:'Source information', sourceExcerpt:'source excerpt', sourceLoading:'Loading source…', sourceError:'This source could not be loaded. Please try again later.', sourceOriginal:'Original English excerpt (PDF text extraction)', sourceChinese:'Reviewed summary (Traditional Chinese)', sourceUnavailable:'No extracted text is available. Please consult the original document.', sourceRead:'Read original source ↗', sourceLocal:'Local paper PDF ↗', sourceVersion:'Version', sourcePage:'Page', sourceClose:'Close source', close:'Close ×',
      posterTitle:'Research Day poster', posterNote:'Poster Figures 1–4 use their own numbering, separate from the paper.', posterPdf:'Open original PDF ↗', posterAlt:'Complete research poster: Introduction, Methods, three clues and study limitations', posterClose:'Close poster',
      user:'Your question', assistant:'Research guide', reviewedSummary:'Reviewed source summary', waiting:'Searching research sources and preparing a reply. One question is processed at a time; please wait.', checked:'Citation IDs checked; semantic accuracy still needs human review.', tooLong:'The question or conversation is too long. Please shorten it.', requestError:'The service cannot process this question right now.', timeout:'Waiting ended and the result is unknown. The service may still be processing; the question was not resent automatically.', connectionError:'The connection was interrupted. The result is unknown; the question was not resent automatically.', guideError:'The full guide could not be loaded. You can still open the poster and paper.',
      playIntro:'Play introduction', playClue:'Play this clue', playAnswer:'Play answer', play:'Play', pause:'Pause', resume:'Resume', stop:'Stop', speechLabel:'Voice guide', speechIdle:'Voice guide ready. Select Play to listen.', speechChecking:'Checking voice service…', speechPreparing:'Preparing audio…', speechPlaying:'Playing', speechPaused:'Paused', speechReady:'Audio ready — tap Play to listen', speechError:'Audio playback failed. Select Play to try again or continue reading. No automatic retry.', speechUnsupported:'Audio playback is unavailable in this browser. Text remains available.', speechUnavailable:'Voice service is unavailable. Text remains available; no automatic retry.', speechBusy:'Voice service is busy. Try Play again later. No automatic retry.', speechTimeout:'Audio preparation timed out. Try Play again later. No automatic retry.', speechNetwork:'Voice connection was interrupted. Try Play again later. No automatic retry.', speechInvalid:'This text cannot be played. Continue reading or select another passage.', speechPolicy:'English and Traditional Chinese audio are prepared by this site’s local service. No microphone or automatic playback.',
      docNames:{paper:'Paper',poster:'Poster',correction:'Correction'}, source:'Source', intro:'Introduction', clue:'Clue', answer:'Answer'
    },
    'zh-TW': {
      pageTitle:'蘭花花紋研究｜一朵蘭花，三條線索', description:'蘭花研究日海報導覽。從三條線索理解反應擴散模型，並透過有來源的本機問答探索花紋。',
      skip:'直接提問', brand:'蘭花花紋研究', institution:'成功大學・研究日海報導覽', researchNav:'研究資料', posterOpen:'看海報 ↗', paperOpen:'讀論文 ↗',
      eyebrow:'花紋，是怎麼長出來的？', title:'一朵蘭花，三條線索', subtitle:'從斑點到紫色斑塊，讀懂花紋背後的數學。', researchTag:'數值模擬研究',
      flowerAlt:'原研究海報中的八種蝴蝶蘭花紋：從離散紫斑到大片紫色斑塊', flowerCaption:'不同的花紋，可能來自不同的調控平衡。', flowerCredit:'原研究海報・Introduction',
      guideHeading:'先用一分鐘，認識這份研究', introExpand:'展開導覽 ＋', introCollapse:'收起導覽 −', introFallback:'這份研究以反應擴散模型探索蝴蝶蘭花紋，預測仍需實驗驗證。',
      clueTabs:'研究的三條線索', tabs:['01 斑點','02 融合','03 邊界'], clueFigure:'海報圖', modelSimulation:'模型模擬', clueAlt:'海報模擬圖', askClue:'問問這條線索 →', previous:'← 上一條線索', next:'下一條線索 →',
      evidenceNote:'模擬能提出機制與預測；研究仍需實驗驗證。',
      chatEyebrow:'把好奇，接著問下去', chatHeading:'和研究對話', clear:'清除對話', checking:'正在確認研究資料與問答服務…', ready:'研究資料與本機問答已就緒。', indexNotReady:'資料索引尚未就緒，可以先讀導覽與來源。', modelNotReady:'本機模型尚未就緒，可以先讀導覽與來源。', healthUnknown:'目前無法確認問答狀態，可以先讀導覽與來源。',
      messagesLabel:'問答內容', welcomeTitle:'從你看見的花紋開始。', welcomeBody:'可以問研究在做什麼、參數代表什麼，或模擬和實驗有什麼不同。回答會附上可展開的來源。', cleared:'對話已清除，可以從新的問題開始。',
      suggestionsLabel:'建議問題', suggestions:[['這份研究在做什麼？','用簡單的方式介紹這份研究在做什麼。'],['miR858 的角色是什麼？','miR858 在模型中扮演什麼角色？'],['這是模擬，還是實驗？','這些花紋已經經過生物實驗驗證了嗎？']],
      questionLabel:'你的問題', placeholder:'例如：為什麼斑點會融合？', inputHelp:'Shift + Enter 換行・最多 600 字', send:'送出問題 ↗', sending:'正在查找與回答…', privacy:'對話只留在此頁面。清除或重整後不保留；不會代為寄送問題。只儲存語言偏好。',
      footerSource:'研究資料：Lu et al. (2024), BMC Plant Biology 24, 681。', correction:'圖號勘誤', license:'論文 CC BY 4.0', contact:'聯絡研究團隊', credit:'圖材裁切自使用者提供海報；原始影像與模擬圖保留研究脈絡。導覽摘要經人工校對，並非逐字引文。',
      sourceTitle:'來源資料', sourceExcerpt:'來源摘錄', sourceLoading:'正在讀取來源…', sourceError:'目前無法讀取這個來源，請稍後再試。', sourceOriginal:'核對英文原文（PDF 文字擷取）', sourceChinese:'導覽摘要（繁體中文）', sourceUnavailable:'此來源暫無文字擷取，請核對原始文件。', sourceRead:'閱讀原始來源 ↗', sourceLocal:'本機論文 PDF ↗', sourceVersion:'版本', sourcePage:'頁', sourceClose:'關閉來源', close:'關閉 ×',
      posterTitle:'研究日海報', posterNote:'海報圖 1–4 與論文圖號獨立。', posterPdf:'開啟原始 PDF ↗', posterAlt:'完整研究日海報：Introduction、Methods、三條線索與研究限制', posterClose:'關閉海報',
      user:'你的問題', assistant:'研究導覽', waiting:'正在檢索研究資料並準備回答；一次只處理一題，請稍候。', checked:'引用 ID 已核對；語意正確性仍需人工判斷。', tooLong:'問題或對話過長，請縮短後再送出。', requestError:'服務目前無法處理這個問題。', timeout:'等待已結束，此題結果未知。服務仍可能處理中，沒有自動重送。', connectionError:'連線中斷，此題結果未知；沒有自動重送。', guideError:'目前無法載入完整導覽，仍可開啟海報與論文。',
      playIntro:'播放介紹', playClue:'播放這條線索', playAnswer:'播放回答', play:'播放', pause:'暫停', resume:'繼續', stop:'停止', speechLabel:'語音導覽', speechIdle:'語音導覽已就緒，按播放開始聆聽。', speechChecking:'正在確認語音服務…', speechPreparing:'正在準備音檔…', speechPlaying:'正在播放', speechPaused:'已暫停', speechReady:'音檔已備妥，請按播放', speechError:'音檔播放失敗，可重新按播放或繼續閱讀。沒有自動重試。', speechUnsupported:'此瀏覽器不支援音檔播放，仍可閱讀文字。', speechUnavailable:'語音服務目前無法使用，仍可閱讀文字；沒有自動重試。', speechBusy:'語音服務忙碌，請稍後重新按播放。沒有自動重試。', speechTimeout:'準備音檔逾時，請稍後重新按播放。沒有自動重試。', speechNetwork:'語音連線中斷，請稍後重新按播放。沒有自動重試。', speechInvalid:'這段文字目前無法播放，請繼續閱讀或選擇其他內容。', speechPolicy:'英文與繁體中文音檔由本站本機服務製作，不使用麥克風，也不自動播放。',
      docNames:{paper:'論文',poster:'海報',correction:'官方勘誤'}, source:'來源', intro:'介紹', clue:'線索', answer:'回答'
    }
  };
  function initialLanguage(storage) {
    try { return storage?.getItem('orchid-language') === 'zh-TW' ? 'zh-TW' : 'en'; } catch { return 'en'; }
  }
  const api = {locales, initialLanguage};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.OrchidLocale = api;
})(globalThis);
