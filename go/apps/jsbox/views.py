from go.conversation.base import ConversationViews
from go.apps.jsbox.forms import JsboxForm, JsboxAppConfigFormset


class JsboxConversationViews(ConversationViews):
    conversation_type = u'jsbox'
    conversation_display_name = u'Javascript App'
    conversation_initiator = None
    edit_conversation_forms = (
        ('jsbox', JsboxForm),
        ('jsbox_app_config', JsboxAppConfigFormset),
        )
