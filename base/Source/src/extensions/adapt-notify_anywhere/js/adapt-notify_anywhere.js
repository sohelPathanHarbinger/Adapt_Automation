define([
  "core/js/adapt",
  "core/js/notify"
], function(Adapt, Notify) {

  function normalizeId(value) {
    return String(value || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '_');
  }

  function getMatchByKey(lookupKey) {
    if (!lookupKey) return null;

    const globalMatch = (window._notifyAnywhereData || []).find(d => {
      const idKey = normalizeId(d && d.id);
      const titleKey = normalizeId(d && d.title);
      return idKey === lookupKey || titleKey === lookupKey;
    });
    if (globalMatch) return globalMatch;

    const components = (Adapt.components && Adapt.components.models) || [];
    for (let i = 0; i < components.length; i++) {
      const notifyData = components[i].get('_notifyAnywhere');
      if (!Array.isArray(notifyData)) continue;

      const modelMatch = notifyData.find(d => {
        const idKey = normalizeId(d && d.id);
        const titleKey = normalizeId(d && d.title);
        return idKey === lookupKey || titleKey === lookupKey;
      });
      if (modelMatch) {
        return Object.assign({}, modelMatch, {
          __componentId: components[i].get('_id')
        });
      }
    }

    return null;
  }

  const notifyView = Backbone.View.extend({
    className: 'notify',

    initialize: function() {
      this.listenTo(Adapt, 'remove', this.remove);
      this.render();
    },

    render: function() {
      _.defer(this.postRender.bind(this));
    },

    postRender: function() {
      const model = this.model;
      const data = model.get('_notifyAnywhere');
      if (!data || !Array.isArray(data)) return;

      // Keep a global registry of all notify data
      window._notifyAnywhereData = window._notifyAnywhereData || [];

      // Avoid duplicates using normalized ids
      data.forEach(item => {
        const itemId = normalizeId(item && item.id);
        if (!itemId) return;

        const existing = (window._notifyAnywhereData || []).find(d => normalizeId(d && d.id) === itemId);
        if (existing && !existing.__componentId) {
          existing.__componentId = model.get('_id');
        }
        if (!existing) {
          window._notifyAnywhereData.push(Object.assign({}, item, {
            __componentId: model.get('_id')
          }));
        }
      });

      // Only attach one global click listener
      if (!window._notifyAnywhereHandlerAttached) {
        document.addEventListener('click', function(event) {
          const clickedItem = event.target.closest('.notify, .g-term');
          if (!clickedItem) return;

          const clickedId =
            clickedItem.getAttribute('id') ||
            clickedItem.getAttribute('data-id') ||
            clickedItem.getAttribute('data-notify-id') ||
            '';

          const clickedText = (clickedItem.textContent || '').trim();
          const lookupKey = normalizeId(clickedId || clickedText);
          if (!lookupKey) return;

          const match = getMatchByKey(lookupKey);

          if (!match) return;

          event.preventDefault();
          Notify.popup({
            _id: match.__componentId || '',
            title: match.title || '',
            body: match.body || ''
          });
        });

        window._notifyAnywhereHandlerAttached = true;
      }
    }
  });

  Adapt.on('componentView:postRender', function(view) {
    const notify = view.model.get('_notifyAnywhere');
    if (!notify) return;

    new notifyView({ model: view.model });
  });

});
