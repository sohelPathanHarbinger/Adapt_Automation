
import Adapt from 'core/js/adapt';
import GraphicExpandView from './graphicExpandView';
class GraphicExpand extends Backbone.Controller {
  initialize() {
    this.listenTo(Adapt, {
      'componentView:postRender': this.onComponentPostRender
    });
  }

  onComponentPostRender(view) {

    const model = view.model;
    if (!this.checkIsEnabled(model)) return;

    const _graphicExpand = model.get('_graphicExpand');
    const componentType = model.get('_component');
    const isGraphicAttributionExpand =
      _graphicExpand?._button?.iconClass === 'graphic-expand-icon';
    const attributionSelectorByComponent = {
      graphic: '.component__attribution-inner.graphic__attribution-inner',
      hotgraphic: '.component__attribution-inner.hotgraphic__attribution-inner'
    };
    const attributionSelector = attributionSelectorByComponent[componentType];
    const $attribution = attributionSelector
      ? view.$el.find(attributionSelector).first()
      : $();

    if (isGraphicAttributionExpand && $attribution.length) {
      const graphicExpandView = new GraphicExpandView({ model: model });
      $attribution.append(graphicExpandView.el);
      $attribution.addClass('has-graphicexpand-inline');
      return;
    }

    const $insertElement = view.$el.find(_graphicExpand._selector || '.component__widget');
    if ($insertElement.length === 0) return;

    if ($insertElement.length > 1) {
      _.each($insertElement, (element) => {
        const graphicExpandView = new GraphicExpandView({ model: model });
        $(element).after(graphicExpandView.el).parent().addClass('has-graphicexpand');
      });

    } else {
      const graphicExpandView = new GraphicExpandView({ model: model });
      $insertElement.after(graphicExpandView.el).parent().addClass('has-graphicexpand');
    }

  }

  checkIsEnabled(model) {
    const _model = model.get('_graphicExpand');
    if (!_model || !_model._isEnabled) return false;
    return true;
  }
}
export default new GraphicExpand();
