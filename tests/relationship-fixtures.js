const canonical=require('../skill/examples/v1.3/relationships-deck.json');
const [datedTimelineSlide,closeDateTimelineSlide,branchSwimlaneSlide,legacyRoadmapSlide]=canonical.slides;

function deck(slides,extra={}) {
  return {schema_version:canonical.schema_version,title:slides[0]?.title||canonical.title,slides,...extra};
}

module.exports={datedTimelineSlide,closeDateTimelineSlide,branchSwimlaneSlide,legacyRoadmapSlide,deck,canonical};
