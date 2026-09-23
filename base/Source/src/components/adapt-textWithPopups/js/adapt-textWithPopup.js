define([
  'core/js/adapt',
  'core/js/views/componentView',
  'core/js/models/componentModel'
], function(Adapt, ComponentView, ComponentModel) {

  var TextWithPopupView = ComponentView.extend({

    events: {
      'click a[id]': 'openPopup' // When clicking on a link with an id, open the popup
    },

    preRender: function() {
      this.checkIfResetOnRevisit(); // Check if reset on revisit is enabled
    },

    postRender: function() {
      this.setReadyStatus(); // Set the component as ready for interaction
      this.setupInview(); // Setup inview behavior if necessary
    },

    setupInview: function() {
      var selector = this.getInviewElementSelector();
      if (!selector) {
        this.setCompletionStatus();
        return;
      }

      if (this.model.get('_isPopupOptional') == true) {
        this.setupInviewCompletion(selector);
      }
    },

    /**
     * Determines which element should be used for inview logic - body, instruction, or title.
     * Returns the selector for that element.
     */
    getInviewElementSelector: function() {
      if (this.model.get('body')) return '.component__body';
      if (this.model.get('instruction')) return '.component__instruction';
      if (this.model.get('displayTitle')) return '.component__title';
      return null;
    },

    checkIfResetOnRevisit: function() {
      var isResetOnRevisit = this.model.get('_isResetOnRevisit');
      // If reset is enabled, set defaults
      if (isResetOnRevisit) {
        this.model.reset(isResetOnRevisit);
      }
    },

    openPopup: function(event) {
      event && event.preventDefault(); // Prevent the default link action

      // Declare and check if popupItems are defined correctly
      var popupItems = this.model.get('_items');
      if (!Array.isArray(popupItems)) {
        console.error("Popup items are not properly defined.");
        return; // Exit if the popup items are not an array or missing
      }

      var currentPopup = event.target; // Get the clicked element
      var popupObject = {}; // Initialize popup object

      // Loop through the popupItems to find the matching ID
      popupItems.forEach(function(current) {
        if (current.id === currentPopup.id) {
          // Set the current popup as visited
          current._isVisited = true;
          popupObject = {
            title: current.title,
            body: current.body
          };
        }
      });

      // If no matching popup is found, return early
      if (!popupObject.title) {
        console.error("Popup not found for ID:", currentPopup.id);
        return;
      }

      // Set completion status if the popup is not optional
      if (this.model.get('_isPopupOptional') == false) {
        this.checkCompletionStatus();
      }

      // Notify and show the popup
      Adapt.notify.popup(popupObject);
    },

    // Helper method to get the visited items
    getVisitedItems: function() {
      return _.filter(this.model.get('_items'), function(item) {
        return item._isVisited;
      });
    },

    // Method to check the completion status of the component
    checkCompletionStatus: function() {
      if (this.model.get('_isOptional') == false) {
        if (this.getVisitedItems().length == this.model.get('_items').length) {
          this.setCompletionStatus(); // Set the component as complete when all popups are visited
        }
      }
    }

  }, {
    template: 'textwithpopup' // Use the 'textwithpopup' template for rendering
  });

  // Register the component with Adapt
  return Adapt.register('textwithpopup', {
    model: ComponentModel.extend({}), // Create a new model for this component
    view: TextWithPopupView // Use the custom view for this component
  });
});
