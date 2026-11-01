import asyncio
import json
import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram.types import CallbackQuery, Message

from commands import (
    _parse_news_add_input,
    callback_news_assign,
    cmd_news_add,
    cmd_news_assign,
    cmd_news_del,
    cmd_news_list,
    cmd_news_preview,
    cmd_news_run,
)
from news_scheduler import NewsConfigurationError, NewsScheduler


@pytest.fixture
def bot():
    client = Mock()
    client.me = AsyncMock(return_value=Mock(id=999))
    client.get_chat_member = AsyncMock(return_value=Mock(
        status='administrator',
        can_post_messages=True,
    ))
    client.send_message = AsyncMock(return_value=Mock(message_id=42))
    return client


@pytest.fixture
def claude():
    client = Mock()
    client.generate_news = AsyncMock(return_value='Готовая новость')
    return client


@pytest.fixture
def scheduler(bot, claude, tmp_path):
    with patch.dict(os.environ, {
        'NEWS_CHANNEL_ID': '-1001234567890',
        'NEWS_TIMEZONE': 'UTC',
    }):
        instance = NewsScheduler(
            bot=bot,
            claude=claude,
            jobs_file=tmp_path / 'store' / 'news_jobs.json',
        )
        yield instance
        instance.shutdown()


@pytest.fixture
def message():
    value = AsyncMock(spec=Message)
    value.chat = Mock(type='private', id=100)
    value.from_user = Mock(id=123)
    value.answer = AsyncMock()
    return value


@pytest.fixture
def news_scheduler_mock():
    value = Mock()
    value.add_job = AsyncMock(return_value='job12345')
    value.remove_job = AsyncMock(return_value=True)
    value.preview_job = AsyncMock(return_value='Предпросмотр новости')
    value.run_now = AsyncMock(return_value='Новость')
    value.assign_channel = AsyncMock()
    value.get_jobs = Mock(return_value=[])
    value.get_job = Mock(return_value={'id': 'job12345', 'channel_id': -1001234567890})
    value.get_next_run = Mock(return_value=None)
    return value


@pytest.mark.asyncio
async def test_add_daily_job_persists(scheduler, bot, claude, tmp_path):
    job_id = await scheduler.add_job('daily', '09:30', 'Сделай пост', created_by=123)

    job = scheduler.get_job(job_id)
    assert job['schedule_type'] == 'daily'
    assert job['time'] == '09:30'
    assert job['weekday'] is None
    assert scheduler.scheduler.get_job(job_id) is not None

    with open(tmp_path / 'store' / 'news_jobs.json', encoding='utf-8') as file:
        data = json.load(file)
    assert data['jobs'][0]['instruction'] == 'Сделай пост'

    restored = NewsScheduler(
        bot=bot,
        claude=claude,
        jobs_file=tmp_path / 'store' / 'news_jobs.json',
    )
    assert restored.get_job(job_id)['instruction'] == 'Сделай пост'


@pytest.mark.asyncio
async def test_add_weekly_job(scheduler):
    job_id = await scheduler.add_job(
        'weekly', '10:00', 'Сделай дайджест', created_by=123, weekday='mon'
    )

    job = scheduler.get_job(job_id)
    assert job['weekday'] == 'mon'
    trigger = scheduler.scheduler.get_job(job_id).trigger
    assert 'mon' in str(trigger)


@pytest.mark.asyncio
@pytest.mark.parametrize('time_value', ['9', '9:00', '24:00', '12:60', 'invalid'])
async def test_add_job_rejects_invalid_time(scheduler, time_value):
    with pytest.raises(ValueError):
        await scheduler.add_job('daily', time_value, 'Пост', created_by=123)


@pytest.mark.asyncio
async def test_add_job_rejects_invalid_weekday(scheduler):
    with pytest.raises(ValueError):
        await scheduler.add_job('weekly', '09:00', 'Пост', created_by=123, weekday='monday')


@pytest.mark.asyncio
async def test_add_job_rejects_overlong_instruction(scheduler):
    with pytest.raises(ValueError, match='4000'):
        await scheduler.add_job('daily', '09:00', 'x' * 4001, created_by=123)


@pytest.mark.asyncio
async def test_add_job_enforces_configured_limit(scheduler):
    scheduler.max_jobs = 1
    await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)

    with pytest.raises(ValueError, match='лимит'):
        await scheduler.add_job('daily', '10:00', 'Пост', created_by=123)


@pytest.mark.parametrize('environment', [
    {'NEWS_TIMEZONE': 'Invalid/Timezone'},
    {'NEWS_CHANNEL_ID': 'invalid-channel'},
    {'NEWS_MAX_JOBS': '0'},
    {'ADMIN_USER_ID': 'invalid'},
])
def test_invalid_news_configuration(bot, claude, tmp_path, environment):
    with patch.dict(os.environ, environment):
        with pytest.raises(NewsConfigurationError):
            NewsScheduler(bot, claude, jobs_file=tmp_path / 'news_jobs.json')


def test_empty_timezone_uses_default(bot, claude, tmp_path):
    with patch.dict(os.environ, {'NEWS_TIMEZONE': '', 'NEWS_CHANNEL_ID': ''}):
        scheduler = NewsScheduler(bot, claude, jobs_file=tmp_path / 'news_jobs.json')

    assert str(scheduler.timezone) == 'Europe/Moscow'


@pytest.mark.asyncio
async def test_add_job_without_default_channel_creates_unassigned_job(bot, claude, tmp_path):
    with patch.dict(os.environ, {'NEWS_CHANNEL_ID': '', 'NEWS_TIMEZONE': 'UTC'}):
        scheduler = NewsScheduler(bot, claude, jobs_file=tmp_path / 'news_jobs.json')
        job_id = await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)

        assert scheduler.get_job(job_id)['channel_id'] is None
        with pytest.raises(NewsConfigurationError, match='не назначен канал'):
            await scheduler.run_now(job_id)
        bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_job(scheduler):
    job_id = await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)

    assert await scheduler.remove_job(job_id) is True
    assert scheduler.get_job(job_id) is None
    assert scheduler.scheduler.get_job(job_id) is None
    assert await scheduler.remove_job(job_id) is False


@pytest.mark.asyncio
async def test_run_now_generates_and_publishes(scheduler, bot, claude):
    job_id = await scheduler.add_job('daily', '09:00', 'Сделай пост', created_by=123)

    text = await scheduler.run_now(job_id)

    assert text == 'Готовая новость'
    claude.generate_news.assert_awaited_once_with('Сделай пост')
    bot.send_message.assert_awaited_once_with(
        chat_id=-1001234567890,
        text='Готовая новость',
        parse_mode=None,
    )
    job = scheduler.get_job(job_id)
    assert job['last_message_id'] == 42
    assert job['last_run_at'] is not None
    assert job['last_error'] is None


@pytest.mark.asyncio
async def test_preview_does_not_publish(scheduler, bot):
    job_id = await scheduler.add_job('daily', '09:00', 'Сделай пост', created_by=123)

    assert await scheduler.preview_job(job_id) == 'Готовая новость'
    bot.send_message.assert_not_awaited()
    assert scheduler.get_job(job_id)['last_run_at'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('generated_text', ['', '   ', 'x' * 4097])
async def test_run_now_rejects_unpublishable_text(scheduler, bot, claude, generated_text):
    job_id = await scheduler.add_job('daily', '09:00', 'Сделай пост', created_by=123)
    claude.generate_news.return_value = generated_text

    with pytest.raises(ValueError):
        await scheduler.run_now(job_id)

    bot.send_message.assert_not_awaited()
    assert scheduler.get_job(job_id)['last_error']


@pytest.mark.asyncio
async def test_send_failure_is_not_retried(scheduler, bot):
    job_id = await scheduler.add_job('daily', '09:00', 'Сделай пост', created_by=123)
    bot.send_message.side_effect = Exception('Telegram unavailable')

    with pytest.raises(Exception, match='Telegram unavailable'):
        await scheduler.run_now(job_id)

    assert bot.send_message.await_count == 1
    assert scheduler.get_job(job_id)['last_error'] == 'Telegram unavailable'


@pytest.mark.asyncio
async def test_start_restores_schedule_and_calculates_next_run(scheduler):
    job_id = await scheduler.add_job('daily', '09:00', 'Сделай пост', created_by=123)

    scheduler.start()

    assert scheduler.get_next_run(job_id) is not None
    scheduler.shutdown()


def test_parse_daily_news_add_input():
    assert _parse_news_add_input('/news_add daily 09:00 Сделай пост\nс переносом') == (
        'daily', '09:00', 'Сделай пост\nс переносом', ''
    )


def test_parse_weekly_news_add_input():
    assert _parse_news_add_input('/news_add weekly mon 10:30 Сделай дайджест') == (
        'weekly', '10:30', 'Сделай дайджест', 'mon'
    )


@pytest.mark.asyncio
async def test_cmd_news_add(message, news_scheduler_mock):
    message.text = '/news_add daily 09:00 Сделай интересный пост'
    with patch('commands.is_allowed_user', return_value=True):
        await cmd_news_add(message, Mock(), news_scheduler_mock)

    news_scheduler_mock.add_job.assert_awaited_once_with(
        schedule_type='daily',
        time_value='09:00',
        instruction='Сделай интересный пост',
        created_by=123,
        weekday=None,
    )
    assert 'job12345' in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_cmd_news_add_rejects_group(message, news_scheduler_mock):
    message.chat.type = 'group'
    message.text = '/news_add daily 09:00 Пост'

    await cmd_news_add(message, Mock(), news_scheduler_mock)

    news_scheduler_mock.add_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_news_list_empty(message, news_scheduler_mock):
    message.text = '/news_list'
    with patch('commands.is_allowed_user', return_value=True):
        await cmd_news_list(message, Mock(), news_scheduler_mock)

    message.answer.assert_awaited_once_with('Автопубликации не настроены')


@pytest.mark.asyncio
async def test_cmd_news_preview(message, news_scheduler_mock):
    message.text = '/news_preview job12345'
    with patch('commands.is_allowed_user', return_value=True):
        await cmd_news_preview(message, Mock(), news_scheduler_mock)

    news_scheduler_mock.preview_job.assert_awaited_once_with('job12345')
    message.answer.assert_awaited_once_with('Предпросмотр новости', parse_mode=None)


@pytest.mark.asyncio
async def test_cmd_news_run(message, news_scheduler_mock):
    message.text = '/news_run job12345'
    with patch('commands.is_allowed_user', return_value=True):
        await cmd_news_run(message, Mock(), news_scheduler_mock)

    news_scheduler_mock.run_now.assert_awaited_once_with('job12345')
    message.answer.assert_awaited_once_with('Новость опубликована')


@pytest.mark.asyncio
async def test_cmd_news_del(message, news_scheduler_mock):
    message.text = '/news_del job12345'
    with patch('commands.is_allowed_user', return_value=True):
        await cmd_news_del(message, Mock(), news_scheduler_mock)

    news_scheduler_mock.remove_job.assert_awaited_once_with('job12345')
    message.answer.assert_awaited_once_with('Автопубликация удалена')


@pytest.mark.asyncio
async def test_assign_channel_overrides_default(scheduler, bot):
    job_id = await scheduler.add_job('daily', '09:00', 'Сделай пост', created_by=123)

    await scheduler.assign_channel(job_id, -1009999999999)
    await scheduler.run_now(job_id)

    assert scheduler.get_job(job_id)['channel_id'] == -1009999999999
    bot.send_message.assert_awaited_once_with(
        chat_id=-1009999999999,
        text='Готовая новость',
        parse_mode=None,
    )


def _configure_channel(message, can_post_messages=True):
    message.bot = Mock()
    message.bot.me = AsyncMock(return_value=Mock(id=999))
    message.bot.get_chat = AsyncMock(return_value=Mock(type='channel', title='Новостной канал'))
    message.bot.get_chat_member = AsyncMock(return_value=Mock(
        status='administrator',
        can_post_messages=can_post_messages,
    ))


@pytest.mark.asyncio
async def test_cmd_news_assign_shows_channel_keyboard(message, news_scheduler_mock):
    message.text = '/news_assign job12345'
    _configure_channel(message)
    claude = Mock()
    claude.get_monitored_channels.return_value = {-1001234567890}

    with patch('commands.is_allowed_user', return_value=True):
        await cmd_news_assign(message, claude, news_scheduler_mock)

    keyboard = message.answer.call_args.kwargs['reply_markup']
    button = keyboard.inline_keyboard[0][0]
    assert button.text == 'Новостной канал'
    assert button.callback_data == 'news_assign:job12345:-1001234567890'


@pytest.mark.asyncio
async def test_callback_news_assign_assigns_channel(message, news_scheduler_mock):
    _configure_channel(message)
    message.edit_text = AsyncMock()
    callback = AsyncMock(spec=CallbackQuery)
    callback.message = message
    callback.from_user = Mock(id=123)
    callback.data = 'news_assign:job12345:-1001234567890'
    callback.answer = AsyncMock()
    claude = Mock()
    claude.get_monitored_channels.return_value = {-1001234567890}

    with patch('commands.is_allowed_user', return_value=True):
        await callback_news_assign(callback, claude, news_scheduler_mock)

    news_scheduler_mock.assign_channel.assert_awaited_once_with('job12345', -1001234567890)
    message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once_with('Канал назначен')


@pytest.mark.asyncio
async def test_generation_is_retried_with_backoff(scheduler, claude):
    job_id = await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)
    claude.generate_news.side_effect = [
        Exception('Temporary error'),
        Exception('Temporary error'),
        'Готовая новость',
    ]

    with patch('news_scheduler.asyncio.sleep', new=AsyncMock()) as sleep:
        assert await scheduler.run_now(job_id) == 'Готовая новость'

    assert claude.generate_news.await_count == 3
    assert [call.args[0] for call in sleep.await_args_list] == [1, 2]


@pytest.mark.asyncio
async def test_generation_failure_is_saved_and_reported(scheduler, claude, bot):
    scheduler.admin_user_id = 123
    job_id = await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)
    claude.generate_news.side_effect = Exception('OmniRoute unavailable')

    with patch('news_scheduler.asyncio.sleep', new=AsyncMock()):
        with pytest.raises(Exception, match='OmniRoute unavailable'):
            await scheduler.run_now(job_id)

    assert claude.generate_news.await_count == 3
    assert scheduler.get_job(job_id)['last_error'] == 'OmniRoute unavailable'
    bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text='Автопубликация ' + job_id + ' завершилась ошибкой:\nOmniRoute unavailable',
        parse_mode=None,
    )


@pytest.mark.asyncio
async def test_admin_notification_failure_preserves_original_error(scheduler, claude, bot):
    scheduler.admin_user_id = 123
    job_id = await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)
    claude.generate_news.side_effect = Exception('Generation failed')
    bot.send_message.side_effect = Exception('Notification failed')

    with patch('news_scheduler.asyncio.sleep', new=AsyncMock()):
        with pytest.raises(Exception, match='Generation failed'):
            await scheduler.run_now(job_id)


@pytest.mark.asyncio
async def test_run_now_rechecks_channel_permission(scheduler, claude, bot):
    job_id = await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)
    bot.get_chat_member.return_value = Mock(status='administrator', can_post_messages=False)

    with pytest.raises(NewsConfigurationError, match='Post messages'):
        await scheduler.run_now(job_id)

    claude.generate_news.assert_not_awaited()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_lock_prevents_second_active_scheduler(bot, claude, tmp_path):
    jobs_file = tmp_path / 'news_jobs.json'
    first = NewsScheduler(bot, claude, jobs_file=jobs_file)
    second = NewsScheduler(bot, claude, jobs_file=jobs_file)
    first.start()
    try:
        with pytest.raises(NewsConfigurationError, match='другой экземпляр'):
            second.start()
    finally:
        first.shutdown()
        second.shutdown()

    third = NewsScheduler(bot, claude, jobs_file=jobs_file)
    third.start()
    third.shutdown()


@pytest.mark.asyncio
async def test_add_job_rolls_back_when_atomic_replace_fails(scheduler):
    with patch('news_scheduler.os.replace', side_effect=OSError('Disk full')):
        with pytest.raises(OSError, match='Disk full'):
            await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)

    assert scheduler.get_jobs() == []
    assert list(scheduler.jobs_file.parent.glob('*.tmp')) == []


@pytest.mark.asyncio
async def test_parallel_assignments_are_persisted(scheduler):
    first_id = await scheduler.add_job('daily', '09:00', 'Первый', created_by=123)
    second_id = await scheduler.add_job('daily', '10:00', 'Второй', created_by=123)

    await asyncio.gather(
        scheduler.assign_channel(first_id, -1001111111111),
        scheduler.assign_channel(second_id, -1002222222222),
    )

    with open(scheduler.jobs_file, encoding='utf-8') as file:
        stored_jobs = {job['id']: job for job in json.load(file)['jobs']}
    assert stored_jobs[first_id]['channel_id'] == -1001111111111
    assert stored_jobs[second_id]['channel_id'] == -1002222222222


@pytest.mark.asyncio
async def test_invalid_restored_job_is_not_scheduled(scheduler, bot, claude):
    valid_id = await scheduler.add_job('daily', '09:00', 'Пост', created_by=123)
    with open(scheduler.jobs_file, encoding='utf-8') as file:
        data = json.load(file)
    invalid_job = dict(data['jobs'][0])
    invalid_job['id'] = 'invalid1'
    invalid_job['time'] = '25:00'
    data['jobs'].append(invalid_job)
    with open(scheduler.jobs_file, 'w', encoding='utf-8') as file:
        json.dump(data, file)

    restored = NewsScheduler(bot, claude, jobs_file=scheduler.jobs_file)
    restored.start()
    try:
        assert restored.get_job(valid_id) is not None
        assert restored.get_job('invalid1') is None
        assert restored.scheduler.get_job('invalid1') is None
    finally:
        restored.shutdown()


@pytest.mark.asyncio
async def test_cmd_news_run_returns_failure_reason(message, news_scheduler_mock):
    message.text = '/news_run job12345'
    news_scheduler_mock.run_now.side_effect = Exception('Telegram unavailable')

    with patch('commands.is_allowed_user', return_value=True):
        await cmd_news_run(message, Mock(), news_scheduler_mock)

    response = message.answer.call_args.args[0]
    assert 'Telegram unavailable' in response
    assert 'Автоматический повтор отправки не выполнялся' in response


@pytest.mark.asyncio
async def test_cmd_news_list_shows_last_error(message, news_scheduler_mock):
    news_scheduler_mock.get_jobs.return_value = [{
        'id': 'job12345',
        'schedule_type': 'daily',
        'weekday': None,
        'time': '09:00',
        'channel_id': -1001234567890,
        'instruction': 'Пост',
        'last_error': 'OmniRoute unavailable',
    }]

    with patch('commands.is_allowed_user', return_value=True):
        await cmd_news_list(message, Mock(), news_scheduler_mock)

    assert 'OmniRoute unavailable' in message.answer.call_args.args[0]
