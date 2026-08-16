from linebot.v3.messaging import ApiClient, Configuration, MessagingApi
from linebot.v3.webhook import WebhookParser

from app.config import settings

line_config = Configuration(access_token=settings.line_channel_access_token)
webhook_parser = WebhookParser(settings.line_channel_secret)


def get_messaging_api() -> MessagingApi:
    api_client = ApiClient(line_config)
    return MessagingApi(api_client)
