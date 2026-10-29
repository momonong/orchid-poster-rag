from typing import Literal

Language = Literal["en", "zh-TW"]

UNKNOWN = {
    "en": "I cannot provide an answer verified against this poster and paper. Please ask the researchers at the event or corresponding author Yu-Chen Shu (ycshu@mail.ncku.edu.tw). This page does not record or send questions on your behalf.",
    "zh-TW": "目前無法根據這份海報與論文，提供通過來源核對的回答。可向現場研究人員，或通訊作者 Yu-Chen Shu（ycshu@mail.ncku.edu.tw）詢問；本頁不會代為記錄或寄送問題。",
}

# Keep internal diagnostic messages intact; translate only known visitor-facing errors.
ERRORS_EN = {
    "選定的英文摘要超過 512 token，未截斷或刪減條件": "The selected English summary exceeds 512 tokens. No text or conditions were truncated; no answer was displayed.",
    "英文校對摘要譯文缺少、不完整或與研究語料版本不符": "Reviewed English summary translations are missing, incomplete or out of date. English question answering is unavailable.",
    "目前訪客較多，請稍後再問": "There are several visitors waiting. Please ask again later.",
    "等候已超時，這題尚未送入模型；請稍後再問": "The waiting time expired before this question reached the model. Please ask again later.",
    "模型目前忙碌，請稍後再問": "The model is busy. Please ask again later.",
    "此題與對話內容超過模型保守 context 預算，請清除對話或縮短問題": "This question and conversation exceed the model's context budget. Please clear the conversation or shorten the question.",
    "問題加上追問前文超過 embedding 長度限制，請縮短問題或清除對話後再問。": "The question and follow-up context exceed the retrieval length limit. Please shorten the question or clear the conversation.",
    "模型連線中斷；此題結果未知，未自動重送": "The model connection was interrupted. The result is unknown; the question was not resent automatically.",
    "服務未確認生成結果；未自動重送": "The service could not confirm the generation result. The question was not resent automatically.",
    "模型回覆未完整或格式不符，未顯示未驗證內容": "The model reply was incomplete or had an invalid format. Unverified content was not displayed.",
    "無法連線至本機模型": "The local model could not be reached.",
    "本機模型尚未就緒": "The local model is not ready.",
    "本機模型拒絕此請求，請現場研究人員檢查服務設定": "The local model rejected the request. Please ask a researcher to check the service settings.",
}


def error_text(message, language, status):
    if language == "zh-TW":
        return message
    return ERRORS_EN.get(message, {
        "busy": "The model is busy or its previous task is still being reconciled. Please read the guide and ask again later.",
        "unknown": "No verified answer was obtained. The result is unknown; the question was not resent automatically.",
        "unavailable": "The local question service is not ready. You can still read the guide and sources.",
    }[status])
