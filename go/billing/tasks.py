from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from decimal import Decimal

from celery.task import task, group

from django.db.models import Sum, Count
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from djcelery_email.tasks import send_email

from go.base.s3utils import Bucket
from go.billing import settings
from go.billing.models import (
    Account, MessageCost, Transaction, Statement, LineItem, TransactionArchive,
    LowCreditNotification)
from go.billing.django_utils import TransactionSerializer
from go.base.utils import vumi_api


def month_range(months_ago=1, today=None):
    """ Return the dates at the start and end of a calendar month.

    :param int months_ago:
        How many months back the range should be.
    :param date today:
        The date which months_ago is relative to.

    :returns:
        A tuple consisting of (from_date, to_date).
    """
    if today is None:
        today = date.today()
    last_month = today - relativedelta(months=months_ago)
    from_date = date(last_month.year, last_month.month, 1)
    to_date = from_date + relativedelta(months=1, days=-1)
    return from_date, to_date


def get_transactions(account, statement):
    return Transaction.objects.filter(
        account_number=account.account_number,
        created__gte=statement.from_date,
        created__lt=(statement.to_date + relativedelta(days=1)))


def get_message_transactions(transactions):
    transactions = transactions.values(
        'tag_pool_name',
        'tag_name',
        'message_direction',
        'message_cost',
        'message_credits',
        'markup_percent')

    transactions = transactions.annotate(
        count=Count('id'),
        total_message_cost=Sum('message_cost'),
        total_message_credits=Sum('message_credits'))

    return transactions


def get_storage_transactions(transactions):
    transactions = transactions.values(
        'storage_cost',
        'storage_credits')

    transactions = transactions.annotate(
        count=Count('id'),
        total_storage_cost=Sum('storage_cost'),
        total_storage_credits=Sum('storage_credits'))

    return transactions


def get_session_transactions(transactions):
    transactions = transactions.filter(session_created=True)

    transactions = transactions.values(
        'tag_pool_name',
        'tag_name',
        'session_cost',
        'session_credits',
        'markup_percent')

    transactions = transactions.annotate(
        count=Count('id'),
        total_session_cost=Sum('session_cost'),
        total_session_credits=Sum('session_credits'))

    return transactions


def get_provider_name(transaction, tagpools):
    if transaction['tag_pool_name'] not in tagpools.pools():
        return transaction['tag_pool_name']
    else:
        return tagpools.display_name(transaction['tag_pool_name'])


def get_channel_name(transaction, tagpools):
    return transaction['tag_name']


def get_message_cost(transaction):
    cost = transaction['total_message_cost']
    return cost if cost is not None else 0


def get_storage_cost(transaction):
    cost = transaction['total_storage_cost']
    return cost if cost is not None else 0


def get_session_cost(transaction):
    cost = transaction['total_session_cost']
    return cost if cost is not None else 0


def get_count(transaction):
    return transaction['count']


def get_message_unit_cost(transaction):
    count = get_count(transaction)
    # count should never be 0 since we count by id
    return get_message_cost(transaction) / count


def get_storage_unit_cost(transaction):
    count = get_count(transaction)
    # count should never be 0 since we count by id
    return get_storage_cost(transaction) / count


def get_session_unit_cost(transaction):
    count = get_count(transaction)
    # count should never be 0 since we count by id
    return get_session_cost(transaction) / count


def get_message_credits(transaction):
    return transaction['total_message_credits']


def get_storage_credits(transaction):
    return transaction['total_storage_credits']


def get_session_credits(transaction):
    return transaction['total_session_credits']


def get_channel_type(transaction, tagpools):
    if transaction['tag_pool_name'] not in tagpools.pools():
        return None
    else:
        delivery_class = tagpools.delivery_class(transaction['tag_pool_name'])
        return tagpools.delivery_class_name(delivery_class)


def get_message_description(transaction):
    if transaction['message_direction'] == MessageCost.DIRECTION_INBOUND:
        return 'Messages received'
    else:
        return 'Messages sent'


def make_message_item(statement, transaction, tagpools):
    return LineItem(
        statement=statement,
        units=get_count(transaction),
        cost=get_message_cost(transaction),
        credits=get_message_credits(transaction),
        channel=get_channel_name(transaction, tagpools),
        billed_by=get_provider_name(transaction, tagpools),
        unit_cost=get_message_unit_cost(transaction),
        channel_type=get_channel_type(transaction, tagpools),
        description=get_message_description(transaction))


def make_storage_item(statement, transaction, tagpools):
    return LineItem(
        billed_by=settings.SYSTEM_BILLER_NAME,
        statement=statement,
        units=get_count(transaction),
        cost=get_storage_cost(transaction),
        credits=get_storage_credits(transaction),
        unit_cost=get_storage_unit_cost(transaction),
        description='Storage cost')


def make_session_item(statement, transaction, tagpools):
    return LineItem(
        statement=statement,
        units=get_count(transaction),
        cost=get_session_cost(transaction),
        credits=get_session_credits(transaction),
        channel=get_channel_name(transaction, tagpools),
        billed_by=get_provider_name(transaction, tagpools),
        unit_cost=get_session_unit_cost(transaction),
        channel_type=get_channel_type(transaction, tagpools),
        description='Sessions')


def make_message_items(statement, transactions, tagpools):
    return [
        make_message_item(statement, transaction, tagpools)
        for transaction in get_message_transactions(transactions)]


def make_storage_items(statement, transactions, tagpools):
    return [
        make_storage_item(statement, transaction, tagpools)
        for transaction in get_storage_transactions(transactions)]


def make_session_items(statement, transactions, tagpools):
    return [
        make_session_item(statement, transaction, tagpools)
        for transaction in get_session_transactions(transactions)]


def make_account_fee_item(statement):
    return LineItem(
        units=1,
        statement=statement,
        credits=None,
        cost=settings.ACCOUNT_FEE,
        billed_by=settings.SYSTEM_BILLER_NAME,
        unit_cost=settings.ACCOUNT_FEE,
        description='Account fee')


def generate_statement_items(statement, transactions, tagpools):
    items = []
    items.extend(make_message_items(statement, transactions, tagpools))
    items.extend(make_session_items(statement, transactions, tagpools))
    items.extend(make_storage_items(statement, transactions, tagpools))
    statement.lineitem_set.bulk_create(items)
    return items


@task()
def generate_monthly_statement(account_id, from_date, to_date):
    """Generate a new *Monthly* ``Statement`` for the given ``account``
       between the given ``from_date`` and ``to_date``.
    """
    account = Account.objects.get(id=account_id)
    tagpools = vumi_api().known_tagpools()

    statement = Statement(
        account=account,
        title=settings.MONTHLY_STATEMENT_TITLE,
        type=Statement.TYPE_MONTHLY,
        from_date=from_date,
        to_date=to_date)

    statement.save()

    transactions = get_transactions(account, statement)

    if transactions:
        generate_statement_items(statement, transactions, tagpools)

    return statement


@task()
def generate_monthly_account_statements():
    """Spawn sub-tasks to generate a *Monthly* ``Statement`` for accounts
       without a *Monthly* statement.
    """
    from_date, to_date = month_range(months_ago=1)
    account_list = Account.objects.exclude(
        statement__type=Statement.TYPE_MONTHLY,
        statement__from_date=from_date,
        statement__to_date=to_date)

    task_list = []
    for account in account_list:
        task_list.append(
            generate_monthly_statement.s(account.id, from_date, to_date))

    return group(task_list)()


@task
def archive_monthly_transactions(months_ago=3):
    """Spawn sub-tasks to archive transactions from N months ago."""
    from_date, to_date = month_range(months_ago=months_ago)
    account_list = Account.objects.exclude(
        transactionarchive__from_date=from_date,
        transactionarchive__to_date=to_date)

    task_list = []
    for account in account_list:
        task_list.append(archive_transactions.s(
            account.id, from_date, to_date))

    return group(task_list)()


@task()
def archive_transactions(account_id, from_date, to_date, delete=True):
    account = Account.objects.get(id=account_id)
    serializer = TransactionSerializer()
    filename = (
        u"transactions-%(account_number)s-%(from)s-to-%(to)s.json" % {
            "account_number": account.account_number,
            "from": from_date,
            "to": to_date,
        })

    transaction_query = Transaction.objects.filter(
        account_number=account.account_number,
        created__gte=from_date,
        created__lt=(to_date + relativedelta(days=1)))

    def generate_chunks(item_iter, items_per_chunk=1000, sep="\n"):
        data = []
        for i, item in enumerate(item_iter):
            data.append(item)
            if i % items_per_chunk == 0:
                yield sep.join(serializer.to_json(data))
                yield sep
                data = []
        if data:
            yield sep.join(serializer.to_json(data))
            yield sep

    bucket = Bucket('billing.archive')
    chunks = generate_chunks(transaction_query.iterator())

    archive = TransactionArchive(
        account=account, filename=filename,
        from_date=from_date, to_date=to_date,
        status=TransactionArchive.STATUS_ARCHIVE_CREATED)
    archive.save()

    bucket.upload(filename, chunks, gzip=True, headers={
        'Content-Type': 'application/json; charset=utf-8',
    })

    archive.status = TransactionArchive.STATUS_TRANSACTIONS_UPLOADED
    archive.save()

    if delete:
        transaction_query.delete()
        archive.status = TransactionArchive.STATUS_ARCHIVE_COMPLETED
        archive.save()

    return archive


@task()
def low_credit_notification_confirm_sent(res, notification_id):
    """
    Confirms that the email has been sent. Returns the datetime that
    the confirmation field has been set to.
    """
    notification = LowCreditNotification.objects.get(pk=notification_id)
    if res >= 1:
        notification.success = datetime.now()
        notification.save()
        return notification.success
    else:
        return None


@task()
def create_low_credit_notification(account_number, threshold, balance):
    """
    Sends a low credit notification. Returns (model instance id, email_task).
    """
    account = Account.objects.get(account_number=account_number)
    notification = LowCreditNotification(
        account=account, threshold=threshold, credit_balance=balance)
    notification.save()
    # Send email
    threshold_percent = Decimal(100) - (threshold * Decimal(100))
    subject = 'Vumi Go account %s (%s) at %s%% left of available credits' % (
        account.user.email, account.user.get_full_name(),
        Decimal(100) - threshold_percent)
    email_from = settings.LOW_CREDIT_NOTIFICATION_EMAIL
    email_to = account.user.email
    message = render_to_string(
        'billing/low_credit_notification_email.txt',
        {
            'user': account.user,
            'account': account,
            'threshold_percent': threshold_percent,
            'credit_balance': balance,
            'reference': notification.id,
        })

    email = EmailMessage(subject, message, email_from, [email_to])
    res = (
        send_email.s(email) |
        low_credit_notification_confirm_sent.s(notification.pk)).apply_async()

    return notification.pk, res
