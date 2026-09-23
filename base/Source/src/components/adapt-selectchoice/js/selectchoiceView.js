import QuestionView from 'core/js/views/questionView';

class SelectChoiceView extends QuestionView {

  initialize(...args) {
    this.onKeyPress = this.onKeyPress.bind(this);
    this.onItemOptionSelect = this.onItemOptionSelect.bind(this);
    super.initialize(...args);
  }

  setupQuestion() {
    this.model.setupRandomisation();
  }

  onQuestionRendered() {
    this.$('.selectchoice__item').imageready(() => this.setReadyStatus());

  }

  onKeyPress(event) {

    if (event.which !== 13) return;
    // <ENTER> keypress
    this.onItemOptionSelect(event);
  }

  onItemOptionSelect(event) {
    if (!this.model.isInteractive()) return;

    const $input = $(event.currentTarget);
    const itemIndex = $input.data('adapt-index');
    const optionIndex = parseInt($input.val());
    const shouldSelectMultipleOptions = this.model.get('_shouldSelectMultipleOptions');

    this.model.setOptionSelected(itemIndex, optionIndex, true);

    if (shouldSelectMultipleOptions) {
      // For multi-select, highlight all selected options
      const item = this.model.get('_items')[itemIndex];
      const selectedIndices = item._options
        .filter(opt => opt._isSelected)
        .map(opt => `${itemIndex}-${opt._value}`)
        .join(',');
      this.model.set('_highlighted', selectedIndices);
    } else {
      this.model.set('_highlighted', `${itemIndex}-${optionIndex}`);
    }
  }

  resetQuestion() {
    this.$('.selectchoice__item').removeClass('is-correct is-incorrect');
    this.model.set('_isAtLeastOneCorrectSelection', false);

    this.model.get('_items').forEach(item => {
      item._options.forEach(option => (option._isSelected = false));
      item._selected = null;
      item._selectedOptions = [];
    });
  }
}
SelectChoiceView.template = 'selectchoice.jsx';

export default SelectChoiceView;
