import Adapt from 'core/js/adapt';
import notify from 'core/js/notify';
import { templates } from 'core/js/reactHelpers';
import React from 'react';
import ReactDOM from 'react-dom';
class GraphicExpandView extends Backbone.View {
  className() {
    return 'graphicexpand';
  }

  attributes() {
    const attributes = { 'data-component': this.model.get('_component') };
    return attributes;
  }

  initialize() {

    this.onClick = this.onClick.bind(this);
    this.render();
  }

  render() {
    const props = { ...this.model.toJSON(), onClick: this.onClick };
    const Template = templates[this.constructor.template.replace('.jsx', '')];
    ReactDOM.render(<Template {...props} />, this.el);
  }

  onClick(event) {
    event.preventDefault();
    const $graphicexpand = $(event.currentTarget);

    // Support both old placement and attribution-inline placement.
    const $component = $graphicexpand.closest('.graphic, .hotgraphic, .component');
    let $img = $component.find('.graphic__image-container img, .hotgraphic__image, img').first();
    if ($img.length === 0) {
      $img = $graphicexpand.closest('.component__inner').find('img').first();
    }
    let imgsrc = $img.attr('data-large') || $img.attr('src');
    if (imgsrc === undefined) {
      const imgsrcLottie = $component.find('div[data-graphiclottie="true"]').first();
      if (imgsrcLottie.length > 0) {
        imgsrc = imgsrcLottie.attr('src');
      }
    }
    if (imgsrc === undefined) return;
    notify.popup({
      _type: 'popup',
      title: '',
      body: '<img src="' + imgsrc + '" />',
      _classes: 'graphicexpand-popup'
    });
  }
}
GraphicExpandView.template = 'graphic-expand';
export default GraphicExpandView;
