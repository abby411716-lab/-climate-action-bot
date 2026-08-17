import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.daily_push import push_daily_question
from app.game_rules import TAIPEI

logger = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    """啟動背景排程：每天 Asia/Taipei 08:00 推送當日題目。

    注意：Render 免費方案的 Web Service 閒置一段時間會休眠，休眠期間排程不會執行；
    若要保證準時推送，之後可以改用 Render 的付費 Cron Job 或外部服務定時呼叫
    /admin/push-daily 來取代（或搭配）這個內建排程。
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone=TAIPEI)
    _scheduler.add_job(push_daily_question, "cron", hour=8, minute=0, id="daily_push")
    _scheduler.start()
    logger.info("排程已啟動：每天 08:00（Asia/Taipei）推送當日題目")
    return _scheduler
