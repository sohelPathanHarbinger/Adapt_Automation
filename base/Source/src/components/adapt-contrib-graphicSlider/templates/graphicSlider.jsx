import React, { useState } from "react";
import { templates } from "core/js/reactHelpers";

const LinkWrapper = ({ href, children, target, className, role }) =>
  href ? (
    <a href={href} target={target} className={className} role={role}>
      {children}
    </a>
  ) : (
    children
  );

export default function GraphicSlider(props) {
  console.log("props", props);
  const { _id, _isScrollable, _scrollPercent, _graphicSlider, _globals } = props;
  var templateCustom;

  const [scrollState, setscrollState] = useState(0);
  const slideCount =props._slideCount;
  var slideImages=[];
  try{
    props._scrollSteps.forEach((arr, i)=>{
      
      slideImages[i] = arr[1];
    });
  } 
  catch{

  }
 
  console.log(slideImages);
  var [imageIndex, setImage] = useState(0);  
  var [position, setposition] = useState(0);
  var [display, setdisplay] = useState(false);
  var eleID = "slider-" + props.cid;
  // setImage(props._scrollSteps[0][1]); 
  var scrolling = (e) => {
    templateCustom = props._scrollSteps.forEach((arr, i) => {
      if (document.getElementById(eleID).value == arr[0]) {
        setscrollState(document.getElementById(eleID).value);
        setposition(arr[0] + "%");
        
        setImage(i);
        setdisplay(true);
      }
    });
  };


  const scrollableProperties = _isScrollable
    ? {
        role: "slider",
        className: "component__widget graphicSlider__widget js-graphicSlider-scrollbar",
        "aria-controls": `graphicSlider__scroll__container__${_id}`,
        "aria-orientation": "vertical",
        "aria-valuemax": "100",
        "aria-valuemin": "0",
        "aria-valuenow": _scrollPercent,
        "aria-label": Handlebars.compile(
          _globals._components._graphicSlider.scrollAriaLabel
        )(props),
        "aria-describedby": _graphicSlider.longdescription
          ? `graphicSlider__longdescription__${_id}`
          : undefined,
        tabIndex: "0",
      }
    : {};

  return (
    <div>
      <div className="component__inner graphicSlider__inner" style={ _graphicSlider.sliderOrient == "vertical" ? {flexDirection: "row "}: {flexDirection: "column"}  }>
        <templates.header {...props} />

        <div>
          <div
            className="component__widget graphicSlider__widget"
            {...scrollableProperties}
          >
            <LinkWrapper
              href={_graphicSlider._url}
              target={_graphicSlider._target}
              className="graphicSlider__link js-graphicSlider-link"
              role="link"
            >
              <div>
                <templates.image
                  {..._graphicSlider}
                  aria-hidden={_isScrollable}
                  id={`graphicSlider__scroll__container__${_id}`}
                  longDescriptionId={`graphicSlider__longdescription__${_id}`}
                  classes="js-graphicSlider-scroll-container"
                  classNamePrefixes={["component", "graphicSlider"]}
                  large={slideImages[imageIndex]}
                  small={slideImages[imageIndex]}
                />{" "}
                {display ? (
                  <div
                    id={"comment-container-" + props.cid}
                    style={ _graphicSlider.sliderOrient == "vertical" ? {top: position}: {left: position,top: "75%"}  }
                    className="comment-container"
                  >
                    
                  </div>
                ) : (
                  <div></div>
                )}
              </div>
              {_graphicSlider.longdescription && (
                <div
                  id={`graphicSlider__longdescription__${_id}`}
                  className="graphicSlider__longdescription"
                >
                  <div className="graphicSlider__longdescription-inner">
                    {_graphicSlider.longdescription}
                  </div>
                </div>
              )}
            </LinkWrapper>
          </div>
        </div>
        <input
                type="range"
                min="0"
                max={slideCount}
                defaultValue={_graphicSlider.sliderOrient == "vertical"? "0" : "0"}
                className={_graphicSlider.sliderOrient == "vertical"? "custom-slider" : "custom-slider"}
                orient={_graphicSlider.sliderOrient == "vertical"? "vertical" : "horizontal"}
                id={"slider-" + props.cid}
                appearance={_graphicSlider.sliderOrient == "vertical"? "slider-vertical" : "slider-horizontal"}
                onChange={(e) => {
                  scrolling(e);
                }}
              ></input>
      </div>
    </div>
  );
}
