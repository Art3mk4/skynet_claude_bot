import asyncio
import copy
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from zoneinfo import ZoneInfo

import aiofiles
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from claude_client import ClaudeClient

logger = logging.getLogger(__name__)

WEEKDAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
MAX_NEWS_LENGTH = 4096


class NewsConfigurationError(Exception):
    pass


class NewsScheduler:
    def __init__(self, bot: Bot, claude: ClaudeClient, jobs_file: Optional[Path] = None):
        self.bot = bot
        self.claude = claude
        self.jobs_file = jobs_file or Path('conversations') / 'news_jobs.json'
        self.channel_id = self._get_channel_id()
        self.timezone = ZoneInfo(os.getenv('NEWS_TIMEZONE', 'Europe/Moscow'))
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        self.jobs: Dict[str, dict] = {}
        self._jobs_lock = asyncio.Lock()
        self._load_jobs()

    @staticmethod
    def _get_channel_id() -> Optional[Union[int, str]]:
        channel_id = os.getenv('NEWS_CHANNEL_ID', '').strip()
        if not channel_id:
            return None
        if channel_id.lstrip('-').isdigit():
            return int(channel_id)
        return channel_id

    @staticmethod
    def _parse_time(value: str) -> tuple[int, int]:
        try:
            hour_value, minute_value = value.split(':')
            hour = int(hour_value)
            minute = int(minute_value)
        except (ValueError, TypeError):
            raise ValueError('Время должно быть в формате HH:MM')
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError('Время должно быть в диапазоне от 00:00 до 23:59')
        return hour, minute

    def _load_jobs(self):
        if not self.jobs_file.exists():
            return
        try:
            with open(self.jobs_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
            for job in data.get('jobs', []):
                if isinstance(job, dict) and job.get('id'):
                    self.jobs[job['id']] = job
            logger.info('Loaded %s scheduled news jobs', len(self.jobs))
        except Exception as error:
            logger.error('Error loading scheduled news jobs: %s', error)

    async def _save_jobs(self):
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        async with self._jobs_lock:
            async with aiofiles.open(self.jobs_file, 'w', encoding='utf-8') as file:
                await file.write(json.dumps({'jobs': list(self.jobs.values())}, ensure_ascii=False, indent=2))

    async def _save_job_status(self):
        try:
            await self._save_jobs()
        except Exception as error:
            logger.error('Error saving scheduled news job status: %s', error)

    def start(self):
        for job in self.jobs.values():
            self._schedule_job(job)
        self.scheduler.start()
        if self.channel_id is None:
            logger.warning('NEWS_CHANNEL_ID is not configured; news jobs require an assigned channel')

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def _schedule_job(self, job: dict):
        hour, minute = self._parse_time(job['time'])
        trigger_args = {
            'hour': hour,
            'minute': minute,
            'timezone': self.timezone,
        }
        if job['schedule_type'] == 'weekly':
            trigger_args['day_of_week'] = job['weekday']

        self.scheduler.add_job(
            self._run_scheduled_job,
            trigger=CronTrigger(**trigger_args),
            args=[job['id']],
            id=job['id'],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )

    async def add_job(
        self,
        schedule_type: str,
        time_value: str,
        instruction: str,
        created_by: int,
        weekday: Optional[str] = None,
    ) -> str:
        if schedule_type not in ('daily', 'weekly'):
            raise ValueError('Тип расписания должен быть daily или weekly')
        self._parse_time(time_value)
        if schedule_type == 'weekly' and weekday not in WEEKDAYS:
            raise ValueError('День недели должен быть одним из: ' + ', '.join(WEEKDAYS))

        instruction = instruction.strip()
        if not instruction:
            raise ValueError('Укажите инструкцию для генерации новости')

        job_id = uuid.uuid4().hex[:8]
        job = {
            'id': job_id,
            'channel_id': self.channel_id,
            'schedule_type': schedule_type,
            'weekday': weekday if schedule_type == 'weekly' else None,
            'time': time_value,
            'instruction': instruction,
            'created_by': created_by,
            'created_at': datetime.now(self.timezone).isoformat(),
            'last_run_at': None,
            'last_message_id': None,
            'last_error': None,
        }
        self.jobs[job_id] = job
        try:
            await self._save_jobs()
        except Exception:
            self.jobs.pop(job_id, None)
            raise
        self._schedule_job(job)
        return job_id

    async def remove_job(self, job_id: str) -> bool:
        job = self.jobs.pop(job_id, None)
        if job is None:
            return False
        try:
            await self._save_jobs()
        except Exception:
            self.jobs[job_id] = job
            raise
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        return True

    async def assign_channel(self, job_id: str, channel_id: int):
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError('Задание не найдено')
        previous_channel_id = job.get('channel_id')
        job['channel_id'] = channel_id
        try:
            await self._save_jobs()
        except Exception:
            job['channel_id'] = previous_channel_id
            raise

    def get_jobs(self) -> List[dict]:
        jobs = sorted(self.jobs.values(), key=lambda job: job['created_at'])
        return copy.deepcopy(jobs)

    def get_job(self, job_id: str) -> Optional[dict]:
        job = self.jobs.get(job_id)
        return copy.deepcopy(job) if job else None

    def get_next_run(self, job_id: str) -> Optional[datetime]:
        scheduled_job = self.scheduler.get_job(job_id)
        return scheduled_job.next_run_time if scheduled_job else None

    async def preview_job(self, job_id: str) -> str:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError('Задание не найдено')
        text = (await self.claude.generate_news(job['instruction'])).strip()
        if not text:
            raise ValueError('OmniRoute вернул пустой текст')
        return text

    async def run_now(self, job_id: str) -> str:
        return await self._execute_job(job_id)

    async def _execute_job(self, job_id: str) -> str:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError('Задание не найдено')

        try:
            channel_id = job.get('channel_id') or self.channel_id
            if channel_id is None:
                raise NewsConfigurationError('Для задания не назначен канал')
            text = (await self.claude.generate_news(job['instruction'])).strip()
            if not text:
                raise ValueError('OmniRoute вернул пустой текст')
            if len(text) > MAX_NEWS_LENGTH:
                raise ValueError('Сгенерированная новость превышает 4096 символов')

            sent_message = await self.bot.send_message(
                chat_id=channel_id,
                text=text,
                parse_mode=None,
            )
            job['last_run_at'] = datetime.now(self.timezone).isoformat()
            job['last_message_id'] = sent_message.message_id
            job['last_error'] = None
            await self._save_job_status()
            return text
        except Exception as error:
            job['last_error'] = str(error)[:500]
            await self._save_job_status()
            raise

    async def _run_scheduled_job(self, job_id: str):
        try:
            await self._execute_job(job_id)
        except Exception as error:
            logger.error('Scheduled news job %s failed: %s', job_id, error, exc_info=True)
