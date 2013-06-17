// go.campaign.dialogue.states
// ===========================
// Structures for each dialogue state type

(function(exports) {
  var utils = go.utils,
      switchViews = utils.switchViews;

  var structures = go.components.structures,
      ViewCollection = structures.ViewCollection;

  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView;

  // Resides on a grid point and contains a dialogue state. It can dynamically
  // change the state type by removing the currently contained view (and its
  // model), and creating a new state view of a different type (representing a
  // new state model).
  var DialogueStateShellView = Backbone.View.extend({
    type: 'choice',
    resetDefaults: {render: true},

    initialize: function(options) {
      this.diagram = options.diagram;
      this.reset(options.type || this.type, {render: false});
    },

    // Reset the view and set it to a new state type
    reset: function(type, options) {
      options = _(options || {}).defaults(this.resetDefaults);

      // TODO ui warnings about the descruction involved
      this.type = type;

      if (this.state) {
        this.diagram.states.remove(this.state, {removeModel: true});
      }

      this.state = this.diagram.states.add(
        'states',
        {shell: this, model: {type: type}},
        {addModel: true, render: options.render});

      return this;
    },

    render: function() { this.state.render(); }
  });

  // Base 'mode' for state views. Each mode acts as a 'delegate view',
  // targeting a dialogue view's element and acting according to the mode type
  // (for eg, `edit`) and state type (for eg, `freetext`).
  var DialogueStateModeView = Backbone.View.extend({
    template: _.template(''),

    // The data passed to the template
    templateData: function() { return {model: this.state.model.toJSON()}; },

    initialize: function(options) {
      this.state = options.state;
    },

    render: function() {
      switchViews(this.state, this);

      var html = this.template(_(this).result('templateData'));
      this.$el.replaceWith(html);
    }
  });

  var DialogueStateShellCollection = ViewCollection.extend({
    type: DialogueStateShellView,
    viewOptions: function() { return {diagram: this.diagram}; },
    initialize: function(options) { this.diagram = options.diagram; }
  });

  // Mode allowing the user to make changes to the dialogue state. Acts as a
  // base for each state type's `edit` mode
  var DialogueStateEditView = DialogueStateModeView.extend();

  // Mode for a 'read-only' preview of the dialogue state. Acts as a base for
  // each state type's `preview` mode
  var DialogueStatePreviewView = DialogueStateModeView.extend();

  // Base view for dialogue states. Dynamically switches between modes
  // (`edit`, `preview`).
  var DialogueStateView = StateView.extend({
    editorType: DialogueStateEditView,
    previewerType: DialogueStatePreviewView,

    subtypes: {
      choice: 'go.campaign.dialogue.states.choice.ChoiceStateView',
      freetext: 'go.campaign.dialogue.states.freetext.FreeStateView',
      end: 'go.campaign.dialogue.states.end.EndStateView'
    },

    id: function() { return this.model.id; },

    initialize: function(options) {
      StateView.prototype.initialize.call(this, options);
      this.shell = options.shell;

      this.previewer = new this.editorType({state: this});
      this.editor = new this.previewerType({state: this});
      this.mode = this.editor;
    },

    // Switch to preview mode
    preview: function() {
      this.mode = this.previewer;
      this.render();
    },

    // Switch to edit mode
    edit: function() {
      this.mode = this.editor;
      this.render();
    },

    render: function() {
      switchViews(this.shell, this);
      this.mode.render();
      this.endpoints.render();
    }
  });

  _(exports).extend({
    DialogueStateShellView: DialogueStateShellView,
    DialogueStateShellCollection: DialogueStateShellCollection,

    DialogueStateModeView: DialogueStateModeView,
    DialogueStatePreviewView: DialogueStatePreviewView,
    DialogueStateEditView: DialogueStateEditView,

    DialogueStateView: DialogueStateView
  });
})(go.campaign.dialogue.states = {});
