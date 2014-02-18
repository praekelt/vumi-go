from optparse import make_option

from django.core.management.base import CommandError

from go.base.command_utils import (
    BaseGoCommand, make_command_option,
    user_details_as_string)


class Command(BaseGoCommand):
    help = "Manage the message cache."

    option_list = BaseGoCommand.option_list + (
        make_command_option('reconcile', help='Reconcile the message cache.'),
        make_option(
            '--email-address', dest='email_address',
            help="Act on the given user's batches."),
        make_option('--conversation-key',
                    dest='conversation_key',
                    help='Act on the given conversation.'),
        make_option('--active-conversations',
                    dest='active_conversations',
                    action='store_true', default=False,
                    help='Act on all active conversations.'),
        make_option('--dry-run',
                    dest='dry_run',
                    action='store_true', default=False,
                    help='Just pretend to act.'),
    )

    def _get_user_apis(self):
        if "email_address" in self.options:
            return [self.mk_user_api(self.options["email_address"])]
        return self.mk_all_user_apis()

    def _get_batches(self, user_api):
        batches = set()
        if 'conversation_key' in self.options:
            conv = user_api.get_conversation(self.options['conversation_key'])
            batches.add(conv.batch.key)
        if self.options.get('active_conversations'):
            batches.update(
                conv.batch.key for conv in user_api.active_conversations())
        return list(batches)

    def _apply_to_batches(self, func, dry_run=None):
        if dry_run is None:
            dry_run = self.options.get('dry_run')

        for user, user_api in self._get_user_apis():
            batches = self._get_batches(user_api)
            if not batches:
                continue
            self.stdout.write(
                "Processing account %s ...\n" % user_details_as_string(user))
            for batch_id in sorted(batches):
                self.stdout.write(
                    "  Preforming %s on batch %s ...\n"
                    % (func.__name__, batch_id))
                if not dry_run:
                    func(user_api, batch_id)
            self.stdout.write("done.\n")

    def handle_command_reconcile(self, *args, **options):
        def reconcile(user_api, batch_id):
            user_api.api.mdb.reconcile_cache(batch_id)

        self._apply_to_batches(reconcile)
