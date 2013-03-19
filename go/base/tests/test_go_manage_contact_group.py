from cStringIO import StringIO

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_manage_contact_group
from go.base.utils import vumi_api_for_user


class GoManageContactGroupCommandTestCase(VumiGoDjangoTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoManageContactGroupCommandTestCase, self).setUp()
        self.setup_api()
        self.user = self.mk_django_user()
        self.user_api = vumi_api_for_user(self.user)
        self.profile = self.user.get_profile()

    def invoke_command(self, command, **kw):
        options = {
            'email-address': self.user.username,
            'list': False,
            'create': False,
            'delete': False,
        }
        options[command] = True
        options.update(kw)
        command = go_manage_contact_group.Command()
        command.stdout = StringIO()
        command.handle(**options)
        return command.stdout.getvalue()

    def test_list_groups(self):
        output = self.invoke_command('list')
        self.assertEqual(output, 'No contact groups found.\n')

        group = self.user_api.contact_store.new_group(u'test group')
        output = self.invoke_command('list')
        self.assertEqual(output, ' * %s [%s] "test group"\n' % (
            group.key, group.created_at.strftime('%Y-%m-%d %H:%M')))

    def test_create_group(self):
        self.assertEqual([], self.user_api.list_groups())
        output = self.invoke_command('create', group=u'new group')
        [group] = self.user_api.list_groups()
        self.assertEqual(group.name, u'new group')
        lines = output.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'Group created:')
        self.assertTrue(group.key in lines[1])

    def test_delete_empty_group(self):
        self.assertEqual([], self.user_api.list_groups())
        group = self.user_api.contact_store.new_group(u'test group')
        [lgroup] = self.user_api.list_groups()
        self.assertEqual(group.key, lgroup.key)
        output = self.invoke_command('delete', group=group.key)
        self.assertEqual([], self.user_api.list_groups())
        lines = output.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], 'Deleting group:')
        self.assertTrue(group.key in lines[1])
        self.assertEqual(lines[2], '')
        self.assertEqual(lines[3], 'Done.')

    def test_delete_full_group(self):
        self.assertEqual([], self.user_api.list_groups())
        group = self.user_api.contact_store.new_group(u'test group')
        self.user_api.contact_store.new_contact(msisdn=u'123', groups=[group])
        self.user_api.contact_store.new_contact(msisdn=u'456', groups=[group])
        [lgroup] = self.user_api.list_groups()
        self.assertEqual(group.key, lgroup.key)
        output = self.invoke_command('delete', group=group.key)
        self.assertEqual([], self.user_api.list_groups())
        lines = output.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], 'Deleting group:')
        self.assertTrue(group.key in lines[1])
        self.assertEqual(lines[2], '..')
        self.assertEqual(lines[3], 'Done.')
