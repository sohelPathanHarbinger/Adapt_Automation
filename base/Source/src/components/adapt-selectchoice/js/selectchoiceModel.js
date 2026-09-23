import Adapt from 'core/js/adapt';
import QuestionModel from 'core/js/models/questionModel';

export default class SelectChoiceModel extends QuestionModel {
  init() {
    super.init();

    this.setupQuestionItemIndexes();
  }

  reset(type = 'hard', canReset = this.get('_canReset')) {
    const wasReset = super.reset(type, canReset);
    if (!wasReset) return false;
    this.set('_isAtLeastOneCorrectSelection', false);
    this.get('_items').forEach((item) => {
      item._options.forEach((option) => (option._isSelected = false));
      item._selected = null;
      item._selectedOptions = [];
    });
    return true;
  }

  setupQuestionItemIndexes() {
    const shouldSelectMultipleOptions = this.get('_shouldSelectMultipleOptions');

    this.get('_choices').forEach((choice, index) => {
      if (choice._value === undefined) {
        choice._value = index + 1;
      }
    });

    this.get('_items').forEach((item, index) => {
      if (item._index === undefined) {
        item._index = index;
        item._selected = false;
        item._selectedOptions = [];
      }
      if (item._options === undefined) {
        item._options = this.get('_choices').map((choice) => {
          // For multi-select, _shouldBeSelected can be an array of values
          const isAllCorrect = item._shouldBeSelected === 0;
          const shouldBeSelectedValues = shouldSelectMultipleOptions
            ? (Array.isArray(item._shouldBeSelected) ? item._shouldBeSelected : [item._shouldBeSelected])
            : [item._shouldBeSelected];

          return {
            text: choice.text,
            _graphic: choice._graphic,
            _value: choice._value,
            _isCorrect: isAllCorrect || shouldBeSelectedValues.includes(choice._value)
          };
        });
      }
      item._options.forEach((option, index) => {
        if (option._index !== undefined) return;
        option._index = index;
        option._isSelected = false;
      });
    });
  }

  setupRandomisation() {
    if (!this.get('_isRandom') || !this.get('_isEnabled')) return;
    const items = _.shuffle(_.clone(this.get('_items')));
    items.forEach((item, newIndex) => {
      item._originalIndex = item._index;
      item._index = newIndex;
    });
    this.set('_items', items);
  }

  restoreUserAnswers() {
    if (!this.get('_isSubmitted')) return;

    const userAnswer = this.get('_userAnswer');
    const shouldSelectMultipleOptions = this.get('_shouldSelectMultipleOptions');

    this.get('_items').forEach((item) => {
      const indexToRestore = item._originalIndex !== undefined ? item._originalIndex : item._index;
      const savedAnswer = userAnswer[indexToRestore];

      if (shouldSelectMultipleOptions) {
        // For multi-select, savedAnswer is an array of selected option values
        const selectedValues = Array.isArray(savedAnswer) ? savedAnswer : [];
        item._selectedOptions = [];

        item._options.forEach((option) => {
          if (selectedValues.includes(option._value)) {
            option._isSelected = true;
            item._selectedOptions.push(option);
          }
        });
        // Set _selected to first selected option for backwards compatibility
        item._selected = item._selectedOptions[0] || null;
      } else {
        // Original single-select behavior
        item._options.forEach((option) => {
          if (option._index !== savedAnswer) return;
          option._isSelected = true;
          item._selected = option;
        });
      }
    });

    this.setQuestionAsSubmitted();
    this.checkCanSubmit();
    this.markQuestion();
    this.setScore();
    this.setupFeedback();
  }

  canSubmit() {
    const shouldSelectMultipleOptions = this.get('_shouldSelectMultipleOptions');

    const canSubmit = this.get('_items').every(({ _options }) => {
      if (shouldSelectMultipleOptions) {
        // For multi-select, at least one option must be selected per item
        return _options.some(({ _isSelected }) => _isSelected);
      }
      // Original single-select behavior
      return _options.some(({ _isSelected }) => _isSelected);
    });

    return canSubmit;
  }

  setOptionSelected(itemIndex, optionIndex, isSelected) {
    const item = this.get('_items')[itemIndex];
    const shouldSelectMultipleOptions = this.get('_shouldSelectMultipleOptions');
    const _optionIndex = optionIndex - 1;

    if (isNaN(_optionIndex)) {
      item._options.forEach((option) => (option._isSelected = false));
      item._selected = null;
      item._selectedOptions = [];
      return this.checkCanSubmit();
    }

    const option = item._options.find(({ _index }) => _index === _optionIndex);

    if (shouldSelectMultipleOptions) {
      // Toggle selection for multi-select
      option._isSelected = !option._isSelected;

      // Update _selectedOptions array
      item._selectedOptions = item._options.filter(({ _isSelected }) => _isSelected);
      // Set _selected to first selected option for backwards compatibility
      item._selected = item._selectedOptions[0] || null;
    } else {
      // Original single-select behavior - deselect others first
      item._options.forEach((opt) => (opt._isSelected = false));
      option._isSelected = isSelected;
      item._selected = option;
    }

    this.checkCanSubmit();
  }

  storeUserAnswer() {
    const userAnswer = new Array(this.get('_items').length);
    const shouldSelectMultipleOptions = this.get('_shouldSelectMultipleOptions');

    this.get('_items').forEach((item) => {
      const indexToStore = item._originalIndex !== undefined ? item._originalIndex : item._index;

      if (shouldSelectMultipleOptions) {
        // Store array of selected option values for multi-select
        const selectedValues = item._options
          .filter(({ _isSelected }) => _isSelected)
          .map(({ _value }) => _value);
        userAnswer[indexToStore] = selectedValues;
      } else {
        // Original single-select behavior
        const optionIndex = item._options.findIndex(({ _isSelected }) => _isSelected);
        userAnswer[indexToStore] = item._options[optionIndex]._value - 1;
      }
    });

    this.set({
      _userAnswer: userAnswer
    });
  }

  isCorrect() {
    const shouldSelectMultipleOptions = this.get('_shouldSelectMultipleOptions');

    const numberOfCorrectAnswers = this.get('_items').reduce((a, item) => {
      let isCorrect;

      if (shouldSelectMultipleOptions) {
        // For multi-select, check if all and only correct options are selected
        const correctOptions = item._options.filter(({ _isCorrect }) => _isCorrect);
        const selectedOptions = item._options.filter(({ _isSelected }) => _isSelected);

        // Check if selected options match correct options exactly
        const allCorrectSelected = correctOptions.every(opt =>
          selectedOptions.some(sel => sel._value === opt._value)
        );
        const noIncorrectSelected = selectedOptions.every(sel =>
          correctOptions.some(opt => opt._value === sel._value)
        );

        isCorrect = allCorrectSelected && noIncorrectSelected && selectedOptions.length > 0;
      } else {
        // Original single-select behavior
        isCorrect = item._selected?._isCorrect;
      }

      item._isCorrect = Boolean(isCorrect);

      if (!isCorrect) {
        return a;
      }
      this.set('_isAtLeastOneCorrectSelection', true);
      return ++a;
    }, 0);

    this.set('_numberOfCorrectAnswers', numberOfCorrectAnswers);

    if (numberOfCorrectAnswers === this.get('_items').length) {
      return true;
    }

    return false;
  }

  setScore() {
    const questionWeight = this.get('_questionWeight');

    if (this.get('_isCorrect')) {
      this.set('_score', questionWeight);
      return;
    }

    const numberOfCorrectAnswers = this.get('_numberOfCorrectAnswers');
    const itemLength = this.get('_items').length;

    const score = (questionWeight * numberOfCorrectAnswers) / itemLength;

    this.set('_score', score);
  }

  isPartlyCorrect() {
    return this.get('_isAtLeastOneCorrectSelection');
  }

  resetUserAnswer() {
    this.set('_userAnswer', []);
  }

  getInteractionObject() {
    const interactions = {
      correctResponsesPattern: null,
      source: null,
      target: null
    };
    const items = this.get('_items');
    const shouldSelectMultipleOptions = this.get('_shouldSelectMultipleOptions');

    interactions.correctResponsesPattern = [
      items
        .map(({ _options }, questionIndex) => {
          questionIndex++;
          return [
            questionIndex,

            _options
              .filter(({ _isCorrect }) => _isCorrect)
              .map(({ _index }) => {
                return `${questionIndex}_${_index + 1}`;
              })
          ].join('[.]');
        })
        .join('[,]')
    ];

    interactions.source = items
      .map((item) => {
        return {
          // Offset by 1.
          id: `${item._index + 1}`,
          description: item.text
        };
      })
      .flat(Infinity);

    interactions.target = items
      .map(({ _options }, index) => {
        index++;
        return _options.map((option) => {
          return {
            id: `${index}_${option._index + 1}`,
            description: option.text
          };
        });
      })
      .flat(Infinity);
    return interactions;
  }

getResponse() {
   const shouldSelectMultipleOptions = this.get('_shouldSelectMultipleOptions');
   const userAnswer = this.get('_userAnswer');
   const responses = userAnswer.map((answer, index) => {
     if (Array.isArray(answer)) {
       // For multi-select or _shouldBeSelected: 0, format as itemIndex.value for each selected
       return answer.map(val => `${index + 1}.${val}`).join(',');
     }
     return `${index + 1}.${answer + 1}`;
   });
   return responses.join('#');
 }
 getResponseType() {
   return 'matching';
 }
 getCorrectAnswerAsText() {
   const correctAnswerTemplate = Adapt.course.get('_globals')._components._selectchoice.ariaCorrectAnswer;
   const ariaAnswer = this.get('_items')
     .map((item) => {
       const correctOptions = item._options.filter(({ _isCorrect }) => _isCorrect);
       if (correctOptions.length > 1) {
         const correctAnswerText = correctOptions.map(opt => opt.text).join(', ');
         return Handlebars.compile(correctAnswerTemplate)({
           itemText: item.text,
           correctAnswer: correctAnswerText
         });
       }
       const correctOption = correctOptions[0];
       return Handlebars.compile(correctAnswerTemplate)({
         itemText: item.text,
         correctAnswer: correctOption.text
       });
     })
     .join('<br>');
   return ariaAnswer;
 }
 getUserAnswerAsText() {
   const userAnswerTemplate = Adapt.course.get('_globals')._components._selectchoice.ariaUserAnswer;
   const answerArray = this.get('_userAnswer');
   const ariaAnswer = this.get('_items')
     .map((item, index) => {
       const answer = answerArray[index];
       if (Array.isArray(answer)) {
         const selectedTexts = answer.map(val => {
           const option = item._options.find(opt => opt._value === val);
           return option ? option.text : '';
         }).join(', ');
         return Handlebars.compile(userAnswerTemplate)({
           itemText: item.text,
           userAnswer: selectedTexts
         });
       }
       return Handlebars.compile(userAnswerTemplate)({
         itemText: item.text,
         userAnswer: item._options[answer].text
       });
     })
     .join('<br>');
   return ariaAnswer;
 }
}
