# adapt-contrib-MultipleNotify

This component is basically a contrib-text which hijacks any anchor tag clicks in the bodyText (`component-body`), and shows a notify popup instead of navigating to the href.

---

<img src="https://raw.githubusercontent.com/zarek3333/adapt-contrib-MultipleNotify/master/notify-multi.jpg" alt="Adapt Multiple Notify Component" width="920" height="628" border="10" />

**IMPORTANT NOTES**:
- This component is dependant on [this commit](https://github.com/taylortom/adapt_framework/commit/a7af2e3f8713979f3b8933ed6c443f254ec6eb27) to the core framework which is yet to be merged.
- Requires adapt-contrib-graphic to be installed.**

---

## Usage

Insert a Notify popup, alert, button or external link to the body of a text component and even a graphic. When adding more than one notifier in the component increase the data-index number within the a tag link ex.(data-index='2'). To show a notify when an anchor is clicked, it must have an `id`:
```
<a data-index='1' href='#mypopup' id='mypopup'>Click to Trigger Notify</a>
```

Use the `_popupData`, `_alertData` or `_externaLink` objects to specify the text shown in the notify or external link. The key values inside are `id` and the `data-index='1'` number must be increased when more notifiers are added to the component.
```
"properties" : {
        "instruction" : "",
        "_graphic" : {
            "alt" : "",
            "large" : "",
            "small" : "",
            "attribution" : ""
        },
        "_notifyopt" : "popup",
        "_popupData" : [ 
            {
                "title" : "Notify Popup Title",
                "message" : "<p>Notify Popup Body copy with link. <a data-index='1' href='#mypopup' id='mypopup'>Click to Trigger Notify</a></p>",
                "copypaste" : "<a data-index='1' href='#' id='mypopup'>copied popup link</a>"
            }
        ],
        "_alertData" : [],
        "_externaLink" : [],
        "_buttonData" : {
            "button" : {
                "classadd" : false,
                "copypaste" : "Click Here",
                "title" : "Title goes here",
                "message" : "<p>Message goes here</p>",
                "confirmButton" : "Continue"
            }
        },
        "bottomText" : ""
    },
```
