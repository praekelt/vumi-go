// go.apps.dialogue.states.httpjson
// ============================
// Structures for httpjson states: states that post/get json

(function(exports) {
  var states = go.apps.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      ExitEndpointView = states.ExitEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var HttpJsonStateEditView = DialogueStateEditView.extend({
    bodyOptions:{
        jst: 'JST.apps_dialogue_states_httpjson_edit'
    },

    data: function() {
      var d = HttpJsonStateEditView.__super__.data.call(this);
      d.method = this.model.get('method');
      d.url = this.model.get('url');

      return d;
    },

    events: _.extend({
      'change .channel-type': function(e) {
        var name = $(e.target).val();

        if (name === 'unassigned') {
          this.model.set('channel_type', null, {silent: true});
        } else if (name !== 'none') {
          this.model.set('channel_type', {name: name}, {silent: true});
        }
      },

      'change .httpjson-method': function(e) {
        var model = $(e.target).val();

        if(model === 'unassigned') {
          this.model.set('method', null, {silent: true});
        } else if( model !== 'none') {
          this.model.set('method', {model: model}, {silent: true});
        }
      },

      'change .httpjson-url': function(e) {
        var url = $(e.target).val();

        if(url === 'unassigned') {
          this.model.set('url', null, {silent: true});
        } else if(url !== 'none') {
          this.model.set('url', {url: url}, {silent: true});
        }
      }
    }, DialogueStateEditView.prototype.events)
  });

  var HttpJsonStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: {
        jst: 'JST.apps_dialogue_states_httpjson_preview'
    },

    data: function() {
      var d = HttpJsonStatePreviewView.__super__.data.call(this);
      d.method = this.model.get('mehtod');
      d.url = this.model.get('url');

      return d;
    }
  });

  var HttpJsonStateView = DialogueStateView.extend({
    typeName: 'http_json',

    editModeType: HttpJsonStateEditView,
    previewModeType: HttpJsonStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint', type: EntryEndpointView},
      {attr: 'exit_endpoint', type: ExitEndpointView}]
  });

  _(exports).extend({
    HttpJsonStateView: HttpJsonStateView,
    HttpJsonStateEditView: HttpJsonStateEditView,
    HttpJsonStatePreviewView: HttpJsonStatePreviewView
  });
})(go.apps.dialogue.states.httpjson = {});
