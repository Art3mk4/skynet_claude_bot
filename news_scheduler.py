import asyncio
import copy
import fcntl
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiofiles
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from claude_client import ClaudeClient

logger = logging.getLogger(__name__)

WEEKDAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
MAX_NEWS_LENGTH = 4096
MAX_INSTRUCTION_LENGTH = 4000
GENERATION_ATTEMPTS = 3


class NewsConfigurationError(Exception):
    pass


class NewsScheduler:
    def __init__(self, bot: Bot, claude: ClaudeClient, jobs_file: Optional[Path] = None):
        self.bot = bot
        self.claude = claude
        self.jobs_file = jobs_file or Path('conversations') / 'news_jobs.json'
        self.channel_id = self._get_channel_id()
        self.max_jobs = self._get_max_jobs()
        self.admin_user_id = self._get_admin_user_id()
        timezone_value = os.getenv('NEWS_TIMEZONE', 'Europe/Moscow').strip() or 'Europe/Moscow'
        try:
            self.timezone = ZoneInfo(timezone_value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise NewsConfigurationError(f'Некорректный NEWS_TIMEZONE: {timezone_value}') from error
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        self.jobs: Dict[str, dict] = {}
        self._jobs_lock = asyncio.Lock()
        self._scheduler_lock_file = None
        self._load_jobs()

    @staticmethod
    def _parse_channel_id(value: str) -> Union[int, str]:
        channel_id = value.strip()
        if channel_id.lstrip('-').isdigit():
            return int(channel_id)
        if re.fullmatch(r'@[A-Za-z][A-Za-z0-9_]{4,31}', channel_id):
            return channel_id
        raise NewsConfigurationError(
            'NEWS_CHANNEL_ID должен содержать числовой ID или публичный @username'
        )

    @classmethod
    def _get_channel_id(cls) -> Optional[Union[int, str]]:
        channel_id = os.getenv('NEWS_CHANNEL_ID', '').strip()
        return cls._parse_channel_id(channel_id) if channel_id else None

    @staticmethod
    def _get_max_jobs() -> int:
        value = os.getenv('NEWS_MAX_JOBS', '20').strip() or '20'
        try:
            max_jobs = int(value)
        except ValueError as error:
            raise NewsConfigurationError('NEWS_MAX_JOBS должен быть положительным целым числом') from error
        if max_jobs <= 0:
            raise NewsConfigurationError('NEWS_MAX_JOBS должен быть положительным целым числом')
        return max_jobs

    @staticmethod
    def _get_admin_user_id() -> Optional[int]:
        value = os.getenv('ADMIN_USER_ID', '').strip()
        if not value:
            return None
        try:
            admin_user_id = int(value)
        except ValueError as error:
            raise NewsConfigurationError('ADMIN_USER_ID должен быть числовым ID пользователя') from error
        if admin_user_id <= 0:
            raise NewsConfigurationError('ADMIN_USER_ID должен быть числовым ID пользователя')
        return admin_user_id

    @staticmethod
    def _parse_time(value: str) -> tuple[int, int]:
        if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
            raise ValueError('Время должно быть в формате HH:MM от 00:00 до 23:59')
        hour_value, minute_value = value.split(':')
        return int(hour_value), int(minute_value)

    @staticmethod
    def _validate_instruction(instruction: str) -> str:
        if not isinstance(instruction, str):
            raise ValueError('Инструкция должна быть текстом')
        instruction = instruction.strip()
        if not instruction:
            raise ValueError('Укажите инструкцию для генерации новости')
        if len(instruction) > MAX_INSTRUCTION_LENGTH:
            raise ValueError(f'Инструкция не должна превышать {MAX_INSTRUCTION_LENGTH} символов')
        return instruction

    def _validate_restored_job(self, job: dict) -> dict:
        if not isinstance(job.get('id'), str) or not job['id']:
            raise ValueError('missing job id')
        if job.get('schedule_type') not in ('daily', 'weekly'):
            raise ValueError('invalid schedule type')
        self._parse_time(job.get('time'))
        job['instruction'] = self._validate_instruction(job.get('instruction'))
        if job['schedule_type'] == 'weekly':
            if job.get('weekday') not in WEEKDAYS:
                raise ValueError('invalid weekday')
        else:
            job['weekday'] = None
        channel_id = job.get('channel_id')
        if channel_id is not None:
            if isinstance(channel_id, bool) or not isinstance(channel_id, (int, str)):
                raise ValueError('invalid channel id')
            if isinstance(channel_id, str):
                job['channel_id'] = self._parse_channel_id(channel_id)
        job.setdefault('created_at', datetime.now(self.timezone).isoformat())
        job.setdefault('last_run_at', None)
        job.setdefault('last_message_id', None)
        job.setdefault('last_error', None)
        return job

    def _load_jobs(self):
        if not self.jobs_file.exists():
            return
        try:
            with open(self.jobs_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
            stored_jobs = data.get('jobs', [])
            if not isinstance(stored_jobs, list):
                raise ValueError('jobs must be a list')
            for stored_job in stored_jobs:
                try:
                    if not isinstance(stored_job, dict):
                        raise ValueError('job must be an object')
                    job = self._validate_restored_job(stored_job)
                    self.jobs[job['id']] = job
                except (NewsConfigurationError, ValueError) as error:
                    logger.error('Skipping invalid scheduled news job: %s', error)
            logger.info('Loaded %s scheduled news jobs', len(self.jobs))
        except Exception as error:
            logger.error('Error loading scheduled news jobs: %s', error)

    async def _save_jobs_locked(self):
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self.jobs_file.with_name(
            f'.{self.jobs_file.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp'
        )
        payload = json.dumps(
            {'jobs': copy.deepcopy(list(self.jobs.values()))},
            ensure_ascii=False,
            indent=2,
        )
        try:
            async with aiofiles.open(temporary_file, 'w', encoding='utf-8') as file:
                await file.write(payload)
            os.replace(temporary_file, self.jobs_file)
        finally:
            temporary_file.unlink(missing_ok=True)

    async def _save_job_status(self, job_id: str, status: dict):
        try:
            async with self._jobs_lock:
                job = self.jobs.get(job_id)
                if job is None:
                    return
                job.update(status)
                await self._save_jobs_locked()
        except Exception as error:
            logger.error('Error saving scheduled news job status: %s', error)

    def _acquire_process_lock(self):
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.jobs_file.with_name(self.jobs_file.name + '.lock')
        lock_file = open(lock_path, 'a', encoding='utf-8')
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            lock_file.close()
            raise NewsConfigurationError(
                f'Не удалось получить блокировку планировщика {lock_path}: '
                'возможно, уже запущен другой экземпляр'
            ) from error
        self._scheduler_lock_file = lock_file

    def _release_process_lock(self):
        if self._scheduler_lock_file is None:
            return
        try:
            fcntl.flock(self._scheduler_lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            self._scheduler_lock_file.close()
            self._scheduler_lock_file = None

    def start(self):
        if self.scheduler.running:
            return
        self._acquire_process_lock()
        try:
            for job in self.jobs.values():
                self._schedule_job(job)
            self.scheduler.start()
        except Exception:
            self._release_process_lock()
            raise
        if self.channel_id is None and any(not job.get('channel_id') for job in self.jobs.values()):
            logger.warning('NEWS_CHANNEL_ID is not configured; news jobs require an assigned channel')

    def shutdown(self):
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
        finally:
            self._release_process_lock()

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
        instruction = self._validate_instruction(instruction)

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
        async with self._jobs_lock:
            if len(self.jobs) >= self.max_jobs:
                raise ValueError(f'Достигнут лимит автопубликаций: {self.max_jobs}')
            self.jobs[job_id] = job
            try:
                await self._save_jobs_locked()
            except Exception:
                self.jobs.pop(job_id, None)
                raise
        self._schedule_job(job)
        return job_id

    async def remove_job(self, job_id: str) -> bool:
        async with self._jobs_lock:
            job = self.jobs.pop(job_id, None)
            if job is None:
                return False
            try:
                await self._save_jobs_locked()
            except Exception:
                self.jobs[job_id] = job
                raise
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
        return True

    async def assign_channel(self, job_id: str, channel_id: int):
        async with self._jobs_lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise ValueError('Задание не найдено')
            previous_channel_id = job.get('channel_id')
            job['channel_id'] = channel_id
            try:
                await self._save_jobs_locked()
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

    @staticmethod
    def _validate_generated_text(text: str) -> str:
        if not text:
            raise ValueError('OmniRoute вернул пустой текст')
        if len(text) > MAX_NEWS_LENGTH:
            raise ValueError('Сгенерированная новость превышает 4096 символов')
        return text

    async def _generate_news(self, job_id: str, instruction: str) -> str:
        for attempt in range(1, GENERATION_ATTEMPTS + 1):
            try:
                return (await self.claude.generate_news(instruction)).strip()
            except Exception as error:
                if attempt == GENERATION_ATTEMPTS:
                    raise
                delay = 2 ** (attempt - 1)
                logger.warning(
                    'News generation for job %s failed on attempt %s/%s: %s; retrying in %ss',
                    job_id,
                    attempt,
                    GENERATION_ATTEMPTS,
                    error,
                    delay,
                )
                await asyncio.sleep(delay)
        raise RuntimeError('News generation exhausted all attempts')

    async def preview_job(self, job_id: str) -> str:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError('Задание не найдено')
        text = await self._generate_news(job_id, job['instruction'])
        return self._validate_generated_text(text)

    async def run_now(self, job_id: str) -> str:
        return await self._execute_job(job_id)

    async def _check_channel_access(self, channel_id: Union[int, str]):
        try:
            bot_info = await self.bot.me()
            member = await self.bot.get_chat_member(channel_id, bot_info.id)
        except Exception as error:
            raise NewsConfigurationError(
                f'Не удалось проверить доступ к каналу {channel_id}: {error}'
            ) from error
        if member.status != 'administrator' or not member.can_post_messages:
            raise NewsConfigurationError(
                f'Бот не является администратором канала {channel_id} с правом Post messages'
            )

    async def _notify_admin(self, job_id: str, error: Exception):
        if self.admin_user_id is None:
            return
        error_text = str(error)[:500] or error.__class__.__name__
        try:
            await self.bot.send_message(
                chat_id=self.admin_user_id,
                text=f'Автопубликация {job_id} завершилась ошибкой:\n{error_text}',
                parse_mode=None,
            )
        except Exception as notification_error:
            logger.error(
                'Cannot notify administrator about scheduled news job %s: %s',
                job_id,
                notification_error,
            )

    async def _execute_job(self, job_id: str) -> str:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError('Задание не найдено')

        try:
            channel_id = job.get('channel_id') or self.channel_id
            if channel_id is None:
                raise NewsConfigurationError('Для задания не назначен канал')
            await self._check_channel_access(channel_id)
            text = self._validate_generated_text(
                await self._generate_news(job_id, job['instruction'])
            )

            sent_message = await self.bot.send_message(
                chat_id=channel_id,
                text=text,
                parse_mode=None,
            )
            await self._save_job_status(job_id, {
                'last_run_at': datetime.now(self.timezone).isoformat(),
                'last_message_id': sent_message.message_id,
                'last_error': None,
            })
            return text
        except Exception as error:
            error_text = str(error)[:500] or error.__class__.__name__
            await self._save_job_status(job_id, {'last_error': error_text})
            await self._notify_admin(job_id, error)
            raise

    async def _run_scheduled_job(self, job_id: str):
        try:
            await self._execute_job(job_id)
        except Exception as error:
            logger.error('Scheduled news job %s failed: %s', job_id, error, exc_info=True)
