describe("go.components.plumbing (connections)", function() {
  var stateMachine = go.components.stateMachine;
      plumbing = go.components.plumbing;

  var testHelpers = plumbing.testHelpers,
      setUp = testHelpers.setUp,
      newSimpleDiagram = testHelpers.newSimpleDiagram,
      newComplexDiagram = testHelpers.newComplexDiagram,
      tearDown = testHelpers.tearDown;

  beforeEach(function() {
    setUp();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".ConnectionView", function() {
    var ConnectionModel = stateMachine.ConnectionModel,
        ConnectionView = plumbing.ConnectionView;

    var diagram,
        x1,
        y1,
        x3_y2;

    beforeEach(function() {
      diagram = new newSimpleDiagram();
      x1 = diagram.endpoints.get('x1');
      y1 = diagram.endpoints.get('y1');
      x3_y2 = diagram.connections.get('x3-y2');
      diagram.render();
    });

    describe(".destroy", function() {
      it("should remove the actual jsPlumb connection", function(done) {
        var plumbConnection = x3_y2.plumbConnection;

        assert(plumbConnection);

        jsPlumb.bind('connectionDetached', function(e) {
          assert.equal(plumbConnection, e.connection);
          assert.isNull(x3_y2.plumbConnection);
          done();
        });

        x3_y2.destroy();
      });
    });

    describe(".render", function() {
      var connection;

      beforeEach(function() {
        connection = diagram.connections.add('connections', {
          model: {
            source: {uuid: 'x1'},
            target: {uuid: 'y1'}
          }
        }, {render: false});
      });

      it("should create the actual jsPlumb connection", function(done) {
        jsPlumb.bind('connection', function(e) {
          assert(connection.source.$el.is(e.source));
          assert(connection.target.$el.is(e.target));
          done();
        });

        connection.render();
      });
    });
  });

  describe(".ConnectionCollection", function() {
    var diagram,
        connections;

    beforeEach(function() {
      diagram = newComplexDiagram();
      connections = diagram.connections.members.get('leftToRight');
    });

    describe(".accepts", function() {
      it("should determine whether the source and target belong", function() {
        var a1L1 = diagram.endpoints.get('a1L1'),
            b1R1 = diagram.endpoints.get('b1R1');

        assert(connections.accepts(a1L1, b1R1));
        assert(!connections.accepts(b1R1, a1L1));
      });
    });
  });
});
