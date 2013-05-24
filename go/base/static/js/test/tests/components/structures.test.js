describe("go.components.structures", function() {
  var structures = go.components.structures;

  describe(".Extendable", function() {
    var Extendable = go.components.structures.Extendable;

    it("should set up the prototype chain correctly", function() {
      var Parent = Extendable.extend(),
          Child = Parent.extend();

       var child = new Child();
       assert.instanceOf(child, Parent);
       assert.instanceOf(child, Child);
    });

    it("should use a constructor function if specified", function() {
      var Thing = Extendable.extend({
        constructor: function (name) { this.name = name; }
      });

      assert.equal(new Thing('foo').name, 'foo');
    });

    it("should default to a parent's constructor", function() {
      var Parent,
          Child;

      Parent = Extendable.extend({
        constructor: function (name) { this.name = name; }
      });
      Child = Parent.extend();

      assert.equal(new Child('foo').name, 'foo');
    });

    it("should accept multiple object arguments", function() {
      var Thing = Extendable.extend({'a': 'one'}, {'b': 'two'}),
          thing = new Thing();

      assert.equal(thing.a, 'one');
      assert.equal(thing.b, 'two');
    });
  });

  describe(".Lookup", function() {
    var Lookup = structures.Lookup,
        lookup;

    beforeEach(function() {
      lookup = new Lookup({a: 1, b: 2, c: 3});
    });

    describe(".keys", function() {
      it("should get the lookup's item's keys", function() {
        assert.deepEqual(lookup.keys(), ['a', 'b', 'c']);
      });
    });

    describe(".values", function() {
      it("should get the lookup's item's values", function() {
        assert.deepEqual(lookup.values(), [1, 2, 3]);
      });
    });

    describe(".items", function() {
      it("should get a shallow copy of the lookup's items", function() {
        var items = lookup.items();

        items.a = 'one';
        assert.deepEqual(items, {a: 'one', b: 2, c: 3});

        assert.deepEqual(lookup.items(), {a: 1, b: 2, c: 3});
      });
    });

    describe(".get", function() {
      it("should get a value by its key", function() {
        assert.equal(lookup.get('a'), 1);
      });

      it("return null if the key does not exist", function() {
        assert.equal(lookup.get('d'), null);
      });
    });

    describe(".add", function() {
      it("should add the item to the lookup", function() {
        assert.equal(lookup.add('d', 4), lookup);
        assert.deepEqual(lookup.items(), {a: 1, b: 2, c: 3, d: 4});
      });

      it("should emit an 'add' event", function(done) {
        lookup.on('add', function(key, value) {
          assert.equal(key, 'd');
          assert.equal(value, 4);
          done();
        });

        lookup.add('d', 4);
      });
    });

    describe(".remove", function() {
      it("should remove an item from the lookup", function() {
        assert.equal(lookup.remove('c'), 3);
        assert.deepEqual(lookup.items(), {a: 1, b: 2});
      });

      it("should emit a 'remove' event", function(done) {
        lookup.on('remove', function(key, value) {
          assert.equal(key, 'c');
          assert.equal(value, 3);
          done();
        });

        lookup.remove('c');
      });
    });
  });

  describe(".ViewCollection", function() {
    var ViewCollection = structures.ViewCollection,
        models,
        views;

    var ToyView = Backbone.View.extend({
      initialize: function() {
        this.rendered = false;
        this.destroyed = false;
      },

      destroy: function() { this.destroyed = true; },
      render: function() { this.rendered = true; }
    });

    var ToyViewCollection = ViewCollection.extend({
      create: function(model) { return new ToyView({model: model}); }
    });

    beforeEach(function() {
      models = new Backbone.Collection([{id: 'a'}, {id: 'b'}, {id: 'c'}]);
      views = new ToyViewCollection(models);
    });

    describe(".add", function() {
      beforeEach(function() {
        // stop the view collection from automatically adding a view when a
        // model is added to the model collection
        models.off('add');
      });

      it("should add a view corresponding to the model with the passed in id",
         function() {
        models.add({id: 'd'});
        views.add('d');
        assert.equal(views.get('d').model, models.get('d'));
      });

      it("should emit an 'add' event", function(done) {
        models.add({id: 'd'});

        views.on('add', function(id, view) {
          assert.equal(id, 'd');
          assert.equal(view, views.get('d'));
          done();
        });

        views.add('d');
      });
    });

    describe(".remove", function() {
      it("should remove the view with the model with the passed in id",
         function() {
        var viewC = views.get('c');
        assert.equal(views.remove('c'), viewC);
        assert.equal(views.get('c'), null);
      });

      it("should emit a 'remove' event", function(done) {
        var viewC = views.get('c');

        views.on('remove', function(id, view) {
          assert.equal(id, 'c');
          assert.equal(view, viewC);
          done();
        });

        views.remove('c');
      });

      it("should call the view's destroy() function if it exists", function() {
        var viewC = views.get('c');

        assert(!viewC.destroyed);
        views.remove('c');
        assert(viewC.destroyed);
      });
    });

    describe(".render()", function() {
      beforeEach(function() {
        // stop the view collection from automatically rendering when a model is
        // added/removed from the model collection
        models.off('add');
        models.off('remove');
      });

      it("should remove 'dead' views", function() {
        models.remove('c');

        assert.deepEqual(views.keys(), ['a', 'b', 'c']);
        views.render();
        assert.deepEqual(views.keys(), ['a', 'b']);
      });

      it("should add 'new' views", function() {
        models.add({id: 'd'});

        assert.deepEqual(views.keys(), ['a', 'b', 'c']);
        views.render();
        assert.deepEqual(views.keys(), ['a', 'b', 'c', 'd']);
      });

      it("should render all the views in the collection", function() {
        views.values().forEach(function(v) { assert(!v.rendered); });
        views.render();
        views.values().forEach(function(v) { assert(v.rendered); });
      });
    });
  });
});
