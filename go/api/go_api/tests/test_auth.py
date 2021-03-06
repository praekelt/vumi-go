"""Test for go.api.go_api.auth."""

import base64

from twisted.cred import error
from twisted.cred.credentials import UsernamePassword
from twisted.internet.defer import inlineCallbacks
from twisted.web import resource
from twisted.web.test import test_web
from twisted.web.iweb import ICredentialFactory

from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.api.go_api.auth import (
    GoUserRealm, GoUserSessionAccessChecker, GoUserAuthSessionWrapper,
    GoAuthBouncerCredentialFactory, IGoAuthBouncerCredentials,
    GoAuthBouncerCredentials, GoAuthBouncerAccessChecker)
from go.api.go_api.session_manager import SessionManager
from go.vumitools.tests.helpers import VumiApiHelper
from .utils import MockAuthServer

import mock


class DummyRequest(test_web.DummyRequest):
    def addRawRequestHeader(self, name, value):
        if not hasattr(self, 'headers'):
            # Twisted >= 16.0
            self.requestHeaders.addRawHeader(name, value)
        else:
            self.headers[name] = value


class TestGoUserRealm(VumiTestCase):
    def test_request_avatar(self):
        expected_resource = object()
        getter = mock.Mock(return_value=expected_resource)
        mind = object()
        realm = GoUserRealm(getter)
        interface, web_resource, cleanup = realm.requestAvatar(
            u"user", mind, resource.IResource)
        self.assertTrue(getter.called_once_with(u"user"))
        self.assertTrue(interface is resource.IResource)
        self.assertTrue(web_resource is expected_resource)
        cleanup()  # run clean-up function to check it doesn't error

    def test_request_avatar_without_iresource_interface(self):
        def getter(user):
            self.fail("Unexpected call to resource retrieval function")
        mind = object()

        realm = GoUserRealm(getter)
        self.assertRaises(NotImplementedError,
                          realm.requestAvatar, u"user", mind)


class TestGoUserSessionAccessChecker(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = self.add_helper(
            PersistenceHelper(is_sync=False))
        self.redis = yield self.persistence_helper.get_redis_manager()
        self.sm = SessionManager(self.redis)

    @inlineCallbacks
    def test_request_avatar_id(self):
        checker = GoUserSessionAccessChecker(self.sm)
        session = {}
        self.sm.set_user_account_key(session, u"user-1")
        yield self.sm.save_session(u"session-1", session, 10)
        creds = UsernamePassword(u"session_id", u"session-1")
        user = yield checker.requestAvatarId(creds)
        self.assertEqual(user, u"user-1")

    @inlineCallbacks
    def test_request_avatar_id_bad_password(self):
        checker = GoUserSessionAccessChecker(self.sm)
        creds = UsernamePassword(u"session_id", u"session-unknown")
        errored = False
        try:
            yield checker.requestAvatarId(creds)
        except error.UnauthorizedLogin:
            errored = True
        self.assertTrue(errored)

    @inlineCallbacks
    def test_request_avatar_id_bad_username(self):
        checker = GoUserSessionAccessChecker(self.sm)
        session = {}
        self.sm.set_user_account_key(session, u"user-1")
        yield self.sm.save_session(u"session-1", session, 10)
        creds = UsernamePassword(u"session_id_BAD", u"session-1")
        try:
            yield checker.requestAvatarId(creds)
        except error.UnauthorizedLogin:
            errored = True
        self.assertTrue(errored)


class TestGoAuthBouncerCredentialFactory(VumiTestCase):
    def test_implements_ICredentialsFactory(self):
        """
        Instances should provide the ICredentialFactory interface.
        """
        factory = GoAuthBouncerCredentialFactory("Test Realm")
        self.assertTrue(ICredentialFactory.providedBy(factory))

    def test_scheme(self):
        """
        Instances should have the scheme 'bearer'.
        """
        factory = GoAuthBouncerCredentialFactory("Test Realm")
        self.assertEqual(factory.scheme, 'bearer')

    def test_decode(self):
        """
        .decode() should return credentials that provide the
        IGoAuthBouncerCredentials interface and contain the original request.
        """
        factory = GoAuthBouncerCredentialFactory("Test Realm")
        response, request = object(), object()
        creds = factory.decode(response, request)
        self.assertTrue(IGoAuthBouncerCredentials.providedBy(creds))
        self.assertEqual(creds.get_request(), request)


class TestGoAuthBouncerCredentials(VumiTestCase):
    def test_implements_IGoAuthBouncerCredentials(self):
        """
        Instances should provide the IGoAuthBouncerCredentials interface.
        """
        request = object()
        creds = GoAuthBouncerCredentials(request)
        self.assertTrue(IGoAuthBouncerCredentials.providedBy(creds))

    def test_get_request(self):
        """
        .get_request() should return the request object given to the credential
        constructor.
        """
        request = object()
        creds = GoAuthBouncerCredentials(request)
        self.assertEqual(creds.get_request(), request)


class TestGoAuthBouncerAccessChecker(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.auth = MockAuthServer()
        self.add_cleanup(self.auth.stop)
        yield self.auth.start()
        self.checker = GoAuthBouncerAccessChecker(self.auth.url)

    def mk_request(self, token=None):
        request = DummyRequest([''])
        request.path = ''
        if token is not None:
            request.addRawRequestHeader(
                "authorization", "Bearer %s" % (token,))
        return request

    @inlineCallbacks
    def test_request_avatar_id_no_auth_header(self):
        """
        When no authentication header is present, authentication should fail.
        """
        request = self.mk_request()
        creds = GoAuthBouncerCredentials(request)
        yield self.assertFailure(
            self.checker.requestAvatarId(creds), error.UnauthorizedLogin)

    @inlineCallbacks
    def test_request_avatar_id_unauthorized_response(self):
        """
        When the authentication server returns a 401 response, authentication
        should fail.
        """
        self.auth.add_response(code=401, body="Unauthorized")
        request = self.mk_request(token="eeep==")
        creds = GoAuthBouncerCredentials(request)
        yield self.assertFailure(
            self.checker.requestAvatarId(creds), error.UnauthorizedLogin)

    @inlineCallbacks
    def test_request_avatar_id_no_owner_id(self):
        """
        When the authentication server does not return an X-Owner-ID header,
        authentication should fail.
        """
        self.auth.add_response(code=200, body="No owner id")
        request = self.mk_request(token="eeep==")
        creds = GoAuthBouncerCredentials(request)
        yield self.assertFailure(
            self.checker.requestAvatarId(creds), error.UnauthorizedLogin)

    @inlineCallbacks
    def test_request_avatar_id_authorized(self):
        """
        When the authentication server returns an X-Owner-ID, authorization
        should succeed and the user returned should be the owner specified in
        the header.
        """
        self.auth.add_response(
            code=200, body="Just right", headers={"X-Owner-ID": "owner-1"})
        request = self.mk_request(token="eeep==")
        creds = GoAuthBouncerCredentials(request)
        owner = yield self.checker.requestAvatarId(creds)
        self.assertEqual(owner, "owner-1")


class TestGoUserAuthSessionWrapper(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.vumi_api = yield self.vumi_helper.get_vumi_api()
        self.auth = MockAuthServer()
        self.add_cleanup(self.auth.stop)
        yield self.auth.start()

    def mk_request(self, user=None, password=None, bearer=None):
        request = DummyRequest([''])
        request.path = ''
        if user is not None:
            request.addRawRequestHeader("authorization", (
                "Basic %s" % base64.b64encode("%s:%s" % (user, password))
            ))
        elif bearer is not None:
            request.addRawRequestHeader(
                "authorization", "Bearer %s" % (bearer,))
        return request

    def mk_wrapper(self, text, bouncer=False):
        class TestResource(resource.Resource):
            isLeaf = True

            def __init__(self, user):
                self.user = user

            def render(self, request):
                request.setResponseCode(200)
                return "%s: %s" % (text, self.user.encode("utf-8"))

        realm = GoUserRealm(lambda user: TestResource(user))
        if not bouncer:
            wrapper = GoUserAuthSessionWrapper(realm, self.vumi_api)
        else:
            wrapper = GoUserAuthSessionWrapper(
                realm, self.vumi_api, self.auth.url)
        return wrapper

    @inlineCallbacks
    def check_request(self, wrapper, request, expected_code, expected_body):
        finished = request.notifyFinish()
        wrapper.render(request)
        yield finished
        self.assertTrue(request.finished)
        self.assertEqual(request.responseCode, expected_code)
        self.assertEqual("".join(request.written), expected_body)

    @inlineCallbacks
    def test_auth_basic_success(self):
        """
        When correct session information is provided via basic authentication,
        a request should succeed.
        """
        session = {}
        self.vumi_api.session_manager.set_user_account_key(session, u"user-1")
        yield self.vumi_api.session_manager.save_session(
            u"session-1", session, 10)
        wrapper = self.mk_wrapper("FOO")
        request = self.mk_request(user=u"session_id", password=u"session-1")
        yield self.check_request(wrapper, request, 200, "FOO: user-1")

    @inlineCallbacks
    def test_auth_bearer_success(self):
        """
        When a correct token is provided via bearer authentication, a request
        should succeed.
        """
        self.auth.add_response(code=200, headers={'X-Owner-ID': 'user-1'})
        wrapper = self.mk_wrapper("FOO", bouncer=True)
        request = self.mk_request(bearer="token-1")
        yield self.check_request(wrapper, request, 200, "FOO: user-1")

    @inlineCallbacks
    def test_auth_failure(self):
        """
        When no authentication is provided, a request should be rejected with a
        401 Unauthorized response.
        """
        wrapper = self.mk_wrapper("FOO")
        request = self.mk_request()
        yield self.check_request(wrapper, request, 401, "Unauthorized")
