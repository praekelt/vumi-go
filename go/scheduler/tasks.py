from celery.task import task, group
from celery.utils.log import get_task_logger
import datetime

from go.scheduler.models import PendingTask, Task
from go.base.utils import (
    get_conversation_view_definition, vumi_api)

logger = get_task_logger(__name__)


@task()
def perform_task(pending_id):
    """ Perform a task. """
    try:
        pending = PendingTask.objects.get(id=pending_id)
    except PendingTask.DoesNotExist:
        logger.error('Cannot find pending task %s' % pending_id)
        return

    task = pending.task
    if task.started_timestamp is None:
        task.started_timestamp = datetime.datetime.utcnow()
        task.save()
    else:
        logger.warning(
            'Task %s (%s) has already been started.' % (task.pk, task))
        return

    if task.task_type == Task.TYPE_CONVERSATION_ACTION:
        perform_conversation_action(task)

    pending.delete()
    task.status = Task.STATUS_COMPLETED
    task.save()


def perform_conversation_action(task):
    """
    Perform a conversation action. ``task_data`` must have the following
    fields:

    conversation_key - The key for the conversation.
    action_name - The name of the action to be performed.
    action_kwargs - A dictionary representing the keyword arguments for an
                    action.
    """
    user_api = vumi_api().get_user_api(
        task.account_id, cleanup_api=True)
    conv = user_api.get_wrapped_conversation(
        task.task_data['conversation_key'])
    view_def = get_conversation_view_definition(
        conv.conversation_type, conv=conv)
    action = view_def.get_action(
        task.task_data['action_name'])
    action.perform_action(task.task_data['action_kwargs'])
    user_api.close()


@task()
def poll_tasks():
    """ Poll for tasks that are due and process them.
    """
    now = datetime.datetime.utcnow()
    ready_tasks = PendingTask.objects.filter(scheduled_for__lte=now)

    task_list = []
    for pending in ready_tasks:
        task_list.append(perform_task.s(pending.pk))

    return group(task_list)()
