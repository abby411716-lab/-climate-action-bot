from concurrent.futures import ThreadPoolExecutor

import requests
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi, MessagingApiBlob
from linebot.v3.webhook import WebhookParser

from app.config import settings

line_config = Configuration(access_token=settings.line_channel_access_token)
webhook_parser = WebhookParser(settings.line_channel_secret)


def get_messaging_api() -> MessagingApi:
    api_client = ApiClient(line_config)
    return MessagingApi(api_client)


def get_messaging_blob_api() -> MessagingApiBlob:
    api_client = ApiClient(line_config)
    return MessagingApiBlob(api_client)


def get_display_names(line_user_ids: list[str]) -> dict[str, str | None]:
    """向 LINE 查每位學生目前的 LINE 顯示名稱（不是真實姓名），給教師後台顯示用，不存進資料庫。

    查詢不扣訊息額度；學生封鎖或刪除官方帳號後就查不到，回傳 None。
    每位學生要各打一次 API，所以用多執行緒同時查，學生列表頁才不會等太久。
    """
    api = get_messaging_api()

    def fetch(line_user_id: str) -> str | None:
        try:
            return api.get_profile(line_user_id).display_name
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=10) as pool:
        return dict(zip(line_user_ids, pool.map(fetch, line_user_ids)))


class LiffAuthError(Exception):
    pass


def get_liff_user_id(liff_access_token: str) -> str:
    """用 LIFF 前端拿到的 access token 跟 LINE 要回經過驗證的 userId。

    刻意不直接信任前端回報的 userId（liff.getProfile() 的結果理論上可以被竄改），
    而是後端拿 access token 去跟 LINE 的 /v2/profile 要一次，這個 API 本身就會驗證
    token 有效性，回應的 userId 才是可信的。
    """
    resp = requests.get(
        "https://api.line.me/v2/profile",
        headers={"Authorization": f"Bearer {liff_access_token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        raise LiffAuthError(f"LINE profile API 回應 {resp.status_code}: {resp.text}")
    return resp.json()["userId"]
