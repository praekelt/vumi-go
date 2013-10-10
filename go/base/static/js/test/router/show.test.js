describe("go.router.show", function() {
  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists;
      oneElExists = testHelpers.oneElExists;

  describe(".RouterActionsView", function() {
    var RouterActionsView = go.router.show.RouterActionsView;

    var actions,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();

      actions = new RouterActionsView({
        el: $([
          '<div>',
            '<button ',
             'class="action" ',
             'data-url="/router/action" ',
             'data-action="action">',
              'Action',
            '</button>',
          '</div>'
        ].join(''))
      });

      bootbox.setDefaults({animate: false});
    });

    afterEach(function() {
      server.restore();

      $('.bootbox')
        .hide()
        .remove();
    });

    describe("when an '.action' button is clicked", function() {
      it("should display a confirmation modal", function() {
        assert(noElExists('.modal'));
        actions.$('.action').eq(0).click();
        assert(oneElExists('.modal'));
      });

      it("should issue a router action request to the appropriate url",
      function(done) {
        server.respondWith(function(req) {
          assert.equal(req.url, '/router/action');
          done();
        });

        actions.$('.action').eq(0).click();
        $('.modal [data-handler=1]').click();
        server.respond();
      });
    });
  });
});
