define([
    'core/js/adapt'
], function(Adapt) {

    var AudioDrawerView = Backbone.View.extend({

        className: "audio-drawer",

        initialize: function() {
            this.listenTo(Adapt, 'remove', this.remove);
            this.listenTo(Adapt.config, 'change:_activeLanguage', this.remove);
            this.render();
        },

        events: {
            "click .item-normal-narration": "turnOnNarration",
            "click .item-mute-narration": "turnOffNarration",
            "click .item-effects":"toggleEffects",
            "click .item-music":"toggleMusic",
            "click .full-button":"setFullText",
            "click .reduced-button":"setReducedText",
            "click .item-autoplay-narration": "toggleAutoplay"
        },

        render: function() {
            var modelData = this.model.toJSON();
            var template = Handlebars.templates["audioDrawer"];
            this.$el.html(template({model: modelData}));

            this.numChannels = 0;

            if (Adapt.course.get('_audio')._channels._narration._isEnabled) {
              this.checkNarration();
              this.numChannels ++;
            }

            if (Adapt.course.get('_audio')._channels._effects._isEnabled) {
              this.checkEffects();
              this.numChannels ++;
            }

            if (Adapt.course.get('_audio')._channels._music._isEnabled) {
              this.checkMusic();
              this.numChannels ++;
            }
	        // this.checkAutoplay();
            this.checkTextSize();

            _.defer(_.bind(this.postRender, this));
            return this;
        },

        postRender: function() {
            this.listenTo(Adapt, 'drawer:triggerCustomView', this.remove);
        },

        toggleAutoplay: function (event) {
            if (event) event.preventDefault();
            this.turnOnNarration();
            Adapt.audio.autoPlayGlobal = false;
            Adapt.trigger('audio:updateAudioAutoplayGlobal', Adapt.audio.autoPlayGlobal);
            // this.checkAutoplay();
        },

        turnOnNarration: function (event) {
            if (event) event.preventDefault();
            // if (Adapt.audio.audioClip[0].status == 0) {
            Adapt.trigger('audio:updateAudioStatus', 0, 1);
            // } else {
            //     Adapt.trigger('audio:updateAudioStatus', 0, 0);
            // }

            Adapt.audio.autoPlayGlobal = true;
            Adapt.trigger('audio:updateAudioAutoplayGlobal', Adapt.audio.autoPlayGlobal);
            // this.checkAutoplay();
            // this.checkNarration();
        },

        turnOffNarration: function (event) {
            Adapt.trigger('audio:updateAudioStatus', 0, 0);
            Adapt.trigger('audio:updateAudioStatus', 1, 0);
            Adapt.trigger('audio:updateAudioStatus', 2, 0);
        },

        toggleEffects: function(event) {
            if (event) event.preventDefault();

            if (this.numChannels == 1) {
              this.toggleAll(Adapt.audio.audioClip[1].status);
            } else {
              if(Adapt.audio.audioClip[1].status == 0){
                  Adapt.trigger('audio:updateAudioStatus', 1, 1);
              } else {
                  Adapt.trigger('audio:updateAudioStatus', 1, 0);
              }
              this.checkEffects();
            }
        },

        toggleMusic: function(event) {
            if (event) event.preventDefault();

            if (this.numChannels == 1) {
              this.toggleAll(Adapt.audio.audioClip[2].status);
            } else {
              if(Adapt.audio.audioClip[2].status == 0){
                  Adapt.trigger('audio:updateAudioStatus', 2, 1);
              } else {
                  Adapt.trigger('audio:updateAudioStatus', 2, 0);
              }
              this.checkMusic();
            }
        },

        toggleAll: function(status) {
            if(status == 0){
                Adapt.trigger('audio:updateAudioStatus', 0, 1);
                Adapt.trigger('audio:updateAudioStatus', 1, 1);
                Adapt.trigger('audio:updateAudioStatus', 2, 1);
            } else {
                Adapt.trigger('audio:updateAudioStatus', 0, 0);
                Adapt.trigger('audio:updateAudioStatus', 1, 0);
                Adapt.trigger('audio:updateAudioStatus', 2, 0);
            }
            this.checkNarration();
            // this.checkAutoplay();
            this.checkEffects();
            this.checkMusic();
        },

        checkTextSize: function() {
            if(Adapt.audio.textSize==0){
                this.$('.text-description').html(Adapt.course.get('_audio')._reducedText.descriptionFull);
                this.$('.full-button').hide();
                this.$('.reduced-button').show();
            } else {
                this.$('.text-description').html(Adapt.course.get('_audio')._reducedText.descriptionReduced);
                this.$('.reduced-button').hide();
                this.$('.full-button').show();
            }
        },

        // checkAutoplay: function () {
        // if (Adapt.audio.autoPlayGlobal) {
        //     this.$('.item-autoplay-narration').find("img").attr("src", "./assets/volume-error-1.svg");
        // } else {
        //     this.$('.item-autoplay-narration').find("img").attr("src", "./assets/volume-error.svg");
        // }
        // },
    

        checkNarration: function() {
            // if (Adapt.audio.audioClip[0].status == 1) {
            //     this.$('.narration-description').html(Adapt.course.get('_audio')._channels._narration.descriptionOn);
            //     this.$('.item-narration').find("img").attr("src", "./assets/volume-normal.svg");
            //     this.$('.item-narration').attr('aria-label', $.a11y_normalize(Adapt.audio.stopAriaLabel));
            // } else {
            //     this.$('.narration-description').html(Adapt.course.get('_audio')._channels._narration.descriptionOff);
            //     this.$('.item-narration').find("img").attr("src", "./assets/volume-mute.svg");
            //     this.$('.item-narration').attr('aria-label', $.a11y_normalize(Adapt.audio.playAriaLabel));
            // }
        },

        checkEffects: function() {
            if(Adapt.audio.audioClip[1].status==1){
                this.$('.effects-description').html(Adapt.course.get('_audio')._channels._effects.descriptionOn);
                this.$('.item-effects').attr("src", "./assets/volume-normal.svg");
                this.$('.item-effects').attr('aria-label', $.a11y_normalize(Adapt.audio.stopAriaLabel));
            } else {
                this.$('.effects-description').html(Adapt.course.get('_audio')._channels._effects.descriptionOff);
                this.$('.item-effects').attr("src", "./assets/volume-mute.svg");
                this.$('.item-effects').attr('aria-label', $.a11y_normalize(Adapt.audio.playAriaLabel));
            }
        },

        checkMusic: function() {
            if(Adapt.audio.audioClip[2].status==1){
                this.$('.music-description').html(Adapt.course.get('_audio')._channels._music.descriptionOn);
                this.$('.item-music').attr("src", "./assets/volume-normal.svg");
                this.$('.item-music').attr('aria-label', $.a11y_normalize(Adapt.audio.stopAriaLabel));
            } else {
                this.$('.music-description').html(Adapt.course.get('_audio')._channels._music.descriptionOff);
                this.$('.item-music').attr("src", "./assets/volume-mute.svg");
                this.$('.item-music').attr('aria-label', $.a11y_normalize(Adapt.audio.playAriaLabel));
            }
        },

        setFullText: function(event) {
            if (event) event.preventDefault();
            // Set text to full
            Adapt.trigger('audio:changeText', 0);
            this.checkTextSize();
        },

        setReducedText: function(event) {
            if (event) event.preventDefault();
            // Set text to small
            Adapt.trigger('audio:changeText', 1);
            this.checkTextSize();
        }
    });

    return AudioDrawerView;

});
