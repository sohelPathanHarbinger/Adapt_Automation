define([
    'core/js/adapt'
], function(Adapt) {

    var AudioNavigationView = Backbone.View.extend({

        className: 'audio-navigation',

        initialize: function() {
            this.listenTo(Adapt.config, 'change:_activeLanguage', this.remove);
            this.listenTo(Adapt, 'audio:updateAudioStatus', this.updateToggle);
            this.bindGlobalListeners()

            this.render();
        },

        events: {
            "click .audio-button":"toggleAudio",
            'click .transcript-toggle': 'toggleTranscriptView',
            'click .transcript-close-button': "closeTranscriptView"
        },

        render: function() {
            var data = this.model.toJSON();
            var template = Handlebars.templates["audioNavigation"];

            this.$el.html(template({
                audioToggle:data
            }));

            // Check for audio being on
            if(Adapt.audio.audioStatus == 1){
                this.$('.audio-button').addClass(Adapt.audio.iconOn);
            } else {
                this.$('.audio-button').addClass(Adapt.audio.iconOff);
            }

            if (!Adapt.course.get('_audio')._showOnNavbar) {
                this.$el.addClass('hidden');
            }

            return this;
        },

        updateToggle: function(){
            // Update based on overall audio status
            if(Adapt.audio.audioStatus == 1){
                this.$('.audio-button').removeClass(Adapt.audio.iconOff);
                this.$('.audio-button').addClass(Adapt.audio.iconOn);
            } else {
                this.$('.audio-button').removeClass(Adapt.audio.iconOn);
                this.$('.audio-button').addClass(Adapt.audio.iconOff);
            }
        },

        toggleAudio: function(event) {
            if (event) event.preventDefault();

            Adapt.trigger('audio:showAudioDrawer');
        },
        toggleTranscriptView: function (event) {
          console.log("hello preetam",event.target);
          
          if (event) event.preventDefault();
            const $button = $(event.target);
            const $container = $button.closest(".audio-inner");
            const isOpen = $button.hasClass("transcript-open");          
            $(".transcript-container").remove();
            $(".transcript-open").removeClass("transcript-open");
          
            if (!isOpen) {
              const modelData = this.model.toJSON();
              const transcriptHTML = Handlebars.templates["transcriptPopup"]({ model: modelData });
              $container.append(transcriptHTML);
              $button.addClass("transcript-open");
            }
          },
          
          bindGlobalListeners: function () {
            console.log(" i am logging from here 6");

            const self = this;          
            $(document).on("mousedown.transcriptPopup", function (e) {
              self._clickedInside = $(e.target).closest(".transcript-container, .transcript-btn").length > 0;
            });
          
            $(document).on("click.transcriptPopup", function () {
              if (!self._clickedInside) {
                $(".transcript-container").remove();
                $(".transcript-open").removeClass("transcript-open");
              }
              self._clickedInside = false;
            });          
            // $(window).on("scroll.transcriptPopup", function () {
            //   if (window.scrollY > 300) {
            //     $(".transcript-container").remove();
            //     $(".transcript-open").removeClass("transcript-open");
            //   }
            // });
          },

          closeTranscriptView:function(event){
            console.log(" i am logging from here 6");
            if (event) event.preventDefault();
            const $button = $(event.target);
            this.$(".transcript-container").remove()
          },
          
          remove() {
            $(document).off(".transcriptPopup");
            $(window).off(".transcriptPopup");
          },

    });

    return AudioNavigationView;

});
