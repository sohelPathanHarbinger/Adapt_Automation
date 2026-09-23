import components from 'core/js/components';
import GraphicView from './GraphicView';
import GraphicModel from './GraphicModel';

export default components.register('graphicSlider', {
  model: GraphicModel,
  view: GraphicView
});
