import datetime

import mock

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.scheduler import tasks
    from go.scheduler.models import Task


class TestPerformTask(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(
            DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

    def test_perform_task(self):
        conv = self.user_helper.create_conversation(u'bulk_message')
        now = datetime.datetime.utcnow()
        task = Task.objects.create(
            account_id=self.user_helper.account_key, label="Task 1",
            scheduled_for=now, task_data={
                'conversation_key': conv.key,
                'action_name': 'bulk_send',
                'action_kwargs': {
                    'message': 'test_message',
                    'delivery_class': 'sms',
                    'dedupe': True,
                    'scheduled_datetime': None,
                },
            })
        [pending] = task.pendingtask_set.all()
        tasks.perform_task(pending.pk)
        self.assertEqual(list(task.pendingtask_set.all()), [])

    def test_skip_task_if_already_started(self):
        '''If started_timestamp is not None, then the task has already been
        started, and we should not try to run it again.'''
        conv = self.user_helper.create_conversation(u'bulk_message')
        now = datetime.datetime.utcnow()
        task = Task.objects.create(
            account_id=self.user_helper.account_key, label="Task 1",
            scheduled_for=now, task_data={
                'conversation_key': conv.key,
                'action_name': 'bulk_send',
                'action_kwargs': {
                    'message': 'test_message',
                    'delivery_class': 'sms',
                    'dedupe': True,
                    'scheduled_datetime': None,
                },
            })
        task.started_timestamp = now
        task.save()

        [pending] = task.pendingtask_set.all()
        tasks.perform_task(pending.pk)

        self.assertEqual(list(task.pendingtask_set.all()), [pending])

    def test_perform_conversation_action(self):
        conv = self.user_helper.create_conversation(u'bulk_message')
        now = datetime.datetime.utcnow()
        task = Task.objects.create(
            account_id=self.user_helper.account_key, label="Task 1",
            scheduled_for=now, task_data={
                'conversation_key': conv.key,
                'action_name': 'bulk_send',
                'action_kwargs': {
                    'message': 'test_message',
                    'delivery_class': 'sms',
                    'dedupe': True,
                    'scheduled_datetime': None,
                },
            })
        [pending] = task.pendingtask_set.all()
        [task] = Task.objects.all()
        self.assertEqual(task.status, Task.STATUS_PENDING)
        tasks.perform_task(pending.pk)

        [command] = conv.api.mapi.amqp_client.commands

        self.assertEqual(command['kwargs']['conversation_key'], conv.key)
        self.assertEqual(
            command['kwargs']['user_account_key'],
            self.user_helper.account_key)
        self.assertEqual(command['command'], 'bulk_send')
        self.assertEqual(command['kwargs']['delivery_class'], 'sms')
        self.assertEqual(command['kwargs']['content'], 'test_message')
        self.assertEqual(command['kwargs']['dedupe'], True)

        [task] = Task.objects.all()
        self.assertEqual(task.status, Task.STATUS_COMPLETED)


class TestPollTasks(GoDjangoTestCase):

    @mock.patch('go.scheduler.tasks.perform_task.s',
                new_callable=mock.MagicMock)
    def test_no_pending_tasks(self, s):
        tasks.poll_tasks()
        s.assert_not_called()

    @mock.patch('go.scheduler.tasks.perform_task.s',
                new_callable=mock.MagicMock)
    def test_some_pending_task(self, s):
        now = datetime.datetime.utcnow()
        t1 = Task.objects.create(
            account_id="user-1", label="Task 1", scheduled_for=now)
        t2 = Task.objects.create(
            account_id="user-2", label="Task 2", scheduled_for=now)
        Task.objects.create(
            account_id="user-2", label="Task 3", scheduled_for=now +
            datetime.timedelta(days=30))

        tasks.poll_tasks()
        s.assertEqual(s.call_args_list, [
            mock.call(t1.pk),
            mock.call(t2.pk),
        ])
